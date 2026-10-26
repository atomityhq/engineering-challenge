"""Required check: an evaluator that always asks for revision stops at the limit."""
import dataclasses

import pytest

from tests.helpers import RUN_ID, approve, begin, events, names
from workflow.config import WorkflowConfig
from workflow.graph import make_router
from workflow.models import ContentItem, Decision, Status, WorkflowState


def test_stops_after_two_revisions(config):
    state, evaluator = begin(config, "always_revise")

    assert state.status == Status.STOPPED
    assert state.revision_count == 2
    assert "maximum revision attempts reached" in state.stop_reason
    assert evaluator.calls == 3          # evaluate, (revise, evaluate) x2 -> no 4th call
    assert names(config) == [
        "workflow_started",
        "evaluation_completed", "revision_requested", "revision_completed",
        "evaluation_completed", "revision_requested", "revision_completed",
        "evaluation_completed", "max_revisions_reached",
    ]
    assert "maximum revision attempts reached" in events(config)[-1].detail


@pytest.mark.parametrize("limit", [0, 1, 2])
def test_limit_is_configurable(config, limit):
    cfg = dataclasses.replace(config, max_revisions=limit)
    state, evaluator = begin(cfg, "always_revise")

    assert state.status == Status.STOPPED
    assert state.revision_count == limit
    assert evaluator.calls == limit + 1
    assert names(cfg).count("revision_requested") == limit


def test_stopped_run_cannot_be_approved(config):
    begin(config, "always_revise")
    state, outcome = approve(config)
    assert outcome == "stopped"
    assert state.status == Status.STOPPED
    assert "workflow_completed" not in names(config)


def test_router_conditions():
    route = make_router(WorkflowConfig(max_revisions=2))
    content = ContentItem(content_id="c", title="t", body="b")

    def state(decision, count):
        return WorkflowState(run_id="r", content=content, evaluation_result=decision,
                             revision_count=count)

    assert route(state(Decision.REVISE, 0)) == "revise"
    assert route(state(Decision.REVISE, 1)) == "revise"
    assert route(state(Decision.REVISE, 2)) == "stop"
    assert route(state(Decision.HUMAN_REVIEW, 2)) == "human_review"
    with pytest.raises(ValueError):
        route(state(None, 0))
