"""Fixtures shared by the format tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

TCX_NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
TPX_NS = "http://www.garmin.com/xmlschemas/ActivityExtension/v2"

# One lap, three samples ten seconds apart. The middle sample carries the kind of
# spike the cleanups exist for: 230 bpm, 200 rpm and 2000 W, mirrored in the lap
# summary the way a device would record it.
SAMPLE_TCX = f"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="{TCX_NS}" xmlns:ns3="{TPX_NS}">
  <Activities>
    <Activity Sport="Biking">
      <Id>2024-03-31T10:00:00.000Z</Id>
      <Lap StartTime="2024-03-31T10:00:00.000Z">
        <TotalTimeSeconds>20.0</TotalTimeSeconds>
        <DistanceMeters>100.0</DistanceMeters>
        <MaximumSpeed>10.0</MaximumSpeed>
        <MaximumHeartRateBpm><Value>230</Value></MaximumHeartRateBpm>
        <Cadence>85</Cadence>
        <Track>
          <Trackpoint>
            <Time>2024-03-31T10:00:00.000Z</Time>
            <HeartRateBpm><Value>140</Value></HeartRateBpm>
            <Cadence>90</Cadence>
            <Extensions><ns3:TPX>
              <ns3:Speed>5.0</ns3:Speed><ns3:Watts>200</ns3:Watts>
            </ns3:TPX></Extensions>
          </Trackpoint>
          <Trackpoint>
            <Time>2024-03-31T10:00:10.000Z</Time>
            <HeartRateBpm><Value>230</Value></HeartRateBpm>
            <Cadence>200</Cadence>
            <Extensions><ns3:TPX>
              <ns3:Speed>6.0</ns3:Speed><ns3:Watts>2000</ns3:Watts>
            </ns3:TPX></Extensions>
          </Trackpoint>
          <Trackpoint>
            <Time>2024-03-31T10:00:20.000Z</Time>
            <HeartRateBpm><Value>150</Value></HeartRateBpm>
            <Cadence>88</Cadence>
            <Extensions><ns3:TPX>
              <ns3:Speed>7.0</ns3:Speed><ns3:Watts>210</ns3:Watts>
            </ns3:TPX></Extensions>
          </Trackpoint>
        </Track>
        <Extensions><ns3:LX>
          <ns3:MaxWatts>2000</ns3:MaxWatts>
          <ns3:MaxBikeCadence>200</ns3:MaxBikeCadence>
        </ns3:LX></Extensions>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>
"""


GPX_NS = "http://www.topografix.com/GPX/1/1"
TPX_EXT_NS = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
POWER_EXT_NS = "http://www.garmin.com/xmlschemas/PowerExtension/v1"

# The same ride as SAMPLE_TCX, and the same spike, but written the way a GPX
# export writes it: whole-second timestamps with no fraction, sensor readings in
# the extension namespaces, and no lap summary anywhere.
SAMPLE_GPX = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Garmin Connect" xmlns="{GPX_NS}"
     xmlns:gpxtpx="{TPX_EXT_NS}" xmlns:gpxpx="{POWER_EXT_NS}">
  <metadata><time>2024-03-31T10:00:00Z</time></metadata>
  <trk>
    <name>Ride</name>
    <type>cycling</type>
    <trkseg>
      <trkpt lat="55.0" lon="37.0">
        <ele>150.0</ele>
        <time>2024-03-31T10:00:00Z</time>
        <extensions>
          <gpxpx:PowerInWatts>200</gpxpx:PowerInWatts>
          <gpxtpx:TrackPointExtension>
            <gpxtpx:hr>140</gpxtpx:hr><gpxtpx:cad>90</gpxtpx:cad>
          </gpxtpx:TrackPointExtension>
        </extensions>
      </trkpt>
      <trkpt lat="55.001" lon="37.001">
        <ele>151.0</ele>
        <time>2024-03-31T10:00:10Z</time>
        <extensions>
          <gpxpx:PowerInWatts>2000</gpxpx:PowerInWatts>
          <gpxtpx:TrackPointExtension>
            <gpxtpx:hr>230</gpxtpx:hr><gpxtpx:cad>200</gpxtpx:cad>
          </gpxtpx:TrackPointExtension>
        </extensions>
      </trkpt>
      <trkpt lat="55.002" lon="37.002">
        <ele>152.0</ele>
        <time>2024-03-31T10:00:20Z</time>
        <extensions>
          <gpxpx:PowerInWatts>210</gpxpx:PowerInWatts>
          <gpxtpx:TrackPointExtension>
            <gpxtpx:hr>150</gpxtpx:hr><gpxtpx:cad>88</gpxtpx:cad>
          </gpxtpx:TrackPointExtension>
        </extensions>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
"""


@pytest.fixture
def tcx_path(tmp_path: Path) -> Path:
    path = tmp_path / "activity.tcx"
    path.write_text(SAMPLE_TCX)
    return path


def texts(path: Path, name: str) -> list[str]:
    """The text of every element with the given local name, in document order."""
    root = etree.parse(str(path)).getroot()
    return [
        (element.text or "").strip()
        for element in root.iter()
        if isinstance(element.tag, str) and element.tag.split("}")[-1] == name
    ]


def text(path: Path, name: str) -> str:
    """The text of the only element with the given local name."""
    found = texts(path, name)
    assert len(found) == 1, f"expected one <{name}>, found {len(found)}"
    return found[0]


def values(path: Path, parent_name: str) -> list[str]:
    """The <Value> texts nested under every element with the given local name."""
    root = etree.parse(str(path)).getroot()
    return [
        (child.text or "").strip()
        for element in root.iter()
        if isinstance(element.tag, str) and element.tag.split("}")[-1] == parent_name
        for child in element
        if isinstance(child.tag, str) and child.tag.split("}")[-1] == "Value"
    ]


# The FIT equivalent of SAMPLE_TCX, built rather than checked in: a binary
# fixture nobody can read in a diff is a liability, and the builder states the
# expected values in the same place the tests read them.
FIT_START_MS = 1711879200000  # 2024-03-31T10:00:00Z
FIT_EPOCH_OFFSET_S = 631065600  # 1989-12-31T00:00:00Z, where FIT counts from
FIT_LOCAL_OFFSET_S = 3 * 3600  # the recording device was three hours ahead
FIT_SAMPLES = (
    # heart rate, cadence, power, speed
    (140, 90, 200, 5.0),
    (230, 200, 2000, 6.0),
    (150, 88, 210, 7.0),
)


def _build_fit(path: Path) -> None:
    from fit_tool.fit_file_builder import FitFileBuilder
    from fit_tool.profile.messages.activity_message import ActivityMessage
    from fit_tool.profile.messages.file_id_message import FileIdMessage
    from fit_tool.profile.messages.lap_message import LapMessage
    from fit_tool.profile.messages.record_message import RecordMessage
    from fit_tool.profile.messages.session_message import SessionMessage
    from fit_tool.profile.profile_type import FileType, Manufacturer, Sport

    builder = FitFileBuilder(auto_define=True)

    file_id = FileIdMessage()
    file_id.type = FileType.ACTIVITY
    file_id.manufacturer = Manufacturer.GARMIN.value
    file_id.time_created = FIT_START_MS
    builder.add(file_id)

    for index, (hr, cadence, power, speed) in enumerate(FIT_SAMPLES):
        record = RecordMessage()
        record.timestamp = FIT_START_MS + index * 10_000
        record.heart_rate = hr
        record.cadence = cadence
        record.power = power
        record.speed = speed
        record.distance = float(index * 50)
        builder.add(record)

    for summary in (LapMessage(), SessionMessage()):
        summary.start_time = FIT_START_MS
        summary.timestamp = FIT_START_MS + 20_000
        summary.total_elapsed_time = 20.0
        summary.total_timer_time = 20.0
        summary.total_distance = 100.0
        summary.avg_speed = 6.0
        summary.max_speed = 7.0
        summary.max_heart_rate = 230
        summary.max_power = 2000
        summary.max_cadence = 200
        if isinstance(summary, SessionMessage):
            summary.sport = Sport.CYCLING
        builder.add(summary)

    activity = ActivityMessage()
    activity.timestamp = FIT_START_MS + 20_000
    activity.local_timestamp = (
        FIT_START_MS // 1000 - FIT_EPOCH_OFFSET_S + 20 + FIT_LOCAL_OFFSET_S
    )
    activity.total_timer_time = 20.0
    builder.add(activity)

    builder.build().to_file(str(path))


@pytest.fixture
def fit_path(tmp_path: Path) -> Path:
    path = tmp_path / "activity.fit"
    _build_fit(path)
    return path


@pytest.fixture
def gpx_path(tmp_path: Path) -> Path:
    path = tmp_path / "activity.gpx"
    path.write_text(SAMPLE_GPX)
    return path
