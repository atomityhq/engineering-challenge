
from collections.abc import Callable

from workflow.models.event import WorkflowEvent, WorkflowEventType
from workflow.models.state import WorkflowState
from workflow.ports.evaluator import EvaluatorPort
from workflow.ports.event_log import EventLogPort


def make_evaluate_node(
    evaluator: EvaluatorPort,
    event_log: EventLogPort,
) -> Callable[[WorkflowState], dict]:
    """Build an evaluation node with injected dependencies."""

    def evaluate_node(state: WorkflowState) -> dict:
        evaluation_index = state["evaluation_count"]

        result = evaluator.evaluate(
            content=state["content"],
            evaluation_index=evaluation_index,
        )

        event_log.append(
            WorkflowEvent.create(
                event_id=(
                    f"{state['workflow_id']}:evaluation:{evaluation_index}"
                ),
                workflow_id=state["workflow_id"],
                event_type=WorkflowEventType.CONTENT_EVALUATED,
                payload={
                    "evaluation_index": evaluation_index,
                    "decision": result.decision.value,
                    "reason": result.reason,
                },
            )
        )

        return {
            "evaluation": result,
            "evaluation_count": evaluation_index + 1,
            "status": "evaluating",
        }

    return evaluate_node