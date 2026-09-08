"""Pick a modifier for a file based on its extension."""

from __future__ import annotations

from pathlib import Path

from training_log_change.base import TrackModifier
from training_log_change.fit import FitModifier
from training_log_change.gpx import GpxModifier
from training_log_change.tcx import TcxModifier

MODIFIERS: dict[str, type[TrackModifier]] = {
    ".tcx": TcxModifier,
    ".fit": FitModifier,
    ".gpx": GpxModifier,
}


class UnsupportedFormatError(Exception):
    """The file extension does not name a format this tool can read."""


def format_of(file_path: str) -> str:
    """The supported extension of ``file_path``, lower-cased.

    Raises :class:`UnsupportedFormatError` if the extension is not one of the
    supported formats.
    """
    suffix = Path(file_path).suffix.lower()
    if suffix not in MODIFIERS:
        supported = ", ".join(sorted(MODIFIERS))
        raise UnsupportedFormatError(
            f"{file_path}: unsupported format '{suffix or Path(file_path).name}'; "
            f"supported formats are {supported}"
        )
    return suffix


def open_track(file_path: str) -> TrackModifier:
    """Load ``file_path`` with the modifier that matches its extension."""
    return MODIFIERS[format_of(file_path)](file_path)
