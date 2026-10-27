
import pytest

from workflow.adapters.fake_evaluator import FakeEvaluator
from workflow.adapters.fake_reviser import FakeReviser
from workflow.adapters.sqlite_event_log import SQLiteEventLog
from workflow.graph import build_workflow_graph
from workflow.models import ContentItem, EvaluationDecision
from workflow.models.event import WorkflowEventType
from workflow.persistence.checkpoint import sqlite_checkpointer
from workflow.services import (
    WorkflowConflictError,
    WorkflowNotFoundError,
    WorkflowService,
)


@pytest.fixture
def content():
    return ContentItem(
        content_id="content-001",
        title="Example article",
        body="Initial content.",
    )


@pytest.fixture
def service_factory(tmp_path):
    """
    Create a real WorkflowService with SQLite persistence.

    Allows tests to select different deterministic evaluator
    sequences without mocking the workflow graph.
    """
    def factory(decisions):
        checkpoint_path = tmp_path / "checkpoints.db"
        event_path = tmp_path / "events.db"

        return checkpoint_path, event_path, decisions

    return factory


@pytest.fixture
def service(tmp_path):
    with sqlite_checkpointer(tmp_path / "checkpoints.db") as saver:
        event_log = SQLiteEventLog(tmp_path / "events.db")

        graph = build_workflow_graph(
            evaluator=FakeEvaluator(
                decisions=[EvaluationDecision.HUMAN_REVIEW]
            ),
            reviser=FakeReviser(),
            event_log=event_log,
            checkpointer=saver,
        )

        yield WorkflowService(
            graph=graph,
            event_log=event_log,
        )


def test_start_creates_workflow(service, content):
    state = service.start(
        workflow_id="workflow-001",
        content=content,
    )

    assert state["workflow_id"] == "workflow-001"
    assert state["evaluation_count"] == 1
    assert state["status"] == "awaiting_review"

    events = service.events("workflow-001")

    assert events[0].event_type == WorkflowEventType.WORKFLOW_STARTED
    assert events[0].payload["original_content"] == content.model_dump(
        mode="json"
    )


def test_start_is_idempotent(service, content):
    first = service.start(
        workflow_id="workflow-001",
        content=content,
    )

    second = service.start(
        workflow_id="workflow-001",
        content=content,
    )

    assert first == second

    events = service.events("workflow-001")

    assert sum(
        event.event_type == WorkflowEventType.WORKFLOW_STARTED
        for event in events
    ) == 1


def test_start_rejects_conflicting_content(service, content):
    service.start(
        workflow_id="workflow-001",
        content=content,
    )

    different_content = ContentItem(
        content_id="content-002",
        title="Different article",
        body="Different content.",
    )

    with pytest.raises(
        WorkflowConflictError,
        match="different request",
    ):
        service.start(
            workflow_id="workflow-001",
            content=different_content,
        )


@pytest.mark.parametrize(
    "changed_field, changed_value",
    [
        ("title", "Changed title"),
        ("body", "Changed body"),
        ("metadata", {"source": "changed"}),
    ],
)
def test_duplicate_start_rejects_changed_original_content(
    service,
    content,
    changed_field,
    changed_value,
):
    service.start(
        workflow_id="workflow-001",
        content=content,
    )

    changed_data = content.model_dump()
    changed_data[changed_field] = changed_value

    changed_content = ContentItem(**changed_data)

    with pytest.raises(
        WorkflowConflictError,
        match="different request",
    ):
        service.start(
            workflow_id="workflow-001",
            content=changed_content,
        )


def test_status_returns_persisted_state(service, content):
    service.start(
        workflow_id="workflow-001",
        content=content,
    )

    state = service.status("workflow-001")

    assert state["workflow_id"] == "workflow-001"
    assert state["revision_count"] == 0
    assert state["status"] == "awaiting_review"


def test_status_reflects_human_review_interrupt(service, content):
    state = service.start(
        workflow_id="workflow-001",
        content=content,
    )

    assert state["status"] == "awaiting_review"

    persisted = service.status("workflow-001")

    assert persisted["status"] == "awaiting_review"
    assert persisted["evaluation_count"] == 1
    assert persisted["revision_count"] == 0


def test_status_rejects_unknown_workflow(service):
    with pytest.raises(WorkflowNotFoundError):
        service.status("unknown-workflow")


def test_approve_completes_workflow(service, content):
    service.start(
        workflow_id="workflow-001",
        content=content,
    )

    state = service.approve("workflow-001")

    assert state["status"] == "completed"

    event_types = [
        event.event_type
        for event in service.events("workflow-001")
    ]

    assert WorkflowEventType.APPROVAL_RECORDED in event_types
    assert WorkflowEventType.WORKFLOW_COMPLETED in event_types


def test_duplicate_approval_is_idempotent(service, content):
    service.start(
        workflow_id="workflow-001",
        content=content,
    )

    first = service.approve("workflow-001")
    second = service.approve("workflow-001")

    assert first == second

    events = service.events("workflow-001")

    assert sum(
        event.event_type == WorkflowEventType.APPROVAL_RECORDED
        for event in events
    ) == 1

    assert sum(
        event.event_type == WorkflowEventType.WORKFLOW_COMPLETED
        for event in events
    ) == 1


def test_approve_unknown_workflow(service):
    with pytest.raises(WorkflowNotFoundError):
        service.approve("unknown-workflow")


def test_events_unknown_workflow(service):
    with pytest.raises(WorkflowNotFoundError):
        service.events("unknown-workflow")


def test_start_rejects_blank_workflow_id(service, content):
    with pytest.raises(
        ValueError,
        match="cannot be blank",
    ):
        service.start(
            workflow_id="   ",
            content=content,
        )


def test_duplicate_start_accepts_original_after_revision(tmp_path):
    """
    The current content may have been revised.

    Duplicate-start validation must compare the original
    submission stored in the start event, not revised content.
    """
    with sqlite_checkpointer(tmp_path / "checkpoints.db") as saver:
        event_log = SQLiteEventLog(tmp_path / "events.db")

        graph = build_workflow_graph(
            evaluator=FakeEvaluator(
                decisions=[
                    EvaluationDecision.REVISE,
                    EvaluationDecision.HUMAN_REVIEW,
                ]
            ),
            reviser=FakeReviser(),
            event_log=event_log,
            checkpointer=saver,
        )

        service = WorkflowService(
            graph=graph,
            event_log=event_log,
        )

        original = ContentItem(
            content_id="content-001",
            title="Original title",
            body="Original body.",
        )

        first = service.start(
            workflow_id="workflow-001",
            content=original,
        )

        assert first["revision_count"] == 1
        assert first["evaluation_count"] == 2
        assert "Revision 1" in first["content"].body

        second = service.start(
            workflow_id="workflow-001",
            content=original,
        )

        assert second == first

        events = service.events("workflow-001")

        assert sum(
            event.event_type == WorkflowEventType.CONTENT_REVISED
            for event in events
        ) == 1

        started_event = event_log.get_event(
            "workflow-001:started"
        )

        assert started_event.payload["original_content"] == (
            original.model_dump(mode="json")
        )


def test_duplicate_start_after_completion_is_idempotent(
    service,
    content,
):
    service.start(
        workflow_id="workflow-001",
        content=content,
    )

    completed = service.approve("workflow-001")

    repeated = service.start(
        workflow_id="workflow-001",
        content=content,
    )

    assert repeated == completed
    assert repeated["status"] == "completed"

    events = service.events("workflow-001")

    assert sum(
        event.event_type == WorkflowEventType.WORKFLOW_COMPLETED
        for event in events
    ) == 1
