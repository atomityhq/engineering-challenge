
import json

import pytest

from workflow.cli import main


@pytest.fixture
def data_dir(tmp_path):
    return str(tmp_path / "workflow-data")


def run_cli(capsys, *args):
    """
    Execute the CLI and capture its output.

    Returns:
        (exit_code, parsed_json, stderr)
    """
    exit_code = main(list(args))
    captured = capsys.readouterr()

    output = (
        json.loads(captured.out)
        if captured.out.strip()
        else None
    )

    return exit_code, output, captured.err


def start_args(data_dir, workflow_id="workflow-001"):
    return (
        "--data-dir",
        data_dir,
        "start",
        workflow_id,
        "--content-id",
        "content-001",
        "--title",
        "Example article",
        "--body",
        "Initial content.",
    )


def test_start_returns_awaiting_review(data_dir, capsys):
    code, output, error = run_cli(
        capsys,
        *start_args(data_dir),
    )

    assert code == 0
    assert error == ""

    assert output["workflow_id"] == "workflow-001"
    assert output["status"] == "awaiting_review"
    assert output["evaluation_count"] == 1
    assert output["revision_count"] == 0


def test_status_reads_persisted_checkpoint(data_dir, capsys):
    run_cli(capsys, *start_args(data_dir))

    code, output, error = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "status",
        "workflow-001",
    )

    assert code == 0
    assert error == ""
    assert output["status"] == "awaiting_review"
    assert output["evaluation_count"] == 1
    assert output["revision_count"] == 0


def test_start_with_one_revision(data_dir, capsys):
    code, output, _ = run_cli(
        capsys,
        *start_args(data_dir),
        "--decisions",
        "revise",
        "human_review",
    )

    assert code == 0
    assert output["status"] == "awaiting_review"
    assert output["evaluation_count"] == 2
    assert output["revision_count"] == 1
    assert "Revision 1" in output["content"]["body"]


def test_start_with_two_revisions(data_dir, capsys):
    code, output, _ = run_cli(
        capsys,
        *start_args(data_dir),
        "--decisions",
        "revise",
        "revise",
        "human_review",
    )

    assert code == 0
    assert output["status"] == "awaiting_review"
    assert output["evaluation_count"] == 3
    assert output["revision_count"] == 2


def test_retry_limit_is_reported_correctly(data_dir, capsys):
    code, output, _ = run_cli(
        capsys,
        *start_args(data_dir),
        "--decisions",
        "revise",
        "revise",
        "revise",
    )

    assert code == 0
    assert output["status"] == "retry_limit_reached"
    assert output["revision_count"] == 2
    assert output["evaluation_count"] == 3

    code, persisted, _ = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "status",
        "workflow-001",
    )

    assert code == 0
    assert persisted["status"] == "retry_limit_reached"


def test_approve_completes_workflow(data_dir, capsys):
    run_cli(capsys, *start_args(data_dir))

    code, output, error = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "approve",
        "workflow-001",
    )

    assert code == 0
    assert error == ""
    assert output["status"] == "completed"
    assert output["evaluation_count"] == 1


def test_completed_status_is_preserved(data_dir, capsys):
    run_cli(capsys, *start_args(data_dir))

    run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "approve",
        "workflow-001",
    )

    code, output, _ = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "status",
        "workflow-001",
    )

    assert code == 0
    assert output["status"] == "completed"


def test_duplicate_approval_is_idempotent(data_dir, capsys):
    run_cli(capsys, *start_args(data_dir))

    approve_args = (
        "--data-dir",
        data_dir,
        "approve",
        "workflow-001",
    )

    code1, first, _ = run_cli(capsys, *approve_args)
    code2, second, _ = run_cli(capsys, *approve_args)

    assert code1 == 0
    assert code2 == 0
    assert first == second

    _, events, _ = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "events",
        "workflow-001",
    )

    event_types = [
        event["event_type"]
        for event in events
    ]

    assert event_types.count("approval_recorded") == 1
    assert event_types.count("workflow_completed") == 1


def test_duplicate_start_is_idempotent(data_dir, capsys):
    args = start_args(data_dir)

    code1, first, _ = run_cli(capsys, *args)
    code2, second, _ = run_cli(capsys, *args)

    assert code1 == 0
    assert code2 == 0
    assert first == second

    _, events, _ = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "events",
        "workflow-001",
    )

    event_types = [
        event["event_type"]
        for event in events
    ]

    assert event_types.count("workflow_started") == 1
    assert event_types.count("content_evaluated") == 1


def test_events_returns_ordered_audit_log(data_dir, capsys):
    run_cli(capsys, *start_args(data_dir))

    run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "approve",
        "workflow-001",
    )

    code, events, error = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "events",
        "workflow-001",
    )

    assert code == 0
    assert error == ""

    assert [
        event["event_type"]
        for event in events
    ] == [
        "workflow_started",
        "content_evaluated",
        "human_review_requested",
        "approval_recorded",
        "workflow_completed",
    ]


def test_unknown_workflow_returns_error(data_dir, capsys):
    code, output, error = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "status",
        "unknown-workflow",
    )

    assert code == 1
    assert output is None
    assert "Workflow not found" in error


def test_approve_unknown_workflow_returns_error(data_dir, capsys):
    code, output, error = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "approve",
        "unknown-workflow",
    )

    assert code == 1
    assert output is None
    assert "Workflow not found" in error


def test_approve_retry_limit_is_rejected(data_dir, capsys):
    run_cli(
        capsys,
        *start_args(data_dir),
        "--decisions",
        "revise",
        "revise",
        "revise",
    )

    code, output, error = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "approve",
        "workflow-001",
    )

    assert code == 1
    assert output is None
    assert "retry limit" in error.lower()


def test_blank_content_id_is_rejected(data_dir, capsys):
    code, output, error = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "start",
        "workflow-001",
        "--content-id",
        "   ",
        "--title",
        "Example article",
        "--body",
        "Initial content.",
    )

    assert code == 1
    assert output is None
    assert "Error:" in error


def test_blank_workflow_id_is_rejected(data_dir, capsys):
    code, output, error = run_cli(
        capsys,
        *start_args(data_dir, workflow_id="   "),
    )

    assert code == 1
    assert output is None
    assert "workflow_id cannot be blank" in error


def test_conflicting_content_id_is_rejected(data_dir, capsys):
    run_cli(capsys, *start_args(data_dir))

    code, output, error = run_cli(
        capsys,
        "--data-dir",
        data_dir,
        "start",
        "workflow-001",
        "--content-id",
        "different-content",
        "--title",
        "Different article",
        "--body",
        "Different content.",
    )

    assert code == 1
    assert output is None
    assert "different request" in error.lower()
