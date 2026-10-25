import pytest
from langgraph.types import Command

from workflow.components import FakeReviser, ScriptedEvaluator
from workflow.graph import build_graph
from workflow.storage import open_storage
from workflow.inputs import load_content, load_evaluator_script
from workflow.models import ContentItem, EvaluationResult, ReviewDecision, Status, WorkflowState

APPROVE = {"decision": "approve", "reviewer": "ada"}


@pytest.fixture
def db(tmp_path):
    return tmp_path / "workflow.db"


def make(db, fixtures_dir, scenario):
    storage = open_storage(db)
    evaluator = ScriptedEvaluator(load_evaluator_script(fixtures_dir / "evaluator" / f"{scenario}.json"))
    reviser = FakeReviser()
    app = build_graph(evaluator, reviser, storage.events, storage.checkpointer)
    return app, evaluator, reviser, storage.events


def start(app, fixtures_dir, run_id="run-001", content="content-001.json", max_revisions=2):
    state = WorkflowState(run_id=run_id, content=load_content(fixtures_dir / "content" / content),
                          max_revisions=max_revisions)
    config = {"configurable": {"thread_id": run_id}}
    return app.invoke(state, config), config


def test_pass_pauses_at_human_review_then_completes(db, fixtures_dir):
    app, evaluator, _, events = make(db, fixtures_dir, "pass")
    out, config = start(app, fixtures_dir)

    assert "__interrupt__" in out  # paused, waiting for a human
    assert app.get_state(config).next == ("human_review",)
    assert out["status"] == Status.AWAITING_REVIEW

    final = app.invoke(Command(resume=APPROVE), config)
    assert final["status"] == Status.COMPLETED
    assert events.names("run-001") == [
        "evaluation_completed", "human_review_required", "human_approved", "workflow_completed",
    ]


def test_one_revision_then_review(db, fixtures_dir):
    app, evaluator, reviser, events = make(db, fixtures_dir, "revise_once")
    out, config = start(app, fixtures_dir)

    assert evaluator.calls == [1, 2] and reviser.calls == [1]
    assert out["revision_count"] == 1
    assert "[Revision 1] Addressed: The 18% figure needs its date range" in out["content"].body
    assert events.names("run-001") == [
        "evaluation_completed", "revision_requested", "revision_completed",
        "evaluation_completed", "human_review_required",
    ]


def test_revision_limit_stops_after_two_revisions(db, fixtures_dir):
    app, evaluator, reviser, events = make(db, fixtures_dir, "always_revise")
    out, config = start(app, fixtures_dir)

    assert evaluator.calls == [1, 2, 3]  # 3 evaluations...
    assert reviser.calls == [1, 2]  # but only 2 revisions
    assert out["status"] == Status.REVISION_LIMIT_REACHED
    assert "after 2 revision attempt(s)" in out["stop_reason"]
    assert app.get_state(config).next == ()  # terminal: nothing left to run
    assert events.names("run-001")[-1] == "revision_limit_reached"


def test_the_limit_is_configurable(db, fixtures_dir):
    app, evaluator, reviser, _ = make(db, fixtures_dir, "always_revise")
    out, _ = start(app, fixtures_dir, max_revisions=0)
    assert reviser.calls == [] and evaluator.calls == [1]
    assert out["status"] == Status.REVISION_LIMIT_REACHED


def test_resume_does_not_rerun_evaluation_or_revision(db, fixtures_dir):
    app, evaluator, reviser, events = make(db, fixtures_dir, "revise_once")
    _, config = start(app, fixtures_dir)

    app2, evaluator2, reviser2, events2 = make(db, fixtures_dir, "revise_once")
    final = app2.invoke(Command(resume=APPROVE), config)

    assert final["status"] == Status.COMPLETED
    assert evaluator2.calls == [] and reviser2.calls == []  # nothing redone
    assert events2.names("run-001").count("evaluation_completed") == 2  # still only the original two
    assert events2.names("run-001").count("human_review_required") == 1  # no duplicate from the re-run node


def test_reject_ends_without_completion(db, fixtures_dir):
    app, _, _, events = make(db, fixtures_dir, "pass")
    _, config = start(app, fixtures_dir)
    final = app.invoke(Command(resume={"decision": "reject", "reviewer": "ada", "note": "Off topic"}), config)
    assert final["status"] == Status.REJECTED
    assert "workflow_completed" not in events.names("run-001")


def test_instructions_in_content_do_not_change_routing(db, fixtures_dir):
    app, evaluator, reviser, events = make(db, fixtures_dir, "revise_once")
    out, _ = start(app, fixtures_dir, content="content-002-injection.json")

    assert evaluator.calls == [1, 2] and reviser.calls == [1]
    assert out["status"] == Status.AWAITING_REVIEW


def test_event_log_ignores_duplicates(db):
    events = open_storage(db).events
    assert events.record("run-001", "workflow_completed", key="completed") is True
    assert events.record("run-001", "workflow_completed", key="completed") is False
    assert events.names("run-001") == ["workflow_completed"]


def test_checkpoint_allowlist_covers_every_state_type(db, fixtures_dir):
    app, *_ = make(db, fixtures_dir, "revise_once")
    _, config = start(app, fixtures_dir)
    app.invoke(Command(resume=APPROVE), config)

    saved = open_storage(db).checkpointer.get_tuple(config).checkpoint["channel_values"]
    assert type(saved["content"]) is ContentItem
    assert type(saved["last_evaluation"]) is EvaluationResult
    assert type(saved["review"]) is ReviewDecision
    assert type(saved["status"]) is Status

def test_completion_is_recorded_once_even_if_complete_runs_twice(db, fixtures_dir):
    app, _, _, events = make(db, fixtures_dir, "pass")
    _, config = start(app, fixtures_dir)
    paused_checkpoint = app.get_state(config).config

    app.invoke(Command(resume=APPROVE), config)
    app.invoke(Command(resume=APPROVE), paused_checkpoint)

    assert events.names("run-001").count("workflow_completed") == 1
    assert events.names("run-001").count("human_approved") == 1