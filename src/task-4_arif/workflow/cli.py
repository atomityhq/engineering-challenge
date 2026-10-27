
import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from pydantic import ValidationError

from workflow.adapters.fake_evaluator import FakeEvaluator
from workflow.adapters.fake_reviser import FakeReviser
from workflow.adapters.sqlite_event_log import SQLiteEventLog
from workflow.graph import build_workflow_graph
from workflow.models import ContentItem, EvaluationDecision
from workflow.persistence.checkpoint import sqlite_checkpointer
from workflow.services import (
    WorkflowConflictError,
    WorkflowNotFoundError,
    WorkflowService,
)


DEFAULT_DATA_DIR = Path(".workflow_data")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="workflow",
        description="Resumable content review workflow",
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory for SQLite persistence files",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    start_parser = subparsers.add_parser(
        "start",
        help="Start a new review workflow",
    )

    start_parser.add_argument(
        "workflow_id",
        help="Unique workflow identifier",
    )
    start_parser.add_argument(
        "--content-id",
        required=True,
    )
    start_parser.add_argument(
        "--title",
        required=True,
    )
    start_parser.add_argument(
        "--body",
        required=True,
    )
    start_parser.add_argument(
        "--decisions",
        nargs="+",
        choices=[
            decision.value
            for decision in EvaluationDecision
        ],
        default=[
            EvaluationDecision.HUMAN_REVIEW.value
        ],
        help="Deterministic evaluator decision sequence",
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Show persisted workflow state",
    )
    status_parser.add_argument("workflow_id")

    approve_parser = subparsers.add_parser(
        "approve",
        help="Approve an interrupted workflow",
    )
    approve_parser.add_argument("workflow_id")

    events_parser = subparsers.add_parser(
        "events",
        help="Show workflow audit events",
    )
    events_parser.add_argument("workflow_id")

    return parser


@contextmanager
def create_service(
    *,
    data_dir: Path,
    decisions: list[EvaluationDecision],
) -> Iterator[WorkflowService]:
    """Create the workflow service with durable SQLite adapters."""

    data_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    event_log = SQLiteEventLog(
        data_dir / "events.db"
    )

    with sqlite_checkpointer(
        data_dir / "checkpoints.db"
    ) as saver:
        graph = build_workflow_graph(
            evaluator=FakeEvaluator(
                decisions=decisions
            ),
            reviser=FakeReviser(),
            event_log=event_log,
            checkpointer=saver,
        )

        yield WorkflowService(
            graph=graph,
            event_log=event_log,
        )


def serialize_state(state: dict) -> dict:
    """Convert workflow state into JSON-compatible values."""

    result = dict(state)

    content = result.get("content")

    if isinstance(content, ContentItem):
        result["content"] = content.model_dump(
            mode="json"
        )

    evaluation = result.get("evaluation")

    if evaluation is not None and hasattr(
        evaluation,
        "model_dump",
    ):
        result["evaluation"] = evaluation.model_dump(
            mode="json"
        )

    return result


def print_json(value: dict | list) -> None:
    """Print structured CLI output."""

    print(
        json.dumps(
            value,
            indent=2,
        )
    )


def run_command(args: argparse.Namespace) -> int:
    """Execute the selected CLI command."""

    if args.command == "start":
        decisions = [
            EvaluationDecision(value)
            for value in args.decisions
        ]
    else:
        # Reading state and resuming an interrupted human-review
        # node do not require another evaluator invocation.
        decisions = [
            EvaluationDecision.HUMAN_REVIEW
        ]

    with create_service(
        data_dir=args.data_dir,
        decisions=decisions,
    ) as service:

        if args.command == "start":
            content = ContentItem(
                content_id=args.content_id,
                title=args.title,
                body=args.body,
            )

            state = service.start(
                workflow_id=args.workflow_id,
                content=content,
            )

            # WorkflowService determines the correct status.
            print_json(
                serialize_state(state)
            )
            return 0

        if args.command == "status":
            state = service.status(
                args.workflow_id
            )

            # No manual status override.
            print_json(
                serialize_state(state)
            )
            return 0

        if args.command == "approve":
            state = service.approve(
                args.workflow_id
            )

            print_json(
                serialize_state(state)
            )
            return 0

        if args.command == "events":
            events = service.events(
                args.workflow_id
            )

            print_json(
                [
                    event.model_dump(mode="json")
                    for event in events
                ]
            )
            return 0

    raise ValueError(
        f"Unsupported command: {args.command}"
    )


def main(
    argv: list[str] | None = None,
) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return run_command(args)

    except (
        ValidationError,
        WorkflowConflictError,
        WorkflowNotFoundError,
        ValueError,
    ) as exc:
        print(
            f"Error: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
