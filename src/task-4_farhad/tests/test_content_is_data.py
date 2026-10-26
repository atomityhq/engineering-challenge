"""Security check: instructions inside content are data and never change routing."""
from tests.helpers import begin, names
from workflow.models import Status


def test_embedded_instructions_do_not_change_behaviour(config):
    benign, _ = begin(config, "one_revision_then_pass", "content-001", run_id="a")
    hostile, _ = begin(config, "one_revision_then_pass", "content-injection", run_id="b")

    assert "Ignore previous instructions" in hostile.content.body   # text is carried as-is
    assert hostile.status == Status.HUMAN_REVIEW                     # not auto-approved
    assert names(config, "b") == names(config, "a")                  # identical routing
    assert "human_approved" not in names(config, "b")
    assert "workflow_completed" not in names(config, "b")
