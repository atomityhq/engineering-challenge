from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

class ContentItem(BaseModel):
    model_config = STRICT

    content_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$", description="e.g. content-001")
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20_000)
    evidence_ids: list[str] = Field(default_factory=list)


class Decision(str, Enum):
    REVISE = "revise"
    HUMAN_REVIEW = "human_review"


class EvaluationResult(BaseModel):
    model_config = STRICT

    decision: Decision
    reasons: list[str] = Field(default_factory=list, description="Why: shown to the reviser and the reviewer")


class EvaluatorScript(BaseModel):
    model_config = STRICT

    scenario: str
    responses: list[EvaluationResult] = Field(min_length=1)

class ReviewDecision(BaseModel):
    model_config = STRICT

    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1_000)


class Status(str, Enum):
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    # This is for the terminal states and it's here, nothing else happens to the run
    COMPLETED = "completed"
    REJECTED = "rejected"
    REVISION_LIMIT_REACHED = "revision_limit_reached"


TERMINAL_STATUSES = frozenset({Status.COMPLETED, Status.REJECTED, Status.REVISION_LIMIT_REACHED})

class WorkflowState(BaseModel):

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    content: ContentItem
    max_revisions: int = Field(default=2, ge=0, le=10)
    revision_count: int = 0
    evaluation_count: int = 0
    last_evaluation: EvaluationResult | None = None
    status: Status = Status.RUNNING
    review: ReviewDecision | None = None
    stop_reason: str | None = None
    checkpoint_version: int = 0