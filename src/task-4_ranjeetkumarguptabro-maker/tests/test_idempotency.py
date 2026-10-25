"""Tests for approval idempotency and invalid state transition handling (Test E).

Verifies:
1. Multiple consecutive approval attempts produce no duplicate completion events.
2. Completed workflows do not repeat downstream work.
3. Ineligible workflows (e.g. revision limit reached) reject approval attempts with clear errors.
"""

import pytest

from fixtures.evaluator_fixtures import (
    get_pass_evaluator,
    get_perpetual_revise_evaluator,
)
from workflow.events import get_event_type_sequence
from workflow.graph import ReviewWorkflowEngine
from workflow.models import (
    ApprovalMetadata,
    ContentItem,
    EventType,
    WorkflowStatus,
)
from workflow.persistence import WorkflowDatabase


def test_duplicate_approval_idempotency(workflow_db: WorkflowDatabase, sample_content: ContentItem) -> None:
    """Test E: Repeated approval of an already-completed workflow does not duplicate completion events."""
    evaluator = get_pass_evaluator()
    engine = ReviewWorkflowEngine(db=workflow_db, evaluator=evaluator)

    # 1. Run and first approval
    engine.run(sample_content)
    first_completion = engine.resume_and_approve(
        sample_content.id,
        approval_metadata=ApprovalMetadata(approved_by="reviewer_1", comment="First approval"),
    )
    assert first_completion.status == WorkflowStatus.COMPLETED

    events_after_first = engine.get_events(sample_content.id)
    completion_events_first = [e for e in events_after_first if e.event_type == EventType.WORKFLOW_COMPLETED]
    assert len(completion_events_first) == 1
    total_events_first = len(events_after_first)

    # 2. Second approval call on already completed workflow
    second_completion = engine.resume_and_approve(
        sample_content.id,
        approval_metadata=ApprovalMetadata(approved_by="reviewer_2", comment="Duplicate approval attempt"),
    )

    # Status remains completed
    assert second_completion.status == WorkflowStatus.COMPLETED

    # Events must NOT increase; no duplicate completion event
    events_after_second = engine.get_events(sample_content.id)
    assert len(events_after_second) == total_events_first
    completion_events_second = [e for e in events_after_second if e.event_type == EventType.WORKFLOW_COMPLETED]
    assert len(completion_events_second) == 1

    # 3. Third approval call
    third_completion = engine.resume_and_approve(sample_content.id)
    assert third_completion.status == WorkflowStatus.COMPLETED
    assert len(engine.get_events(sample_content.id)) == total_events_first


def test_duplicate_run_on_completed_workflow(workflow_db: WorkflowDatabase, sample_content: ContentItem) -> None:
    """Re-running engine.run on an already completed content item returns existing state without side effects."""
    evaluator = get_pass_evaluator()
    engine = ReviewWorkflowEngine(db=workflow_db, evaluator=evaluator)

    # Run and complete
    engine.run(sample_content)
    engine.resume_and_approve(sample_content.id)

    events_before = engine.get_events(sample_content.id)
    initial_event_count = len(events_before)

    # Attempt to re-run
    repeated_state = engine.run(sample_content)
    assert repeated_state.status == WorkflowStatus.COMPLETED

    # Ensure no new events were recorded
    events_after = engine.get_events(sample_content.id)
    assert len(events_after) == initial_event_count


def test_approval_rejected_when_revision_limit_reached(
    workflow_db: WorkflowDatabase, sample_content: ContentItem
) -> None:
    """Attempting to approve a workflow that terminated due to revision limit must fail predictably."""
    evaluator = get_perpetual_revise_evaluator()
    engine = ReviewWorkflowEngine(db=workflow_db, evaluator=evaluator)

    state = engine.run(sample_content, max_revisions=2)
    assert state.status == WorkflowStatus.REVISION_LIMIT_REACHED

    # Resuming / approving must raise ValueError explaining why it cannot be approved
    with pytest.raises(ValueError, match="reached revision limit and cannot be approved"):
        engine.resume_and_approve(sample_content.id)


def test_resume_non_existent_workflow_raises_error(workflow_db: WorkflowDatabase) -> None:
    """Attempting to resume a workflow that was never created must fail predictably."""
    engine = ReviewWorkflowEngine(db=workflow_db)
    with pytest.raises(ValueError, match="No checkpoint found for content ID 'non-existent'"):
        engine.resume_and_approve("non-existent")
