"""Tests for durable SQLite persistence, metadata tracking, and checkpointer storage."""

from datetime import datetime, timezone
import pytest

from workflow.events import create_event
from workflow.models import (
    ContentItem,
    EventType,
    WorkflowEvent,
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
)
from workflow.persistence import WorkflowDatabase


def test_sqlite_tables_created(temp_db_path: str) -> None:
    """Verify that WorkflowDatabase initializes all required SQLite tables and pragmas."""
    db = WorkflowDatabase(temp_db_path)
    with db.get_connection() as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('workflow_runs', 'workflow_events', 'checkpoints');"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert "workflow_runs" in tables
        assert "workflow_events" in tables
        assert "checkpoints" in tables


def test_save_and_retrieve_run_metadata(workflow_db: WorkflowDatabase, sample_content: ContentItem) -> None:
    """Verify run metadata upserts and field accuracy."""
    state = WorkflowState(
        run_id="run_test_meta",
        content_id=sample_content.id,
        content=sample_content,
        status=WorkflowStatus.AWAITING_HUMAN_REVIEW,
        stage=WorkflowStage.HUMAN_REVIEW,
        revision_count=1,
        evaluation_count=2,
        max_revisions=2,
        checkpoint_version=1,
    )
    workflow_db.save_run(state)

    retrieved = workflow_db.get_run_by_content_id(sample_content.id)
    assert retrieved is not None
    assert retrieved["run_id"] == "run_test_meta"
    assert retrieved["status"] == WorkflowStatus.AWAITING_HUMAN_REVIEW.value
    assert retrieved["revision_count"] == 1
    assert retrieved["evaluation_count"] == 2
    assert retrieved["checkpoint_version"] == 1

    # Update state and verify upsert
    state.status = WorkflowStatus.COMPLETED
    state.stage = WorkflowStage.COMPLETE
    workflow_db.save_run(state)

    updated = workflow_db.get_run_by_content_id(sample_content.id)
    assert updated is not None
    assert updated["status"] == WorkflowStatus.COMPLETED.value
    assert updated["stage"] == WorkflowStage.COMPLETE.value


def test_event_persistence_and_ordering(workflow_db: WorkflowDatabase) -> None:
    """Verify append-only event logging, persistence, and ordering."""
    evt1 = create_event(
        workflow_id="run_evt_test",
        content_id="content_evt_test",
        event_type=EventType.WORKFLOW_STARTED,
        stage=WorkflowStage.INITIAL,
        revision_count=0,
        explanation="Started",
        db=workflow_db,
    )
    evt2 = create_event(
        workflow_id="run_evt_test",
        content_id="content_evt_test",
        event_type=EventType.EVALUATION_COMPLETED,
        stage=WorkflowStage.EVALUATE,
        revision_count=0,
        explanation="Evaluated",
        decision="revise",
        db=workflow_db,
    )
    evt3 = create_event(
        workflow_id="run_evt_test",
        content_id="content_evt_test",
        event_type=EventType.CHECKPOINT_SAVED,
        stage=WorkflowStage.HUMAN_REVIEW,
        revision_count=1,
        explanation="Saved checkpoint",
        db=workflow_db,
    )

    events = workflow_db.get_events("run_evt_test")
    assert len(events) == 3
    assert events[0].event_type == EventType.WORKFLOW_STARTED
    assert events[1].event_type == EventType.EVALUATION_COMPLETED
    assert events[2].event_type == EventType.CHECKPOINT_SAVED

    # Ensure idempotency on event_id: saving evt1 again should not duplicate
    workflow_db.save_event(evt1)
    events_after = workflow_db.get_events("run_evt_test")
    assert len(events_after) == 3
