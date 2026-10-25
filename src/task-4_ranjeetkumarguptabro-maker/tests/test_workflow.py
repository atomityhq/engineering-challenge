"""Automated tests for workflow routing, revisions, limits, and completion.

Covers:
- Test A: Normal pass to human review
- Test B: One revision then pass
- Test C: Revision limit enforcement (max 2 revisions)
"""

import pytest

from fixtures.evaluator_fixtures import (
    get_one_revision_evaluator,
    get_pass_evaluator,
    get_perpetual_revise_evaluator,
    get_two_revisions_then_pass_evaluator,
)
from workflow.events import get_event_type_sequence
from workflow.graph import ReviewWorkflowEngine
from workflow.models import (
    ApprovalMetadata,
    ContentItem,
    EventType,
    HumanReviewStatus,
    WorkflowStage,
    WorkflowStatus,
)
from workflow.persistence import WorkflowDatabase


def test_normal_pass_to_human_review(workflow_db: WorkflowDatabase, sample_content: ContentItem) -> None:
    """Test A: Content passes evaluation directly, pauses for human review, and completes on approval."""
    evaluator = get_pass_evaluator()
    engine = ReviewWorkflowEngine(db=workflow_db, evaluator=evaluator)

    # 1. Start workflow
    paused_state = engine.run(sample_content, max_revisions=2)

    # Assert paused at human review boundary
    assert paused_state.status == WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert paused_state.stage == WorkflowStage.HUMAN_REVIEW
    assert paused_state.human_review_status == HumanReviewStatus.PENDING
    assert paused_state.revision_count == 0
    assert paused_state.evaluation_count == 1
    assert paused_state.checkpoint_version == 1
    assert paused_state.next_action == "await_human_approval"

    # Verify checkpoint persisted in DB
    persisted_run = workflow_db.get_run_by_content_id(sample_content.id)
    assert persisted_run is not None
    assert persisted_run["status"] == WorkflowStatus.AWAITING_HUMAN_REVIEW.value
    assert persisted_run["stage"] == WorkflowStage.HUMAN_REVIEW.value

    # 2. Approve and complete
    approval = ApprovalMetadata(approved_by="lead_editor", comment="LGTM for publication")
    final_state = engine.resume_and_approve(sample_content.id, approval_metadata=approval)

    assert final_state.status == WorkflowStatus.COMPLETED
    assert final_state.stage == WorkflowStage.COMPLETE
    assert final_state.human_review_status == HumanReviewStatus.APPROVED
    assert final_state.approval_metadata is not None
    assert final_state.approval_metadata.approved_by == "lead_editor"
    assert final_state.revision_count == 0

    # 3. Verify event log sequence
    events = engine.get_events(sample_content.id)
    event_types = get_event_type_sequence(events)

    expected_types = [
        EventType.WORKFLOW_STARTED,
        EventType.EVALUATION_COMPLETED,
        EventType.HUMAN_REVIEW_REQUIRED,
        EventType.CHECKPOINT_SAVED,
        EventType.WORKFLOW_RESUMED,
        EventType.HUMAN_APPROVED,
        EventType.WORKFLOW_COMPLETED,
    ]
    assert event_types == expected_types

    # Ensure exactly one completion event
    completion_events = [e for e in events if e.event_type == EventType.WORKFLOW_COMPLETED]
    assert len(completion_events) == 1


def test_one_revision_then_pass(workflow_db: WorkflowDatabase, sample_content: ContentItem) -> None:
    """Test B: Evaluator requests revision, revision is executed, next evaluation passes, workflow completes."""
    evaluator = get_one_revision_evaluator()
    engine = ReviewWorkflowEngine(db=workflow_db, evaluator=evaluator)

    # 1. Start workflow
    paused_state = engine.run(sample_content, max_revisions=2)

    # Reached review after 1 revision
    assert paused_state.status == WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert paused_state.stage == WorkflowStage.HUMAN_REVIEW
    assert paused_state.revision_count == 1
    assert paused_state.evaluation_count == 2
    assert len(paused_state.revision_history) == 1
    assert paused_state.revision_history[0].revision_number == 1
    assert "[Revision 1:" in paused_state.content.body

    # 2. Approve and complete
    final_state = engine.resume_and_approve(sample_content.id)
    assert final_state.status == WorkflowStatus.COMPLETED
    assert final_state.stage == WorkflowStage.COMPLETE
    assert final_state.revision_count == 1

    # 3. Assert complete event log sequence
    events = engine.get_events(sample_content.id)
    event_types = get_event_type_sequence(events)

    expected_types = [
        EventType.WORKFLOW_STARTED,
        EventType.EVALUATION_COMPLETED,
        EventType.REVISION_REQUESTED,
        EventType.REVISION_COMPLETED,
        EventType.EVALUATION_COMPLETED,
        EventType.HUMAN_REVIEW_REQUIRED,
        EventType.CHECKPOINT_SAVED,
        EventType.WORKFLOW_RESUMED,
        EventType.HUMAN_APPROVED,
        EventType.WORKFLOW_COMPLETED,
    ]
    assert event_types == expected_types
    assert len([e for e in events if e.event_type == EventType.WORKFLOW_COMPLETED]) == 1


def test_two_revisions_then_pass(workflow_db: WorkflowDatabase, sample_content: ContentItem) -> None:
    """Verify that two revisions succeed when the second revision passes evaluation."""
    evaluator = get_two_revisions_then_pass_evaluator()
    engine = ReviewWorkflowEngine(db=workflow_db, evaluator=evaluator)

    paused_state = engine.run(sample_content, max_revisions=2)
    assert paused_state.status == WorkflowStatus.AWAITING_HUMAN_REVIEW
    assert paused_state.revision_count == 2
    assert paused_state.evaluation_count == 3
    assert len(paused_state.revision_history) == 2

    final_state = engine.resume_and_approve(sample_content.id)
    assert final_state.status == WorkflowStatus.COMPLETED
    assert final_state.revision_count == 2


def test_revision_limit_stops_execution(workflow_db: WorkflowDatabase, sample_content: ContentItem) -> None:
    """Test C: Perpetual revision requests halt strictly after configured max attempts (2) without infinite loop."""
    evaluator = get_perpetual_revise_evaluator()
    engine = ReviewWorkflowEngine(db=workflow_db, evaluator=evaluator)

    # Run with maximum 2 revisions
    terminal_state = engine.run(sample_content, max_revisions=2)

    # Must enter documented terminal state REVISION_LIMIT_REACHED
    assert terminal_state.status == WorkflowStatus.REVISION_LIMIT_REACHED
    assert terminal_state.stage == WorkflowStage.REVISION_LIMIT_REACHED
    assert terminal_state.revision_count == 2
    assert terminal_state.evaluation_count == 3  # Initial + after rev 1 + after rev 2
    assert terminal_state.next_action == "workflow_halted_limit_reached"

    # Confirm event log explains why workflow stopped
    events = engine.get_events(sample_content.id)
    event_types = get_event_type_sequence(events)

    expected_types = [
        EventType.WORKFLOW_STARTED,
        EventType.EVALUATION_COMPLETED,
        EventType.REVISION_REQUESTED,
        EventType.REVISION_COMPLETED,
        EventType.EVALUATION_COMPLETED,
        EventType.REVISION_REQUESTED,
        EventType.REVISION_COMPLETED,
        EventType.EVALUATION_COMPLETED,
        EventType.REVISION_LIMIT_REACHED,
    ]
    assert event_types == expected_types

    limit_event = [e for e in events if e.event_type == EventType.REVISION_LIMIT_REACHED][0]
    assert "Maximum revision limit of 2 attempts reached" in limit_event.explanation

    # Confirm it does NOT reach human review or completion
    assert EventType.HUMAN_REVIEW_REQUIRED not in event_types
    assert EventType.WORKFLOW_COMPLETED not in event_types
