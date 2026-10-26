"""Required check: approving an already-completed workflow is a safe no-op."""
import pytest

from tests.helpers import RUN_ID, approve, begin, names
from workflow.events import SqliteEventLog
from workflow.models import Status
from workflow.service import UnknownRun, open_runtime, resume_run
from workflow.evaluator import FakeReviser, ScriptedEvaluator


def test_duplicate_approval_does_not_duplicate_completion(config):
    begin(config, "pass_first_time")
    state, outcome = approve(config)
    assert outcome == "completed"
    snapshot = names(config)

    for _ in range(3):
        state, outcome = approve(config)
        assert outcome == "already_completed"
        assert state.status == Status.COMPLETED

    all_names = names(config)
    assert all_names.count("workflow_completed") == 1
    assert all_names.count("human_approved") == 1
    # Only a distinct, clearly-named audit event is added for each ignored attempt.
    assert all_names[len(snapshot):] == ["duplicate_approval_ignored"] * 3


def test_event_log_backstop_blocks_second_completion(tmp_path):
    log = SqliteEventLog(tmp_path / "e.db")
    assert log.append_once("r", "workflow_completed") is True
    assert log.append_once("r", "workflow_completed") is False
    assert [e.event for e in log.list("r")] == ["workflow_completed"]
    # Other runs are independent.
    assert log.append_once("other", "workflow_completed") is True


def test_unknown_run_is_reported(config):
    with open_runtime(config, ScriptedEvaluator([]), FakeReviser()) as rt:
        with pytest.raises(UnknownRun):
            resume_run(rt, "does-not-exist")
