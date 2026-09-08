"""Modifier for GPX, the interchange format every tool can read.

GPX is a route format first. It has no speed and no duration of its own -- a
speedup is entirely a matter of compressing the timestamps, and the speed that
results is whatever the reader computes from the points. Sensor readings live in
the TrackPointExtension namespace rather than the base schema, and there are no
lap summaries to keep consistent with the samples.
"""

from __future__ import annotations

from collections.abc import Iterable

from training_log_change.xml_base import (
    XmlTrackModifier,
    find_leaves,
    parse_number,
)


class GpxModifier(XmlTrackModifier):
    """Edit a ``.gpx`` track in place."""

    ROOT_NAME = "gpx"
    TIME_ELEMENTS = frozenset({"time"})

    #: GPX 1.0 had a <speed> element and some extensions still write one. When
    #: it is there it has to follow the speedup; when it is not, compressing the
    #: timestamps is the whole operation.
    FASTER_FIELDS = frozenset({"speed"})

    #: Heart rate and cadence come from TrackPointExtension. Power has no agreed
    #: spelling: the Garmin extension calls it PowerInWatts, Strava writes a bare
    #: <power>, so both are accepted.
    HR_FIELDS = ("hr",)
    POWER_FIELDS = ("power", "PowerInWatts")
    CADENCE_FIELDS = ("cad",)

    def speedup(self, multiplier: float) -> None:
        if multiplier <= 0:
            raise ValueError("speedup multiplier must be positive")
        self._scale_numbers({name: multiplier for name in self.FASTER_FIELDS})
        self._compress_times(multiplier)

    def cleanup_heart_rate(self, max_hr: int) -> None:
        self._zero_above(self.HR_FIELDS, max_hr)

    def cleanup_power(self, max_power: float) -> None:
        self._zero_above(self.POWER_FIELDS, max_power)

    def cleanup_cadence(self, max_cadence: int) -> None:
        self._zero_above(self.CADENCE_FIELDS, max_cadence)

    def _zero_above(self, names: Iterable[str], limit: float) -> None:
        """Zero every reading above ``limit``.

        Unlike TCX and FIT there is nothing to repair afterwards: GPX records no
        summary that could go on claiming the spike.
        """
        for element in find_leaves(self.root, names):
            value = parse_number(element.text)
            if value is not None and value > limit:
                element.text = "0"
