"""The interface every format-specific modifier implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class TrackModifier(ABC):
    """Read a recorded activity, change it in place and write it back.

    Every implementation keeps the activity in its own native representation --
    a parsed XML tree for TCX and GPX, decoded FIT records for FIT -- and edits
    that representation directly. Nothing is projected onto a common intermediate
    model, so fields this tool does not know about (laps, vendor extensions,
    developer fields) survive a load/save round trip untouched.
    """

    @abstractmethod
    def __init__(self, file_path: str) -> None:
        """Load the activity stored at ``file_path``."""

    @abstractmethod
    def save(self, file_path: str) -> None:
        """Write the current state to ``file_path`` in the source format."""

    @abstractmethod
    def speedup(self, multiplier: float) -> None:
        """Make the activity faster by ``multiplier``.

        ``1.1`` means a 10% speedup: recorded speeds are scaled up, elapsed
        durations are scaled down, and every timestamp is moved towards the start
        of the activity so the track keeps the same shape in less time. The start
        of the activity does not move.
        """

    @abstractmethod
    def cleanup_heart_rate(self, max_hr: int) -> None:
        """Zero heart rate readings above ``max_hr``.

        A chest strap losing contact reports isolated spikes far above anything
        the athlete can reach; those samples are sensor errors, not data.
        """

    @abstractmethod
    def cleanup_power(self, max_power: float) -> None:
        """Zero power readings above ``max_power``.

        A power meter sometimes reports unreal values, like 2 kW for one second
        while the cyclist is not pedalling at all.
        """

    @abstractmethod
    def cleanup_cadence(self, max_cadence: int) -> None:
        """Zero cadence readings above ``max_cadence``.

        A magnetic cadence sensor sometimes reports unreal values, like 200 rpm
        for one second while the cyclist is not pedalling at all.
        """

    @abstractmethod
    def update_start_time(self, start_time: datetime) -> None:
        """Move the activity so it starts at ``start_time``.

        Every timestamp in the file is shifted by the same offset, so durations
        and the gaps between samples are unchanged.
        """
