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
