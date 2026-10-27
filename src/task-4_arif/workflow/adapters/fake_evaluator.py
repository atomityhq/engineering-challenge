
from collections.abc import Sequence

from workflow.models.content import ContentItem
from workflow.models.evaluation import (
    EvaluationDecision,
    EvaluationResult,
)


class FakeEvaluator:
    """Deterministic evaluator for local execution and tests."""

    def __init__(
        self,
        decisions: Sequence[EvaluationDecision],
    ) -> None:
        if not decisions:
            raise ValueError("At least one decision is required")

        self._decisions = tuple(decisions)

    def evaluate(
        self,
        content: ContentItem,
        evaluation_index: int,
    ) -> EvaluationResult:
        if type(evaluation_index) is not int or evaluation_index < 0:
            raise ValueError(
                "evaluation_index must be a non-negative integer"
            )

        if evaluation_index >= len(self._decisions):
            raise ValueError(
                f"No evaluation fixture for index {evaluation_index}"
            )

        decision = self._decisions[evaluation_index]

        return EvaluationResult(
            decision=decision,
            reason=(
                f"Deterministic evaluation "
                f"{evaluation_index + 1}: {decision.value}"
            ),
        )
