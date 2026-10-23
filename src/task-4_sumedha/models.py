from typing import Literal, TypedDict

from pydantic import BaseModel, field_validator


EvaluationDecision = Literal["revise", "human_review"]
WorkflowStatus = Literal[
    "pending",
    "evaluating",
    "revising",
    "awaiting_human_review",
    "retry_limit_reached",
    "completed",
]


class ContentInput(BaseModel):
    content_id: str
    text: str

    @field_validator("content_id", "text")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class WorkflowState(TypedDict):
    run_id: str
    content: ContentInput
    evaluation_decision: EvaluationDecision | None
    evaluation_reason: str | None
    revision_count: int
    max_revisions: int
    status: WorkflowStatus
    human_approved: bool | None
    event_log: list[str]
