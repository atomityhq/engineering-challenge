import argparse
import json
from pathlib import Path
from typing import cast
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import ValidationError

from evaluator import FakeEvaluator
from models import ContentInput, EvaluationDecision
from persistence import open_sqlite_checkpointer
from workflow import build_workflow, create_initial_state, resume_after_review


DEFAULT_DATABASE = Path(__file__).with_name("workflow_checkpoints.sqlite3")
FIXTURE_PATH = Path(__file__).with_name("fixtures") / "workflow_scenarios.json"
SCENARIO_NAMES = ("pass", "revise-once", "retry-limit")
TERMINAL_STATUSES = {"completed", "retry_limit_reached"}


class CliError(Exception):
    pass


def load_workflow_fixture(
    path: Path = FIXTURE_PATH,
) -> tuple[ContentInput, dict[str, list[EvaluationDecision]]]:
    try:
        with path.open(encoding="utf-8") as fixture_file:
            fixture = json.load(fixture_file)
    except FileNotFoundError as error:
        raise CliError(f"workflow fixture not found: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise CliError(f"could not read workflow fixture {path}: {error}") from error

    try:
        if not isinstance(fixture, dict):
            raise ValueError("fixture root must be a JSON object")
        content = ContentInput.model_validate(fixture["content_item"])
        raw_scenarios = fixture["scenarios"]
        if not isinstance(raw_scenarios, dict):
            raise ValueError("scenarios must be a JSON object")

        scenarios: dict[str, list[EvaluationDecision]] = {}
        for name in SCENARIO_NAMES:
            scenario = raw_scenarios[name]
            if not isinstance(scenario, dict):
                raise ValueError(f"scenario {name!r} must be a JSON object")
            raw_decisions = scenario["decisions"]
            if not isinstance(raw_decisions, list) or not raw_decisions:
                raise ValueError(f"scenario {name!r} must contain decisions")
            decisions = cast(list[EvaluationDecision], raw_decisions)
            FakeEvaluator(decisions)
            scenarios[name] = decisions
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        raise CliError(f"invalid workflow fixture {path}: {error}") from error

    return content, scenarios


def thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def print_event_history(state: dict) -> None:
    print("Event history:")
    for event in state["event_log"]:
        print(f"  - {event}")


def find_active_thread(
    checkpointer: SqliteSaver,
    content_id: str,
) -> str | None:
    seen_threads: set[str] = set()
    for checkpoint in checkpointer.list(None):
        thread_id = checkpoint.config["configurable"]["thread_id"]
        if thread_id in seen_threads:
            continue
        seen_threads.add(thread_id)

        state = checkpoint.checkpoint["channel_values"]
        content = state.get("content")
        if (
            isinstance(content, ContentInput)
            and content.content_id == content_id
            and state.get("status") not in TERMINAL_STATUSES
        ):
            return thread_id
    return None


def run_workflow(args: argparse.Namespace) -> None:
    content, scenarios = load_workflow_fixture()
    if args.content_id != content.content_id:
        raise CliError(f"unknown fixture content ID: {args.content_id}")

    with open_sqlite_checkpointer(args.database) as checkpointer:
        active_thread = find_active_thread(checkpointer, args.content_id)
        if active_thread is not None:
            raise CliError(
                f"content {args.content_id!r} already has an active workflow "
                f"with thread ID {active_thread}"
            )

        thread_id = str(uuid4())
        config = thread_config(thread_id)
        graph = build_workflow(
            FakeEvaluator(scenarios[args.scenario]),
            checkpointer=checkpointer,
        )
        if graph.get_state(config).values:
            raise CliError(f"thread ID {thread_id} already exists")

        state = create_initial_state(
            thread_id,
            content,
        )
        result = graph.invoke(state, config)

    print_event_history(result)
    if result["status"] == "awaiting_human_review":
        print("Workflow paused for human review.")
    elif result["status"] == "retry_limit_reached":
        print("Workflow stopped because the revision limit was reached.")
    else:
        print(f'Workflow status: {result["status"]}')
    print(f"Thread ID: {thread_id}")


def resume_workflow(args: argparse.Namespace) -> None:
    config = thread_config(args.thread_id)
    with open_sqlite_checkpointer(args.database) as checkpointer:
        graph = build_workflow(FakeEvaluator([]), checkpointer=checkpointer)
        snapshot = graph.get_state(config)
        if not snapshot.values:
            raise CliError(f"unknown thread ID: {args.thread_id}")

        state = snapshot.values
        if state["status"] == "completed":
            if args.decline:
                raise CliError("a completed workflow cannot be declined")
            print("Workflow is already completed; no additional approval was applied.")
            print_event_history(state)
            return
        if state["status"] == "retry_limit_reached":
            raise CliError("workflow stopped at the retry limit and cannot be resumed")
        if state["status"] != "awaiting_human_review":
            raise CliError(
                f'workflow is not paused for human review: {state["status"]}'
            )

        result = graph.invoke(resume_after_review(args.approve), config)

    if args.approve:
        print(f'Workflow status: {result["status"]}')
    else:
        print("Review declined; workflow remains paused for human review.")
    print_event_history(result)


def show_status(args: argparse.Namespace) -> None:
    config = thread_config(args.thread_id)
    with open_sqlite_checkpointer(args.database) as checkpointer:
        graph = build_workflow(FakeEvaluator([]), checkpointer=checkpointer)
        snapshot = graph.get_state(config)
        if not snapshot.values:
            raise CliError(f"unknown thread ID: {args.thread_id}")
        state = snapshot.values

    print(f'Thread ID: {args.thread_id}')
    print(f'Status: {state["status"]}')
    print_event_history(state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Task 4 review workflow.")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"checkpoint database (default: {DEFAULT_DATABASE.name})",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="start a workflow")
    run_parser.add_argument("content_id")
    run_parser.add_argument(
        "--scenario",
        choices=SCENARIO_NAMES,
        default="pass",
    )
    run_parser.set_defaults(handler=run_workflow)

    resume_parser = commands.add_parser("resume", help="resume human review")
    resume_parser.add_argument("thread_id")
    decision = resume_parser.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--decline", action="store_true")
    resume_parser.set_defaults(handler=resume_workflow)

    status_parser = commands.add_parser("status", help="show persisted state")
    status_parser.add_argument("thread_id")
    status_parser.set_defaults(handler=show_status)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except CliError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
