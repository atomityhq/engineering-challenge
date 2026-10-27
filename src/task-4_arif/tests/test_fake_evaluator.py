
import pytest

from workflow.adapters.fake_evaluator import FakeEvaluator
from workflow.models import (
    ContentItem,
    EvaluationDecision,
)
from workflow.ports.evaluator import EvaluatorPort


@pytest.fixture
def content() -> ContentItem:
    return ContentItem(
        content_id="content-001",
        title="Example",
        body="Initial content",
    )


def test_fake_evaluator_implements_port():
    evaluator: EvaluatorPort = FakeEvaluator(
        [EvaluationDecision.HUMAN_REVIEW]
    )

    assert evaluator is not None


def test_evaluation_is_deterministic(content):
    evaluator = FakeEvaluator(
        [
            EvaluationDecision.REVISE,
            EvaluationDecision.HUMAN_REVIEW,
        ]
    )

    first = evaluator.evaluate(content, 0)
    repeated = evaluator.evaluate(content, 0)
    second = evaluator.evaluate(content, 1)

    assert first == repeated
    assert first.decision == EvaluationDecision.REVISE
    assert second.decision == EvaluationDecision.HUMAN_REVIEW


def test_missing_fixture_fails_explicitly(content):
    evaluator = FakeEvaluator(
        [EvaluationDecision.REVISE]
    )

    with pytest.raises(ValueError, match="No evaluation fixture"):
        evaluator.evaluate(content, 1)


def test_empty_fixture_is_rejected():
    with pytest.raises(ValueError):
        FakeEvaluator([])