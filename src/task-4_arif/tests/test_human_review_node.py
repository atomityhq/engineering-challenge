
import pytest

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from workflow.adapters.sqlite_event_log import SQLiteEventLog
from workflow.models import ContentItem, WorkflowState
from workflow.models.event import WorkflowEventType
from workflow.nodes import (
    make_complete_node,
    make_human_review_node,
)


@pytest.fixture
def event_log(tmp_path):
    return SQLiteEventLog(tmp_path / "events.db")


@pytest.fixture
def initial_state() -> WorkflowState:
    return {
        "workflow_id": "workflow-001",
        "content": ContentItem(
            content_id="content-001",
            title="Example article",
            body="Content awaiting approval.",
        ),
        "evaluation": None,
        "evaluation_count": 1,
        "revision_count": 0,
        "status": "awaiting_review",
    }


@pytest.fixture
def graph(event_log):
    builder = StateGraph(WorkflowState)

    builder.add_node(
        "human_review",
        make_human_review_node(event_log),
    )
    builder.add_node(
        "complete",
        make_complete_node(event_log),
    )

    builder.add_edge(START, "human_review")
    builder.add_edge("human_review", "complete")
    builder.add_edge("complete", END)

    return builder.compile(checkpointer=InMemorySaver())


def test_review_interrupts_and_waits(graph, event_log, initial_state):
    config = {"configurable": {"thread_id": "workflow-001"}}

    result = graph.invoke(initial_state, config=config)

    assert "__interrupt__" in result
    assert event_log.get_event("workflow-001:review:requested") is not None
    assert event_log.get_event("workflow-001:approval") is None
    assert event_log.get_event("workflow-001:completed") is None


def test_approval_resumes_and_completes(graph, event_log, initial_state):
    config = {"configurable": {"thread_id": "workflow-001"}}

    graph.invoke(initial_state, config=config)

    result = graph.invoke(
        Command(resume={"approved": True}),
        config=config,
    )

    assert result["status"] == "completed"

    events = event_log.list_events("workflow-001")
    event_types = [event.event_type for event in events]

    assert event_types == [
        WorkflowEventType.HUMAN_REVIEW_REQUESTED,
        WorkflowEventType.APPROVAL_RECORDED,
        WorkflowEventType.WORKFLOW_COMPLETED,
    ]


def test_review_request_not_duplicated_on_resume(
    graph,
    event_log,
    initial_state,
):
    config = {"configurable": {"thread_id": "workflow-001"}}

    graph.invoke(initial_state, config=config)

    graph.invoke(
        Command(resume={"approved": True}),
        config=config,
    )

    review_events = [
        event
        for event in event_log.list_events("workflow-001")
        if event.event_type
        == WorkflowEventType.HUMAN_REVIEW_REQUESTED
    ]

    assert len(review_events) == 1


def test_rejected_approval_does_not_complete(
    graph,
    event_log,
    initial_state,
):
    config = {"configurable": {"thread_id": "workflow-001"}}

    graph.invoke(initial_state, config=config)

    with pytest.raises(
        ValueError,
        match="explicit human approval",
    ):
        graph.invoke(
            Command(resume={"approved": False}),
            config=config,
        )

    assert event_log.get_event("workflow-001:completed") is None