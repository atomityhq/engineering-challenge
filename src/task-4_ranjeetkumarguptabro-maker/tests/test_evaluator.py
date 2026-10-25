"""Tests for deterministic evaluator components and interfaces."""

import pytest

from workflow.evaluator import (
    Evaluator,
    FunctionalEvaluator,
    RuleBasedEvaluator,
    ScriptedEvaluator,
)
from workflow.models import (
    ContentItem,
    EvaluationResult,
    EvaluatorDecision,
)


def test_scripted_evaluator_sequence() -> None:
    """Verify scripted evaluator returns sequence and caps at final element."""
    evaluator = ScriptedEvaluator([
        (EvaluatorDecision.REVISE, "Reason 1"),
        (EvaluatorDecision.HUMAN_REVIEW, "Reason 2"),
    ])
    item = ContentItem(id="test-1", title="Title", body="Body")

    res1 = evaluator.evaluate(item, 0)
    assert res1.decision == EvaluatorDecision.REVISE
    assert res1.reason == "Reason 1"

    res2 = evaluator.evaluate(item, 1)
    assert res2.decision == EvaluatorDecision.HUMAN_REVIEW
    assert res2.reason == "Reason 2"

    # Beyond sequence length: repeats last
    res3 = evaluator.evaluate(item, 2)
    assert res3.decision == EvaluatorDecision.HUMAN_REVIEW

    # Reset
    evaluator.reset()
    assert evaluator.evaluate(item, 0).decision == EvaluatorDecision.REVISE


def test_rule_based_evaluator_markers() -> None:
    """Verify rule-based evaluator matches markers in body."""
    evaluator = RuleBasedEvaluator()

    # Pass item
    item_pass = ContentItem(id="pass", title="Clean", body="Everything verified.")
    assert evaluator.evaluate(item_pass, 0).decision == EvaluatorDecision.HUMAN_REVIEW

    # Needs revision item
    item_rev = ContentItem(id="rev", title="Draft", body="Check this. [NEEDS_REVISION]")
    assert evaluator.evaluate(item_rev, 0).decision == EvaluatorDecision.REVISE
    # After revision (revision_count == 1), marker check passes
    assert evaluator.evaluate(item_rev, 1).decision == EvaluatorDecision.HUMAN_REVIEW

    # Perpetual fail item
    item_fail = ContentItem(id="fail", title="Bad", body="Flawed study. [FAIL_LIMIT]")
    assert evaluator.evaluate(item_fail, 0).decision == EvaluatorDecision.REVISE
    assert evaluator.evaluate(item_fail, 2).decision == EvaluatorDecision.REVISE

    # Policy rejection item
    item_reject = ContentItem(id="reject", title="Banned", body="Illegal claims. [REJECT]")
    assert evaluator.evaluate(item_reject, 0).decision == EvaluatorDecision.REJECT


def test_functional_evaluator_adapter() -> None:
    """Verify functional evaluator adapter wraps callables."""
    def custom_func(content: ContentItem, rev_count: int) -> EvaluationResult:
        return EvaluationResult(
            decision=EvaluatorDecision.HUMAN_REVIEW,
            reason=f"Custom check passed for {content.id}",
        )

    evaluator = FunctionalEvaluator(custom_func)
    item = ContentItem(id="item-custom", title="Title", body="Body")
    result = evaluator.evaluate(item, 0)
    assert result.decision == EvaluatorDecision.HUMAN_REVIEW
    assert "Custom check passed for item-custom" in result.reason
