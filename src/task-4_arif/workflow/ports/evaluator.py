
from typing import Protocol

from workflow.models.content import ContentItem
from workflow.models.evaluation import EvaluationResult


class EvaluatorPort(Protocol):
    """Contract for evaluating content."""

    def evaluate(
        self,
        content: ContentItem,
        evaluation_index: int,
    ) -> EvaluationResult:
        ...
