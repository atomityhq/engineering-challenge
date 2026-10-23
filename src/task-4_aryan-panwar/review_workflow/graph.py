"""LangGraph definition: state, nodes, routing conditions and terminal states.

    START -> evaluate --revise (count < max)--> revise -> evaluate
                     --revise (count = max)--> stop_revision_limit -> END
                     --human_review---------> request_review -> await_review (interrupt)
    await_review --approve--> complete -> END
                 --reject---> reject   -> END
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .fakes import Evaluator, Reviser
from .models import ContentItem, EvaluationResult, HumanDecision


class WorkflowState(TypedDict):
    run_id: str
    content_id: str
    content: dict
    evaluator_ref: str
    max_revisions: int
    status: str
    revision_count: int
    evaluation_result: dict | None
    review: dict | None
    # Append-only; stored inside the checkpoint so the log can never disagree with the state.
    events: Annotated[list[dict], operator.add]


def _events(state: WorkflowState, *items: tuple[str, int, dict]) -> list[dict]:
    start = len(state["events"])
    return [
        {"seq": start + i, "event": name, "revision_count": count, "detail": detail}
        for i, (name, count, detail) in enumerate(items)
    ]


def build_graph(evaluator_factory: Callable[[str], Evaluator], reviser: Reviser) -> StateGraph:
    def evaluate(state: WorkflowState) -> dict[str, Any]:
        content = ContentItem.model_validate(state["content"])
        count = state["revision_count"]
        evaluator = evaluator_factory(state["evaluator_ref"])
        # Validate evaluator output even from the fake: a real model could return anything.
        result = EvaluationResult.model_validate(evaluator.evaluate(content, count), from_attributes=True)
        return {
            "status": "evaluating",
            "evaluation_result": result.model_dump(),
            "events": _events(
                state,
                ("evaluation_completed", count, {"decision": result.decision, "feedback": result.feedback}),
            ),
        }

    def route_after_evaluation(state: WorkflowState) -> str:
        if state["evaluation_result"]["decision"] == "human_review":
            return "request_review"
        if state["revision_count"] < state["max_revisions"]:
            return "revise"
        return "stop_revision_limit"

    def revise(state: WorkflowState) -> dict[str, Any]:
        attempt = state["revision_count"] + 1
        feedback = state["evaluation_result"]["feedback"]
        revised = reviser.revise(ContentItem.model_validate(state["content"]), feedback, attempt)
        return {
            "status": "revising",
            "content": ContentItem.model_validate(revised, from_attributes=True).model_dump(),
            "revision_count": attempt,
            "events": _events(state, ("revision_completed", attempt, {"attempt": attempt, "feedback": feedback})),
        }

    def stop_revision_limit(state: WorkflowState) -> dict[str, Any]:
        count = state["revision_count"]
        return {
            "status": "stopped_revision_limit",
            "events": _events(
                state,
                ("revision_limit_reached", count, {"max_revisions": state["max_revisions"]}),
                ("workflow_stopped", count, {"reason": "evaluator still requested revision after the maximum number of revisions"}),
            ),
        }

    def request_review(state: WorkflowState) -> dict[str, Any]:
        # Kept separate from await_review: LangGraph re-runs an interrupted node from its
        # start on resume, so nothing with a side effect may sit before interrupt().
        return {
            "status": "awaiting_review",
            "events": _events(state, ("human_review_required", state["revision_count"], {})),
        }

    def await_review(state: WorkflowState) -> dict[str, Any]:
        raw = interrupt({"run_id": state["run_id"], "content_id": state["content_id"], "expects": "approve | reject"})
        decision = HumanDecision.model_validate(raw)
        name = "human_approved" if decision.decision == "approve" else "human_rejected"
        return {
            "review": decision.model_dump(),
            "events": _events(state, (name, state["revision_count"], decision.model_dump(exclude_none=True))),
        }

    def route_after_review(state: WorkflowState) -> str:
        return "complete" if state["review"]["decision"] == "approve" else "reject"

    def complete(state: WorkflowState) -> dict[str, Any]:
        return {"status": "completed", "events": _events(state, ("workflow_completed", state["revision_count"], {}))}

    def reject(state: WorkflowState) -> dict[str, Any]:
        return {"status": "rejected", "events": _events(state, ("workflow_rejected", state["revision_count"], {}))}

    g = StateGraph(WorkflowState)
    for node in (evaluate, revise, stop_revision_limit, request_review, await_review, complete, reject):
        g.add_node(node.__name__, node)
    g.add_edge(START, "evaluate")
    g.add_conditional_edges("evaluate", route_after_evaluation, ["revise", "request_review", "stop_revision_limit"])
    g.add_edge("revise", "evaluate")
    g.add_edge("request_review", "await_review")
    g.add_conditional_edges("await_review", route_after_review, ["complete", "reject"])
    g.add_edge("stop_revision_limit", END)
    g.add_edge("complete", END)
    g.add_edge("reject", END)
    return g
