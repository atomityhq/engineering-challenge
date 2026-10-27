
import pytest

from workflow.adapters.sqlite_event_log import SQLiteEventLog
from workflow.models import ContentItem, WorkflowState
from workflow.models.event import WorkflowEvent, WorkflowEventType
from workflow.nodes import make_complete_node


@pytest.fixture
def event_log(tmp_path):
    return SQLiteEventLog(tmp_path / "events.db")


@pytest.fixture
def state() -> WorkflowState:
    return {
        "workflow_id": "workflow-001",
        "content": ContentItem(
            content_id="content-001",
            title="Example article",
            body="Final content.",
        ),
        "evaluation": None,
        "evaluation_count": 1,
        "revision_count": 0,
        "status": "awaiting_review",
    }


def record_approval(event_log, workflow_id="workflow-001"):
    event_log.append(
        WorkflowEvent.create(
            event_id=f"{workflow_id}:approval",
            workflow_id=workflow_id,
            event_type=WorkflowEventType.APPROVAL_RECORDED,
            payload={"approved": True},
        )
    )


def test_complete_node_marks_workflow_completed(event_log, state):
    record_approval(event_log)

    node = make_complete_node(event_log)
    update = node(state)

    assert update == {"status": "completed"}


def test_complete_node_records_completion_event(event_log, state):
    record_approval(event_log)

    node = make_complete_node(event_log)
    node(state)

    event = event_log.get_event("workflow-001:completed")

    assert event is not None
    assert event.event_type == WorkflowEventType.WORKFLOW_COMPLETED
    assert event.payload["content_id"] == "content-001"
    assert event.payload["revision_count"] == 0
    assert event.payload["evaluation_count"] == 1


def test_complete_node_requires_approval(event_log, state):
    node = make_complete_node(event_log)

    with pytest.raises(
        ValueError,
        match="without human approval",
    ):
        node(state)

    assert event_log.get_event("workflow-001:completed") is None


def test_complete_node_rejects_invalid_approval(event_log, state):
    event_log.append(
        WorkflowEvent.create(
            event_id="workflow-001:approval",
            workflow_id="workflow-001",
            event_type=WorkflowEventType.APPROVAL_RECORDED,
            payload={"approved": False},
        )
    )

    node = make_complete_node(event_log)

    with pytest.raises(
        ValueError,
        match="without valid human approval",
    ):
        node(state)


def test_complete_node_is_idempotent(event_log, state):
    record_approval(event_log)

    node = make_complete_node(event_log)

    first = node(state)
    second = node(state)

    assert first == {"status": "completed"}
    assert second == {"status": "completed"}

    completion_events = [
        event
        for event in event_log.list_events("workflow-001")
        if event.event_type == WorkflowEventType.WORKFLOW_COMPLETED
    ]

    assert len(completion_events) == 1


def test_completion_event_survives_restart(tmp_path, state):
    database_path = tmp_path / "events.db"

    first_log = SQLiteEventLog(database_path)
    record_approval(first_log)

    make_complete_node(first_log)(state)

    reopened_log = SQLiteEventLog(database_path)

    event = reopened_log.get_event("workflow-001:completed")

    assert event is not None
    assert event.event_type == WorkflowEventType.WORKFLOW_COMPLETED