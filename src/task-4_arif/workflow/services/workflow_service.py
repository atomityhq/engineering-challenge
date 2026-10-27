
from typing import Any

from langgraph.types import Command

from workflow.models.content import ContentItem
from workflow.models.event import WorkflowEvent, WorkflowEventType
from workflow.models.state import WorkflowState
from workflow.ports.event_log import EventLogPort


class WorkflowNotFoundError(Exception):
    """The requested workflow does not exist."""


class WorkflowConflictError(Exception):
    """The requested operation conflicts with workflow state."""


class WorkflowService:
    """Application service for starting and resuming workflows."""

    def __init__(
        self,
        *,
        graph: Any,
        event_log: EventLogPort,
    ) -> None:
        self._graph = graph
        self._event_log = event_log

    @staticmethod
    def _config(workflow_id: str) -> dict:
        """Build a stable LangGraph checkpoint configuration."""
        return {
            "configurable": {
                "thread_id": workflow_id,
            }
        }

    def _snapshot(self, workflow_id: str):
        """Retrieve the latest persisted LangGraph checkpoint."""
        return self._graph.get_state(
            self._config(workflow_id)
        )

    @staticmethod
    def _state_from_snapshot(
        snapshot,
    ) -> WorkflowState | None:
        """
        Return persisted state with its effective workflow status.

        An interrupted human_review node has not returned a state
        update yet. LangGraph records the pending node in
        snapshot.next, which identifies the review checkpoint.
        """
        if not snapshot.values:
            return None

        state = dict(snapshot.values)

        if snapshot.next == ("human_review",):
            state["status"] = "awaiting_review"

        return state

    def _existing_state(
        self,
        workflow_id: str,
    ) -> WorkflowState | None:
        """Return the current workflow state, if it exists."""
        snapshot = self._snapshot(workflow_id)
        return self._state_from_snapshot(snapshot)

    def _validate_duplicate_start(
        self,
        *,
        workflow_id: str,
        content: ContentItem,
    ) -> None:
        """
        Ensure a repeated start uses the original content.

        Compare against the workflow_started event rather than the
        current checkpoint content, which may have been revised.
        """
        started_event = self._event_log.get_event(
            f"{workflow_id}:started"
        )

        if started_event is None:
            raise WorkflowConflictError(
                "Existing workflow has no start event"
            )

        if started_event.event_type != WorkflowEventType.WORKFLOW_STARTED:
            raise WorkflowConflictError(
                "Existing workflow has an invalid start event"
            )

        original_content = started_event.payload.get(
            "original_content"
        )

        if original_content is None:
            raise WorkflowConflictError(
                "Existing workflow has no original request data"
            )

        if original_content != content.model_dump(mode="json"):
            raise WorkflowConflictError(
                "Workflow ID already belongs to a different request"
            )

    def start(
        self,
        *,
        workflow_id: str,
        content: ContentItem,
    ) -> WorkflowState:
        """
        Start a new workflow or return its existing state.

        Repeated requests are accepted only when their original
        content matches exactly.
        """
        if not workflow_id.strip():
            raise ValueError(
                "workflow_id cannot be blank"
            )

        existing = self._existing_state(workflow_id)

        if existing is not None:
            self._validate_duplicate_start(
                workflow_id=workflow_id,
                content=content,
            )
            return existing

        initial_state: WorkflowState = {
            "workflow_id": workflow_id,
            "content": content,
            "evaluation": None,
            "evaluation_count": 0,
            "revision_count": 0,
            "status": "pending",
        }

        self._event_log.append(
            WorkflowEvent.create(
                event_id=f"{workflow_id}:started",
                workflow_id=workflow_id,
                event_type=WorkflowEventType.WORKFLOW_STARTED,
                payload={
                    "content_id": content.content_id,
                    "original_content": content.model_dump(
                        mode="json"
                    ),
                },
            )
        )

        self._graph.invoke(
            initial_state,
            config=self._config(workflow_id),
        )

        return self.status(workflow_id)

    def status(
        self,
        workflow_id: str,
    ) -> WorkflowState:
        """
        Return the latest persisted workflow state.

        Human-review status is derived from the LangGraph
        checkpoint, not inferred by the CLI.
        """
        state = self._existing_state(workflow_id)

        if state is None:
            raise WorkflowNotFoundError(
                f"Workflow not found: {workflow_id}"
            )

        return state

    def approve(
        self,
        workflow_id: str,
    ) -> WorkflowState:
        """
        Resume a workflow awaiting human approval.

        A repeated approval of an already completed workflow
        returns the existing state without invoking LangGraph.
        """
        snapshot = self._snapshot(workflow_id)
        state = self._state_from_snapshot(snapshot)

        if state is None:
            raise WorkflowNotFoundError(
                f"Workflow not found: {workflow_id}"
            )

        if state["status"] == "completed":
            return state

        if state["status"] == "retry_limit_reached":
            raise WorkflowConflictError(
                "Cannot approve a workflow that reached its retry limit"
            )

        if snapshot.next != ("human_review",):
            raise WorkflowConflictError(
                "Workflow is not awaiting human review"
            )

        self._graph.invoke(
            Command(resume={"approved": True}),
            config=self._config(workflow_id),
        )

        return self.status(workflow_id)

    def events(
        self,
        workflow_id: str,
    ) -> list[WorkflowEvent]:
        """Return ordered audit events for an existing workflow."""
        self.status(workflow_id)

        return self._event_log.list_events(workflow_id)