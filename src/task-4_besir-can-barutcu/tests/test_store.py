"""SQLite storage: the event log, and a run that survives closing and reopening the file."""

import pytest

from tests.helpers import CountingEvaluator, CountingReviser
from workflow.graph import approve_run, build_graph, initial_state, is_waiting_for_review, start_run
from workflow.models import load_content, load_scenario
from workflow.store import open_storage


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "data" / "workflow.db"


def open_graph(storage, scenario_id):
    """Build the graph the way a fresh process would: new fakes, same database."""
    scenario = load_scenario(scenario_id)
    evaluator, reviser = CountingEvaluator(scenario), CountingReviser(scenario)
    graph = build_graph(evaluator, reviser, storage.events, storage.checkpointer)
    return graph, evaluator, reviser


# --- event log ------------------------------------------------------------


def test_open_storage_creates_the_folder(db_path):
    with open_storage(db_path):
        pass
    assert db_path.exists()


def test_same_operation_key_is_stored_once(db_path):
    with open_storage(db_path) as storage:
        assert storage.events.record("run-1", "completed", "workflow_completed") is True
        assert storage.events.record("run-1", "completed", "workflow_completed") is False
        assert [e["event"] for e in storage.events.events("run-1")] == ["workflow_completed"]


def test_events_keep_order_and_details(db_path):
    with open_storage(db_path) as storage:
        storage.events.record("run-1", "evaluate:0", "evaluation_completed", decision="revise", revision_count=0)
        storage.events.record("run-1", "revise:1", "revision_completed", revision_count=1)
        events = storage.events.events("run-1")

    assert [e["event"] for e in events] == ["evaluation_completed", "revision_completed"]
    assert events[0]["decision"] == "revise"
    assert events[1]["revision_count"] == 1
    assert all("at" in e for e in events)


def test_events_are_kept_per_run(db_path):
    with open_storage(db_path) as storage:
        storage.events.record("run-1", "completed", "workflow_completed")
        storage.events.record("run-2", "completed", "workflow_completed")
        assert len(storage.events.events("run-1")) == 1
        assert storage.events.events("run-3") == []


def test_events_survive_reopening(db_path):
    with open_storage(db_path) as storage:
        storage.events.record("run-1", "completed", "workflow_completed")
    with open_storage(db_path) as storage:
        assert [e["event"] for e in storage.events.events("run-1")] == ["workflow_completed"]
        assert storage.events.record("run-1", "completed", "workflow_completed") is False


# --- a run across reopened storage -----------------------------------------


def test_paused_run_survives_reopening(db_path):
    with open_storage(db_path) as storage:
        graph, *_ = open_graph(storage, "one-revision")
        start_run(graph, storage.events, initial_state("run-1", load_content("content-001"), "one-revision"))

    with open_storage(db_path) as storage:
        graph, *_ = open_graph(storage, "one-revision")
        snapshot = graph.get_state({"configurable": {"thread_id": "run-1"}})

    assert is_waiting_for_review(snapshot)
    assert snapshot.values["status"] == "WAITING_FOR_REVIEW"
    assert snapshot.values["revision_count"] == 1
    assert snapshot.values["body"] == load_scenario("one-revision").revised_content[0]


def test_resume_after_reopening_does_not_rerun_work(db_path):
    with open_storage(db_path) as storage:
        graph, *_ = open_graph(storage, "one-revision")
        start_run(graph, storage.events, initial_state("run-1", load_content("content-001"), "one-revision"))

    with open_storage(db_path) as storage:
        graph, evaluator, reviser = open_graph(storage, "one-revision")
        assert approve_run(graph, storage.events, "run-1") == "completed"
        assert (evaluator.calls, reviser.calls) == (0, 0)
        names = [e["event"] for e in storage.events.events("run-1")]

    assert names == [
        "evaluation_completed",
        "revision_completed",
        "evaluation_completed",
        "human_review_required",
        "checkpoint_saved",
        "checkpoint_loaded",
        "human_approved",
        "workflow_completed",
    ]


def test_second_approval_after_reopening_changes_nothing(db_path):
    with open_storage(db_path) as storage:
        graph, *_ = open_graph(storage, "normal-pass")
        start_run(graph, storage.events, initial_state("run-1", load_content("content-001"), "normal-pass"))
        approve_run(graph, storage.events, "run-1")

    with open_storage(db_path) as storage:
        graph, *_ = open_graph(storage, "normal-pass")
        assert approve_run(graph, storage.events, "run-1") == "already_completed"
        names = [e["event"] for e in storage.events.events("run-1")]

    assert names.count("workflow_completed") == 1
