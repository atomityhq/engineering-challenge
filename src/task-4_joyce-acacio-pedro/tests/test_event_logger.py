from workflow.event_logger import EventLogger
from workflow.models import EventRecord


def test_event_logger_saves_and_retrieves_events():
    logger = EventLogger(":memory:")

    event = EventRecord(
        workflow_id="workflow-001",
        event_type="evaluation_completed",
        details={
            "decision": "pass",
            "score": 1.0,
        },
    )

    logger.log(event)

    events = logger.get_events("workflow-001")

    assert len(events) == 1
    assert events[0]["event_type"] == "evaluation_completed"
    assert events[0]["details"]["decision"] == "pass"

    logger.close()