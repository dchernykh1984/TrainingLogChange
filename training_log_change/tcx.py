"""Modifier for TCX, the Garmin Training Center XML format."""

from __future__ import annotations

from training_log_change.xml_base import XmlTrackModifier


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

    def cleanup_heart_rate(self, max_hr: int) -> None:
        # Not implemented yet; see the Status section of the README.
        pass

    def cleanup_power(self, max_power: float) -> None:
        # Not implemented yet; see the Status section of the README.
        pass

    def cleanup_cadence(self, max_cadence: int) -> None:
        # Not implemented yet; see the Status section of the README.
        pass
