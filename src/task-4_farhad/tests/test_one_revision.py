"""Required check: one revision, then pass to human review, persist, resume, complete."""
from tests.helpers import approve, begin, names
from workflow.models import Status


def test_one_revision_then_pass(config):
    state, evaluator = begin(config, "one_revision_then_pass")

    assert state.status == Status.HUMAN_REVIEW
    assert state.revision_count == 1
    assert state.content.body.endswith("[revised 1]")
    assert evaluator.calls == 2

    final, outcome = approve(config)
    assert outcome == "completed" and final.status == Status.COMPLETED

    assert names(config) == [
        "workflow_started",
        "evaluation_completed",   # decision: revise
        "revision_requested",
        "revision_completed",
        "evaluation_completed",   # decision: human_review
        "human_review_required",
        "checkpoint_saved",
        "checkpoint_loaded",
        "human_approved",
        "workflow_completed",
    ]
