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


def test_writing_a_different_format_than_it_read_is_rejected(
    tcx_path, tmp_path, capsys
):
    with pytest.raises(SystemExit):
        main([str(tcx_path), str(tmp_path / "out.gpx"), "--speedup", "2"])

    assert "converting between" in capsys.readouterr().err


def test_it_runs_on_a_gpx_file(gpx_path, tmp_path):
    out = tmp_path / "out.gpx"

    assert main([str(gpx_path), str(out), "--max-hr", "200"]) == 0

    assert texts(out, "hr") == ["140", "0", "150"]


def test_it_runs_on_a_fit_file(fit_path, tmp_path):
    from fit_tool.fit_file import FitFile
    from fit_tool.profile.messages.record_message import RecordMessage

    out = tmp_path / "out.fit"

    assert main([str(fit_path), str(out), "--max-hr", "200"]) == 0

    records = [
        record.message
        for record in FitFile.from_file(str(out)).records
        if isinstance(record.message, RecordMessage)
    ]
    assert [record.heart_rate for record in records] == [140, 0, 150]


def test_it_applies_a_cadence_cap_and_a_new_start_date(tcx_path, tmp_path):
    out = tmp_path / "out.tcx"

    assert (
        main(
            [
                str(tcx_path),
                str(out),
                "--max-cadence",
                "150",
                "--start-date",
                "2025-01-01T08:00:00.000Z",
            ]
        )
        == 0
    )

    assert texts(out, "Cadence") == ["85", "90", "0", "88"]
    assert texts(out, "Time")[0] == "2025-01-01T08:00:00.000Z"


def test_a_non_positive_speedup_is_rejected_by_the_parser(tcx_path, tmp_path, capsys):
    with pytest.raises(SystemExit):
        main([str(tcx_path), str(tmp_path / "out.tcx"), "--speedup", "0"])

    assert "greater than zero" in capsys.readouterr().err


def test_a_speedup_that_is_not_a_number_is_rejected(tcx_path, tmp_path, capsys):
    with pytest.raises(SystemExit):
        main([str(tcx_path), str(tmp_path / "out.tcx"), "--speedup", "fast"])

    assert "not a number" in capsys.readouterr().err


def test_an_activity_that_cannot_be_modified_is_reported(tmp_path, capsys):
    path = tmp_path / "empty.tcx"
    path.write_text(
        '<?xml version="1.0"?>'
        '<TrainingCenterDatabase xmlns="urn:x"><Activities/></TrainingCenterDatabase>'
    )

    assert main([str(path), str(tmp_path / "out.tcx"), "--speedup", "2"]) == 1

    assert "no timestamps" in capsys.readouterr().err


def test_an_output_that_cannot_be_written_is_reported(tcx_path, tmp_path, capsys):
    unwritable = tmp_path / "missing directory" / "out.tcx"

    assert main([str(tcx_path), str(unwritable), "--speedup", "2"]) == 1

    assert "error:" in capsys.readouterr().err


def test_a_change_the_format_cannot_hold_is_reported(fit_path, tmp_path, capsys):
    out = tmp_path / "out.fit"

    assert main([str(fit_path), str(out), "--speedup", "20"]) == 1

    assert "does not fit in a FIT file" in capsys.readouterr().err
