"""Tests for choosing a modifier from a file extension."""

from __future__ import annotations

import pytest

from training_log_change.factory import (
    UnsupportedFormatError,
    format_of,
    open_track,
)
from training_log_change.tcx import TcxModifier


def test_the_extension_is_matched_case_insensitively(tcx_path):
    renamed = tcx_path.with_suffix(".TCX")
    tcx_path.rename(renamed)

    assert isinstance(open_track(str(renamed)), TcxModifier)


def test_an_unknown_extension_names_the_supported_formats(tmp_path):
    with pytest.raises(UnsupportedFormatError, match=r"supported formats are .*\.tcx"):
        format_of(str(tmp_path / "activity.csv"))


def test_a_file_without_an_extension_is_rejected(tmp_path):
    with pytest.raises(UnsupportedFormatError, match="activity"):
        format_of(str(tmp_path / "activity"))
