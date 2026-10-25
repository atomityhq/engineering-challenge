"""Data contracts, validated models, and enumerations for the Resumable Review Workflow.

Defines typed Pydantic models for content items, evaluator decisions,
workflow states, revision history, approval metadata, and audit events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import operator
import re
from typing import Annotated, Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field, field_validator, model_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowStatus(str, Enum):
    """Lifecycle status of the workflow."""

    PENDING = "pending"
    EVALUATING = "evaluating"
    REVISING = "revising"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    APPROVED = "approved"
    COMPLETED = "completed"
    REVISION_LIMIT_REACHED = "revision_limit_reached"
    REJECTED = "rejected"
    FAILED = "failed"


class WorkflowStage(str, Enum):
    """Current processing stage inside the LangGraph workflow."""

    INITIAL = "initial"
    EVALUATE = "evaluate"
    REVISE = "revise"
    HUMAN_REVIEW = "human_review"
    APPROVAL = "approval"
    COMPLETE = "complete"
    REVISION_LIMIT_REACHED = "revision_limit_reached"
    REJECTED = "rejected"


class HumanReviewStatus(str, Enum):
    """Human review decision status."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EvaluatorDecision(str, Enum):
    """Possible outcomes from an evaluation step."""

    REVISE = "revise"
    HUMAN_REVIEW = "human_review"
    REJECT = "reject"


class EventType(str, Enum):
    """Types of inspectable lifecycle events."""

    WORKFLOW_STARTED = "workflow_started"
    EVALUATION_COMPLETED = "evaluation_completed"
    REVISION_REQUESTED = "revision_requested"
    REVISION_COMPLETED = "revision_completed"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    CHECKPOINT_SAVED = "checkpoint_saved"
    WORKFLOW_RESUMED = "workflow_resumed"
    HUMAN_APPROVED = "human_approved"
    WORKFLOW_COMPLETED = "workflow_completed"
    REVISION_LIMIT_REACHED = "revision_limit_reached"
    WORKFLOW_REJECTED = "workflow_rejected"


class ContentItem(BaseModel):
    """Validated content item passed to the review workflow."""

    id: str = Field(..., description="Unique identifier for the content item.")
    title: str = Field(..., description="Title of the content.")
    body: str = Field(..., description="Body text of the content.")
    version: int = Field(default=1, ge=1, description="Content version number.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata.")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Content ID cannot be empty or whitespace only.")
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", trimmed):
            raise ValueError(f"Content ID '{trimmed}' contains invalid characters. Use alphanumeric, dash, dot, or underscore.")
        return trimmed

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Content title cannot be empty or whitespace only.")
        return trimmed

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Content body cannot be empty or whitespace only.")
        return trimmed


class EvaluationResult(BaseModel):
    """Result returned by an evaluator for a content item."""

    decision: EvaluatorDecision = Field(..., description="The evaluator's routing decision.")
    reason: str = Field(..., min_length=1, description="Explanation for the decision.")
    scores: Dict[str, float] = Field(default_factory=dict, description="Optional metric scores.")
    evaluator_name: str = Field(default="mock_evaluator", description="Name of the evaluator component.")
    evaluated_at: datetime = Field(default_factory=_utc_now, description="Timestamp of evaluation.")


class RevisionRecord(BaseModel):
    """Record of a revision performed on the content."""

    revision_number: int = Field(..., ge=1, description="Sequential revision number.")
    reason: str = Field(..., description="Reason the revision was performed.")
    previous_body: str = Field(..., description="Content body prior to revision.")
    revised_body: str = Field(..., description="Content body after revision.")
    timestamp: datetime = Field(default_factory=_utc_now, description="When revision was executed.")


class ApprovalMetadata(BaseModel):
    """Metadata recorded when a human reviewer approves a workflow."""

    approved_by: str = Field(default="human_reviewer", description="Identifier of the reviewer.")
    comment: Optional[str] = Field(default=None, description="Optional reviewer notes or feedback.")
    approved_at: datetime = Field(default_factory=_utc_now, description="Timestamp of approval.")


class WorkflowEvent(BaseModel):
    """Immutable audit event recorded during workflow execution."""

    event_id: str = Field(
        default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}",
        description="Unique identifier for the event."
    )
    workflow_id: str = Field(..., description="Associated workflow run identifier.")
    content_id: str = Field(..., description="Associated content item identifier.")
    event_type: EventType = Field(..., description="Type of event.")
    stage: WorkflowStage = Field(..., description="Stage where the event was recorded.")
    revision_count: int = Field(default=0, ge=0, description="Revision count at time of event.")
    decision: Optional[str] = Field(default=None, description="Associated evaluator decision if any.")
    explanation: str = Field(..., description="Human-readable explanation of what happened.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Structured contextual metadata.")
    timestamp: datetime = Field(default_factory=_utc_now, description="UTC timestamp of the event.")


class WorkflowState(BaseModel):
    """Typed state for the LangGraph review workflow.
    
    Contains all context required to execute, persist, interrupt,
    resume, and audit the workflow without losing state.
    """

    run_id: str = Field(..., description="Unique run/thread ID.")
    content_id: str = Field(..., description="Content item identifier.")
    content: ContentItem = Field(..., description="The content item being processed.")
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING, description="Overall workflow status.")
    stage: WorkflowStage = Field(default=WorkflowStage.INITIAL, description="Current workflow stage.")
    revision_count: int = Field(default=0, ge=0, description="Number of revisions completed.")
    evaluation_count: int = Field(default=0, ge=0, description="Number of evaluations performed.")
    max_revisions: int = Field(default=2, ge=0, description="Maximum permitted revisions before stopping.")
    human_review_status: HumanReviewStatus = Field(
        default=HumanReviewStatus.NOT_REQUIRED,
        description="Human review decision state."
    )
    evaluation_result: Optional[EvaluationResult] = Field(
        default=None,
        description="Most recent evaluation outcome."
    )
    revision_history: List[RevisionRecord] = Field(
        default_factory=list,
        description="Chronological log of revisions."
    )
    approval_metadata: Optional[ApprovalMetadata] = Field(
        default=None,
        description="Metadata when approved."
    )
    checkpoint_version: int = Field(default=0, ge=0, description="Monotonically increasing checkpoint version.")
    next_action: Optional[str] = Field(
        default=None,
        description="Information indicating the next step required (e.g. 'await_approval')."
    )
    created_at: datetime = Field(default_factory=_utc_now, description="Workflow creation timestamp.")
    updated_at: datetime = Field(default_factory=_utc_now, description="Last update timestamp.")
    events: Annotated[List[WorkflowEvent], operator.add] = Field(
        default_factory=list,
        description="Appended audit event log."
    )

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Run ID cannot be empty.")
        return trimmed

    @model_validator(mode="after")
    def validate_consistency(self) -> WorkflowState:
        if self.content.id != self.content_id:
            raise ValueError(
                f"Mismatch between content_id ('{self.content_id}') and content.id ('{self.content.id}')."
            )
        return self
