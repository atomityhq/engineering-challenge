"""StateGraph definition, routing conditions and the revision limit.

    START -> evaluate --revise & count < max--> revise -> evaluate
                      --revise & count >= max-> stop_max_revisions -> END
                      --human_review----------> request_review -> await_approval
                                                  (interrupt: checkpoint persisted)
                                                -> complete -> END
"""
from typing import Optional

from langgraph.graph import END, START, StateGraph

from workflow.config import WorkflowConfig
from workflow.evaluator import Evaluator, Reviser
from workflow.events import EventLog
from workflow.models import Decision, WorkflowState
from workflow.nodes import make_nodes


def make_router(config: WorkflowConfig):
    def route_after_evaluation(state: WorkflowState) -> str:
        if state.evaluation_result is None:
            raise ValueError("routing requires an evaluation result")
        if state.evaluation_result == Decision.REVISE:
            # Explicit, testable limit: revisions already done vs. the configured max.
            return "revise" if state.revision_count < config.max_revisions else "stop"
        return "human_review"

    return route_after_evaluation


def build_graph(evaluator: Evaluator, reviser: Reviser, events: EventLog,
                config: Optional[WorkflowConfig] = None, checkpointer=None):
    if checkpointer is None:
        raise ValueError("a checkpointer is required: human review pauses via interrupt()")
    config = config or WorkflowConfig()
    n = make_nodes(evaluator, reviser, events)

    g = StateGraph(WorkflowState)
    g.add_node("evaluate", n.evaluate)
    g.add_node("revise", n.revise)
    g.add_node("stop_max_revisions", n.stop_max_revisions)
    g.add_node("request_review", n.request_review)
    g.add_node("await_approval", n.await_approval)
    g.add_node("complete", n.complete)

    g.add_edge(START, "evaluate")
    g.add_conditional_edges("evaluate", make_router(config), {
        "revise": "revise",
        "human_review": "request_review",
        "stop": "stop_max_revisions",
    })
    g.add_edge("revise", "evaluate")
    g.add_edge("request_review", "await_approval")
    g.add_edge("await_approval", "complete")
    g.add_edge("complete", END)
    g.add_edge("stop_max_revisions", END)
    return g.compile(checkpointer=checkpointer)
