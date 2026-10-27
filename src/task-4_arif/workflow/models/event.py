
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class WorkflowEventType(str, Enum):
    WORKFLOW_STARTED = "workflow_started"
    CONTENT_EVALUATED = "content_evaluated"
    CONTENT_REVISED = "content_revised"
    HUMAN_REVIEW_REQUESTED = "human_review_requested"
    APPROVAL_RECORDED = "approval_recorded"
    RETRY_LIMIT_REACHED = "retry_limit_reached"
    WORKFLOW_COMPLETED = "workflow_completed"


class WorkflowEvent(BaseModel):
    """Immutable audit event for a workflow operation."""

    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
    )

    event_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    event_type: WorkflowEventType
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "workflow_id")
    @classmethod
    def reject_blank_identifiers(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Identifier cannot be blank")
        return value

    @field_validator("timestamp")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must be timezone-aware")

        if value.utcoffset().total_seconds() != 0:
            raise ValueError("Timestamp must use UTC")

        return value

    @classmethod
    def create(
        cls,
        *,
        event_id: str,
        workflow_id: str,
        event_type: WorkflowEventType,
        payload: dict[str, Any] | None = None,
    ) -> "WorkflowEvent":
        """Create an event with the current UTC timestamp."""

        return cls(
            event_id=event_id,
            workflow_id=workflow_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            payload=payload if payload is not None else {},
        )