"""Command line interface.

    python -m workflow run <content-id> --scenario <scenario-id> [--run-id ID] [--max-revisions N]
    python -m workflow approve <run-id>
    python -m workflow status <run-id>
    python -m workflow events <run-id>

Every command accepts --db PATH (default: data/workflow.db).
Exit code 0 means the command did what was asked; 1 means it was refused with a message.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .fakes import Evaluator, Reviser, ScriptedEvaluator, ScriptedReviser
from .graph import (
    NotWaitingForReviewError,
    RunExistsError,
    UnknownRunError,
    approve_run,
    build_graph,
    initial_state,
    is_waiting_for_review,
    start_run,
)
from .models import (
    DEFAULT_MAX_REVISIONS,
    ContentItem,
    EvalResult,
    FixtureNotFoundError,
    check_run_inputs,
    load_content,
    load_scenario,
)
from .store import DEFAULT_DB_PATH, Storage, open_storage


class CommandError(Exception):
    """A refused command. The message is shown to the user."""


class _NoRerunEvaluator(Evaluator):
    """Used when a saved run is opened. Resuming must never evaluate again."""

    def evaluate(self, item: ContentItem, step: int) -> EvalResult:
        raise RuntimeError("a saved run tried to run evaluation again")


class _NoRerunReviser(Reviser):
    """Used when a saved run is opened. Resuming must never revise again."""

    def revise(self, item: ContentItem, step: int) -> ContentItem:
        raise RuntimeError("a saved run tried to run a revision again")


def _saved_run_graph(storage: Storage):
    return build_graph(_NoRerunEvaluator(), _NoRerunReviser(), storage.events, storage.checkpointer)


def _saved_values(graph, run_id: str) -> tuple[dict[str, Any], Any]:
    snapshot = graph.get_state({"configurable": {"thread_id": run_id}})
    if not snapshot.values:
        raise CommandError(f"No run with id '{run_id}'.")
    return snapshot.values, snapshot


def _validation_message(what: str, exc: ValidationError) -> str:
    lines = [f"Invalid {what}:"]
    for err in exc.errors():
        field = ".".join(str(part) for part in err["loc"]) or "(item)"
        lines.append(f"  {field}: {err['msg']}")
    return "\n".join(lines)


def _print_progress(events: list[dict[str, Any]]) -> None:
    for e in events:
        name = e["event"]
        if name == "evaluation_completed":
            print("Evaluation completed")
            print(f"Decision: {e['decision']} ({e['reason']})")
        elif name == "revision_completed":
            print(f"Revision attempt: {e['revision_count']}")
        elif name == "human_review_required":
            print("Human review required")
        elif name == "checkpoint_saved":
            print("Checkpoint saved")
        elif name == "revision_limit_reached":
            print(f"Maximum revision attempts reached ({e['max_revisions']}).")
        print()


def cmd_run(args: argparse.Namespace) -> None:
    try:
        item = load_content(args.content_id)
    except FixtureNotFoundError as exc:
        raise CommandError(f"Unknown content id '{args.content_id}'.") from exc
    except ValidationError as exc:
        raise CommandError(_validation_message(f"content item '{args.content_id}'", exc)) from exc
    try:
        scenario = load_scenario(args.scenario)
    except FixtureNotFoundError as exc:
        raise CommandError(f"Unknown scenario '{args.scenario}'.") from exc
    except ValidationError as exc:
        raise CommandError(_validation_message("scenarios file", exc)) from exc
    try:
        check_run_inputs(item, scenario, args.max_revisions)
    except ValueError as exc:
        raise CommandError(f"Invalid run input: {exc}.") from exc

    run_id = args.run_id or f"run-{uuid.uuid4().hex[:6]}"
    with open_storage(args.db) as storage:
        graph = build_graph(ScriptedEvaluator(scenario), ScriptedReviser(scenario), storage.events, storage.checkpointer)
        try:
            snapshot = start_run(graph, storage.events, initial_state(run_id, item, scenario.id, args.max_revisions))
        except RunExistsError as exc:
            raise CommandError(f"Run '{run_id}' already exists. Choose another --run-id.") from exc
        print(f"Run: {run_id}  (content: {item.content_id}, scenario: {scenario.id})\n")
        _print_progress(storage.events.events(run_id))

    values = snapshot.values
    if is_waiting_for_review(snapshot):
        print("Workflow paused for human review.")
        print(f"Title: {values['title']}")
        print(f"Body:  {values['body']}\n")
        print(f"To approve, run:  python -m workflow approve {run_id}")
    else:
        print(f"Workflow stopped. Status: {values['status']}")


def cmd_approve(args: argparse.Namespace) -> None:
    with open_storage(args.db) as storage:
        graph = _saved_run_graph(storage)
        try:
            outcome = approve_run(graph, storage.events, args.run_id)
        except UnknownRunError as exc:
            raise CommandError(f"No run with id '{args.run_id}'.") from exc
        except NotWaitingForReviewError as exc:
            status = graph.get_state({"configurable": {"thread_id": args.run_id}}).values["status"]
            raise CommandError(f"Run '{args.run_id}' cannot be approved. Status: {status}.") from exc

    if outcome == "already_completed":
        print(f"Run '{args.run_id}' is already completed. Nothing changed.")
        return
    print("Loaded checkpoint")
    print("Current stage: human_review")
    print("Approved.")
    print("Workflow completed.")


def cmd_status(args: argparse.Namespace) -> None:
    with open_storage(args.db) as storage:
        values, snapshot = _saved_values(_saved_run_graph(storage), args.run_id)
        waiting = is_waiting_for_review(snapshot)
        next_nodes = ", ".join(snapshot.next) or "none (finished)"

    print(f"Run:            {values['run_id']}")
    print(f"Content:        {values['content_id']}")
    print(f"Scenario:       {values['scenario_id']}")
    print(f"Status:         {values['status']}")
    print(f"Revisions:      {values['revision_count']} of {values['max_revisions']}")
    print(f"Last decision:  {values['decision']} ({values['reason']})")
    print(f"Next step:      {next_nodes}")
    if waiting:
        print(f"\nWaiting for review. Approve with:  python -m workflow approve {values['run_id']}")


def cmd_events(args: argparse.Namespace) -> None:
    with open_storage(args.db) as storage:
        _saved_values(_saved_run_graph(storage), args.run_id)
        events = storage.events.events(args.run_id)
    print(json.dumps(events, indent=2))


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite file (default: data/workflow.db)")

    parser = argparse.ArgumentParser(prog="python -m workflow", description="Resumable review workflow.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", parents=[common], help="start a new run until it pauses or stops")
    run.add_argument("content_id")
    run.add_argument("--scenario", required=True, help="scenario id from fixtures/scenarios.json")
    run.add_argument("--run-id", help="run id to use (default: a random id)")
    run.add_argument("--max-revisions", type=int, default=DEFAULT_MAX_REVISIONS)
    run.set_defaults(handler=cmd_run)

    for name, handler, text in [
        ("approve", cmd_approve, "approve a run that is waiting for review"),
        ("status", cmd_status, "show where a run is"),
        ("events", cmd_events, "print the event log of a run as JSON"),
    ]:
        p = sub.add_parser(name, parents=[common], help=text)
        p.add_argument("run_id")
        p.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        args.handler(args)
    except CommandError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
