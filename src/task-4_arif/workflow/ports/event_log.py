
from typing import Protocol

from workflow.models.event import WorkflowEvent


class EventConflictError(Exception):
    """An event ID was reused with conflicting event data."""


class EventLogPort(Protocol):
    """Contract for durable workflow audit logging."""

    def append(self, event: WorkflowEvent) -> bool:
        """
        Persist an event idempotently.

        Returns:
            True if a new event was inserted.
            False if the same logical event already exists.

        Raises:
            EventConflictError:
                If event_id exists with conflicting logical data.
        """
        ...

    def list_events(self, workflow_id: str) -> list[WorkflowEvent]:
        """
        Return events for a workflow in insertion order.
        """
        ...

    def get_event(self, event_id: str) -> WorkflowEvent | None:
        """
        Return an event by ID, or None if it does not exist.
        """
        ...