"""Modifier for TCX, the Garmin Training Center XML format."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from lxml import etree

from training_log_change.xml_base import (
    XmlTrackModifier,
    find_leaves,
    format_number,
    local_name,
    parse_number,
)


class TcxModifier(XmlTrackModifier):
    """Edit a ``.tcx`` activity in place.

    Timestamps live in ``<Id>`` (the activity start), in ``<Trackpoint><Time>``
    and in the ``StartTime`` attribute of every ``<Lap>``.
    """

    ROOT_NAME = "TrainingCenterDatabase"
    TIME_ELEMENTS = frozenset({"Time", "Id"})
    TIME_ATTRIBUTES = frozenset({"StartTime"})

    #: Speeds rise with the multiplier. Distance is deliberately left alone: the
    #: same route covered in less time is exactly what makes the activity faster.
    FASTER_FIELDS = frozenset({"Speed", "MaximumSpeed", "MaxSpeed", "AvgSpeed"})
    #: Durations fall with the multiplier.
    SHORTER_FIELDS = frozenset({"TotalTimeSeconds"})

    def speedup(self, multiplier: float) -> None:
        if multiplier <= 0:
            raise ValueError("speedup multiplier must be positive")
        factors = {name: multiplier for name in self.FASTER_FIELDS}
        factors.update({name: 1 / multiplier for name in self.SHORTER_FIELDS})
        self._scale_numbers(factors)
        self._compress_times(multiplier)

    #: Per-sample readings, and the lap summary that has to follow them down.
    #: Lap averages are left alone: recomputing them from a track whose samples
    #: are unevenly spaced is guesswork, and a wrong average is worse than a
    #: stale one.
    HR_FIELDS = (("HeartRateBpm",), ("MaximumHeartRateBpm",))
    POWER_FIELDS = (("Watts",), ("MaxWatts",))
    CADENCE_FIELDS = (("Cadence", "RunCadence"), ("MaxBikeCadence", "MaxRunCadence"))

    def cleanup_heart_rate(self, max_hr: int) -> None:
        self._cleanup(*self.HR_FIELDS, limit=max_hr)

    def cleanup_power(self, max_power: float) -> None:
        self._cleanup(*self.POWER_FIELDS, limit=max_power)

    def cleanup_cadence(self, max_cadence: int) -> None:
        self._cleanup(*self.CADENCE_FIELDS, limit=max_cadence)

    def _cleanup(
        self, sample_names: Iterable[str], summary_names: Iterable[str], *, limit: float
    ) -> None:
        """Zero out-of-range samples, then repair the lap summary above them.

        A lap that recorded a 2000 W spike also reports MaxWatts 2000. Zeroing
        the sample alone would leave the summary claiming a wattage that appears
        nowhere in the track, so a summary that is itself out of range is reset
        to the highest value the lap still has.
        """
        sample_names = tuple(sample_names)
        summary_names = tuple(summary_names)
        for lap in self._laps():
            peak = self._zero_samples(lap, sample_names, limit)
            for element in find_leaves(lap, summary_names, skip="Track"):
                value = parse_number(element.text)
                if value is not None and value > limit:
                    element.text = format_number(peak)

    def _laps(self) -> Iterator[etree._Element]:
        """Every lap, or the whole document if the file records no laps."""
        found = False
        for element in self.root.iter():
            if isinstance(element.tag, str) and local_name(element) == "Lap":
                found = True
                yield element
        if not found:
            yield self.root

    @staticmethod
    def _zero_samples(lap: etree._Element, names: Iterable[str], limit: float) -> float:
        """Zero every out-of-range sample in ``lap`` and return the highest left."""
        peak = 0.0
        for point in lap.iter():
            if not isinstance(point.tag, str) or local_name(point) != "Trackpoint":
                continue
            for element in find_leaves(point, names):
                value = parse_number(element.text)
                if value is None:
                    continue
                if value > limit:
                    element.text = "0"
                    value = 0.0
                peak = max(peak, value)
        return peak
