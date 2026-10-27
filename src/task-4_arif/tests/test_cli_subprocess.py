
import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(
    data_dir: Path,
    *arguments: str,
    expected_returncode: int = 0,
) -> dict | list | None:
    """
    Run one CLI command in a fresh Python process.

    Every invocation starts a new interpreter, constructs a new
    graph, and opens the persisted SQLite databases.
    """
    command = [
        sys.executable,
        "-m",
        "workflow.cli",
        "--data-dir",
        str(data_dir),
        *arguments,
    ]

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == expected_returncode, (
        f"Command: {' '.join(command)}\n"
        f"Expected exit code: {expected_returncode}\n"
        f"Actual exit code: {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    if expected_returncode != 0:
        return None

    return json.loads(result.stdout)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "workflow-data"


def test_full_workflow_across_independent_processes(data_dir):
    # Process 1: start and pause at human review.
    started = run_cli(
        data_dir,
        "start",
        "workflow-001",
        "--content-id",
        "content-001",
        "--title",
        "Subprocess test",
        "--body",
        "Initial content.",
        "--decisions",
        "revise",
        "human_review",
    )

    assert started["workflow_id"] == "workflow-001"
    assert started["status"] == "awaiting_review"
    assert started["evaluation_count"] == 2
    assert started["revision_count"] == 1
    assert "Revision 1" in started["content"]["body"]

    # Process 2: read the checkpoint from a new interpreter.
    pending = run_cli(
        data_dir,
        "status",
        "workflow-001",
    )

    assert pending["status"] == "awaiting_review"
    assert pending["evaluation_count"] == 2
    assert pending["revision_count"] == 1
    assert pending["content"] == started["content"]

    # Process 3: resume the interrupted graph.
    approved = run_cli(
        data_dir,
        "approve",
        "workflow-001",
    )

    assert approved["status"] == "completed"
    assert approved["evaluation_count"] == 2
    assert approved["revision_count"] == 1
    assert approved["content"] == started["content"]

    # Process 4: read the event log from another interpreter.
    events = run_cli(
        data_dir,
        "events",
        "workflow-001",
    )

    assert [event["event_type"] for event in events] == [
        "workflow_started",
        "content_evaluated",
        "content_revised",
        "content_evaluated",
        "human_review_requested",
        "approval_recorded",
        "workflow_completed",
    ]

    assert len({event["event_id"] for event in events}) == 7

    # Process 5: confirm terminal checkpoint is persisted.
    completed = run_cli(
        data_dir,
        "status",
        "workflow-001",
    )

    assert completed["status"] == "completed"
    assert completed["evaluation_count"] == 2
    assert completed["revision_count"] == 1


def test_duplicate_approval_across_processes(data_dir):
    run_cli(
        data_dir,
        "start",
        "workflow-duplicate",
        "--content-id",
        "content-duplicate",
        "--title",
        "Duplicate approval",
        "--body",
        "Initial content.",
    )

    first = run_cli(
        data_dir,
        "approve",
        "workflow-duplicate",
    )

    events_before = run_cli(
        data_dir,
        "events",
        "workflow-duplicate",
    )

    # A separate process submits the same approval again.
    second = run_cli(
        data_dir,
        "approve",
        "workflow-duplicate",
    )

    events_after = run_cli(
        data_dir,
        "events",
        "workflow-duplicate",
    )

    assert first == second
    assert first["status"] == "completed"
    assert events_before == events_after

    event_types = [event["event_type"] for event in events_after]

    assert event_types.count("approval_recorded") == 1
    assert event_types.count("workflow_completed") == 1


def test_retry_limit_persists_across_processes(data_dir):
    result = run_cli(
        data_dir,
        "start",
        "workflow-limit",
        "--content-id",
        "content-limit",
        "--title",
        "Retry limit",
        "--body",
        "Initial content.",
        "--decisions",
        "revise",
        "revise",
        "revise",
    )

    assert result["status"] == "retry_limit_reached"
    assert result["revision_count"] == 2
    assert result["evaluation_count"] == 3

    # The new process reads the terminal checkpoint.
    persisted = run_cli(
        data_dir,
        "status",
        "workflow-limit",
    )

    assert persisted == result

    events = run_cli(
        data_dir,
        "events",
        "workflow-limit",
    )

    event_types = [event["event_type"] for event in events]

    assert event_types.count("content_revised") == 2
    assert event_types.count("content_evaluated") == 3
    assert event_types.count("retry_limit_reached") == 1
    assert "workflow_completed" not in event_types

    # Approval is invalid for a retry-limit terminal workflow.
    run_cli(
        data_dir,
        "approve",
        "workflow-limit",
        expected_returncode=1,
    )

    assert run_cli(
        data_dir,
        "events",
        "workflow-limit",
    ) == events


def test_duplicate_start_across_processes(data_dir):
    arguments = (
        "start",
        "workflow-start",
        "--content-id",
        "content-start",
        "--title",
        "Duplicate start",
        "--body",
        "Initial content.",
    )

    first = run_cli(data_dir, *arguments)

    events_before = run_cli(
        data_dir,
        "events",
        "workflow-start",
    )

    second = run_cli(data_dir, *arguments)

    events_after = run_cli(
        data_dir,
        "events",
        "workflow-start",
    )

    assert first == second
    assert events_before == events_after

    event_types = [event["event_type"] for event in events_after]

    assert event_types.count("workflow_started") == 1
    assert event_types.count("content_evaluated") == 1
    assert event_types.count("human_review_requested") == 1


def test_unknown_workflow_returns_error_in_new_process(data_dir):
    run_cli(
        data_dir,
        "status",
        "nonexistent-workflow",
        expected_returncode=1,
    )

    run_cli(
        data_dir,
        "approve",
        "nonexistent-workflow",
        expected_returncode=1,
    )

    run_cli(
        data_dir,
        "events",
        "nonexistent-workflow",
        expected_returncode=1,
    )
