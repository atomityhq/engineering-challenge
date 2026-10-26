"""CLI:
    python -m workflow run <content-id|file.json> [--scenario NAME] [--db PATH]
    python -m workflow resume <run-id> [--approve] [--reviewer NAME] [--db PATH]
    python -m workflow approve <run-id>            (same as: resume --approve)
    python -m workflow log <run-id> [--json]
Exit codes: 0 ok, 1 runtime problem (unknown/duplicate run), 2 invalid input.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from workflow.config import WorkflowConfig
from workflow.evaluator import (FakeReviser, ScriptedEvaluator, load_content,
                                load_content_file, load_script, script_names)
from workflow.models import Event, Status
from workflow.service import (NotAwaitingApproval, RunAlreadyExists, UnknownRun,
                              get_state, open_runtime, resume_run, start_run)

DEFAULT_SCENARIO = "one_revision_then_pass"


def _fmt(e: Event) -> str:
    line = f"  [{e.seq}] {e.event}"
    if e.event in {"evaluation_completed", "revision_requested", "revision_completed",
                   "max_revisions_reached", "human_review_required", "checkpoint_saved"}:
        line += f" (revision {e.revision_count})"
    return line + (f" - {e.detail}" if e.detail else "")


def _print_new(rt, run_id: str, since: int) -> None:
    for e in rt.events.list(run_id):
        if e.seq > since:
            print(_fmt(e))


def _last_seq(rt, run_id: str) -> int:
    events = rt.events.list(run_id)
    return events[-1].seq if events else 0


def cmd_run(args) -> int:
    try:
        src = args.content
        content = load_content_file(src) if src.lower().endswith(".json") else load_content(src)
        decisions = load_script(args.scenario)
    except (ValidationError, OSError, KeyError) as exc:
        print(f"Invalid input, nothing started: {exc}", file=sys.stderr)
        return 2
    run_id = args.run_id or f"run-{content.content_id}"
    config = WorkflowConfig(db_path=Path(args.db))
    with open_runtime(config, ScriptedEvaluator(decisions), FakeReviser()) as rt:
        try:
            state = start_run(rt, run_id, content)
        except RunAlreadyExists:
            print(f"Run {run_id} already exists. Use: python -m workflow resume {run_id}",
                  file=sys.stderr)
            return 1
        _print_new(rt, run_id, 0)
    print(f"\nRun ID: {run_id}")
    if state.status == Status.HUMAN_REVIEW:
        print(f"Workflow paused at human review. Resume with:\n"
              f"  python -m workflow resume {run_id}")
    elif state.status == Status.STOPPED:
        print(f"Workflow stopped: {state.stop_reason}")
    return 0


def cmd_resume(args) -> int:
    config = WorkflowConfig(db_path=Path(args.db))
    # Empty script: any attempt to re-run evaluation after a restart raises an error.
    with open_runtime(config, ScriptedEvaluator([]), FakeReviser()) as rt:
        try:
            state, paused = get_state(rt, args.run_id)
        except UnknownRun:
            print(f"Unknown run: {args.run_id}", file=sys.stderr)
            return 1
        print(f"Loaded checkpoint\nCurrent stage: {state.status.value}")
        approve = args.approve
        if paused and not approve:
            if sys.stdin.isatty():
                approve = input("Approval required. Approve? [y/N] ").strip().lower() == "y"
            else:
                print("Approval required. Re-run with --approve.")
        if paused and not approve:
            return 0
        since = _last_seq(rt, args.run_id)
        try:
            state, outcome = resume_run(rt, args.run_id, reviewer=args.reviewer)
        except NotAwaitingApproval as exc:
            print(str(exc), file=sys.stderr)
            return 1
        _print_new(rt, args.run_id, since)
    messages = {"completed": "Approved.\nWorkflow completed.",
                "already_completed": "Already completed; nothing repeated.",
                "stopped": f"Workflow is stopped: {state.stop_reason}"}
    print(messages[outcome])
    return 0


def cmd_log(args) -> int:
    config = WorkflowConfig(db_path=Path(args.db))
    with open_runtime(config, ScriptedEvaluator([]), FakeReviser()) as rt:
        events = rt.events.list(args.run_id)
    if not events:
        print(f"No events for {args.run_id}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([e.model_dump(exclude={"run_id"}, exclude_none=True) for e in events],
                         indent=2))
    else:
        for e in events:
            print(_fmt(e))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="workflow", description="Resumable review workflow")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--db", default="workflow.db", help="local SQLite file (default: workflow.db)")

    r = sub.add_parser("run", help="start a workflow run")
    r.add_argument("content", help="fixture content id (e.g. content-001) or path to a .json file")
    r.add_argument("--scenario", default=DEFAULT_SCENARIO, choices=script_names())
    r.add_argument("--run-id", default=None)
    common(r)
    r.set_defaults(func=cmd_run)

    for name in ("resume", "approve"):
        s = sub.add_parser(name, help="resume from the saved checkpoint and approve")
        s.add_argument("run_id")
        s.add_argument("--approve", action="store_true", default=(name == "approve"),
                       help="approve without prompting")
        s.add_argument("--reviewer", default="reviewer")
        common(s)
        s.set_defaults(func=cmd_resume)

    lg = sub.add_parser("log", help="print the event log")
    lg.add_argument("run_id")
    lg.add_argument("--json", action="store_true")
    common(lg)
    lg.set_defaults(func=cmd_log)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
