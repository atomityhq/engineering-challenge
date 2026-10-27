
from unittest.mock import Mock

import pytest

from workflow.models import (
    ContentItem,
    EvaluationDecision,
    EvaluationResult,
)
from workflow.nodes import make_evaluate_node, make_revise_node
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


def test_evaluate_node_returns_correct_update(state):
    evaluator = Mock()
    event_log = Mock()

    evaluator.evaluate.return_value = EvaluationResult(
        decision=EvaluationDecision.HUMAN_REVIEW,
        reason="Ready for review",
    )

    node = make_evaluate_node(evaluator, event_log)
    update = node(state)

    assert update["evaluation_count"] == 1
    assert update["status"] == "evaluating"
    assert update["evaluation"].decision == EvaluationDecision.HUMAN_REVIEW

    evaluator.evaluate.assert_called_once_with(
        content=state["content"],
        evaluation_index=0,
    )


def test_evaluate_node_uses_persisted_index(state):
    state["evaluation_count"] = 2

    evaluator = Mock()
    event_log = Mock()

    evaluator.evaluate.return_value = EvaluationResult(
        decision=EvaluationDecision.HUMAN_REVIEW,
        reason="Ready for review",
    )

    node = make_evaluate_node(evaluator, event_log)
    update = node(state)

    assert update["evaluation_count"] == 3

    evaluator.evaluate.assert_called_once_with(
        content=state["content"],
        evaluation_index=2,
    )


def test_evaluate_node_records_event(state):
    evaluator = Mock()
    event_log = Mock()

    evaluator.evaluate.return_value = EvaluationResult(
        decision=EvaluationDecision.REVISE,
        reason="Needs improvement",
    )

    node = make_evaluate_node(evaluator, event_log)
    node(state)

    event_log.append.assert_called_once()

    event = event_log.append.call_args.args[0]

    assert event.event_id == "workflow-001:evaluation:0"
    assert event.payload["decision"] == "revise"


def test_revise_node_updates_content_and_count(state):
    state["evaluation"] = EvaluationResult(
        decision=EvaluationDecision.REVISE,
        reason="Needs improvement",
    )

    reviser = Mock()
    event_log = Mock()

    revised_content = ContentItem(
        content_id="content-001",
        title="Example article",
        body="Improved content.",
    )

    reviser.revise.return_value = revised_content

    node = make_revise_node(
        reviser,
        event_log,
        RevisionPolicy(),
    )

    update = node(state)

    assert update["content"].body == "Improved content."
    assert update["revision_count"] == 1
    assert update["status"] == "revising"

    reviser.revise.assert_called_once_with(
        content=state["content"],
        evaluation=state["evaluation"],
        revision_number=1,
    )


def test_revise_node_records_event(state):
    state["evaluation"] = EvaluationResult(
        decision=EvaluationDecision.REVISE,
        reason="Needs improvement",
    )

    reviser = Mock()
    event_log = Mock()
    reviser.revise.return_value = state["content"]

    node = make_revise_node(
        reviser,
        event_log,
        RevisionPolicy(),
    )

    node(state)

    event_log.append.assert_called_once()

    event = event_log.append.call_args.args[0]

    assert event.event_id == "workflow-001:revision:1"
    assert event.payload["revision_number"] == 1


def test_revise_node_rejects_missing_evaluation(state):
    reviser = Mock()
    event_log = Mock()

    node = make_revise_node(
        reviser,
        event_log,
        RevisionPolicy(),
    )

    with pytest.raises(
        ValueError,
        match="Cannot revise without an evaluation",
    ):
        node(state)

    reviser.revise.assert_not_called()
    event_log.append.assert_not_called()


def test_revise_node_enforces_revision_limit(state):
    state["revision_count"] = 2
    state["evaluation"] = EvaluationResult(
        decision=EvaluationDecision.REVISE,
        reason="Still needs improvement",
    )

    reviser = Mock()
    event_log = Mock()

    node = make_revise_node(
        reviser,
        event_log,
        RevisionPolicy(),
    )

    with pytest.raises(
        ValueError,
        match="Revision limit reached",
    ):
        node(state)

    reviser.revise.assert_not_called()
    event_log.append.assert_not_called()