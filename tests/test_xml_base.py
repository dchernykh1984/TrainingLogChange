"""Tests for the timestamp and number helpers shared by the XML formats."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import text, texts, values
from training_log_change.xml_base import (
    format_number,
    format_timestamp,
    parse_number,
    parse_timestamp,
)


@pytest.mark.parametrize(
    "text",
    [
        "2024-03-31T10:00:00.000Z",
        "2024-03-31T10:00:00Z",
        "2024-03-31T10:00:00+03:00",
        "2024-03-31T10:00:00",
    ],
)
def test_a_timestamp_survives_a_parse_and_format_round_trip(text):
    parsed = parse_timestamp(text)
    assert parsed is not None

    assert format_timestamp(*parsed) == text


def test_a_timestamp_keeps_its_own_zone_when_it_is_moved(tcx_offset="+03:00"):
    parsed = parse_timestamp(f"2024-03-31T10:00:00{tcx_offset}")
    assert parsed is not None
    moment, style = parsed

    moved = moment + timedelta(hours=1)

    assert moment == datetime(2024, 3, 31, 7, 0, tzinfo=UTC)
    assert format_timestamp(moved.astimezone(moment.tzinfo), style) == (
        f"2024-03-31T11:00:00{tcx_offset}"
    )


def test_a_timestamp_without_a_zone_is_read_as_utc():
    parsed = parse_timestamp("2024-03-31T10:00:00")
    assert parsed is not None

    assert parsed[0] == datetime(2024, 3, 31, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize("text", [None, "", "not a date", "2024-03-31", "10:00:00"])
def test_text_that_is_not_a_timestamp_is_rejected(text):
    assert parse_timestamp(text) is None


def test_a_number_is_not_rendered_with_floating_point_noise():
    # 5.5 * 1.1 is 6.050000000000001 in binary floating point.
    assert format_number(5.5 * 1.1) == "6.05"


def test_a_whole_number_stays_whole():
    assert format_number(10.0) == "10"


def test_a_number_that_rounds_away_to_nothing_is_zero():
    assert format_number(-1e-12) == "0"


@pytest.mark.parametrize("text", [None, "", "n/a"])
def test_text_that_is_not_a_number_is_rejected(text):
    assert parse_number(text) is None


def test_a_number_may_be_padded_with_whitespace():
    assert parse_number("  42.5\n") == 42.5


ENTITY_TCX = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE TrainingCenterDatabase [
<!ENTITY start "2024-03-31T10:00:00.000Z">
<!ENTITY spike "250">
]>
<TrainingCenterDatabase xmlns="urn:x">
  <Activities><Activity>
    <Id>&start;</Id>
    <Lap StartTime="&start;">
      <MaximumHeartRateBpm><Value>250</Value></MaximumHeartRateBpm>
      <Track>
        <Trackpoint>
          <Time>2024-03-31T10:00:10.000Z</Time>
          <HeartRateBpm><Value>&spike;</Value></HeartRateBpm>
        </Trackpoint>
        <Trackpoint>
          <Time>2024-03-31T10:00:20.000Z</Time>
          <HeartRateBpm><Value>120</Value></HeartRateBpm>
        </Trackpoint>
      </Track>
    </Lap>
  </Activity></Activities>
</TrainingCenterDatabase>
"""


def entity_activity(tmp_path):
    path = tmp_path / "activity.tcx"
    path.write_text(ENTITY_TCX)
    return path


def test_a_timestamp_written_as_an_entity_is_still_moved(tmp_path):
    from datetime import datetime

    from training_log_change.tcx import TcxModifier

    out = tmp_path / "out.tcx"
    modifier = TcxModifier(str(entity_activity(tmp_path)))
    modifier.update_start_time(datetime(2025, 1, 1, tzinfo=UTC))
    modifier.save(str(out))

    # The activity start has to keep matching its own track.
    assert text(out, "Id") == "2025-01-01T00:00:00.000Z"
    assert texts(out, "Time")[0] == "2025-01-01T00:00:10.000Z"


def test_a_reading_written_as_an_entity_is_still_cleaned(tmp_path):
    from training_log_change.tcx import TcxModifier

    out = tmp_path / "out.tcx"
    modifier = TcxModifier(str(entity_activity(tmp_path)))
    modifier.cleanup_heart_rate(180)
    modifier.save(str(out))

    # Skipping the sample while repairing the summary above it would leave the
    # lap reporting a maximum of 120 over a sample of 250.
    assert values(out, "HeartRateBpm") == ["0", "120"]
    assert values(out, "MaximumHeartRateBpm") == ["120"]


def test_a_document_type_definition_cannot_reach_outside_the_file(tmp_path):
    from training_log_change.base import ActivityFormatError
    from training_log_change.tcx import TcxModifier

    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET-TOKEN")
    path = tmp_path / "external.tcx"
    path.write_text(
        '<?xml version="1.0"?>\n'
        "<!DOCTYPE TrainingCenterDatabase "
        f'[ <!ENTITY xxe SYSTEM "file://{secret}"> ]>\n'
        '<TrainingCenterDatabase xmlns="urn:x">'
        "<Id>2024-03-31T10:00:00.000Z</Id><Notes>&xxe;</Notes>"
        "</TrainingCenterDatabase>"
    )

    # The entity is never fetched, so it stays undefined and the file is
    # rejected rather than quietly absorbing the target.
    with pytest.raises(ActivityFormatError):
        TcxModifier(str(path))
