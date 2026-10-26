"""Shared test helpers. Each helper opens a FRESH runtime, which simulates a restart:
nothing is carried over in memory except what the SQLite checkpoint/event log hold."""
import json
import subprocess
import sys
from pathlib import Path

from workflow.config import WorkflowConfig
from workflow.evaluator import FakeReviser, ScriptedEvaluator, load_content, load_script
from workflow.events import SqliteEventLog
from workflow.service import open_runtime, resume_run, start_run

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "run-test"


def begin(config: WorkflowConfig, scenario: str, content_id: str = "content-001",
          run_id: str = RUN_ID):
    evaluator = ScriptedEvaluator(load_script(scenario))
    with open_runtime(config, evaluator, FakeReviser()) as rt:
        state = start_run(rt, run_id, load_content(content_id))
    return state, evaluator


def approve(config: WorkflowConfig, run_id: str = RUN_ID, reviewer: str = "tester"):
    # Empty script: if anything re-evaluated after the restart it would raise.
    evaluator = ScriptedEvaluator([])
    with open_runtime(config, evaluator, FakeReviser()) as rt:
        state, outcome = resume_run(rt, run_id, reviewer)
    assert evaluator.calls == 0, "resume must not re-run evaluation"
    return state, outcome


def events(config: WorkflowConfig, run_id: str = RUN_ID):
    return SqliteEventLog(config.db_path).list(run_id)


def names(config: WorkflowConfig, run_id: str = RUN_ID) -> list[str]:
    return [e.event for e in events(config, run_id)]


def cli(*args: str) -> subprocess.CompletedProcess:
    """Run the real CLI in a separate OS process."""
    return subprocess.run([sys.executable, "-m", "workflow", *args], cwd=ROOT,
                          capture_output=True, text=True, timeout=180)


def cli_log(db: Path, run_id: str = RUN_ID) -> list[dict]:
    proc = cli("log", run_id, "--json", "--db", str(db))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)
