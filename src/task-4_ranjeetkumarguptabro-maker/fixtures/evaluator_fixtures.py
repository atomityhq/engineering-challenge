"""Deterministic scripted evaluators for testing specific workflow branching paths."""

from typing import List, Tuple

from workflow.evaluator import ScriptedEvaluator
from workflow.models import EvaluatorDecision


def get_pass_evaluator() -> ScriptedEvaluator:
    """Evaluator that immediately routes content to human review."""
    return ScriptedEvaluator(
        decision_sequence=[
            (EvaluatorDecision.HUMAN_REVIEW, "Content conforms to all validation checks. Ready for human sign-off.")
        ],
        evaluator_name="pass_evaluator",
    )


def get_one_revision_evaluator() -> ScriptedEvaluator:
    """Evaluator that requests one revision, then approves on the second evaluation."""
    return ScriptedEvaluator(
        decision_sequence=[
            (EvaluatorDecision.REVISE, "Evidence references require exact numerical bounding and source citation."),
            (EvaluatorDecision.HUMAN_REVIEW, "Revisions verified against evidence sources. Ready for human review."),
        ],
        evaluator_name="one_revision_evaluator",
    )


def get_two_revisions_then_pass_evaluator() -> ScriptedEvaluator:
    """Evaluator that requests two revisions before routing to human review."""
    return ScriptedEvaluator(
        decision_sequence=[
            (EvaluatorDecision.REVISE, "First revision requested: clarify section 1 methodology."),
            (EvaluatorDecision.REVISE, "Second revision requested: expand benchmark comparison table."),
            (EvaluatorDecision.HUMAN_REVIEW, "All revisions verified. Quality gates satisfied."),
        ],
        evaluator_name="two_revisions_then_pass_evaluator",
    )


def get_perpetual_revise_evaluator() -> ScriptedEvaluator:
    """Evaluator that continuously requests revisions to test retry limits."""
    return ScriptedEvaluator(
        decision_sequence=[
            (EvaluatorDecision.REVISE, "Revision attempt 1 requested: unverified claims."),
            (EvaluatorDecision.REVISE, "Revision attempt 2 requested: citations still missing."),
            (EvaluatorDecision.REVISE, "Revision attempt 3 requested: persistent quality gate failure."),
            (EvaluatorDecision.REVISE, "Revision attempt 4 requested: persistent quality gate failure."),
        ],
        evaluator_name="perpetual_revise_evaluator",
    )


def get_policy_reject_evaluator() -> ScriptedEvaluator:
    """Evaluator that triggers an immediate terminal rejection."""
    return ScriptedEvaluator(
        decision_sequence=[
            (EvaluatorDecision.REJECT, "Direct policy rejection: ungrounded or prohibited claims detected.")
        ],
        evaluator_name="policy_reject_evaluator",
    )
