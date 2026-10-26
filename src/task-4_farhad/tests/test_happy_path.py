"""Required check: normal pass to human review, persisted, approved, completed."""
import pytest

from tests.helpers import RUN_ID, approve, begin, names
from workflow.evaluator import FakeReviser, ScriptedEvaluator, load_content
from workflow.models import Decision, Status
from workflow.service import RunAlreadyExists, get_state, open_runtime, start_run


def test_reaches_human_review_and_persists(config):
    state, evaluator = begin(config, "pass_first_time")

    assert state.status == Status.HUMAN_REVIEW
    assert state.revision_count == 0
    assert state.checkpoint_version == 1
    assert evaluator.calls == 1
    assert names(config) == ["workflow_started", "evaluation_completed",
                             "human_review_required", "checkpoint_saved"]

    # A brand-new runtime (restart) can load the persisted state and sees the pause.
    with open_runtime(config, ScriptedEvaluator([]), FakeReviser()) as rt:
        loaded, paused = get_state(rt, RUN_ID)
    assert paused is True
    assert loaded.status == Status.HUMAN_REVIEW
    assert loaded.evaluation_result == Decision.HUMAN_REVIEW
    assert loaded.content.content_id == "content-001"
    assert loaded.run_id == RUN_ID


def test_approval_completes(config):
    begin(config, "pass_first_time")
    state, outcome = approve(config)

    assert outcome == "completed"
    assert state.status == Status.COMPLETED
    assert state.approved_by == "tester"
    assert names(config)[-3:] == ["checkpoint_loaded", "human_approved", "workflow_completed"]


def test_starting_an_existing_run_is_rejected_without_side_effects(config):
    begin(config, "pass_first_time")
    before = names(config)
    with open_runtime(config, ScriptedEvaluator(["human_review"]), FakeReviser()) as rt:
        with pytest.raises(RunAlreadyExists):
            start_run(rt, RUN_ID, load_content("content-001"))
    assert names(config) == before
