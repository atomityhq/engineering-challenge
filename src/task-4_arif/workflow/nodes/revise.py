
from collections.abc import Callable

from workflow.models.event import WorkflowEvent, WorkflowEventType
from workflow.models.state import WorkflowState
from workflow.policies.revision import RevisionPolicy
from workflow.ports.event_log import EventLogPort
from workflow.ports.reviser import ReviserPort


def make_revise_node(
    reviser: ReviserPort,
    event_log: EventLogPort,
    revision_policy: RevisionPolicy,
) -> Callable[[WorkflowState], dict]:
    """Build a revision node with injected dependencies."""

    def revise_node(state: WorkflowState) -> dict:
        if not revision_policy.can_revise(state["revision_count"]):
            raise ValueError("Revision limit reached")

        evaluation = state["evaluation"]

        if evaluation is None:
            raise ValueError("Cannot revise without an evaluation")

        revision_number = state["revision_count"] + 1

        revised_content = reviser.revise(
            content=state["content"],
            evaluation=evaluation,
            revision_number=revision_number,
        )

        event_log.append(
            WorkflowEvent.create(
                event_id=(
                    f"{state['workflow_id']}:revision:{revision_number}"
                ),
                workflow_id=state["workflow_id"],
                event_type=WorkflowEventType.CONTENT_REVISED,
                payload={
                    "revision_number": revision_number,
                    "content_id": revised_content.content_id,
                },
            )
        )

        return {
            "content": revised_content,
            "revision_count": revision_number,
            "status": "revising",
        }

    return revise_node