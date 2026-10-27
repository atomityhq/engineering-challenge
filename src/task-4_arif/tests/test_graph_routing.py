
import pytest

from workflow.graph import route_after_evaluation
from workflow.models import (
    ContentItem,
    EvaluationDecision,
    EvaluationResult,
)
from workflow.policies.revision import RevisionPolicy


@pytest.fixture
def state():
    return {
        "workflow_id": "workflow-001",
        "content": ContentItem(
            content_id="content-001",
            title="Example article",
            body="Initial content.",
        ),
        "evaluation": None,
        "evaluation_count": 0,
        "revision_count": 0,
        "status": "pending",
    }


@pytest.mark.parametrize(
    ("revision_count", "expected_route"),
    [
        (0, "revise"),
        (1, "revise"),
        (2, "retry_limit"),
    ],
)
def test_revision_routing(state, revision_count, expected_route):
    state["revision_count"] = revision_count
    state["evaluation"] = EvaluationResult(
        decision=EvaluationDecision.REVISE,
        reason="Needs improvement",
    )

    route = route_after_evaluation(state, RevisionPolicy())

    assert route == expected_route


@pytest.mark.parametrize("revision_count", [0, 1, 2])
def test_human_review_routing(state, revision_count):
    state["revision_count"] = revision_count
    state["evaluation"] = EvaluationResult(
        decision=EvaluationDecision.HUMAN_REVIEW,
        reason="Ready for review",
    )

    route = route_after_evaluation(state, RevisionPolicy())

    assert route == "human_review"


def test_routing_requires_evaluation(state):
    with pytest.raises(ValueError, match="without an evaluation"):
        route_after_evaluation(state, RevisionPolicy())