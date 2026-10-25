"""Tests for persistence and resumption across process restarts (Test D).

Verifies:
1. Workflow pauses at human review and checkpoints state to SQLite.
2. Process termination and fresh process restart.
3. Resuming loads state and continues directly from human review boundary.
4. Earlier evaluation and revision nodes are NOT re-executed.
5. Real external subprocess restart execution.
"""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from fixtures.evaluator_fixtures import get_one_revision_evaluator
from workflow.evaluator import Evaluator
from workflow.events import get_event_type_sequence
from workflow.graph import ReviewWorkflowEngine
from workflow.models import (
    ContentItem,
    EvaluationResult,
    EventType,
    WorkflowStage,
    WorkflowStatus,
)
from workflow.persistence import WorkflowDatabase


class FailingEvaluator(Evaluator):
    """Evaluator that raises an assertion error if invoked.
    
    Used to prove that resuming does NOT re-run the evaluation node.
    """

    def evaluate(self, content: ContentItem, revision_count: int) -> EvaluationResult:
        raise AssertionError("CRITICAL FAILURE: evaluate_node was invoked during resume!")


def test_resume_does_not_rerun_completed_nodes(temp_db_path: str, sample_content: ContentItem) -> None:
    """Test D: Fresh engine session resumes without rerunning earlier evaluation or revision nodes."""
    db1 = WorkflowDatabase(temp_db_path)
    evaluator1 = get_one_revision_evaluator()
    engine1 = ReviewWorkflowEngine(db=db1, evaluator=evaluator1)

    # 1. Run until human review boundary (1 revision performed)
    state1 = engine1.run(sample_content, max_revisions=2)
    assert state1.status == WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert state1.revision_count == 1
    assert state1.evaluation_count == 2

    # Capture event count prior to shutdown
    events_before = engine1.get_events(sample_content.id)
    assert len(events_before) == 7

    # 2. Simulate complete memory teardown: drop engine1 and db1 references
    del engine1
    del db1

    # 3. Fresh session using the same SQLite storage, equipped with an evaluator that would fail if called
    db2 = WorkflowDatabase(temp_db_path)
    engine2 = ReviewWorkflowEngine(db=db2, evaluator=FailingEvaluator())

    # Verify loaded checkpoint state before resume
    loaded_state = engine2.get_state(sample_content.id)
    assert loaded_state is not None
    assert loaded_state.status == WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert loaded_state.stage == WorkflowStage.HUMAN_REVIEW
    assert loaded_state.revision_count == 1
    assert loaded_state.evaluation_count == 2

    # 4. Resume and approve - FailingEvaluator would crash if evaluate was executed
    final_state = engine2.resume_and_approve(sample_content.id)

    assert final_state.status == WorkflowStatus.COMPLETED
    assert final_state.stage == WorkflowStage.COMPLETE
    # Revision and evaluation counts must remain unchanged
    assert final_state.revision_count == 1
    assert final_state.evaluation_count == 2

    # 5. Confirm event sequence reflects clean resume without duplicate evaluation/revision
    events_after = engine2.get_events(sample_content.id)
    event_types = get_event_type_sequence(events_after)

    expected_types = [
        EventType.WORKFLOW_STARTED,
        EventType.EVALUATION_COMPLETED,
        EventType.REVISION_REQUESTED,
        EventType.REVISION_COMPLETED,
        EventType.EVALUATION_COMPLETED,
        EventType.HUMAN_REVIEW_REQUIRED,
        EventType.CHECKPOINT_SAVED,
        # Resumed events:
        EventType.WORKFLOW_RESUMED,
        EventType.HUMAN_APPROVED,
        EventType.WORKFLOW_COMPLETED,
    ]
    assert event_types == expected_types


def test_real_process_restart_via_cli_subprocess(temp_db_path: str) -> None:
    """Test D: Start workflow in one OS process, terminate, then resume in a fresh OS process."""
    env = os.environ.copy()
    cwd = str(Path(__file__).resolve().parent.parent)

    content_id = "content-proc-restart-1"

    # Process 1: Run workflow to pause using CLI
    cmd_run = [
        sys.executable,
        "-m",
        "workflow.cli",
        "run",
        content_id,
        "--scenario",
        "revise-once",
        "--db",
        temp_db_path,
    ]
    res1 = subprocess.run(cmd_run, cwd=cwd, env=env, capture_output=True, text=True)
    assert res1.returncode == 0, f"Process 1 failed: {res1.stderr}"
    assert "Workflow paused." in res1.stdout
    assert "Checkpoint saved" in res1.stdout

    # Process 2: Inspect status in a completely new OS process
    cmd_status = [
        sys.executable,
        "-m",
        "workflow.cli",
        "status",
        content_id,
        "--db",
        temp_db_path,
    ]
    res2 = subprocess.run(cmd_status, cwd=cwd, env=env, capture_output=True, text=True)
    assert res2.returncode == 0, f"Process 2 status check failed: {res2.stderr}"
    assert "awaiting_human_review" in res2.stdout

    # Process 3: Resume and approve in a third independent OS process
    cmd_resume = [
        sys.executable,
        "-m",
        "workflow.cli",
        "resume",
        content_id,
        "--reviewer",
        "test_cli_reviewer",
        "--db",
        temp_db_path,
    ]
    res3 = subprocess.run(cmd_resume, cwd=cwd, env=env, capture_output=True, text=True)
    assert res3.returncode == 0, f"Process 3 resume failed: {res3.stderr}"
    assert "Loaded checkpoint" in res3.stdout
    assert "Workflow completed." in res3.stdout

    # Process 4: Verify completion and event count in a fourth OS process
    cmd_events = [
        sys.executable,
        "-m",
        "workflow.cli",
        "events",
        content_id,
        "--json",
        "--db",
        temp_db_path,
    ]
    res4 = subprocess.run(cmd_events, cwd=cwd, env=env, capture_output=True, text=True)
    assert res4.returncode == 0
    assert "workflow_completed" in res4.stdout
    assert "test_cli_reviewer" in res4.stdout
