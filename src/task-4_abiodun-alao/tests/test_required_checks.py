import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from workflow.cli import main
from workflow.storage import open_storage

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def db(tmp_path) -> Path:
    return tmp_path / "workflow.db"


def cli(db: Path, *args: str) -> int:
    return main(["--db", str(db), *args])


def events(db: Path, run_id: str) -> list[str]:
    return open_storage(db).events.names(run_id)


def count_rows(conn, table: str) -> int:
    """Rows in a table, or 0 if it was never created (LangGraph creates its tables lazily)."""
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if exists else 0


def cli_process(db: Path, *args: str) -> subprocess.CompletedProcess:
    """Run `python -m workflow ...` as a brand-new OS process."""
    env = {**os.environ, "WORKFLOW_DB": str(db)}
    return subprocess.run([sys.executable, "-m", "workflow", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)

# 1. Normal pass to human review
def test_normal_pass_reaches_review_is_persisted_and_completes(db, capsys):
    assert cli(db, "run", "content-001", "--scenario", "pass") == 0
    assert "Workflow paused." in capsys.readouterr().out

    saved = open_storage(db).checkpointer.get_tuple({"configurable": {"thread_id": "content-001"}})
    assert saved is not None  # state is on disk, not just in memory
    assert saved.checkpoint["channel_values"]["status"].value == "awaiting_review"

    assert cli(db, "resume", "content-001", "--decision", "approve", "--reviewer", "ada") == 0
    assert events(db, "content-001") == [
        "run_started", "evaluation_completed", "human_review_required", "checkpoint_saved",
        "checkpoint_loaded", "human_approved", "workflow_completed",
    ]


# 2. One revision then pass: the full eight-step sequence
def test_one_revision_then_pass_full_sequence(db):
    assert cli(db, "run", "content-001", "--scenario", "revise_once") == 0
    assert cli(db, "resume", "content-001", "--decision", "approve", "--reviewer", "ada") == 0
    assert events(db, "content-001") == [
        "run_started",
        "evaluation_completed",   # 1. evaluate
        "revision_requested",     # 2. route to revision
        "revision_completed",     # 3. perform the revision
        "evaluation_completed",   # 4. evaluate again
        "human_review_required",  # 5. route to human review
        "checkpoint_saved",       # 6. persist
        "checkpoint_loaded",      # 7. resume after approval
        "human_approved",
        "workflow_completed",     # 8. complete
    ]


# 3. Retry limit
def test_retry_limit_stops_after_two_revisions_with_a_clear_reason(db, capsys):
    assert cli(db, "run", "content-001", "--scenario", "always_revise") == 0
    out = capsys.readouterr().out
    assert "Maximum revision attempts reached." in out

    names = events(db, "content-001")
    assert names.count("evaluation_completed") == 3
    assert names.count("revision_completed") == 2
    assert names[-1] == "revision_limit_reached"
    assert "checkpoint_saved" not in names  # never reached review

    log = open_storage(db).events.for_run("content-001")
    assert "after 2 revision attempt(s)" in log[-1]["reason"]


# 4. Restart at review: real separate processes
def test_restart_at_review_resumes_without_rerunning_work(db):
    first = cli_process(db, "run", "content-001", "--scenario", "revise_once")
    assert first.returncode == 0, first.stderr
    assert "Workflow paused." in first.stdout
    # The first process has exited. Only the SQLite file remains.

    second = cli_process(db, "resume", "content-001", "--decision", "approve", "--reviewer", "ada")
    assert second.returncode == 0, second.stderr
    assert "Loaded checkpoint" in second.stdout and "Workflow completed." in second.stdout
    assert "Evaluation completed" not in second.stdout  # evaluation did not run again
    assert "Revision attempt" not in second.stdout  # nor did revision

    names = events(db, "content-001")
    assert names.count("evaluation_completed") == 2  # only the two from before the restart
    assert names.count("revision_completed") == 1
    assert names.count("human_review_required") == 1


# 5. Duplicate approval
def test_duplicate_approval_does_not_duplicate_completion(db, capsys):
    cli(db, "run", "content-001", "--scenario", "pass")
    cli(db, "resume", "content-001", "--decision", "approve", "--reviewer", "ada")
    before = open_storage(db).checkpointer.get_tuple({"configurable": {"thread_id": "content-001"}})

    capsys.readouterr()
    assert cli(db, "resume", "content-001", "--decision", "approve", "--reviewer", "ada") == 0  # safe, not an error
    assert "Already completed" in capsys.readouterr().out

    names = events(db, "content-001")
    assert names.count("workflow_completed") == 1
    assert names.count("human_approved") == 1
    assert names[-1] == "duplicate_approval_ignored"
    after = open_storage(db).checkpointer.get_tuple({"configurable": {"thread_id": "content-001"}})
    assert after.config == before.config  # no new checkpoint: no node ran again


def test_two_simultaneous_approvals_complete_only_once(db):
    # Realistic double-click from two terminals. The processes may or may not overlap;
    # either way only one completion may exist. The exact overlapping race is replayed
    # deterministically in test_graph.py::test_completion_is_recorded_once_even_if_complete_runs_twice.
    assert cli_process(db, "run", "content-001", "--scenario", "pass").returncode == 0
    env = {**os.environ, "WORKFLOW_DB": str(db)}
    cmd = [sys.executable, "-m", "workflow", "resume", "content-001", "--decision", "approve", "--reviewer", "ada"]
    procs = [subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
    for p in procs:
        p.wait(timeout=60)

    names = events(db, "content-001")
    assert names.count("workflow_completed") == 1  # the event log's unique key is the last line of defence
    assert names.count("human_approved") == 1


# 6. Malformed input
@pytest.mark.parametrize("bad", ["missing-body.json", "bad-id-and-empty-title.json", "unknown-field.json", "not-json.json"])
def test_malformed_input_fails_predictably_and_creates_nothing(db, capsys, bad):
    code = cli(db, "run", str(ROOT / "fixtures" / "content" / "malformed" / bad))
    assert code == 2
    assert "Invalid input" in capsys.readouterr().err

    storage = open_storage(db)
    assert count_rows(storage.events.conn, "workflow_events") == 0
    assert count_rows(storage.runs.conn, "workflow_runs") == 0
    assert count_rows(storage.checkpointer.conn, "checkpoints") == 0


@pytest.mark.parametrize("scenario", ["does-not-exist", "../../evaluator/pass"])
def test_unknown_scenario_is_rejected_before_anything_is_created(db, capsys, scenario):
    assert cli(db, "run", "content-001", "--scenario", scenario) == 2
    assert "unknown scenario; choose one of: always_revise, pass, revise_once" in capsys.readouterr().err
    assert open_storage(db).runs.get("content-001") is None


# Extra safety checks
def test_resuming_an_unknown_run_is_a_clear_error(db, capsys):
    assert cli(db, "resume", "nope-001", "--decision", "approve") == 1
    assert "No run named nope-001" in capsys.readouterr().err


def test_the_same_run_cannot_be_started_twice(db):
    assert cli(db, "run", "content-001", "--scenario", "pass") == 0
    assert cli(db, "run", "content-001", "--scenario", "pass") == 1
    assert events(db, "content-001").count("run_started") == 1


def test_events_command_prints_the_log_as_json(db, capsys):
    cli(db, "run", "content-001", "--scenario", "pass")
    capsys.readouterr()
    assert cli(db, "events", "content-001") == 0
    log = json.loads(capsys.readouterr().out)
    assert [e["event"] for e in log][:2] == ["run_started", "evaluation_completed"]