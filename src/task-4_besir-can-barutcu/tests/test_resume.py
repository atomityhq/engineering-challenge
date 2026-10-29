"""Restart tests: every command runs in its own Python process, sharing one SQLite file.

Nothing is shared between the processes except the database file, so these tests show
that a paused run really survives the end of the process that started it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent

FULL_ONE_REVISION_LOG = [
    "evaluation_completed",
    "revision_completed",
    "evaluation_completed",
    "human_review_required",
    "checkpoint_saved",
    "checkpoint_loaded",
    "human_approved",
    "workflow_completed",
]

# Starts a run, then ends the process at once with os._exit(): no cleanup, no closing
# of the database connections. This is as close to a crash as a test can safely get.
START_THEN_CRASH = """
import os, sys
from pathlib import Path
from workflow.fakes import ScriptedEvaluator, ScriptedReviser
from workflow.graph import build_graph, initial_state, start_run
from workflow.models import load_content, load_scenario
from workflow.store import open_storage

db, run_id, scenario_id = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
opened = open_storage(db)  # keep a reference so the connections stay open until os._exit
storage = opened.__enter__()
scenario = load_scenario(scenario_id)
graph = build_graph(ScriptedEvaluator(scenario), ScriptedReviser(scenario), storage.events, storage.checkpointer)
start_run(graph, storage.events, initial_state(run_id, load_content("content-001"), scenario_id))
os._exit(0)
"""


def _python(args: list[str]) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, *args], cwd=PROJECT_DIR, env=env, capture_output=True, text=True, timeout=120
    )


@pytest.fixture
def db(tmp_path):
    return tmp_path / "workflow.db"


def cli(db: Path, *args: str) -> subprocess.CompletedProcess:
    return _python(["-m", "workflow", *args, "--db", str(db)])


def event_names(db: Path, run_id: str) -> list[str]:
    result = cli(db, "events", run_id)
    assert result.returncode == 0, result.stderr
    return [e["event"] for e in json.loads(result.stdout)]


def test_restart_at_review_does_not_rerun_finished_work(db):
    first = cli(db, "run", "content-001", "--scenario", "one-revision", "--run-id", "run-1")
    assert first.returncode == 0, first.stderr
    assert "Workflow paused for human review." in first.stdout
    before_restart = event_names(db, "run-1")
    assert before_restart == FULL_ONE_REVISION_LOG[:5]

    second = cli(db, "approve", "run-1")
    assert second.returncode == 0, second.stderr
    assert "Workflow completed." in second.stdout

    after_restart = event_names(db, "run-1")
    assert after_restart == FULL_ONE_REVISION_LOG
    new_events = after_restart[len(before_restart):]
    assert new_events == ["checkpoint_loaded", "human_approved", "workflow_completed"]
    assert "Status:         COMPLETED" in cli(db, "status", "run-1").stdout


def test_run_survives_an_abrupt_process_exit(db):
    crashed = _python(["-c", START_THEN_CRASH, str(db), "run-1", "one-revision"])
    assert crashed.returncode == 0, crashed.stderr

    status = cli(db, "status", "run-1")
    assert status.returncode == 0, status.stderr
    assert "Status:         WAITING_FOR_REVIEW" in status.stdout
    assert "Revisions:      1 of 2" in status.stdout

    assert cli(db, "approve", "run-1").returncode == 0
    assert event_names(db, "run-1") == FULL_ONE_REVISION_LOG


def test_duplicate_approval_in_separate_processes(db):
    assert cli(db, "run", "content-001", "--scenario", "normal-pass", "--run-id", "run-1").returncode == 0
    assert cli(db, "approve", "run-1").returncode == 0

    again = cli(db, "approve", "run-1")
    assert again.returncode == 0
    assert "already completed. Nothing changed." in again.stdout

    names = event_names(db, "run-1")
    assert names.count("human_approved") == 1
    assert names.count("workflow_completed") == 1


def test_stopped_run_stays_stopped_after_restart(db):
    assert cli(db, "run", "content-001", "--scenario", "revision-limit", "--run-id", "run-1").returncode == 0

    approve = cli(db, "approve", "run-1")
    assert approve.returncode == 1
    assert "REVISION_LIMIT_REACHED" in approve.stderr
    assert event_names(db, "run-1")[-1] == "revision_limit_reached"


def test_malformed_input_leaves_nothing_to_resume(db):
    bad = cli(db, "run", "content-bad", "--scenario", "normal-pass", "--run-id", "run-1")
    assert bad.returncode == 1
    assert "body: Field required" in bad.stderr

    status = cli(db, "status", "run-1")
    assert status.returncode == 1
    assert "No run with id 'run-1'" in status.stderr
