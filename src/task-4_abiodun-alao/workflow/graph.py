from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .components import Evaluator, Reviser
from .events import EventLog
from .models import Decision, ReviewDecision, Status, WorkflowState


def build_graph(evaluator: Evaluator, reviser: Reviser, events: EventLog, checkpointer: BaseCheckpointSaver):

    def evaluate(state: WorkflowState) -> dict:
        attempt = state.evaluation_count + 1
        result = evaluator.evaluate(state.content, attempt)
        events.record(
            state.run_id, "evaluation_completed", key=f"evaluation:{attempt}",
            attempt=attempt, revision_count=state.revision_count,
            decision=result.decision.value, reasons=result.reasons,
        )
        return {"last_evaluation": result, "evaluation_count": attempt}

    def revise(state: WorkflowState) -> dict:
        attempt = state.revision_count + 1
        feedback = state.last_evaluation.reasons if state.last_evaluation else []
        events.record(state.run_id, "revision_requested", key=f"revision_requested:{attempt}",
                      revision_count=attempt, feedback=feedback)
        revised = reviser.revise(state.content, feedback, attempt)
        events.record(state.run_id, "revision_completed", key=f"revision:{attempt}", revision_count=attempt)
        return {"content": revised, "revision_count": attempt}

    def revision_limit_reached(state: WorkflowState) -> dict:
        reason = (f"Evaluator still requested revision after {state.max_revisions} "
                  f"revision attempt(s) ({state.evaluation_count} evaluations)")
        events.record(state.run_id, "revision_limit_reached", key="terminal",
                      revision_count=state.revision_count, max_revisions=state.max_revisions, reason=reason)
        return {"status": Status.REVISION_LIMIT_REACHED, "stop_reason": reason}

    def request_review(state: WorkflowState) -> dict:
        version = state.checkpoint_version + 1
        events.record(state.run_id, "human_review_required", key=f"review_required:{version}",
                      revision_count=state.revision_count, checkpoint_version=version,
                      reasons=state.last_evaluation.reasons if state.last_evaluation else [])
        return {"status": Status.AWAITING_REVIEW, "checkpoint_version": version}

    def human_review(state: WorkflowState) -> dict:
        answer = interrupt({"run_id": state.run_id, "content_id": state.content.content_id,
                            "question": "Approve or reject this content?"})
        review = ReviewDecision.model_validate(answer)
        approved = review.decision == "approve"
        events.record(state.run_id, "human_approved" if approved else "human_rejected",
                      key=f"review_decision:{state.checkpoint_version}",
                      reviewer=review.reviewer, note=review.note)
        return {"review": review, "status": Status.RUNNING if approved else Status.REJECTED,
                "stop_reason": None if approved else f"Rejected by {review.reviewer}"}

    def complete(state: WorkflowState) -> dict:
        events.record(state.run_id, "workflow_completed", key="completed",
                      revision_count=state.revision_count, approved_by=state.review.reviewer if state.review else None)
        return {"status": Status.COMPLETED}

    # ── Routing: pure functions that read the state and name the next node ──

    def route_after_evaluation(state: WorkflowState) -> Literal["request_review", "revise", "revision_limit_reached"]:
        if state.last_evaluation and state.last_evaluation.decision == Decision.HUMAN_REVIEW:
            return "request_review"
        if state.revision_count < state.max_revisions:
            return "revise"
        return "revision_limit_reached"

    def route_after_review(state: WorkflowState) -> Literal["complete", "__end__"]:
        return "complete" if state.status == Status.RUNNING else END

    # ── Wiring ──
    graph = StateGraph(WorkflowState)
    graph.add_node("evaluate", evaluate)
    graph.add_node("revise", revise)
    graph.add_node("revision_limit_reached", revision_limit_reached)
    graph.add_node("request_review", request_review)
    graph.add_node("human_review", human_review)
    graph.add_node("complete", complete)

    graph.add_edge(START, "evaluate")
    graph.add_conditional_edges("evaluate", route_after_evaluation)
    graph.add_edge("revise", "evaluate")
    graph.add_edge("request_review", "human_review")
    graph.add_conditional_edges("human_review", route_after_review)
    graph.add_edge("complete", END)
    graph.add_edge("revision_limit_reached", END)

    return graph.compile(checkpointer=checkpointer)