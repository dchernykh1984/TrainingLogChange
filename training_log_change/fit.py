"""Modifier for FIT, the binary format Garmin devices record and upload.

FIT is a stream of typed messages, not a document, so there is no tree to walk.
The file is decoded into its messages, the fields of interest are edited in
place, and it is re-encoded: fit-tool copies the original bytes of every record
that was not touched, so messages this tool knows nothing about -- developer
fields, device settings, HRV data -- come out exactly as they went in.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from datetime import UTC, datetime, timedelta

from fit_tool.data_message import DataMessage
from fit_tool.field import Field
from fit_tool.fit_file import FitFile
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage

from training_log_change.base import ActivityFormatError, TrackModifier

#: FIT counts its local timestamps in seconds from this moment.
FIT_EPOCH = datetime(1989, 12, 31, tzinfo=UTC)


def _from_unix_ms(value: float) -> datetime:
    return datetime.fromtimestamp(value / 1000, UTC)


def _to_unix_ms(moment: datetime) -> int:
    return round(moment.timestamp() * 1000)


def _from_fit_seconds(value: float) -> datetime:
    return FIT_EPOCH + timedelta(seconds=value)


def _to_fit_seconds(moment: datetime) -> int:
    return round((moment - FIT_EPOCH).total_seconds())


#: FIT keeps time in two shapes. A ``date_time`` is an instant, which fit-tool
#: hands over as milliseconds since the Unix epoch. A ``local_date_time`` is the
#: wall clock the athlete saw, counted in seconds from the FIT epoch and
#: carrying no zone at all, so it cannot be compared with an instant until the
#: timestamp beside it says what the offset was.
INSTANT = "date_time"
WALL_CLOCK = "local_date_time"
TIME_TYPES = frozenset({INSTANT, WALL_CLOCK})


def _is_dropout(field: Field) -> bool:
    """Does this field hold FIT's marker for "nothing was recorded here"?

    A FIT file declares its record layout once and then writes every field on
    every record, so a strap or meter that drops out is written as the invalid
    pattern for the field's base type -- 0xFF for a heart rate, 0xFFFF for a
    speed. fit-tool scales that pattern like any other number, so the gap comes
    back as a plausible-looking 255 bpm or 65.535 m/s.
    """
    raw = field.encoded_values
    if not raw:
        return False
    invalid = field.base_type.invalid_raw_value()
    return all(value == invalid for value in raw)


def _read(message: DataMessage, field: Field) -> float | int | None:
    if _is_dropout(field):
        return None
    value = field.get_value(sub_field=field.get_valid_sub_field(message.fields))
    return value if isinstance(value, (int, float)) else None


def _write(message: DataMessage, field: Field, value: float | int) -> None:
    field.set_value(0, value, field.get_valid_sub_field(message.fields))


class FitModifier(TrackModifier):
    """Edit a ``.fit`` activity in place."""

    #: Speeds rise with a speedup, durations fall. Distances are left alone.
    FASTER_FIELDS = frozenset(
        {
            "speed",
            "enhanced_speed",
            "avg_speed",
            "max_speed",
            "enhanced_avg_speed",
            "enhanced_max_speed",
        }
    )
    SHORTER_FIELDS = frozenset(
        {
            "total_elapsed_time",
            "total_timer_time",
            "total_moving_time",
            "avg_lap_time",
        }
    )

    #: Per-sample readings, and the summary fields that have to follow them down.
    HR_FIELDS = (("heart_rate",), ("max_heart_rate",))
    POWER_FIELDS = (("power",), ("max_power",))
    CADENCE_FIELDS = (("cadence",), ("max_cadence", "max_running_cadence"))

    def __init__(self, file_path: str) -> None:
        try:
            self.fit = FitFile.from_file(file_path)
        except OSError:
            raise
        except Exception as exc:
            raise ActivityFormatError(
                f"{file_path} is not a readable FIT file: {exc}"
            ) from exc
        if not any(True for _ in self._time_fields()):
            raise ActivityFormatError(f"{file_path} contains no timestamps")

    def save(self, file_path: str) -> None:
        self.fit.to_file(file_path)

    # -- messages -----------------------------------------------------------

    def _messages(self) -> Iterator[DataMessage]:
        for record in self.fit.records:
            message = record.message
            if isinstance(message, DataMessage):
                yield message

    def _records(self) -> Iterator[RecordMessage]:
        for message in self._messages():
            if isinstance(message, RecordMessage):
                yield message

    def _summaries(self) -> Iterator[LapMessage | SessionMessage]:
        for message in self._messages():
            if isinstance(message, (LapMessage, SessionMessage)):
                yield message

    # -- timestamps ---------------------------------------------------------

    def _time_fields(self) -> Iterator[tuple[DataMessage, Field, str]]:
        for message in self._messages():
            yield from self._time_fields_of(message)

    @staticmethod
    def _time_fields_of(
        message: DataMessage,
    ) -> Iterator[tuple[DataMessage, Field, str]]:
        for field in message.fields:
            if field.type_name in TIME_TYPES and _read(message, field) is not None:
                yield message, field, field.type_name

    def start_time(self) -> datetime:
        """When the activity started, as an instant."""
        moments = [
            _from_unix_ms(value)
            for message, field, clock in self._time_fields()
            if clock == INSTANT and (value := _read(message, field)) is not None
        ]
        if not moments:
            raise ActivityFormatError("activity contains no timestamps")
        return min(moments)

    @staticmethod
    def _instant_of(message: DataMessage) -> datetime | None:
        """The message's own ``timestamp``, read before anything is edited."""
        field = message.get_field_by_name("timestamp")
        value = _read(message, field) if field is not None else None
        if field is None or value is None or field.type_name != INSTANT:
            return None
        return _from_unix_ms(value)

    def _shift_times(self, transform: Callable[[datetime, datetime], datetime]) -> None:
        """Move every timestamp in the file through ``transform``.

        A wall clock reading is moved by following the instant recorded on the
        same message and putting the original UTC offset back afterwards. Doing
        it any other way breaks under a speedup: the file usually holds a single
        local_date_time, which would then be its own reference and never move,
        leaving the activity claiming a local end time it no longer has.
        """
        start = self.start_time()
        for message in self._messages():
            anchor = self._instant_of(message)
            for _, field, clock in list(self._time_fields_of(message)):
                value = _read(message, field)
                if value is None:
                    continue
                if clock == INSTANT:
                    _write(
                        message,
                        field,
                        _to_unix_ms(transform(_from_unix_ms(value), start)),
                    )
                    continue
                wall = _from_fit_seconds(value)
                reference = anchor if anchor is not None else wall
                offset = wall - reference
                _write(
                    message,
                    field,
                    _to_fit_seconds(transform(reference, start) + offset),
                )

    def update_start_time(self, start_time: datetime) -> None:
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=UTC)
        offset = start_time - self.start_time()
        self._shift_times(lambda moment, _start: moment + offset)

    # -- operations ---------------------------------------------------------

    def speedup(self, multiplier: float) -> None:
        if multiplier <= 0:
            raise ValueError("speedup multiplier must be positive")
        factors = {name: multiplier for name in self.FASTER_FIELDS}
        factors.update({name: 1 / multiplier for name in self.SHORTER_FIELDS})
        self._scale_numbers(factors)
        self._shift_times(lambda moment, start: start + (moment - start) / multiplier)

    def _scale_numbers(self, factors: Mapping[str, float]) -> None:
        for message in self._messages():
            for field in message.fields:
                factor = factors.get(field.name)
                value = _read(message, field) if factor is not None else None
                if factor is not None and value is not None:
                    _write(message, field, type(value)(value * factor))

    def cleanup_heart_rate(self, max_hr: int) -> None:
        self._cleanup(*self.HR_FIELDS, limit=max_hr)

    def cleanup_power(self, max_power: float) -> None:
        self._cleanup(*self.POWER_FIELDS, limit=max_power)

    def cleanup_cadence(self, max_cadence: int) -> None:
        self._cleanup(*self.CADENCE_FIELDS, limit=max_cadence)

    def _cleanup(
        self, sample_names: Iterable[str], summary_names: Iterable[str], *, limit: float
    ) -> None:
        """Zero out-of-range samples, then repair the summaries above them.

        A lap that recorded a 2000 W spike also reports max_power 2000. Records
        are a flat stream in FIT rather than children of a lap, so each summary
        is repaired from the samples that fall inside its own start..end window.

        A window that catches no samples falls back to the peak of the whole
        activity: an empty window usually means the summary and the records
        disagree about the boundary, not that nothing was recorded. If the file
        carries no readings of this kind at all there is nothing to reason from,
        and the summaries are left as recorded rather than zeroed.
        """
        samples = self._zero_samples(tuple(sample_names), limit)
        if not samples:
            return
        overall = max(value for _, value in samples)
        summary_names = tuple(summary_names)
        for message in self._summaries():
            window = self._window(message)
            within = [value for moment, value in samples if window(moment)]
            peak = max(within) if within else overall
            for name in summary_names:
                field = message.get_field_by_name(name)
                value = _read(message, field) if field is not None else None
                if field is not None and value is not None and value > limit:
                    _write(message, field, type(value)(peak))

    def _zero_samples(
        self, names: tuple[str, ...], limit: float
    ) -> list[tuple[datetime | None, float]]:
        """Zero every out-of-range sample and return what is left, with its time."""
        samples: list[tuple[datetime | None, float]] = []
        for message in self._records():
            timestamp = message.get_field_by_name("timestamp")
            raw = _read(message, timestamp) if timestamp is not None else None
            moment = _from_unix_ms(raw) if raw is not None else None
            for name in names:
                field = message.get_field_by_name(name)
                value = _read(message, field) if field is not None else None
                if field is None or value is None:
                    continue
                if value > limit:
                    _write(message, field, type(value)(0))
                    value = 0.0
                samples.append((moment, value))
        return samples

    @staticmethod
    def _window(
        message: LapMessage | SessionMessage,
    ) -> Callable[[datetime | None], bool]:
        """Does a sample taken at this moment belong to this lap or session?"""
        bounds = []
        for name in ("start_time", "timestamp"):
            field = message.get_field_by_name(name)
            value = _read(message, field) if field is not None else None
            bounds.append(_from_unix_ms(value) if value is not None else None)
        start, end = bounds

        def contains(moment: datetime | None) -> bool:
            if moment is None or start is None or end is None:
                return True
            return start <= moment <= end

        return contains
