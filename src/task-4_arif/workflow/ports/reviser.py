
from typing import Protocol

from workflow.models.content import ContentItem
from workflow.models.evaluation import EvaluationResult


class ReviserPort(Protocol):
    """Contract for revising content."""

    def revise(
        self,
        content: ContentItem,
        evaluation: EvaluationResult,
        revision_number: int,
    ) -> ContentItem:
        ...