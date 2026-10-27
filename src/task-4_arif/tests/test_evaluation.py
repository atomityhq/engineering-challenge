
import pytest
from pydantic import ValidationError

from workflow.models import EvaluationDecision, EvaluationResult


@pytest.mark.parametrize(
    "decision",
    [
        EvaluationDecision.REVISE,
        EvaluationDecision.HUMAN_REVIEW,
    ],
)
def test_valid_evaluation_decisions(decision):
    result = EvaluationResult(
        decision=decision,
        reason="Deterministic evaluation result",
    )

    assert result.decision == decision


@pytest.mark.parametrize("invalid_reason", ["", "   "])
def test_reject_blank_reason(invalid_reason):
    with pytest.raises(ValidationError):
        EvaluationResult(
            decision=EvaluationDecision.REVISE,
            reason=invalid_reason,
        )


def test_reject_invalid_decision():
    with pytest.raises(ValidationError):
        EvaluationResult(
            decision="approve",
            reason="Unsupported decision",
        )


def test_reject_raw_string_in_strict_python_mode():
    with pytest.raises(ValidationError):
        EvaluationResult(
            decision="revise",
            reason="Requires revision",
        )


def test_reject_missing_reason():
    with pytest.raises(ValidationError):
        EvaluationResult(
            decision=EvaluationDecision.REVISE,
        )


def test_reject_unexpected_fields():
    with pytest.raises(ValidationError):
        EvaluationResult(
            decision=EvaluationDecision.REVISE,
            reason="Requires revision",
            score=90,
        )


def test_evaluation_result_is_immutable():
    result = EvaluationResult(
        decision=EvaluationDecision.REVISE,
        reason="Requires revision",
    )

    with pytest.raises(ValidationError):
        result.reason = "Changed reason"


def test_json_round_trip():
    original = EvaluationResult(
        decision=EvaluationDecision.HUMAN_REVIEW,
        reason="Ready for human review",
    )

    restored = EvaluationResult.model_validate_json(
        original.model_dump_json()
    )

    assert restored == original
