
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    """Content that will be evaluated by the workflow."""

    content_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class WorkflowInput(BaseModel):
    """Initial data required to start a workflow."""

    workflow_id: str = Field(min_length=1)
    content: ContentItem


class EvaluationResult(BaseModel):
    """Result returned by the content evaluator."""

    decision: Literal["pass", "revise", "human_review"]
    feedback: str
    score: float | None = Field(default=None, ge=0, le=1)


class WorkflowOutput(BaseModel):
    """Final or intermediate result returned by the workflow."""

    workflow_id: str
    status: Literal[
        "awaiting_human_review",
        "completed",
        "revision_limit_reached",
    ]
    content: ContentItem
    revision_count: int = Field(ge=0, le=2)
    evaluation: EvaluationResult


class EventRecord(BaseModel):
    """An event recorded during workflow execution."""

    workflow_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    details: dict = Field(default_factory=dict)
