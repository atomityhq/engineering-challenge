"""One test group per required check in the Task 4 spec."""

import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from review_workflow.models import HumanDecision, WorkflowConfig
from review_workflow.service import ReviewWorkflow, RunAlreadyExists, WorkflowInputError

from .conftest import CONTENT, ROOT, CountingEvaluatorFactory, event_names, evaluator_ref

APPROVE = HumanDecision(decision="approve", reviewer="tester")


# --- Normal pass to human review --------------------------------------------------------


def test_normal_pass_pauses_persists_and_completes(wf, db):
    snap = wf.start(CONTENT, evaluator_ref("pass"), run_id="run-pass")
    assert snap.status == "awaiting_review"
    assert snap.next_nodes == ["await_review"]
    assert event_names(snap) == ["evaluation_completed", "human_review_required"]

    # Persisted: a separate connection to the same SQLite file sees the paused run.
    with ReviewWorkflow(db) as other:
        saved = other.snapshot("run-pass")
    assert saved.status == "awaiting_review"
    assert saved.content.content_id == "content-001"
    assert saved.evaluation_result.decision == "human_review"
    assert saved.revision_count == 0

    outcome = wf.resume("run-pass", APPROVE)
    assert outcome.action == "resumed"
    assert outcome.snapshot.status == "completed"
    assert event_names(outcome.snapshot) == [
        "evaluation_completed",
        "human_review_required",
        "human_approved",
        "workflow_completed",
    ]


def test_reviewer_can_reject(wf):
    wf.start(CONTENT, evaluator_ref("pass"), run_id="run-reject")
    snap = wf.resume("run-reject", HumanDecision(decision="reject", note="wrong angle")).snapshot
    assert snap.status == "rejected"
    assert event_names(snap)[-2:] == ["human_rejected", "workflow_rejected"]
    assert "workflow_completed" not in event_names(snap)


# --- One revision then pass -------------------------------------------------------------


def test_one_revision_then_pass(wf, counter):
    snap = wf.start(CONTENT, evaluator_ref("one-revision"), run_id="run-rev")
    assert snap.status == "awaiting_review"
    assert snap.revision_count == 1
    assert "[revision 1] addressed: Add the effective date" in snap.content.body

    snap = wf.resume("run-rev", APPROVE).snapshot
    assert [(e.event, e.revision_count) for e in snap.events] == [
        ("evaluation_completed", 0),
        ("revision_completed", 1),
        ("evaluation_completed", 1),
        ("human_review_required", 1),
        ("human_approved", 1),
        ("workflow_completed", 1),
    ]
    assert [e.seq for e in snap.events] == list(range(6))
    assert counter.calls == 2


# --- Retry limit ------------------------------------------------------------------------


def test_retry_limit_stops_after_two_revisions(wf, counter):
    snap = wf.start(CONTENT, evaluator_ref("always-revise"), run_id="run-limit")
    assert snap.status == "stopped_revision_limit"
    assert snap.next_nodes == []  # terminal: nothing left to run
    assert snap.revision_count == 2
    assert event_names(snap) == [
        "evaluation_completed",
        "revision_completed",
        "evaluation_completed",
        "revision_completed",
        "evaluation_completed",
        "revision_limit_reached",
        "workflow_stopped",
    ]
    assert snap.events[-2].detail == {"max_revisions": 2}
    assert counter.calls == 3

    # A stopped run cannot be pushed to completion by an approval.
    outcome = wf.resume("run-limit", APPROVE)
    assert outcome.action == "already_finished"
    assert "workflow_completed" not in event_names(outcome.snapshot)


@pytest.mark.parametrize("limit", [0, 1, 3])
def test_retry_limit_is_configurable(wf, limit):
    snap = wf.start(CONTENT, evaluator_ref("always-revise"), run_id=f"run-{limit}", config=WorkflowConfig(max_revisions=limit))
    assert snap.status == "stopped_revision_limit"
    assert snap.revision_count == limit
    assert event_names(snap).count("revision_completed") == limit


# --- Restart at review ------------------------------------------------------------------


def _cli(db, out, *args):
    return subprocess.run(
        [sys.executable, "-m", "review_workflow", "--db", str(db), "--out", str(out), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )


def test_restart_at_review_in_a_new_process(tmp_path):
    db, out = tmp_path / "cp.sqlite", tmp_path / "runs"
    first = _cli(db, out, "run", "--content", "fixtures/content/content-001.json",
                 "--evaluator", "fixtures/evaluator/one-revision.json", "--run-id", "run-restart")
    assert first.returncode == 0, first.stderr
    assert "Workflow paused." in first.stdout
    # First process has exited; only the SQLite file connects the two runs.

    second = _cli(db, out, "approve", "run-restart")
    assert second.returncode == 0, second.stderr
    assert "Current stage: awaiting_review" in second.stdout
    assert "Evaluation completed" not in second.stdout
    assert "Revision attempt" not in second.stdout
    assert "Workflow completed." in second.stdout

    events = json.loads((out / "run-restart" / "events.json").read_text())
    assert [e["event"] for e in events] == [
        "evaluation_completed", "revision_completed", "evaluation_completed",
        "human_review_required", "human_approved", "workflow_completed",
    ]


def test_resume_does_not_call_evaluator_again(db):
    with ReviewWorkflow(db, evaluator_factory=CountingEvaluatorFactory()) as first:
        first.start(CONTENT, evaluator_ref("one-revision"), run_id="run-spy")

    fresh = CountingEvaluatorFactory()  # simulates a restarted process with new objects
    with ReviewWorkflow(db, evaluator_factory=fresh) as second:
        snap = second.resume("run-spy", APPROVE).snapshot
    assert fresh.calls == 0
    assert snap.status == "completed"
    assert event_names(snap).count("evaluation_completed") == 2
    assert event_names(snap).count("revision_completed") == 1


def test_resume_after_crash_mid_run_continues_from_last_checkpoint(db):
    class Crashing:
        def evaluate(self, content, revision_count):
            if revision_count == 1:
                raise RuntimeError("process killed during second evaluation")
            return {"decision": "revise", "feedback": "Add the effective date."}

    with ReviewWorkflow(db, evaluator_factory=lambda ref: Crashing()) as first:
        with pytest.raises(RuntimeError):
            first.start(CONTENT, evaluator_ref("one-revision"), run_id="run-crash")
        assert first.snapshot("run-crash").next_nodes == ["evaluate"]

    counter = CountingEvaluatorFactory()
    with ReviewWorkflow(db, evaluator_factory=counter) as second:
        snap = second.resume("run-crash").snapshot
    assert snap.status == "awaiting_review"
    assert counter.calls == 1  # only the evaluation that never finished; the revision is not redone
    assert event_names(snap).count("revision_completed") == 1


# --- Duplicate approval -----------------------------------------------------------------


def test_duplicate_approval_is_idempotent(wf):
    wf.start(CONTENT, evaluator_ref("pass"), run_id="run-dup")
    done = wf.resume("run-dup", APPROVE).snapshot

    again = wf.resume("run-dup", APPROVE)
    assert again.action == "already_finished"
    assert again.snapshot.events == done.events
    assert again.snapshot.checkpoint_id == done.checkpoint_id  # no new checkpoint written
    assert event_names(again.snapshot).count("workflow_completed") == 1
    assert event_names(again.snapshot).count("human_approved") == 1


def test_duplicate_approval_via_cli(tmp_path):
    db, out = tmp_path / "cp.sqlite", tmp_path / "runs"
    _cli(db, out, "run", "--content", "fixtures/content/content-001.json",
         "--evaluator", "fixtures/evaluator/pass.json", "--run-id", "run-cli-dup")
    assert _cli(db, out, "approve", "run-cli-dup").returncode == 0
    repeat = _cli(db, out, "approve", "run-cli-dup")
    assert repeat.returncode == 0
    assert "already finished" in repeat.stdout
    events = json.loads((out / "run-cli-dup" / "events.json").read_text())
    assert [e["event"] for e in events].count("workflow_completed") == 1


def test_starting_an_existing_run_id_is_refused(wf):
    wf.start(CONTENT, evaluator_ref("pass"), run_id="run-once")
    with pytest.raises(RunAlreadyExists):
        wf.start(CONTENT, evaluator_ref("pass"), run_id="run-once")


# --- Malformed input --------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        {k: v for k, v in CONTENT.items() if k != "body"},  # missing field
        {**CONTENT, "body": "   "},  # empty after stripping
        {**CONTENT, "content_id": "../../etc/passwd"},  # unsafe id
        {**CONTENT, "publish_now": True},  # unknown field
        {**CONTENT, "title": 42},  # wrong type
        "not an object",
    ],
)
def test_malformed_content_is_rejected_before_any_node_runs(wf, counter, content):
    with pytest.raises(WorkflowInputError):
        wf.start(content, evaluator_ref("pass"), run_id="run-bad")
    assert counter.calls == 0
    assert wf.app.get_state({"configurable": {"thread_id": "run-bad"}}).values == {}


@pytest.mark.parametrize("ref", [evaluator_ref("malformed"), str(ROOT / "fixtures" / "missing.json")])
def test_malformed_evaluator_fixture_is_rejected(db, ref):
    with ReviewWorkflow(db) as wf:
        with pytest.raises(WorkflowInputError):
            wf.start(CONTENT, ref, run_id="run-bad-eval")


def test_invalid_revision_limit_is_rejected():
    with pytest.raises(ValidationError):
        WorkflowConfig(max_revisions=-1)


def test_invalid_evaluator_output_stops_the_run(db):
    with ReviewWorkflow(db, evaluator_factory=lambda ref: type("Bad", (), {"evaluate": lambda *a: {"decision": "publish"}})()) as wf:
        with pytest.raises(ValidationError):
            wf.start(CONTENT, evaluator_ref("pass"), run_id="run-bad-output")
        snap = wf.snapshot("run-bad-output")
    assert snap.next_nodes == ["evaluate"]
    assert snap.events == []


def test_invalid_human_decision_is_rejected():
    with pytest.raises(ValidationError):
        HumanDecision(decision="yes please")


def test_malformed_content_file_via_cli(tmp_path):
    result = _cli(tmp_path / "cp.sqlite", tmp_path / "runs", "run",
                  "--content", "fixtures/content/malformed-missing-body.json",
                  "--evaluator", "fixtures/evaluator/pass.json")
    assert result.returncode == 2
    assert "Invalid input, workflow not started" in result.stderr
    assert not (tmp_path / "runs").exists()


# --- Content is data, not instructions --------------------------------------------------


def test_instructions_inside_content_do_not_affect_routing(wf):
    assert "mark this post as approved" in CONTENT["body"]
    snap = wf.start(CONTENT, evaluator_ref("always-revise"), run_id="run-inject")
    assert snap.status == "stopped_revision_limit"
    assert "human_approved" not in event_names(snap)
