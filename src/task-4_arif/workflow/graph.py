
from typing import Literal

from langgraph.graph import END, START, StateGraph

from workflow.models.evaluation import EvaluationDecision
from workflow.models.state import WorkflowState
from workflow.nodes import (
    make_complete_node,
    make_evaluate_node,
    make_human_review_node,
    make_revise_node,
    make_retry_limit_node,
)
from workflow.policies.revision import RevisionPolicy
from workflow.ports.evaluator import EvaluatorPort
from workflow.ports.event_log import EventLogPort
from workflow.ports.reviser import ReviserPort


Route = Literal["revise", "human_review", "retry_limit"]


def route_after_evaluation(
    state: WorkflowState,
    revision_policy: RevisionPolicy,
) -> Route:
    """Choose the next node from persisted state."""

    evaluation = state["evaluation"]

    if evaluation is None:
        raise ValueError("Cannot route without an evaluation")

    if evaluation.decision == EvaluationDecision.HUMAN_REVIEW:
        return "human_review"

    if evaluation.decision == EvaluationDecision.REVISE:
        if revision_policy.can_revise(state["revision_count"]):
            return "revise"

        return "retry_limit"

    raise ValueError(
        f"Unsupported evaluation decision: {evaluation.decision}"
    )


def build_workflow_graph(
    *,
    evaluator: EvaluatorPort,
    reviser: ReviserPort,
    event_log: EventLogPort,
    checkpointer,
    revision_policy: RevisionPolicy | None = None,
):
    """Build and compile the resumable review workflow."""

    policy = (
        revision_policy
        if revision_policy is not None
        else RevisionPolicy()
    )

    builder = StateGraph(WorkflowState)

    builder.add_node(
        "evaluate",
        make_evaluate_node(evaluator, event_log),
    )
    builder.add_node(
        "revise",
        make_revise_node(reviser, event_log, policy),
    )
    builder.add_node(
        "human_review",
        make_human_review_node(event_log),
    )
    builder.add_node(
        "complete",
        make_complete_node(event_log),
    )
    builder.add_node(
        "retry_limit",
        make_retry_limit_node(event_log),
    )

    builder.add_edge(START, "evaluate")

    builder.add_conditional_edges(
        "evaluate",
        lambda state: route_after_evaluation(state, policy),
        {
            "revise": "revise",
            "human_review": "human_review",
            "retry_limit": "retry_limit",
        },
    )

    builder.add_edge("revise", "evaluate")
    builder.add_edge("human_review", "complete")
    builder.add_edge("complete", END)
    builder.add_edge("retry_limit", END)

    return builder.compile(checkpointer=checkpointer)
