
import argparse
import json

from pydantic import ValidationError
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from workflow.graph import build_workflow
from workflow.event_logger import EventLogger
from workflow.models import WorkflowInput, EventRecord

CHECKPOINT_DB = "workflow_checkpoints.sqlite"
EVENT_DB = "workflow_events.sqlite"


def create_serializer():
    return JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("workflow.models", "ContentItem"),
            ("workflow.models", "EvaluationResult"),
        ]
    )


def get_config(workflow_id: str):
    return {
        "configurable": {
            "thread_id": workflow_id
        }
    }


def start_workflow(input_path: str):
    try:
        with open(input_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        workflow_input = WorkflowInput.model_validate(data)

    except (FileNotFoundError, json.JSONDecodeError, ValidationError) as error:
        print(f"Erro ao carregar os dados: {error}")
        return

    with (
        SqliteSaver.from_conn_string(CHECKPOINT_DB) as checkpointer,
        EventLogger(EVENT_DB) as logger
    ):
        checkpointer.serde = create_serializer()

        graph = build_workflow(
            checkpointer=checkpointer,
            event_logger=logger,
        )

        initial_state = {
            "workflow_id": workflow_input.workflow_id,
            "content": workflow_input.content,
            "evaluation": None,
            "revision_count": 0,
            "status": "running",
        }

        config = get_config(workflow_input.workflow_id)

        result = graph.invoke(initial_state, config=config)

        if result["status"] == "awaiting_human_review":
            logger.log(
                EventRecord(
                    workflow_id=workflow_input.workflow_id,
                    event_type="checkpoint_saved",
                    details={
                        "status": result["status"],
                        "next_step": "human_review",
                    },
                ),
                event_key="checkpoint_saved",
            )

        print(json.dumps(
            {
                "workflow_id": workflow_input.workflow_id,
                "status": result["status"],
                "revision_count": result["revision_count"],
                "content": result["content"].model_dump(),
            },
            indent=4,
            ensure_ascii=False,
        ))


def approve_workflow(workflow_id: str):
    with (
        SqliteSaver.from_conn_string(CHECKPOINT_DB) as checkpointer,
        EventLogger(EVENT_DB) as logger
    ):
        checkpointer.serde = create_serializer()

        graph = build_workflow(
            checkpointer=checkpointer,
            event_logger=logger,
        )

        config = get_config(workflow_id)
        snapshot = graph.get_state(config)

        if not snapshot.values:
            print("Workflow não encontrado.")
            return

        current_status = snapshot.values.get("status")

        if current_status == "completed":
            print(
                "Este workflow já foi concluído. "
                "Nenhuma acção duplicada foi executada."
            )
            return

        if current_status != "awaiting_human_review":
            print(
                "Este workflow não está à espera de aprovação. "
                f"Estado: {current_status}"
            )
            return

        result = graph.invoke(
            Command(resume="approve"),
            config=config,
        )

        print(f"Workflow {workflow_id}: {result['status']}")


def show_status(workflow_id: str):
    with SqliteSaver.from_conn_string(CHECKPOINT_DB) as checkpointer:
        checkpointer.serde = create_serializer()

        graph = build_workflow(checkpointer=checkpointer)

        config = get_config(workflow_id)
        snapshot = graph.get_state(config)

        if not snapshot.values:
            print("Workflow não encontrado.")
            return

        print(json.dumps(
            {
                "workflow_id": workflow_id,
                "status": snapshot.values.get("status"),
                "revision_count": snapshot.values.get("revision_count"),
                "next": list(snapshot.next),
            },
            indent=4,
            ensure_ascii=False,
            default=str,
        ))


def main():
    parser = argparse.ArgumentParser(
        description="Resumable Review Workflow CLI"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--input", required=True)

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--workflow-id", required=True)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--workflow-id", required=True)

    args = parser.parse_args()

    if args.command == "start":
        start_workflow(args.input)

    elif args.command == "approve":
        approve_workflow(args.workflow_id)

    elif args.command == "status":
        show_status(args.workflow_id)


if __name__ == "__main__":
    main()
