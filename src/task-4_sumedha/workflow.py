from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from evaluator import FakeEvaluator
from models import ContentInput, WorkflowState


DEFAULT_MAX_REVISIONS = 2


def create_initial_state(
    run_id: str,
    content: ContentInput,
    max_revisions: int = DEFAULT_MAX_REVISIONS,
) -> WorkflowState:
    if max_revisions < 0:
        raise ValueError("max_revisions must not be negative")

    return {
        "run_id": run_id,
        "content": content,
        "evaluation_decision": None,
        "evaluation_reason": None,
        "revision_count": 0,
        "max_revisions": max_revisions,
        "status": "pending",
        "human_approved": None,
        "event_log": [],
    }


def revise(state: WorkflowState) -> dict:
    revision_count = state["revision_count"] + 1
    content = ContentInput(
        content_id=state["content"].content_id,
        text=f'{state["content"].text}\n\nRevision {revision_count}',
    )
    return {
        "content": content,
        "evaluation_decision": None,
        "evaluation_reason": None,
        "revision_count": revision_count,
        "status": "revising",
        "event_log": [
            *state["event_log"],
            f"revision: completed attempt {revision_count}",
        ],
    }


def prepare_human_review(state: WorkflowState) -> dict:
    return {
        "status": "awaiting_human_review",
        "human_approved": None,
        "event_log": [*state["event_log"], "human_review: awaiting approval"],
    }


def human_review(state: WorkflowState) -> dict:
    approved = interrupt(
        {
            "type": "human_review",
            "run_id": state["run_id"],
            "content_id": state["content"].content_id,
            "message": "Approve this content to complete the workflow.",
        },
        response_schema=bool,
    )
    outcome = "approved" if approved else "not approved"
    return {
        "human_approved": approved,
        "event_log": [*state["event_log"], f"human_review: {outcome}"],
    }


def complete(state: WorkflowState) -> dict:
    if state["status"] == "completed":
        return {}

    completion_event = "workflow: completed"
    event_log = state["event_log"]
    if completion_event not in event_log:
        event_log = [*event_log, completion_event]
    return {"status": "completed", "event_log": event_log}


def retry_limit_reached(state: WorkflowState) -> dict:
    return {
        "status": "retry_limit_reached",
        "event_log": [
            *state["event_log"],
            f"retry_limit_reached: maximum of {state['max_revisions']} revisions",
        ],
    }


def route_from_start(state: WorkflowState) -> Literal["evaluate", "stop"]:
    if state["status"] in {
        "awaiting_human_review",
        "retry_limit_reached",
        "completed",
    }:
        return "stop"
    return "evaluate"


def route_after_evaluation(
    state: WorkflowState,
) -> Literal["revise", "prepare_human_review", "retry_limit_reached"]:
    if state["evaluation_decision"] == "human_review":
        return "prepare_human_review"
    if state["revision_count"] >= state["max_revisions"]:
        return "retry_limit_reached"
    return "revise"


def route_after_human_review(
    state: WorkflowState,
) -> Literal["complete", "review_again"]:
    return "complete" if state["human_approved"] else "review_again"


def resume_after_review(approved: bool = True) -> Command:
    return Command(resume=approved)


def build_workflow(
    evaluator: FakeEvaluator,
    checkpointer: BaseCheckpointSaver | None = None,
):
    def evaluate(state: WorkflowState) -> dict:
        decision = evaluator.evaluate(
            state["content"],
            evaluation_index=state["revision_count"],
        )
        return {
            "evaluation_decision": decision,
            "evaluation_reason": f"fake evaluator requested {decision}",
            "status": "evaluating",
            "event_log": [*state["event_log"], f"evaluation: {decision}"],
        }

    graph = StateGraph(WorkflowState)
    graph.add_node("evaluate", evaluate)
    graph.add_node("revise", revise)
    graph.add_node("prepare_human_review", prepare_human_review)
    graph.add_node("human_review", human_review)
    graph.add_node("complete", complete)
    graph.add_node("retry_limit_reached", retry_limit_reached)

    graph.add_conditional_edges(
        START,
        route_from_start,
        {"evaluate": "evaluate", "stop": END},
    )
    graph.add_conditional_edges("evaluate", route_after_evaluation)
    graph.add_edge("revise", "evaluate")
    graph.add_edge("prepare_human_review", "human_review")
    graph.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {"complete": "complete", "review_again": "human_review"},
    )
    graph.add_edge("complete", END)
    graph.add_edge("retry_limit_reached", END)
    return graph.compile(checkpointer=checkpointer)
