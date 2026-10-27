
from collections.abc import Callable

from workflow.models.event import WorkflowEvent, WorkflowEventType
from workflow.models.state import WorkflowState
from workflow.ports.event_log import EventLogPort


def make_complete_node(
    event_log: EventLogPort,
) -> Callable[[WorkflowState], dict]:
    """Build a node that finalizes an approved workflow."""

    def complete_node(state: WorkflowState) -> dict:
        workflow_id = state["workflow_id"]

        approval_event = event_log.get_event(
            f"{workflow_id}:approval"
        )

        if approval_event is None:
            raise ValueError(
                "Cannot complete workflow without human approval"
            )

        if (
            approval_event.workflow_id != workflow_id
            or approval_event.event_type
            != WorkflowEventType.APPROVAL_RECORDED
            or approval_event.payload.get("approved") is not True
        ):
            raise ValueError(
                "Cannot complete workflow without valid human approval"
            )

        event_log.append(
            WorkflowEvent.create(
                event_id=f"{workflow_id}:completed",
                workflow_id=workflow_id,
                event_type=WorkflowEventType.WORKFLOW_COMPLETED,
                payload={
                    "content_id": state["content"].content_id,
                    "revision_count": state["revision_count"],
                    "evaluation_count": state["evaluation_count"],
                },
            )
        )

        return {
            "status": "completed",
        }

    return complete_node