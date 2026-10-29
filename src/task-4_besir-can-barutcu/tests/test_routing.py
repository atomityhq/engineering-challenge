"""Routing through the graph. Every test runs twice: in memory and on a SQLite file."""

from contextlib import ExitStack
from dataclasses import dataclass

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from tests.helpers import CountingEvaluator, CountingReviser
from workflow.graph import (
    NotWaitingForReviewError,
    RunExistsError,
    UnknownRunError,
    approve_run,
    build_graph,
    initial_state,
    is_waiting_for_review,
    start_run,
)
from workflow.models import load_content, load_scenario
from workflow.store import EventLog, InMemoryEventLog, open_storage


@dataclass
class Harness:
    graph: object
    events: EventLog
    evaluator: CountingEvaluator
    reviser: CountingReviser
    scenario_id: str

    def start(self, run_id="run-1", content_id="content-001", scenario_id=None, max_revisions=2):
        state = initial_state(run_id, load_content(content_id), scenario_id or self.scenario_id, max_revisions)
        return start_run(self.graph, self.events, state)

    def approve(self, run_id="run-1"):
        return approve_run(self.graph, self.events, run_id)

    def names(self, run_id="run-1"):
        return [e["event"] for e in self.events.events(run_id)]

    def state(self, run_id="run-1"):
        return self.graph.get_state({"configurable": {"thread_id": run_id}})


@pytest.fixture(params=["memory", "sqlite"])
def harness(request, tmp_path):
    with ExitStack() as stack:

        def make(scenario_id):
            if request.param == "memory":
                checkpointer, events = InMemorySaver(), InMemoryEventLog()
            else:
                storage = stack.enter_context(open_storage(tmp_path / "workflow.db"))
                checkpointer, events = storage.checkpointer, storage.events
            scenario = load_scenario(scenario_id)
            evaluator = CountingEvaluator(scenario)
            reviser = CountingReviser(scenario)
            graph = build_graph(evaluator, reviser, events, checkpointer)
            return Harness(graph, events, evaluator, reviser, scenario_id)

        yield make


# --- required checks -------------------------------------------------------


def test_normal_pass_pauses_at_review_then_completes(harness):
    h = harness("normal-pass")

    snapshot = h.start()
    assert snapshot.values["status"] == "WAITING_FOR_REVIEW"
    assert is_waiting_for_review(snapshot)
    assert h.names() == ["evaluation_completed", "human_review_required", "checkpoint_saved"]

    assert h.approve() == "completed"
    assert h.state().values["status"] == "COMPLETED"
    assert h.state().next == ()
    assert h.names()[-3:] == ["checkpoint_loaded", "human_approved", "workflow_completed"]


def test_one_revision_then_pass(harness):
    h = harness("one-revision")

    snapshot = h.start()
    assert snapshot.values["revision_count"] == 1
    assert snapshot.values["body"] == load_scenario("one-revision").revised_content[0]
    h.approve()

    assert h.names() == [
        "evaluation_completed",
        "revision_completed",
        "evaluation_completed",
        "human_review_required",
        "checkpoint_saved",
        "checkpoint_loaded",
        "human_approved",
        "workflow_completed",
    ]
    decisions = [e["decision"] for e in h.events.events("run-1") if e["event"] == "evaluation_completed"]
    assert decisions == ["revise", "human_review"]


def test_revision_limit_stops_after_two_revisions(harness):
    h = harness("revision-limit")

    snapshot = h.start()
    assert snapshot.values["status"] == "REVISION_LIMIT_REACHED"
    assert snapshot.values["revision_count"] == 2
    assert snapshot.next == ()
    assert h.evaluator.calls == 3
    assert h.reviser.calls == 2
    assert h.names() == [
        "evaluation_completed",
        "revision_completed",
        "evaluation_completed",
        "revision_completed",
        "evaluation_completed",
        "revision_limit_reached",
    ]
    assert h.events.events("run-1")[-1]["reason"] == "max_revisions_reached"


@pytest.mark.parametrize("limit, revisions", [(0, 0), (1, 1)])
def test_revision_limit_is_configurable(harness, limit, revisions):
    h = harness("revision-limit")
    snapshot = h.start(max_revisions=limit)
    assert snapshot.values["status"] == "REVISION_LIMIT_REACHED"
    assert snapshot.values["revision_count"] == revisions
    assert h.reviser.calls == revisions


def test_approval_does_not_rerun_finished_work(harness):
    h = harness("one-revision")
    h.start()
    calls_before = (h.evaluator.calls, h.reviser.calls)

    h.approve()

    assert (h.evaluator.calls, h.reviser.calls) == calls_before == (2, 1)


def test_duplicate_approval_does_not_complete_twice(harness):
    h = harness("normal-pass")
    h.start()

    assert h.approve() == "completed"
    assert h.approve() == "already_completed"
    assert h.names().count("workflow_completed") == 1
    assert h.names().count("human_approved") == 1


# --- guards ---------------------------------------------------------------


def test_limit_reached_run_cannot_be_approved(harness):
    h = harness("revision-limit")
    h.start()
    with pytest.raises(NotWaitingForReviewError):
        h.approve()
    assert "workflow_completed" not in h.names()


def test_unknown_run_cannot_be_approved(harness):
    with pytest.raises(UnknownRunError):
        harness("normal-pass").approve("no-such-run")


def test_run_id_cannot_be_reused(harness):
    h = harness("normal-pass")
    h.start()
    with pytest.raises(RunExistsError):
        h.start()


def test_injected_instructions_do_not_skip_review(harness):
    h = harness("normal-pass")
    snapshot = h.start(content_id="content-injection")
    assert snapshot.values["status"] == "WAITING_FOR_REVIEW"
    assert "workflow_completed" not in h.names()
    assert "human_approved" not in h.names()
