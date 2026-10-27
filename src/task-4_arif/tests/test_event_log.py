
from datetime import datetime, timezone

import pytest

from workflow.adapters.sqlite_event_log import SQLiteEventLog
from workflow.models.event import WorkflowEvent, WorkflowEventType
from workflow.ports.event_log import EventConflictError, EventLogPort


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "workflow.db"


@pytest.fixture
def event_log(database_path):
    return SQLiteEventLog(database_path)


def make_event(
    event_id="workflow-001:started",
    workflow_id="workflow-001",
    event_type=WorkflowEventType.WORKFLOW_STARTED,
    payload=None,
):
    return WorkflowEvent(
        event_id=event_id,
        workflow_id=workflow_id,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        payload=payload or {},
    )


def test_adapter_satisfies_port(event_log):
    port: EventLogPort = event_log
    assert port is not None


def test_append_and_retrieve_event(event_log):
    event = make_event()

    assert event_log.append(event) is True
    assert event_log.get_event(event.event_id) == event


def test_duplicate_event_is_idempotent(event_log):
    event = make_event()

    assert event_log.append(event) is True
    assert event_log.append(event) is False
    assert len(event_log.list_events(event.workflow_id)) == 1


def test_duplicate_with_different_timestamp_is_idempotent(event_log):
    first = make_event()
    retry = make_event()

    assert event_log.append(first) is True
    assert event_log.append(retry) is False


def test_conflicting_duplicate_raises(event_log):
    original = make_event(payload={"decision": "revise"})
    conflicting = make_event(payload={"decision": "human_review"})

    event_log.append(original)

    with pytest.raises(EventConflictError):
        event_log.append(conflicting)


def test_events_survive_reopening_database(database_path):
    first_instance = SQLiteEventLog(database_path)
    event = make_event()

    first_instance.append(event)

    second_instance = SQLiteEventLog(database_path)

    assert second_instance.get_event(event.event_id) == event


def test_events_are_returned_in_insertion_order(event_log):
    first = make_event(event_id="workflow-001:started")
    second = make_event(
        event_id="workflow-001:evaluation:0",
        event_type=WorkflowEventType.CONTENT_EVALUATED,
    )

    event_log.append(first)
    event_log.append(second)

    events = event_log.list_events("workflow-001")

    assert [event.event_id for event in events] == [
        first.event_id,
        second.event_id,
    ]


def test_events_are_isolated_by_workflow(event_log):
    event_log.append(make_event(workflow_id="workflow-001"))
    event_log.append(
        make_event(
            event_id="workflow-002:started",
            workflow_id="workflow-002",
        )
    )

    assert len(event_log.list_events("workflow-001")) == 1
    assert len(event_log.list_events("workflow-002")) == 1


def test_missing_event_returns_none(event_log):
    assert event_log.get_event("nonexistent") is None
