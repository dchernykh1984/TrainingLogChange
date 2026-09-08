"""Tests for the TCX modifier."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.conftest import text, texts, values
from training_log_change.base import ActivityFormatError
from training_log_change.tcx import TcxModifier


def modified(tcx_path: Path, tmp_path: Path, change) -> Path:
    modifier = TcxModifier(str(tcx_path))
    change(modifier)
    out = tmp_path / "out.tcx"
    modifier.save(str(out))
    return out


def test_speedup_scales_speeds_and_shortens_the_lap(tcx_path, tmp_path):
    out = modified(tcx_path, tmp_path, lambda m: m.speedup(2.0))

    assert text(out, "MaximumSpeed") == "20"
    assert texts(out, "Speed") == ["10", "12", "14"]
    assert text(out, "TotalTimeSeconds") == "10"


def test_speedup_leaves_distance_alone(tcx_path, tmp_path):
    out = modified(tcx_path, tmp_path, lambda m: m.speedup(2.0))

    assert text(out, "DistanceMeters") == "100.0"


def test_speedup_compresses_the_track_towards_its_start(tcx_path, tmp_path):
    out = modified(tcx_path, tmp_path, lambda m: m.speedup(2.0))

    assert texts(out, "Time") == [
        "2024-03-31T10:00:00.000Z",
        "2024-03-31T10:00:05.000Z",
        "2024-03-31T10:00:10.000Z",
    ]
    assert text(out, "Id") == "2024-03-31T10:00:00.000Z"


def test_speedup_rejects_a_non_positive_multiplier(tcx_path):
    with pytest.raises(ValueError, match="must be positive"):
        TcxModifier(str(tcx_path)).speedup(0)


def test_update_start_time_moves_every_timestamp_by_the_same_offset(tcx_path, tmp_path):
    new_start = datetime(2025, 1, 1, 8, 0, tzinfo=UTC)
    out = modified(tcx_path, tmp_path, lambda m: m.update_start_time(new_start))

    assert text(out, "Id") == "2025-01-01T08:00:00.000Z"
    assert texts(out, "Time") == [
        "2025-01-01T08:00:00.000Z",
        "2025-01-01T08:00:10.000Z",
        "2025-01-01T08:00:20.000Z",
    ]


def test_update_start_time_moves_the_lap_start_attribute(tcx_path, tmp_path):
    new_start = datetime(2025, 1, 1, 8, 0, tzinfo=UTC)
    out = modified(tcx_path, tmp_path, lambda m: m.update_start_time(new_start))
    modifier = TcxModifier(str(out))

    assert modifier.start_time() == new_start


def test_update_start_time_accepts_a_naive_datetime_as_utc(tcx_path, tmp_path):
    out = modified(
        tcx_path, tmp_path, lambda m: m.update_start_time(datetime(2025, 1, 1, 8, 0))
    )

    assert text(out, "Id") == "2025-01-01T08:00:00.000Z"


def test_cleanup_heart_rate_zeroes_the_spike_and_repairs_the_lap_maximum(
    tcx_path, tmp_path
):
    out = modified(tcx_path, tmp_path, lambda m: m.cleanup_heart_rate(200))

    # Lap maximum first in document order, then the three samples.
    assert values(out, "MaximumHeartRateBpm") == ["150"]
    assert values(out, "HeartRateBpm") == ["140", "0", "150"]


def test_cleanup_power_zeroes_the_spike_and_repairs_the_lap_maximum(tcx_path, tmp_path):
    out = modified(tcx_path, tmp_path, lambda m: m.cleanup_power(1000))

    assert texts(out, "Watts") == ["200", "0", "210"]
    assert text(out, "MaxWatts") == "210"


def test_cleanup_cadence_zeroes_the_spike_and_repairs_the_lap_maximum(
    tcx_path, tmp_path
):
    out = modified(tcx_path, tmp_path, lambda m: m.cleanup_cadence(150))

    # Document order puts the lap average cadence before the three samples.
    assert texts(out, "Cadence") == ["85", "90", "0", "88"]
    assert text(out, "MaxBikeCadence") == "90"


def test_cleanup_leaves_a_summary_that_is_already_in_range(tcx_path, tmp_path):
    out = modified(tcx_path, tmp_path, lambda m: m.cleanup_power(5000))

    assert text(out, "MaxWatts") == "2000"


def test_rejects_a_file_that_is_not_tcx(tmp_path):
    path = tmp_path / "activity.tcx"
    path.write_text('<?xml version="1.0"?><gpx><trk/></gpx>')

    with pytest.raises(ActivityFormatError, match="expected <TrainingCenterDatabase>"):
        TcxModifier(str(path))


def test_rejects_a_file_that_is_not_xml(tmp_path):
    path = tmp_path / "activity.tcx"
    path.write_text("not xml at all")

    with pytest.raises(ActivityFormatError, match="not well-formed XML"):
        TcxModifier(str(path))


def test_rejects_a_file_without_timestamps(tmp_path):
    path = tmp_path / "activity.tcx"
    path.write_text(
        '<?xml version="1.0"?>'
        '<TrainingCenterDatabase xmlns="urn:x"><Activities/></TrainingCenterDatabase>'
    )

    with pytest.raises(ActivityFormatError, match="no timestamps"):
        TcxModifier(str(path)).start_time()


LAP_WITHOUT_A_TRACK = """<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="urn:x">
  <Activities><Activity>
    <Id>2024-03-31T10:00:00.000Z</Id>
    <Lap StartTime="2024-03-31T10:00:00.000Z">
      <AverageHeartRateBpm><Value>150</Value></AverageHeartRateBpm>
      <MaximumHeartRateBpm><Value>230</Value></MaximumHeartRateBpm>
    </Lap>
  </Activity></Activities>
</TrainingCenterDatabase>
"""

TWO_LAPS_ONE_WITHOUT_READINGS = """<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="urn:x">
  <Activities><Activity>
    <Id>2024-03-31T10:00:00.000Z</Id>
    <Lap StartTime="2024-03-31T10:00:00.000Z">
      <MaximumHeartRateBpm><Value>230</Value></MaximumHeartRateBpm>
      <Track><Trackpoint>
        <Time>2024-03-31T10:00:00.000Z</Time>
        <HeartRateBpm><Value>150</Value></HeartRateBpm>
      </Trackpoint></Track>
    </Lap>
    <Lap StartTime="2024-03-31T10:01:00.000Z">
      <MaximumHeartRateBpm><Value>230</Value></MaximumHeartRateBpm>
      <Track><Trackpoint><Time>2024-03-31T10:01:00.000Z</Time></Trackpoint></Track>
    </Lap>
  </Activity></Activities>
</TrainingCenterDatabase>
"""


def test_a_lap_with_no_readings_at_all_keeps_its_summary(tmp_path):
    path = tmp_path / "activity.tcx"
    path.write_text(LAP_WITHOUT_A_TRACK)

    out = modified(path, tmp_path, lambda m: m.cleanup_heart_rate(200))

    # Reporting a maximum of zero beside an average of 150 would be a worse file
    # than the one that came in.
    assert values(out, "MaximumHeartRateBpm") == ["230"]


def test_a_lap_with_no_readings_falls_back_to_the_rest_of_the_activity(tmp_path):
    path = tmp_path / "activity.tcx"
    path.write_text(TWO_LAPS_ONE_WITHOUT_READINGS)

    out = modified(path, tmp_path, lambda m: m.cleanup_heart_rate(200))

    assert values(out, "MaximumHeartRateBpm") == ["150", "150"]
