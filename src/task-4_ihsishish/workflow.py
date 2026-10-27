from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from data import WorkflowState
from steps import Evaluator, Reviser


def choose_next(state: WorkflowState) -> str:
    if state["evaluation_result"] == "human_review":
        return "review"
    if state["revision_count"] >= state["max_revisions"]:
        return "limit"
    return "revise"


def review(state: WorkflowState) -> dict:
    return {
        "status": "human_review",
        "events": state["events"] + [
            {
                "event": "human_review_required",
                "revision_count": state["revision_count"],
            }
        ],
    }


def limit(state: WorkflowState) -> dict:
    return {
        "status": "retry_limit",
        "events": state["events"] + [
            {
                "event": "revision_limit_reached",
                "revision_count": state["revision_count"],
            }
        ],
    }


def approve(state: WorkflowState) -> dict:
    approved = interrupt({
        "content_id": state["content_id"],
        "text": state["text"],
        "question": "Approve this content?",
    })

    if approved is not True:
        return {
            "status": "rejected",
            "events": state["events"] + [
                {
                    "event": "human_rejected",
                    "revision_count": state["revision_count"],
                }
            ],
        }

    return {
        "status": "completed",
        "events": state["events"] + [
            {
                "event": "human_approved",
                "revision_count": state["revision_count"],
            },
            {
                "event": "workflow_completed",
                "revision_count": state["revision_count"],
            },
        ],
    }


def build_workflow(checkpointer, evaluator: Evaluator, reviser: Reviser):
    def evaluate_node(state: WorkflowState) -> dict:
        result = evaluator.evaluate(state["text"])
        return {
            "evaluation_result": result.decision,
            "evaluation_reason": result.reason,
            "events": state["events"] + [
                {
                    "event": "evaluation_completed",
                    "revision_count": state["revision_count"],
                    "decision": result.decision,
                    "reason": result.reason,
                }
            ],
        }

    def revise_node(state: WorkflowState) -> dict:
        new_count = state["revision_count"] + 1

        prepared_text = state["revised_text"]
        if new_count == 2 and state.get("second_revised_text"):
            prepared_text = state["second_revised_text"]

        new_text = reviser.revise(state["text"], prepared_text)

        return {
            "text": new_text,
            "revision_count": new_count,
            "events": state["events"] + [
                {
                    "event": "revision_completed",
                    "revision_count": new_count,
                }
            ],
        }

    graph = StateGraph(WorkflowState)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("revise", revise_node)
    graph.add_node("review", review)
    graph.add_node("limit", limit)
    graph.add_node("approve", approve)

    graph.add_edge(START, "evaluate")
    graph.add_conditional_edges("evaluate", choose_next)
    graph.add_edge("revise", "evaluate")
    graph.add_edge("review", "approve")
    graph.add_edge("limit", END)
    graph.add_edge("approve", END)

    return graph.compile(checkpointer=checkpointer)	