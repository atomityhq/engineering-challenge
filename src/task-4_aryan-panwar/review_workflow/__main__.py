"""CLI: run | resume | approve | status.

    python -m review_workflow run --content fixtures/content/content-001.json \
        --evaluator fixtures/evaluator/one-revision.json --run-id run-001
    python -m review_workflow resume run-001            # prompts for approve/reject
    python -m review_workflow approve run-001           # non-interactive approval
    python -m review_workflow status run-001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .models import HumanDecision, WorkflowConfig, WorkflowSnapshot
from .service import ReviewWorkflow, RunAlreadyExists, RunNotFound, WorkflowInputError

EXIT_OK, EXIT_ERROR, EXIT_INVALID_INPUT, EXIT_DECISION_REQUIRED = 0, 1, 2, 3


def _print_events(snap: WorkflowSnapshot, since: int) -> None:
    for e in snap.events[since:]:
        d = e.detail
        match e.event:
            case "evaluation_completed":
                print(f"Evaluation completed (revisions so far: {e.revision_count})\n  Decision: {d['decision']}")
            case "revision_completed":
                print(f"Revision attempt: {d['attempt']}")
            case "human_review_required":
                print("Human review required")
            case "revision_limit_reached":
                print(f"Maximum revision attempts reached ({d['max_revisions']}).")
            case "workflow_stopped":
                print("Workflow stopped.")
            case "human_approved" | "human_rejected":
                print(f"{'Approved' if e.event == 'human_approved' else 'Rejected'} by {d['reviewer']}.")
            case "workflow_completed":
                print("Workflow completed.")
            case "workflow_rejected":
                print("Workflow finished: content rejected.")


def _export(snap: WorkflowSnapshot, out_dir: Path) -> Path:
    run_dir = out_dir / snap.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "state.json").write_text(snap.model_dump_json(indent=2, exclude={"events"}) + "\n")
    (run_dir / "events.json").write_text(
        json.dumps([e.model_dump() for e in snap.events], indent=2) + "\n"
    )
    return run_dir


def _report(snap: WorkflowSnapshot, out_dir: Path) -> None:
    run_dir = _export(snap, out_dir)
    if snap.status == "awaiting_review":
        print(f"Checkpoint saved: {snap.checkpoint_id}\nWorkflow paused.")
    print(f"Status: {snap.status}  (state + event log: {run_dir}/)")


def _ask_decision() -> HumanDecision | None:
    if not sys.stdin.isatty():
        return None
    answer = input("Approve this content? [approve/reject]: ").strip().lower()
    return HumanDecision(decision=answer) if answer in ("approve", "reject") else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="review_workflow")
    p.add_argument("--db", default=".workflow/checkpoints.sqlite", help="SQLite checkpoint file")
    p.add_argument("--out", default="runs", help="directory for exported state.json / events.json")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="start a workflow and run until review or a terminal state")
    run.add_argument("--content", required=True, type=Path)
    run.add_argument("--evaluator", required=True, help="evaluator fixture (deterministic responses)")
    run.add_argument("--run-id")
    run.add_argument("--max-revisions", type=int, default=2)

    res = sub.add_parser("resume", help="load a saved run and continue it")
    res.add_argument("run_id")
    res.add_argument("--decision", choices=["approve", "reject"])
    res.add_argument("--reviewer", default="cli")
    res.add_argument("--note")

    appr = sub.add_parser("approve", help="shortcut for: resume RUN_ID --decision approve")
    appr.add_argument("run_id")
    appr.add_argument("--reviewer", default="cli")

    st = sub.add_parser("status", help="print the saved state")
    st.add_argument("run_id")

    args = p.parse_args(argv)
    out = Path(args.out)

    try:
        with ReviewWorkflow(args.db) as wf:
            if args.cmd == "run":
                try:
                    content = json.loads(args.content.read_text())
                    config = WorkflowConfig(max_revisions=args.max_revisions)
                except (OSError, ValueError, ValidationError) as exc:
                    raise WorkflowInputError(str(exc)) from exc
                snap = wf.start(content, args.evaluator, args.run_id, config)
                print(f"Run {snap.run_id} started for {snap.content_id}")
                _print_events(snap, 0)
                _report(snap, out)
                return EXIT_OK

            if args.cmd == "status":
                snap = wf.snapshot(args.run_id)
                print(snap.model_dump_json(indent=2))
                return EXIT_OK

            before = wf.snapshot(args.run_id)
            print(f"Loaded checkpoint {before.checkpoint_id}\nCurrent stage: {before.status}")
            if args.cmd == "approve":
                decision = HumanDecision(decision="approve", reviewer=args.reviewer)
            elif args.decision:
                decision = HumanDecision(decision=args.decision, reviewer=args.reviewer, note=args.note)
            elif before.status == "awaiting_review":
                print("Approval required.")
                decision = _ask_decision()
            else:
                decision = None

            outcome = wf.resume(args.run_id, decision)
            if outcome.action == "already_finished":
                print(f"Run already finished ({outcome.snapshot.status}); nothing to do.")
            elif outcome.action == "decision_required":
                print("No decision given. Use --decision approve|reject or `approve RUN_ID`.")
                return EXIT_DECISION_REQUIRED
            _print_events(outcome.snapshot, len(before.events))
            _report(outcome.snapshot, out)
            return EXIT_OK

    except WorkflowInputError as exc:
        print(f"Invalid input, workflow not started:\n{exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except (RunNotFound, RunAlreadyExists) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
