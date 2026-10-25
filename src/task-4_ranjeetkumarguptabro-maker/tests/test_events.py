"""Tests for structured event serialization, formatting, and auditability."""

import json
from workflow.events import (
    create_event,
    format_events_json,
    format_events_table,
    get_event_type_sequence,
)
from workflow.models import (
    EventType,
    WorkflowEvent,
    WorkflowStage,
)


def test_event_formatting_and_json_serialization() -> None:
    """Verify event formatting to table and JSON formats."""
    evt1 = create_event(
        workflow_id="run-fmt-1",
        content_id="content-fmt-1",
        event_type=EventType.WORKFLOW_STARTED,
        stage=WorkflowStage.INITIAL,
        revision_count=0,
        explanation="Workflow initialization",
        metadata={"key": "val"},
    )
    evt2 = create_event(
        workflow_id="run-fmt-1",
        content_id="content-fmt-1",
        event_type=EventType.WORKFLOW_COMPLETED,
        stage=WorkflowStage.COMPLETE,
        revision_count=0,
        explanation="Workflow completed successfully",
    )

    events = [evt1, evt2]

    # Table format
    table_str = format_events_table(events)
    assert "workflow_started" in table_str
    assert "workflow_completed" in table_str
    assert "Workflow initialization" in table_str

    # JSON format
    json_str = format_events_json(events)
    parsed = json.loads(json_str)
    assert len(parsed) == 2
    assert parsed[0]["event_type"] == "workflow_started"
    assert parsed[0]["metadata"]["key"] == "val"
    assert parsed[1]["event_type"] == "workflow_completed"

    # Sequence extractor
    seq = get_event_type_sequence(events)
    assert seq == [EventType.WORKFLOW_STARTED, EventType.WORKFLOW_COMPLETED]


def test_format_events_table_empty() -> None:
    """Empty event list produces clean empty message."""
    assert format_events_table([]) == "No events recorded."
