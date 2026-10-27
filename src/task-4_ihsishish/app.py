import argparse
import json
import textwrap
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from data import InputData
from steps import ManualEvaluator, PresetReviser, RuleBasedEvaluator, ScriptedEvaluator
from workflow import build_workflow


DATABASE = Path(__file__).with_name("review.sqlite")


def show(graph, content_id, message=None):
    config = {"configurable": {"thread_id": content_id}}
    saved = graph.get_state(config)

    if not saved.values:
        print("No saved run with that content ID.")
        return

    state = saved.values

    print("\n" + "=" * 60)
    print(f"  CONTENT: {state['content_id']}")
    print("=" * 60)
    print("\nWORKFLOW EVENTS")

    for event in state["events"]:
        name = event["event"]

        if name == "evaluation_completed":
            print("\nEvaluation completed")
            print(f"  Decision: {event['decision'].upper()}")
            if event.get("reason"):
                print(f"  Reason: {event['reason']}")

        elif name == "revision_completed":
            print(f"\nRevision attempt: {event['revision_count']}")

        elif name == "human_review_required":
            print("\nHuman review required")

        elif name == "revision_limit_reached":
            print(
                f"\nMaximum revision attempts reached "
                f"({event['revision_count']})"
            )
            print("Workflow stopped")

        elif name == "human_approved":
            print("\nHuman decision: APPROVED")

        elif name == "human_rejected":
            print("\nHuman decision: NOT APPROVED")

        elif name == "workflow_completed":
            print("Workflow completed")

        else:
            print(f"\n{name.replace('_', ' ').capitalize()}")

    print("\n" + "-" * 60)
    print("RESULT")
    print(f"  Status: {state['status'].upper()}")
    print(f"  Revisions: {state['revision_count']}")

    if state["status"] == "human_review":
        print("  Checkpoint saved. Workflow paused for a person to review.")
        print(
            f"  Next: .\\.venv\\Scripts\\python.exe "
            f"app.py review {content_id}"
        )

    if message:
        print(f"  {message}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start")
    start.add_argument("file")
    start.add_argument("--max-revisions", type=int, default=2)

    approve = commands.add_parser("approve")
    approve.add_argument("content_id")

    review = commands.add_parser("review")
    review.add_argument("content_id")

    inspect = commands.add_parser("show")
    inspect.add_argument("content_id")

    args = parser.parse_args()

    if args.command == "start":
        if not 0 <= args.max_revisions <= 2:
            parser.error("--max-revisions must be 0, 1, or 2")

        try:
            raw = Path(args.file).read_text(encoding="utf-8-sig")
            item = InputData.model_validate(json.loads(raw))
        except (OSError, ValueError) as error:
            parser.error(f"Invalid input: {error}")

        content_id = item.content_id
    else:
        content_id = args.content_id

    config = {"configurable": {"thread_id": content_id}}
    message = None

    with SqliteSaver.from_conn_string(str(DATABASE)) as saver:
        if args.command == "start" and item.evaluation_mode == "manual":
            if item.evaluation_responses is not None:
                parser.error(
                    "A manual fixture cannot include evaluator responses"
                )
            evaluator = ManualEvaluator()

        elif args.command == "start" and item.evaluation_responses is not None:
            evaluator = ScriptedEvaluator(item.evaluation_responses)

        elif args.command == "start" and item.evaluation_mode == "scripted":
            parser.error("A scripted fixture needs evaluation_responses")

        else:
            evaluator = RuleBasedEvaluator()

        graph = build_workflow(saver, evaluator, PresetReviser())
        saved = graph.get_state(config)

        if args.command == "start":
            if saved.values:
                parser.error("This content ID already has a saved run")

            graph.invoke(
                {
                    "run_id": content_id,
                    "content_id": content_id,
                    "text": item.text,
                    "revised_text": item.revised_text,
                    "second_revised_text": item.second_revised_text,
                    "evaluation_result": None,
                    "evaluation_reason": None,
                    "revision_count": 0,
                    "max_revisions": args.max_revisions,
                    "status": "running",
                    "events": [],
                },
                config,
            )
            print("Checkpoint file:", DATABASE)

        elif args.command == "approve":
            if not saved.values:
                parser.error("No saved run with that content ID")

            if saved.values["status"] == "completed":
                message = "Already completed. Nothing was repeated."
            elif saved.values["status"] != "human_review":
                parser.error("This run is not waiting for approval")
            else:
                print("Loaded checkpoint. Current stage: HUMAN REVIEW")
                graph.invoke(Command(resume=True), config)

        elif args.command == "review":
            if not saved.values:
                parser.error("No saved run with that content ID")

            if saved.values["status"] != "human_review":
                parser.error(
                    "This run is not waiting for human review"
                )

            print("Loaded checkpoint. Current stage: HUMAN REVIEW")
            print("\n" + "=" * 60)
            print("  CONTENT TO REVIEW")
            print("=" * 60)
            print(textwrap.fill(saved.values["text"], width=76))
            print("=" * 60)

            answer = input(
                "\nApprove this content? [y/n]: "
            ).strip().lower()

            if answer not in ("y", "yes", "n", "no"):
                parser.error(
                    "Enter y or n; the run is still paused"
                )

            approved = answer in ("y", "yes")
            graph.invoke(Command(resume=approved), config)

        elif args.command == "show" and saved.values:
            print("Loaded checkpoint.")

        show(graph, content_id, message)


if __name__ == "__main__":
    main()