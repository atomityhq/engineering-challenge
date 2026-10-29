"""The LangGraph workflow: nodes, routing, the human-review pause, and run helpers.

    evaluate ──► revise ──► evaluate ...          (while revision_count < max_revisions)
        │
        ├──► limit_reached ──► END                (revise asked, limit used up)
        └──► request_review ──► human_review ──► complete ──► END
                                   (interrupt)
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, StateSnapshot, interrupt

from .fakes import Evaluator, Reviser
from .models import DEFAULT_MAX_REVISIONS, ContentItem, WorkflowState
from .store import EventLog

APPROVE = "approve"

# start_run and approve_run pass durability="sync": each checkpoint is written before
# the next step starts, so a crash loses at most the step that was running. That step
# runs again on resume, and its event is not logged twice (same op_key).


class UnknownRunError(LookupError):
    """No saved run has this run id."""


class RunExistsError(ValueError):
    """A run with this run id already exists."""


class NotWaitingForReviewError(RuntimeError):
    """The run is not paused at human review, so it cannot be approved."""


def _item(state: WorkflowState) -> ContentItem:
    return ContentItem(content_id=state["content_id"], title=state["title"], body=state["body"])


def route_after_evaluate(state: WorkflowState) -> str:
    if state["decision"] == "human_review":
        return "request_review"
    if state["revision_count"] < state["max_revisions"]:
        return "revise"
    return "limit_reached"


def build_graph(
    evaluator: Evaluator,
    reviser: Reviser,
    events: EventLog,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    def evaluate(state: WorkflowState) -> dict[str, Any]:
        step = state["revision_count"]
        result = evaluator.evaluate(_item(state), step)
        events.record(
            state["run_id"], f"evaluate:{step}", "evaluation_completed",
            decision=result.decision, reason=result.reason, revision_count=step,
        )
        return {"decision": result.decision, "reason": result.reason, "status": "EVALUATING"}

    def revise(state: WorkflowState) -> dict[str, Any]:
        step = state["revision_count"]
        revised = reviser.revise(_item(state), step)
        if revised.body == state["body"]:
            raise ValueError(f"revision {step + 1} did not change the content")
        count = step + 1
        events.record(state["run_id"], f"revise:{count}", "revision_completed", revision_count=count)
        return {"body": revised.body, "revision_count": count}

    def limit_reached(state: WorkflowState) -> dict[str, Any]:
        events.record(
            state["run_id"], "limit_reached", "revision_limit_reached",
            reason="max_revisions_reached",
            revision_count=state["revision_count"], max_revisions=state["max_revisions"],
        )
        return {"status": "REVISION_LIMIT_REACHED"}

    def request_review(state: WorkflowState) -> dict[str, Any]:
        # Logged here, not in human_review: LangGraph runs human_review again from its
        # first line on resume, so anything before interrupt() there would run twice.
        events.record(
            state["run_id"], "review_requested", "human_review_required",
            revision_count=state["revision_count"],
        )
        return {"status": "WAITING_FOR_REVIEW"}

    def human_review(state: WorkflowState) -> dict[str, Any]:
        decision = interrupt(
            {
                "run_id": state["run_id"],
                "content_id": state["content_id"],
                "title": state["title"],
                "body": state["body"],
                "revision_count": state["revision_count"],
                "reason": state["reason"],
            }
        )
        if decision != APPROVE:
            raise ValueError(f"unknown review decision: {decision!r}")
        events.record(state["run_id"], "approved", "human_approved")
        return {}

    def complete(state: WorkflowState) -> dict[str, Any]:
        events.record(state["run_id"], "completed", "workflow_completed")
        return {"status": "COMPLETED"}

    g = StateGraph(WorkflowState)
    g.add_node("evaluate", evaluate)
    g.add_node("revise", revise)
    g.add_node("limit_reached", limit_reached)
    g.add_node("request_review", request_review)
    g.add_node("human_review", human_review)
    g.add_node("complete", complete)

    g.add_edge(START, "evaluate")
    g.add_conditional_edges("evaluate", route_after_evaluate, ["revise", "request_review", "limit_reached"])
    g.add_edge("revise", "evaluate")
    g.add_edge("request_review", "human_review")
    g.add_edge("human_review", "complete")
    g.add_edge("limit_reached", END)
    g.add_edge("complete", END)
    return g.compile(checkpointer=checkpointer)


def _config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def is_waiting_for_review(snapshot: StateSnapshot) -> bool:
    """True only when the saved state has a real pending interrupt at human_review."""
    return snapshot.next == ("human_review",) and any(task.interrupts for task in snapshot.tasks)


def initial_state(
    run_id: str, item: ContentItem, scenario_id: str, max_revisions: int = DEFAULT_MAX_REVISIONS
) -> WorkflowState:
    return {
        "run_id": run_id,
        "content_id": item.content_id,
        "scenario_id": scenario_id,
        "title": item.title,
        "body": item.body,
        "revision_count": 0,
        "max_revisions": max_revisions,
        "decision": None,
        "reason": None,
        "status": "EVALUATING",
    }


def start_run(graph: CompiledStateGraph, events: EventLog, state: WorkflowState) -> StateSnapshot:
    """Run a new workflow until it pauses at human review or ends."""
    run_id = state["run_id"]
    config = _config(run_id)
    if graph.get_state(config).values:
        raise RunExistsError(f"run {run_id!r} already exists")

    graph.invoke(state, config, durability="sync")
    snapshot = graph.get_state(config)
    if is_waiting_for_review(snapshot):
        events.record(run_id, "checkpoint_saved", "checkpoint_saved", stage="human_review")
    return snapshot


def approve_run(graph: CompiledStateGraph, events: EventLog, run_id: str) -> str:
    """Approve a paused run. Returns "completed", or "already_completed" with no changes."""
    config = _config(run_id)
    snapshot = graph.get_state(config)
    if not snapshot.values:
        raise UnknownRunError(f"no run with id {run_id!r}")
    if snapshot.values["status"] == "COMPLETED":
        return "already_completed"
    if not is_waiting_for_review(snapshot):
        raise NotWaitingForReviewError(
            f"run {run_id!r} is {snapshot.values['status']}, not waiting for review"
        )

    events.record(run_id, "checkpoint_loaded", "checkpoint_loaded", stage="human_review")
    graph.invoke(Command(resume=APPROVE), config, durability="sync")
    return "completed"
