
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from workflow.models import WorkflowEvent, WorkflowEventType


def make_event(**overrides):
    data = {
        "event_id": "workflow-001:evaluation:0",
        "workflow_id": "workflow-001",
        "event_type": WorkflowEventType.CONTENT_EVALUATED,
        "timestamp": datetime.now(timezone.utc),
        "payload": {"decision": "revise"},
    }
    data.update(overrides)
    return WorkflowEvent(**data)


def test_create_valid_event():
    event = make_event()

    assert event.workflow_id == "workflow-001"
    assert event.event_type == WorkflowEventType.CONTENT_EVALUATED


def test_factory_creates_utc_timestamp():
    event = WorkflowEvent.create(
        event_id="workflow-001:started",
        workflow_id="workflow-001",
        event_type=WorkflowEventType.WORKFLOW_STARTED,
    )

    assert event.timestamp.utcoffset() == timedelta(0)


@pytest.mark.parametrize("identifier", ["", "   "])
def test_reject_blank_event_id(identifier):
    with pytest.raises(ValidationError):
        make_event(event_id=identifier)


def test_reject_naive_timestamp():
    with pytest.raises(ValidationError):
        make_event(timestamp=datetime(2026, 1, 1))


def test_reject_non_utc_timestamp():
    non_utc = timezone(timedelta(hours=5))

    with pytest.raises(ValidationError):
        make_event(
            timestamp=datetime(2026, 1, 1, tzinfo=non_utc)
        )


def test_reject_unknown_event_type():
    with pytest.raises(ValidationError):
        make_event(event_type="unknown_event")


def test_reject_unexpected_fields():
    with pytest.raises(ValidationError):
        WorkflowEvent(
            **make_event().model_dump(),
            unexpected="value",
        )


def test_event_is_frozen():
    event = make_event()

    with pytest.raises(ValidationError):
        event.event_id = "changed"


def test_json_round_trip():
    event = make_event()

    restored = WorkflowEvent.model_validate_json(
        event.model_dump_json()
    )

    assert restored == event
