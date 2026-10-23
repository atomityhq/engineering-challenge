"""Typed contracts for workflow input, evaluator output, human decisions and the exported state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"

Status = Literal[
    "evaluating",
    "revising",
    "awaiting_review",
    "completed",
    "rejected",
    "stopped_revision_limit",
]
TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "rejected", "stopped_revision_limit"})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ContentItem(_Strict):
    """The mock content item that enters the workflow. Treated as data only."""

    content_id: str = Field(pattern=ID_PATTERN)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


class EvaluationResult(_Strict):
    """What an evaluator must return. Anything else is rejected before routing."""

    decision: Literal["revise", "human_review"]
    feedback: str = Field(min_length=1)


class EvaluatorScript(_Strict):
    """Fixture of deterministic evaluator responses, consumed in order (last one repeats)."""

    responses: list[EvaluationResult] = Field(min_length=1)


class HumanDecision(_Strict):
    decision: Literal["approve", "reject"]
    reviewer: str = Field(default="cli", min_length=1)
    note: str | None = None


class WorkflowConfig(_Strict):
    max_revisions: int = Field(default=2, ge=0, le=10)


class Event(_Strict):
    seq: int
    event: str
    revision_count: int
    detail: dict = Field(default_factory=dict)


class WorkflowSnapshot(_Strict):
    """Human-readable export of the persisted state (the SQLite checkpoint is the source of truth)."""

    run_id: str
    content_id: str
    status: Status
    revision_count: int
    max_revisions: int
    evaluation_result: EvaluationResult | None
    review: HumanDecision | None
    content: ContentItem
    evaluator_ref: str
    next_nodes: list[str]
    checkpoint_id: str | None
    events: list[Event]
