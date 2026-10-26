"""LangGraph node functions, built around injected evaluator / reviser / event log.

IMPORTANT: a node that calls interrupt() re-executes from its start on resume.
`await_approval` therefore has NO side effects before interrupt(); the review
events live in `request_review` (runs once, before the pause) and `complete`.
"""
from types import SimpleNamespace

from langgraph.types import interrupt

from workflow.evaluator import Evaluator, Reviser
from workflow.events import EventLog
from workflow.models import Status, WorkflowState


def make_nodes(evaluator: Evaluator, reviser: Reviser, events: EventLog) -> SimpleNamespace:
    def evaluate(state: WorkflowState) -> dict:
        decision = evaluator.evaluate(state.content)
        events.append(state.run_id, "evaluation_completed", state.revision_count,
                      detail=decision.value)
        return {"evaluation_result": decision, "status": Status.EVALUATING}

    def revise(state: WorkflowState) -> dict:
        attempt = state.revision_count + 1
        events.append(state.run_id, "revision_requested", attempt)
        revised = reviser.revise(state.content, attempt)
        events.append(state.run_id, "revision_completed", attempt)
        return {"content": revised, "revision_count": attempt, "status": Status.REVISING}

    def stop_max_revisions(state: WorkflowState) -> dict:
        reason = f"maximum revision attempts reached ({state.revision_count})"
        events.append(state.run_id, "max_revisions_reached", state.revision_count, detail=reason)
        return {"status": Status.STOPPED, "stop_reason": reason}

    def request_review(state: WorkflowState) -> dict:
        events.append(state.run_id, "human_review_required", state.revision_count)
        return {"status": Status.HUMAN_REVIEW,
                "checkpoint_version": state.checkpoint_version + 1}

    def await_approval(state: WorkflowState) -> dict:
        # Pauses the graph; the checkpointer persists state at this boundary.
        # On resume, interrupt() returns the value passed via Command(resume=...).
        decision = interrupt({"run_id": state.run_id, "stage": "human_review",
                              "revision_count": state.revision_count})
        reviewer = decision.get("reviewer") if isinstance(decision, dict) else None
        return {"approved_by": reviewer or "reviewer"}

    def complete(state: WorkflowState) -> dict:
        # append_once + unique index: safe even if this node were retried.
        events.append_once(state.run_id, "human_approved", state.revision_count,
                           detail=state.approved_by)
        events.append_once(state.run_id, "workflow_completed", state.revision_count)
        return {"status": Status.COMPLETED}

    return SimpleNamespace(evaluate=evaluate, revise=revise,
                           stop_max_revisions=stop_max_revisions,
                           request_review=request_review,
                           await_approval=await_approval, complete=complete)
