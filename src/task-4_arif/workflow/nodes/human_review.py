
from collections.abc import Callable

from langgraph.types import interrupt

from workflow.models.event import WorkflowEvent, WorkflowEventType
from workflow.models.state import WorkflowState
from workflow.ports.event_log import EventLogPort


def make_human_review_node(
    event_log: EventLogPort,
) -> Callable[[WorkflowState], dict]:
    """Pause workflow until a human approves the content."""

    def human_review_node(state: WorkflowState) -> dict:
        workflow_id = state["workflow_id"]

        event_log.append(
            WorkflowEvent.create(
                event_id=f"{workflow_id}:review:requested",
                workflow_id=workflow_id,
                event_type=WorkflowEventType.HUMAN_REVIEW_REQUESTED,
                payload={
                    "content_id": state["content"].content_id,
                    "revision_count": state["revision_count"],
                },
            )
        )

        approval = interrupt(
            {
                "workflow_id": workflow_id,
                "content_id": state["content"].content_id,
                "title": state["content"].title,
                "body": state["content"].body,
                "message": "Human approval required",
            }
        )

        if not isinstance(approval, dict) or approval.get("approved") is not True:
            raise ValueError("An explicit human approval is required")

        event_log.append(
            WorkflowEvent.create(
                event_id=f"{workflow_id}:approval",
                workflow_id=workflow_id,
                event_type=WorkflowEventType.APPROVAL_RECORDED,
                payload={"approved": True},
            )
        )

        return {
            "status": "awaiting_review",
        }

    return human_review_node