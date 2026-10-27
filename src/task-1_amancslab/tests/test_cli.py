"""Tests for the command-line interface."""

from pathlib import Path

from source_filter.cli import main


SUBMISSION_DIR = Path(__file__).resolve().parents[1]

FIXTURE_PATH = (
    SUBMISSION_DIR / "fixtures" / "source_records.json"
)

POLICY_PATH = SUBMISSION_DIR / "policy.json"


def test_cli_runs_pipeline_successfully(tmp_path, capsys):
    output_dir = tmp_path / "output"

    exit_code = main(
        [
            "--input",
            str(FIXTURE_PATH),
            "--policy",
            str(POLICY_PATH),
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "completed" in captured.out.lower()
    assert "Eligible records: 2" in captured.out
    assert (output_dir / "eligible.json").exists()
    assert (output_dir / "excluded.json").exists()
    assert (output_dir / "summary.json").exists()


def test_cli_reports_missing_input_file(tmp_path, capsys):
    missing_input = tmp_path / "missing.json"

    exit_code = main(
        [
            "--input",
            str(missing_input),
            "--policy",
            str(POLICY_PATH),
            "--output-dir",
            str(tmp_path / "output"),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "ERROR:" in captured.err
    assert not (tmp_path / "output").exists()