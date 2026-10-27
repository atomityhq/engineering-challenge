
from typing import Literal, TypedDict

from workflow.models.content import ContentItem
from workflow.models.evaluation import EvaluationResult


WorkflowStatus = Literal[
    "pending",
    "evaluating",
    "revising",
    "awaiting_review",
    "completed",
    "retry_limit_reached",
]


class WorkflowState(TypedDict):
    """State persisted and restored by LangGraph."""

    workflow_id: str
    content: ContentItem
    evaluation: EvaluationResult | None
    evaluation_count: int
    revision_count: int
    status: WorkflowStatus
