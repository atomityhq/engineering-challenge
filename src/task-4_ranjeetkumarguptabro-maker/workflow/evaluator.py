"""Deterministic evaluators and replaceable evaluator interface for the review workflow.

Enables reliable, reproducible workflow orchestration without requiring paid
LLM APIs, external accounts, or network access at runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, Tuple, Union

from workflow.models import (
    ContentItem,
    EvaluationResult,
    EvaluatorDecision,
)


class Evaluator(ABC):
    """Abstract interface for all content evaluators."""

    @abstractmethod
    def evaluate(self, content: ContentItem, revision_count: int) -> EvaluationResult:
        """Evaluate the content item and return a typed decision."""
        raise NotImplementedError


class ScriptedEvaluator(Evaluator):
    """Deterministic evaluator that returns a pre-configured sequence of decisions.
    
    Ideal for automated testing of specific execution paths (e.g. 1 revision then pass,
    or perpetual revisions triggering retry limits).
    """

    def __init__(
        self,
        decision_sequence: List[Tuple[EvaluatorDecision, str]],
        evaluator_name: str = "scripted_evaluator",
    ) -> None:
        if not decision_sequence:
            raise ValueError("Scripted decision sequence cannot be empty.")
        self.decision_sequence = decision_sequence
        self.evaluator_name = evaluator_name
        self._call_count: int = 0

    def evaluate(self, content: ContentItem, revision_count: int) -> EvaluationResult:
        # Step through the sequence; repeat the last outcome if calls exceed sequence length
        idx = min(self._call_count, len(self.decision_sequence) - 1)
        decision, reason = self.decision_sequence[idx]
        self._call_count += 1

        return EvaluationResult(
            decision=decision,
            reason=reason,
            scores={"confidence": 1.0, "step": float(self._call_count)},
            evaluator_name=self.evaluator_name,
        )

    def reset(self) -> None:
        """Reset sequence pointer."""
        self._call_count = 0


class RuleBasedEvaluator(Evaluator):
    """Deterministic evaluator inspecting mock markers in content text.
    
    Provides predictable behavior based on content markers without external services:
    - '[NEEDS_REVISION]' or '[REVISE]' -> requests revision unless revised
    - '[FAIL_LIMIT]' -> repeatedly requests revision to test retry boundaries
    - '[REJECT]' -> rejects content directly
    - Default -> passes to human review
    """

    def __init__(self, evaluator_name: str = "rule_based_evaluator") -> None:
        self.evaluator_name = evaluator_name

    def evaluate(self, content: ContentItem, revision_count: int) -> EvaluationResult:
        body = content.body.upper()
        title = content.title.upper()
        text = f"{title}\n{body}"

        if "[FAIL_LIMIT]" in text:
            return EvaluationResult(
                decision=EvaluatorDecision.REVISE,
                reason=f"Persistent revision marker present. (Revision attempt {revision_count + 1})",
                scores={"compliance": 0.4},
                evaluator_name=self.evaluator_name,
            )

        if "[REJECT]" in text:
            return EvaluationResult(
                decision=EvaluatorDecision.REJECT,
                reason="Policy violation marker '[REJECT]' found in content body.",
                scores={"compliance": 0.0},
                evaluator_name=self.evaluator_name,
            )

        if ("[NEEDS_REVISION]" in text or "[REVISE]" in text) and revision_count == 0:
            return EvaluationResult(
                decision=EvaluatorDecision.REVISE,
                reason="Initial draft requires evidence citation and formatting refinement.",
                scores={"clarity": 0.6, "evidence_grounding": 0.5},
                evaluator_name=self.evaluator_name,
            )

        return EvaluationResult(
            decision=EvaluatorDecision.HUMAN_REVIEW,
            reason="Content passed automated quality checks. Ready for human review.",
            scores={"clarity": 0.95, "evidence_grounding": 0.98},
            evaluator_name=self.evaluator_name,
        )


class FunctionalEvaluator(Evaluator):
    """Adapter allowing a simple Python function to act as an Evaluator."""

    def __init__(
        self,
        func: Callable[[ContentItem, int], EvaluationResult],
        evaluator_name: str = "functional_evaluator",
    ) -> None:
        self._func = func
        self.evaluator_name = evaluator_name

    def evaluate(self, content: ContentItem, revision_count: int) -> EvaluationResult:
        return self._func(content, revision_count)
