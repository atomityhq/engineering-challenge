
from collections.abc import Callable

from workflow.models.event import WorkflowEvent, WorkflowEventType
from workflow.models.state import WorkflowState
from workflow.ports.event_log import EventLogPort


def make_retry_limit_node(
    event_log: EventLogPort,
) -> Callable[[WorkflowState], dict]:
    """Record that no further revisions are permitted."""

    def retry_limit_node(state: WorkflowState) -> dict:
        workflow_id = state["workflow_id"]

        event_log.append(
            WorkflowEvent.create(
                event_id=f"{workflow_id}:retry_limit",
                workflow_id=workflow_id,
                event_type=WorkflowEventType.RETRY_LIMIT_REACHED,
                payload={
                    "revision_count": state["revision_count"],
                    "evaluation_count": state["evaluation_count"],
                },
            )
        )

        return {"status": "retry_limit_reached"}

    return retry_limit_node