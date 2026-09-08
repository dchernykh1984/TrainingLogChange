"""Tests for the GPX modifier."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.conftest import texts
from training_log_change.base import ActivityFormatError
from training_log_change.gpx import GpxModifier


def modified(gpx_path: Path, tmp_path: Path, change) -> Path:
    modifier = GpxModifier(str(gpx_path))
    change(modifier)
    out = tmp_path / "out.gpx"
    modifier.save(str(out))
    return out


def test_speedup_compresses_the_track_towards_its_start(gpx_path, tmp_path):
    out = modified(gpx_path, tmp_path, lambda m: m.speedup(2.0))

    # The metadata time is the first of the four, and is the start itself.
    assert texts(out, "time") == [
        "2024-03-31T10:00:00Z",
        "2024-03-31T10:00:00Z",
        "2024-03-31T10:00:05Z",
        "2024-03-31T10:00:10Z",
    ]


def test_speedup_leaves_the_route_alone(gpx_path, tmp_path):
    out = modified(gpx_path, tmp_path, lambda m: m.speedup(2.0))

    assert texts(out, "ele") == ["150.0", "151.0", "152.0"]


def test_speedup_rejects_a_non_positive_multiplier(gpx_path):
    with pytest.raises(ValueError, match="must be positive"):
        GpxModifier(str(gpx_path)).speedup(0)


def test_timestamps_keep_the_whole_second_spelling_gpx_uses(gpx_path, tmp_path):
    new_start = datetime(2025, 1, 1, 8, 0, tzinfo=UTC)
    out = modified(gpx_path, tmp_path, lambda m: m.update_start_time(new_start))

    assert texts(out, "time")[-1] == "2025-01-01T08:00:20Z"


def test_update_start_time_moves_the_metadata_time_too(gpx_path, tmp_path):
    new_start = datetime(2025, 1, 1, 8, 0, tzinfo=UTC)
    out = modified(gpx_path, tmp_path, lambda m: m.update_start_time(new_start))

    assert texts(out, "time")[0] == "2025-01-01T08:00:00Z"


def test_cleanup_heart_rate_zeroes_the_spike(gpx_path, tmp_path):
    out = modified(gpx_path, tmp_path, lambda m: m.cleanup_heart_rate(200))

    assert texts(out, "hr") == ["140", "0", "150"]


def test_cleanup_cadence_zeroes_the_spike(gpx_path, tmp_path):
    out = modified(gpx_path, tmp_path, lambda m: m.cleanup_cadence(150))

    assert texts(out, "cad") == ["90", "0", "88"]


def test_cleanup_power_reads_the_garmin_spelling(gpx_path, tmp_path):
    out = modified(gpx_path, tmp_path, lambda m: m.cleanup_power(1000))

    assert texts(out, "PowerInWatts") == ["200", "0", "210"]


def test_cleanup_power_also_reads_the_bare_power_element(tmp_path):
    path = tmp_path / "activity.gpx"
    path.write_text(
        '<?xml version="1.0"?>'
        '<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
        "<trkpt><time>2024-03-31T10:00:00Z</time>"
        "<extensions><power>2000</power></extensions></trkpt>"
        "</trkseg></trk></gpx>"
    )
    out = modified(path, tmp_path, lambda m: m.cleanup_power(1000))

    assert texts(out, "power") == ["0"]


def test_a_file_that_is_not_gpx_is_rejected(tmp_path):
    path = tmp_path / "activity.gpx"
    path.write_text('<?xml version="1.0"?><TrainingCenterDatabase/>')

    with pytest.raises(ActivityFormatError, match="expected <gpx>"):
        GpxModifier(str(path))
