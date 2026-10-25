"""Pure node functions for the LangGraph Resumable Review Workflow.

Contains discrete, testable logic for:
- evaluate: evaluates content against quality policies
- revise: applies deterministic revisions based on feedback
- limit_reached: handles retry limit terminal boundary
- human_review: prepares the human-review pause and saves checkpoint
- approve_and_complete: handles approval and terminal completion idempotently
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.runnables import RunnableConfig

from workflow.events import create_event
from workflow.evaluator import Evaluator, RuleBasedEvaluator
from workflow.models import (
    ApprovalMetadata,
    ContentItem,
    EvaluatorDecision,
    EventType,
    HumanReviewStatus,
    RevisionRecord,
    WorkflowEvent,
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
)


def _get_configurable(config: Optional[RunnableConfig]) -> Dict[str, Any]:
    if not config or "configurable" not in config:
        return {}
    return config["configurable"]


def evaluate_node(state: WorkflowState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Node: Evaluate content item deterministically."""
    configurable = _get_configurable(config)
    evaluator: Evaluator = configurable.get("evaluator") or RuleBasedEvaluator()
    db = configurable.get("db")

    result = evaluator.evaluate(state.content, state.revision_count)
    events: List[WorkflowEvent] = []

    # Record evaluation_completed event
    evt_eval = create_event(
        workflow_id=state.run_id,
        content_id=state.content_id,
        event_type=EventType.EVALUATION_COMPLETED,
        stage=WorkflowStage.EVALUATE,
        revision_count=state.revision_count,
        decision=result.decision.value,
        explanation=f"Evaluation completed with decision: {result.decision.value}. ({result.reason})",
        metadata={"scores": result.scores, "evaluator": result.evaluator_name},
        db=db,
    )
    events.append(evt_eval)

    # If decision is revise and under budget, also record revision_requested
    if result.decision == EvaluatorDecision.REVISE and state.revision_count < state.max_revisions:
        evt_rev_req = create_event(
            workflow_id=state.run_id,
            content_id=state.content_id,
            event_type=EventType.REVISION_REQUESTED,
            stage=WorkflowStage.EVALUATE,
            revision_count=state.revision_count + 1,
            decision=result.decision.value,
            explanation=f"Revision attempt {state.revision_count + 1} requested: {result.reason}",
            metadata={"reason": result.reason},
            db=db,
        )
        events.append(evt_rev_req)

    return {
        "stage": WorkflowStage.EVALUATE,
        "status": WorkflowStatus.EVALUATING,
        "evaluation_result": result,
        "evaluation_count": state.evaluation_count + 1,
        "events": events,
        "updated_at": datetime.now(timezone.utc),
    }


def revise_node(state: WorkflowState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Node: Perform deterministic revision on the content."""
    configurable = _get_configurable(config)
    db = configurable.get("db")

    new_revision_num = state.revision_count + 1
    reason = (
        state.evaluation_result.reason
        if state.evaluation_result
        else "Automated revision pass"
    )

    # Predictable, non-executable content revision update
    revised_body = f"{state.content.body}\n\n[Revision {new_revision_num}: Addressed '{reason}']"
    updated_content = state.content.model_copy(
        update={
            "body": revised_body,
            "version": state.content.version + 1,
        }
    )

    record = RevisionRecord(
        revision_number=new_revision_num,
        reason=reason,
        previous_body=state.content.body,
        revised_body=revised_body,
        timestamp=datetime.now(timezone.utc),
    )

    evt_rev_comp = create_event(
        workflow_id=state.run_id,
        content_id=state.content_id,
        event_type=EventType.REVISION_COMPLETED,
        stage=WorkflowStage.REVISE,
        revision_count=new_revision_num,
        explanation=f"Revision {new_revision_num} completed successfully.",
        metadata={"revision_number": new_revision_num, "reason": reason},
        db=db,
    )

    return {
        "stage": WorkflowStage.REVISE,
        "status": WorkflowStatus.REVISING,
        "content": updated_content,
        "revision_count": new_revision_num,
        "revision_history": state.revision_history + [record],
        "events": [evt_rev_comp],
        "updated_at": datetime.now(timezone.utc),
    }


def limit_reached_node(state: WorkflowState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Node: Terminal state reached when maximum revision limit is exhausted."""
    configurable = _get_configurable(config)
    db = configurable.get("db")

    explanation = (
        f"Maximum revision limit of {state.max_revisions} attempts reached "
        f"after {state.evaluation_count} evaluations without passing quality checks."
    )

    evt_limit = create_event(
        workflow_id=state.run_id,
        content_id=state.content_id,
        event_type=EventType.REVISION_LIMIT_REACHED,
        stage=WorkflowStage.REVISION_LIMIT_REACHED,
        revision_count=state.revision_count,
        decision=state.evaluation_result.decision.value if state.evaluation_result else None,
        explanation=explanation,
        metadata={"max_revisions": state.max_revisions, "evaluation_count": state.evaluation_count},
        db=db,
    )

    return {
        "stage": WorkflowStage.REVISION_LIMIT_REACHED,
        "status": WorkflowStatus.REVISION_LIMIT_REACHED,
        "next_action": "workflow_halted_limit_reached",
        "events": [evt_limit],
        "updated_at": datetime.now(timezone.utc),
    }


def human_review_node(state: WorkflowState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Node: Reached human review boundary. Prepares state for pause and checkpointing."""
    configurable = _get_configurable(config)
    db = configurable.get("db")

    new_checkpoint_version = state.checkpoint_version + 1

    evt_review = create_event(
        workflow_id=state.run_id,
        content_id=state.content_id,
        event_type=EventType.HUMAN_REVIEW_REQUIRED,
        stage=WorkflowStage.HUMAN_REVIEW,
        revision_count=state.revision_count,
        decision=state.evaluation_result.decision.value if state.evaluation_result else None,
        explanation="Content passed automated evaluation. Human review required for publication.",
        metadata={"revisions_performed": state.revision_count},
        db=db,
    )

    evt_cp = create_event(
        workflow_id=state.run_id,
        content_id=state.content_id,
        event_type=EventType.CHECKPOINT_SAVED,
        stage=WorkflowStage.HUMAN_REVIEW,
        revision_count=state.revision_count,
        explanation=f"Workflow checkpoint v{new_checkpoint_version} persisted at human-review boundary.",
        metadata={"checkpoint_version": new_checkpoint_version},
        db=db,
    )

    return {
        "stage": WorkflowStage.HUMAN_REVIEW,
        "status": WorkflowStatus.AWAITING_HUMAN_REVIEW,
        "human_review_status": HumanReviewStatus.PENDING,
        "next_action": "await_human_approval",
        "checkpoint_version": new_checkpoint_version,
        "events": [evt_review, evt_cp],
        "updated_at": datetime.now(timezone.utc),
    }


def approve_and_complete_node(state: WorkflowState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Node: Handles human approval and transitions workflow to completion idempotently."""
    # Idempotency guard: if already completed, do not re-execute or duplicate completion
    if state.status == WorkflowStatus.COMPLETED:
        return {}

    configurable = _get_configurable(config)
    db = configurable.get("db")

    approval: ApprovalMetadata = configurable.get("approval_metadata") or (
        state.approval_metadata or ApprovalMetadata(approved_by="human_reviewer")
    )

    events: List[WorkflowEvent] = []

    # If resuming from human review pause, record resume event
    if state.status == WorkflowStatus.AWAITING_HUMAN_REVIEW or state.stage == WorkflowStage.HUMAN_REVIEW:
        evt_resume = create_event(
            workflow_id=state.run_id,
            content_id=state.content_id,
            event_type=EventType.WORKFLOW_RESUMED,
            stage=WorkflowStage.APPROVAL,
            revision_count=state.revision_count,
            explanation="Workflow execution resumed from persisted checkpoint.",
            metadata={"resumed_from_version": state.checkpoint_version},
            db=db,
        )
        events.append(evt_resume)

    # Record approval event
    evt_approve = create_event(
        workflow_id=state.run_id,
        content_id=state.content_id,
        event_type=EventType.HUMAN_APPROVED,
        stage=WorkflowStage.APPROVAL,
        revision_count=state.revision_count,
        explanation=f"Content approved by {approval.approved_by}.",
        metadata={"approved_by": approval.approved_by, "comment": approval.comment},
        db=db,
    )
    events.append(evt_approve)

    # Record completion event
    evt_complete = create_event(
        workflow_id=state.run_id,
        content_id=state.content_id,
        event_type=EventType.WORKFLOW_COMPLETED,
        stage=WorkflowStage.COMPLETE,
        revision_count=state.revision_count,
        explanation="Workflow completed successfully.",
        metadata={"final_revision_count": state.revision_count},
        db=db,
    )
    events.append(evt_complete)

    return {
        "stage": WorkflowStage.COMPLETE,
        "status": WorkflowStatus.COMPLETED,
        "human_review_status": HumanReviewStatus.APPROVED,
        "approval_metadata": approval,
        "next_action": "none",
        "events": events,
        "updated_at": datetime.now(timezone.utc),
    }
