from collections.abc import Sequence

from models import ContentInput, EvaluationDecision


class FakeEvaluator:
    def __init__(self, decisions: Sequence[EvaluationDecision]) -> None:
        for decision in decisions:
            if decision not in ("revise", "human_review"):
                raise ValueError(f"invalid evaluation decision: {decision!r}")
        self._decisions = tuple(decisions)

    def evaluate(
        self,
        content: ContentInput,
        evaluation_index: int,
    ) -> EvaluationDecision:
        if evaluation_index < 0 or evaluation_index >= len(self._decisions):
            raise RuntimeError("evaluator response sequence is exhausted")
        return self._decisions[evaluation_index]
