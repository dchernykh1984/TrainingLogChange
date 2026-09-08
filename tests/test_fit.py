"""Tests for the FIT modifier."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fit_tool.fit_file import FitFile
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage

from tests.conftest import FIT_EPOCH_OFFSET_S, FIT_LOCAL_OFFSET_S, FIT_START_MS
from training_log_change.base import ActivityFormatError
from training_log_change.fit import FitModifier


def messages(path: Path, kind: type):
    return [
        record.message
        for record in FitFile.from_file(str(path)).records
        if isinstance(record.message, kind)
    ]


def only(path: Path, kind: type):
    found = messages(path, kind)
    assert len(found) == 1, f"expected one {kind.__name__}, found {len(found)}"
    return found[0]


def modified(fit_path: Path, tmp_path: Path, change) -> Path:
    modifier = FitModifier(str(fit_path))
    change(modifier)
    out = tmp_path / "out.fit"
    modifier.save(str(out))
    return out


def test_a_file_that_is_not_changed_is_written_back_byte_for_byte(fit_path, tmp_path):
    out = modified(fit_path, tmp_path, lambda m: None)

    assert out.read_bytes() == fit_path.read_bytes()


def test_speedup_scales_the_samples_and_the_summaries(fit_path, tmp_path):
    out = modified(fit_path, tmp_path, lambda m: m.speedup(2.0))

    assert [m.speed for m in messages(out, RecordMessage)] == [10.0, 12.0, 14.0]
    assert only(out, LapMessage).max_speed == 14.0
    assert only(out, LapMessage).total_elapsed_time == 10.0
    assert only(out, SessionMessage).total_timer_time == 10.0


def test_speedup_leaves_distance_alone(fit_path, tmp_path):
    out = modified(fit_path, tmp_path, lambda m: m.speedup(2.0))

    assert [m.distance for m in messages(out, RecordMessage)] == [0.0, 50.0, 100.0]
    assert only(out, LapMessage).total_distance == 100.0


def test_speedup_compresses_the_records_towards_the_start(fit_path, tmp_path):
    out = modified(fit_path, tmp_path, lambda m: m.speedup(2.0))

    assert [m.timestamp for m in messages(out, RecordMessage)] == [
        FIT_START_MS,
        FIT_START_MS + 5_000,
        FIT_START_MS + 10_000,
    ]


def test_speedup_rejects_a_non_positive_multiplier(fit_path):
    with pytest.raises(ValueError, match="must be positive"):
        FitModifier(str(fit_path)).speedup(0)


def test_update_start_time_moves_every_message_including_the_file_header(
    fit_path, tmp_path
):
    new_start = datetime(2025, 1, 1, 8, 0, tzinfo=UTC)
    out = modified(fit_path, tmp_path, lambda m: m.update_start_time(new_start))
    expected = round(new_start.timestamp() * 1000)

    assert only(out, FileIdMessage).time_created == expected
    assert messages(out, RecordMessage)[0].timestamp == expected
    assert only(out, LapMessage).start_time == expected


def test_update_start_time_keeps_the_recorded_durations(fit_path, tmp_path):
    new_start = datetime(2025, 1, 1, 8, 0, tzinfo=UTC)
    out = modified(fit_path, tmp_path, lambda m: m.update_start_time(new_start))

    assert only(out, LapMessage).total_elapsed_time == 20.0


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda m: m.speedup(2.0), id="speedup"),
        pytest.param(
            lambda m: m.update_start_time(datetime(2025, 1, 1, 8, 0, tzinfo=UTC)),
            id="update_start_time",
        ),
    ],
)
def test_the_local_wall_clock_keeps_its_offset_from_the_instant(
    fit_path, tmp_path, change
):
    out = modified(fit_path, tmp_path, change)
    activity = only(out, ActivityMessage)

    instant_in_fit_seconds = activity.timestamp / 1000 - FIT_EPOCH_OFFSET_S

    assert activity.local_timestamp - instant_in_fit_seconds == FIT_LOCAL_OFFSET_S


def test_cleanup_heart_rate_zeroes_the_spike_and_repairs_the_summaries(
    fit_path, tmp_path
):
    out = modified(fit_path, tmp_path, lambda m: m.cleanup_heart_rate(200))

    assert [m.heart_rate for m in messages(out, RecordMessage)] == [140, 0, 150]
    assert only(out, LapMessage).max_heart_rate == 150
    assert only(out, SessionMessage).max_heart_rate == 150


def test_cleanup_power_zeroes_the_spike_and_repairs_the_summaries(fit_path, tmp_path):
    out = modified(fit_path, tmp_path, lambda m: m.cleanup_power(1000))

    assert [m.power for m in messages(out, RecordMessage)] == [200, 0, 210]
    assert only(out, LapMessage).max_power == 210


def test_cleanup_cadence_zeroes_the_spike_and_repairs_the_summaries(fit_path, tmp_path):
    out = modified(fit_path, tmp_path, lambda m: m.cleanup_cadence(150))

    assert [m.cadence for m in messages(out, RecordMessage)] == [90, 0, 88]
    assert only(out, LapMessage).max_cadence == 90


def test_cleanup_leaves_a_summary_that_is_already_in_range(fit_path, tmp_path):
    out = modified(fit_path, tmp_path, lambda m: m.cleanup_power(5000))

    assert only(out, LapMessage).max_power == 2000


def test_a_summary_is_repaired_only_from_the_samples_inside_its_own_window(
    fit_path, tmp_path
):
    # Shrink the lap so it covers the first sample only. Its max_heart_rate must
    # then fall back to that sample's 140, not to the 150 recorded later on.
    def change(modifier):
        for record in modifier.fit.records:
            if isinstance(record.message, LapMessage):
                record.message.timestamp = FIT_START_MS
        modifier.cleanup_heart_rate(200)

    out = modified(fit_path, tmp_path, change)

    assert only(out, LapMessage).max_heart_rate == 140
    assert only(out, SessionMessage).max_heart_rate == 150


def test_a_file_that_is_not_fit_is_rejected(tmp_path):
    path = tmp_path / "activity.fit"
    path.write_bytes(b"not a fit file at all")

    with pytest.raises(ActivityFormatError, match="not a readable FIT file"):
        FitModifier(str(path))


def test_a_missing_file_raises_the_underlying_os_error(tmp_path):
    with pytest.raises(OSError):
        FitModifier(str(tmp_path / "missing.fit"))


def test_a_summary_whose_window_catches_nothing_uses_the_whole_activity(
    fit_path, tmp_path
):
    # Push the lap window ahead of every record. An empty window means the
    # summary and the records disagree about the boundary, not that the lap
    # recorded nothing, so its max_heart_rate must not collapse to zero.
    def change(modifier):
        for record in modifier.fit.records:
            if isinstance(record.message, LapMessage):
                record.message.start_time = FIT_START_MS + 600_000
                record.message.timestamp = FIT_START_MS + 900_000
        modifier.cleanup_heart_rate(200)

    out = modified(fit_path, tmp_path, change)

    assert only(out, LapMessage).max_heart_rate == 150


def test_summaries_are_left_alone_when_the_file_has_no_such_readings(
    fit_path, tmp_path
):
    def change(modifier):
        for record in modifier.fit.records:
            if isinstance(record.message, RecordMessage):
                record.message.power = None
        modifier.cleanup_power(1000)

    out = modified(fit_path, tmp_path, change)

    assert only(out, LapMessage).max_power == 2000
    assert only(out, SessionMessage).max_power == 2000
