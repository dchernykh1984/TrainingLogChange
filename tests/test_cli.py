"""Tests for the command line entry point."""

from __future__ import annotations

import pytest

from tests.conftest import text, texts
from training_log_change.cli import main, valid_date


def test_it_applies_several_changes_in_one_run(tcx_path, tmp_path, capsys):
    out = tmp_path / "out.tcx"

    assert main([str(tcx_path), str(out), "--speedup", "2", "--max-hr", "200"]) == 0

    assert text(out, "TotalTimeSeconds") == "10"
    assert texts(out, "Time")[-1] == "2024-03-31T10:00:10.000Z"
    assert "sped up by 2.0" in capsys.readouterr().out


def test_the_original_underscored_option_names_still_work(tcx_path, tmp_path):
    out = tmp_path / "out.tcx"

    assert main([str(tcx_path), str(out), "--max_power", "1000"]) == 0

    assert texts(out, "Watts") == ["200", "0", "210"]


def test_a_run_that_asks_for_nothing_is_an_error(tcx_path, tmp_path, capsys):
    out = tmp_path / "out.tcx"

    assert main([str(tcx_path), str(out)]) == 1

    assert not out.exists()
    assert "nothing to do" in capsys.readouterr().err


def test_a_missing_input_file_is_reported_without_a_traceback(tmp_path, capsys):
    missing = tmp_path / "missing.tcx"

    assert main([str(missing), str(tmp_path / "out.tcx"), "--speedup", "2"]) == 1

    assert "error:" in capsys.readouterr().err


def test_an_input_that_is_not_an_activity_is_reported(tmp_path, capsys):
    broken = tmp_path / "broken.tcx"
    broken.write_text("not xml at all")

    assert main([str(broken), str(tmp_path / "out.tcx"), "--speedup", "2"]) == 1

    assert "not well-formed XML" in capsys.readouterr().err


def test_an_unsupported_extension_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "a.csv"), str(tmp_path / "b.csv"), "--speedup", "2"])


def test_an_output_in_an_unsupported_format_is_rejected(tcx_path, tmp_path, capsys):
    with pytest.raises(SystemExit):
        main([str(tcx_path), str(tmp_path / "out.csv"), "--speedup", "2"])

    assert "unsupported format" in capsys.readouterr().err


def test_a_start_date_that_is_not_a_date_is_rejected(tcx_path, tmp_path, capsys):
    with pytest.raises(SystemExit):
        main([str(tcx_path), str(tmp_path / "out.tcx"), "--start-date", "yesterday"])

    assert "not a valid ISO 8601 date" in capsys.readouterr().err


def test_valid_date_accepts_the_format_the_original_script_documented():
    assert valid_date("2024-03-31T23:53:51.000Z").year == 2024
