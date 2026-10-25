import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from .inputs import InvalidInputError, load_content
from .models import ReviewDecision
from .service import NotResumableError, RunExistsError, RunNotFoundError, RunView, WorkflowService

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURES = ROOT / "fixtures"
DEFAULT_DB = ROOT / "data" / "workflow.db"


def _find_content_file(ref: str, fixtures_dir: Path) -> Path:
    if ref.endswith(".json") or "/" in ref:
        return Path(ref)
    direct = fixtures_dir / "content" / f"{ref}.json"
    if direct.exists():
        return direct
    for candidate in sorted((fixtures_dir / "content").glob(f"{ref}*.json")):
        return candidate
    return direct 


def _describe(event: dict) -> list[str]:
    name = event["event"]
    if name == "run_started":
        return [f"Run started: content {event['content_id']}, scenario {event['scenario']}, "
                f"max revisions {event['max_revisions']}"]
    if name == "evaluation_completed":
        reasons = "; ".join(event.get("reasons", [])) or "no reasons given"
        return ["", f"Evaluation completed (attempt {event['attempt']})", f"Decision: {event['decision']}",
                f"Reasons: {reasons}"]
    if name == "revision_requested":
        return ["", f"Revision attempt: {event['revision_count']}"]
    if name == "revision_limit_reached":
        return ["", "Maximum revision attempts reached.", f"Workflow stopped: {event['reason']}"]
    if name == "human_review_required":
        return ["", "Human review required"]
    if name == "checkpoint_saved":
        return [f"Checkpoint saved (version {event['checkpoint_version']})"]
    if name == "checkpoint_loaded":
        return ["Loaded checkpoint", f"Current stage: {event['stage']}"]
    if name == "human_approved":
        return ["", f"Approved by {event['reviewer']}."]
    if name == "human_rejected":
        note = f" Note: {event['note']}" if event.get("note") else ""
        return ["", f"Rejected by {event['reviewer']}.{note}"]
    if name == "workflow_completed":
        return ["", "Workflow completed."]
    if name == "duplicate_approval_ignored":
        return ["Already completed: nothing to do. No duplicate completion was recorded."]
    if name == "resume_ignored":
        return [f"Run already finished ({event['status']}): nothing to resume."]
    return [] if name == "revision_completed" else [name]

def _print_view(view: RunView, run_id: str) -> None:
    for event in view.new_events:
        for line in _describe(event):
            print(line)
    if view.paused_for_review:
        print("\nWorkflow paused.")
        print(f"Resume with: python -m workflow resume {run_id}")


def _ask_decision(service: WorkflowService, run_id: str, reviewer: str | None) -> ReviewDecision | None:
    view = service.status(run_id)
    if not view.paused_for_review:
        return ReviewDecision(decision="approve", reviewer=reviewer or getpass.getuser())  # service will report
    print(f"Run {run_id} is waiting for review ({view.revision_count} revision(s) so far).")
    answer = input("Approve this content? [a]pprove / [r]eject / anything else to cancel: ").strip().lower()
    if answer not in {"a", "approve", "r", "reject"}:
        print("Cancelled. The run is still paused.")
        return None
    note = None if answer.startswith("a") else (input("Reason for rejecting (optional): ").strip() or None)
    return ReviewDecision(decision="approve" if answer.startswith("a") else "reject",
                          reviewer=reviewer or getpass.getuser(), note=note)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m workflow", description="Resumable review workflow (LangGraph)")
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("WORKFLOW_DB", DEFAULT_DB)),
                        help="SQLite file for checkpoints and the event log (default: data/workflow.db)")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="start a workflow for a content item")
    run.add_argument("content", help="content ID (e.g. content-001) or path to a content JSON file")
    run.add_argument("--scenario", default="revise_once",
                     help="evaluator fixture in fixtures/evaluator (pass, revise_once, always_revise)")
    run.add_argument("--run-id", help="defaults to the content ID")
    run.add_argument("--max-revisions", type=int, default=2)

    resume = sub.add_parser("resume", help="continue a run paused for human review")
    resume.add_argument("run_id")
    resume.add_argument("--decision", choices=["approve", "reject"], help="skip the prompt")
    resume.add_argument("--reviewer", help="defaults to your OS user name")
    resume.add_argument("--note")

    for name, text in (("status", "show where a run is"), ("events", "print a run's event log as JSON")):
        cmd = sub.add_parser(name, help=text)
        cmd.add_argument("run_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = WorkflowService(args.db, args.fixtures)
    try:
        if args.command == "run":
            content = load_content(_find_content_file(args.content, args.fixtures))
            run_id = args.run_id or content.content_id
            _print_view(service.start(content, args.scenario, run_id, args.max_revisions), run_id)

        elif args.command == "resume":
            if args.decision:
                decision = ReviewDecision(decision=args.decision, reviewer=args.reviewer or getpass.getuser(),
                                          note=args.note)
            else:
                decision = _ask_decision(service, args.run_id, args.reviewer)
                if decision is None:
                    return 0
            _print_view(service.resume(args.run_id, decision), args.run_id)

        elif args.command == "status":
            view = service.status(args.run_id)
            print(json.dumps({"run_id": view.run_id, "status": view.status.value,
                              "paused_for_review": view.paused_for_review, "revision_count": view.revision_count,
                              "evaluation_count": view.evaluation_count, "stop_reason": view.stop_reason}, indent=2))

        elif args.command == "events":
            print(json.dumps(service.events(args.run_id), indent=2))
        return 0

    except InvalidInputError as e:
        print(f"Invalid input ({e.source}):", file=sys.stderr)
        for problem in e.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2
    except ValidationError as e:
        print(f"Invalid input: {e}", file=sys.stderr)
        return 2
    except (RunNotFoundError, RunExistsError, NotResumableError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        service.close()