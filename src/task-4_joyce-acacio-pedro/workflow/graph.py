from typing import TypedDict
from workflow.models import ContentItem, EvaluationResult
from workflow.nodes import evaluate_content, revise_content
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver
from workflow.event_logger import EventLogger
from workflow.models import EventRecord







class WorkflowState(TypedDict):
    workflow_id: str
    content: ContentItem
    evaluation: EvaluationResult | None
    revision_count: int
    status: str


def evaluation_node(state: WorkflowState, event_logger=None) -> dict:
    result = evaluate_content(state["content"])

    if event_logger:
        event_logger.log(
            EventRecord(
                workflow_id=state["workflow_id"],
                event_type="evaluation_completed",
                details={
                    "decision": result.decision,
                    "score": result.score,
                    "feedback": result.feedback,
                    "attempt": state["revision_count"],
                },
            ),
            event_key=f"evaluation_completed:{state['revision_count']}",
        )

    status = (
        "awaiting_human_review"
        if result.decision == "human_review"
        else "evaluated"
    )

    return {
        "evaluation": result,
        "status": status,
    }


def revision_node(state: WorkflowState, event_logger=None) -> dict:
    revised_content = revise_content(state["content"])
    new_revision_count = state["revision_count"] + 1

    if event_logger:
        event_logger.log(
            EventRecord(
                workflow_id=state["workflow_id"],
                event_type="revision_requested",
                details={
                    "revision_number": new_revision_count,
                    "feedback": state["evaluation"].feedback,
                },
            ),
            event_key=f"revision_requested:{new_revision_count}",
        )

    return {
        "content": revised_content,
        "revision_count": new_revision_count,
        "status": "revised",
    }


def route_after_evaluation(state: WorkflowState) -> str:
    evaluation = state["evaluation"]

    if evaluation is None:
        raise ValueError("The workflow has no evaluation result.")

    if evaluation.decision == "pass":
        return "complete"

    if evaluation.decision == "human_review":
        return "human_review"

    if evaluation.decision == "revise":
        if state["revision_count"] >= 2:
            return "revision_limit_reached"

        return "revise"

    raise ValueError("Unknown evaluation decision.")


def complete_node(state: WorkflowState, event_logger=None) -> dict:
    if event_logger:
        event_logger.log(
            EventRecord(
                workflow_id=state["workflow_id"],
                event_type="workflow_completed",
                details={
                    "content_id": state["content"].content_id,
                    "revision_count": state["revision_count"],
                },
            ),
            event_key="workflow_completed",
        )

    return {"status": "completed"}


def human_review_node(state: WorkflowState, event_logger=None) -> dict:
    content_id = state["content"].content_id

    if event_logger:
        event_logger.log(
            EventRecord(
                workflow_id=state["workflow_id"],
                event_type="human_review_required",
                details={
                    "content_id": content_id,
                    "feedback": state["evaluation"].feedback,
                },
            ),
            event_key=f"human_review_required:{content_id}",
        )

    approval = interrupt({
        "message": "This content requires human approval.",
        "workflow_id": state["workflow_id"],
        "content": state["content"].model_dump(),
    })

    if approval != "approve":
        raise ValueError("The content was not approved.")

    if event_logger:
        event_logger.log(
            EventRecord(
                workflow_id=state["workflow_id"],
                event_type="human_approved",
                details={
                    "content_id": content_id,
                },
            ),
            event_key=f"human_approved:{content_id}",
        )

    return {"status": "approved"}

def revision_limit_node(state: WorkflowState) -> dict:
    return {
        "status": "revision_limit_reached",
    }


def build_workflow(checkpointer=None, event_logger=None):
    builder = StateGraph(WorkflowState)

    # Register nodes
    builder.add_node(
    "evaluate",
    lambda state: evaluation_node(state, event_logger)
    )
    builder.add_node(
    "revise",
    lambda state: revision_node(state, event_logger)
    )
    builder.add_node(
    "complete",
    lambda state: complete_node(state, event_logger)
)
    builder.add_node(
    "human_review",
    lambda state: human_review_node(state, event_logger)
    )
    builder.add_node("revision_limit_reached", revision_limit_node)

    # Define the starting point
    builder.add_edge(START, "evaluate")

    # Define conditional routing after evaluation
    builder.add_conditional_edges(
        "evaluate",
        route_after_evaluation,
        {
            "complete": "complete",
            "human_review": "human_review",
            "revise": "revise",
            "revision_limit_reached": "revision_limit_reached",
        },
    )

    # After revision, evaluate the content again
    builder.add_edge("revise", "evaluate")

    # Define terminal nodes
    builder.add_edge("complete", END)
    builder.add_edge("human_review", "complete")
    builder.add_edge("revision_limit_reached", END)

    return builder.compile(checkpointer=checkpointer)