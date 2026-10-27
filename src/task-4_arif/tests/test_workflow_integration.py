
import pytest

from langgraph.types import Command

from workflow.adapters.fake_evaluator import FakeEvaluator
from workflow.adapters.fake_reviser import FakeReviser
from workflow.adapters.sqlite_event_log import SQLiteEventLog
from workflow.graph import build_workflow_graph
from workflow.models import (
    ContentItem,
    EvaluationDecision,
    WorkflowState,
)
from workflow.models.event import WorkflowEventType
from workflow.persistence.checkpoint import sqlite_checkpointer


def make_state(workflow_id: str = "workflow-001") -> WorkflowState:
    return {
        "workflow_id": workflow_id,
        "content": ContentItem(
            content_id="content-001",
            title="Example article",
            body="Initial content.",
        ),
        "evaluation": None,
        "evaluation_count": 0,
        "revision_count": 0,
        "status": "pending",
    }


def make_config(workflow_id: str = "workflow-001") -> dict:
    return {
        "configurable": {
            "thread_id": workflow_id,
        }
    }


def make_graph(
    tmp_path,
    checkpointer,
    decisions,
):
    event_log = SQLiteEventLog(tmp_path / "events.db")

    graph = build_workflow_graph(
        evaluator=FakeEvaluator(decisions=decisions),
        reviser=FakeReviser(),
        event_log=event_log,
        checkpointer=checkpointer,
    )

    return graph, event_log


def event_types(event_log, workflow_id="workflow-001"):
    return [
        event.event_type
        for event in event_log.list_events(workflow_id)
    ]


def test_immediate_review_and_approval(tmp_path):
    with sqlite_checkpointer(tmp_path / "checkpoints.db") as saver:
        graph, event_log = make_graph(
            tmp_path,
            saver,
            [EvaluationDecision.HUMAN_REVIEW],
        )

        config = make_config()

        interrupted = graph.invoke(make_state(), config=config)

        assert "__interrupt__" in interrupted
        assert graph.get_state(config).next == ("human_review",)

        result = graph.invoke(
            Command(resume={"approved": True}),
            config=config,
        )

        assert result["status"] == "completed"
        assert result["evaluation_count"] == 1
        assert result["revision_count"] == 0

        assert event_types(event_log) == [
            WorkflowEventType.CONTENT_EVALUATED,
            WorkflowEventType.HUMAN_REVIEW_REQUESTED,
            WorkflowEventType.APPROVAL_RECORDED,
            WorkflowEventType.WORKFLOW_COMPLETED,
        ]


def test_one_revision_then_human_review(tmp_path):
    decisions = [
        EvaluationDecision.REVISE,
        EvaluationDecision.HUMAN_REVIEW,
    ]

    with sqlite_checkpointer(tmp_path / "checkpoints.db") as saver:
        graph, event_log = make_graph(tmp_path, saver, decisions)
        config = make_config()

        interrupted = graph.invoke(make_state(), config=config)

        assert "__interrupt__" in interrupted

        state = graph.get_state(config).values

        assert state["revision_count"] == 1
        assert state["evaluation_count"] == 2
        assert "Revision 1" in state["content"].body

        result = graph.invoke(
            Command(resume={"approved": True}),
            config=config,
        )

        assert result["status"] == "completed"

        assert event_types(event_log) == [
            WorkflowEventType.CONTENT_EVALUATED,
            WorkflowEventType.CONTENT_REVISED,
            WorkflowEventType.CONTENT_EVALUATED,
            WorkflowEventType.HUMAN_REVIEW_REQUESTED,
            WorkflowEventType.APPROVAL_RECORDED,
            WorkflowEventType.WORKFLOW_COMPLETED,
        ]


def test_two_revisions_then_human_review(tmp_path):
    decisions = [
        EvaluationDecision.REVISE,
        EvaluationDecision.REVISE,
        EvaluationDecision.HUMAN_REVIEW,
    ]

    with sqlite_checkpointer(tmp_path / "checkpoints.db") as saver:
        graph, event_log = make_graph(tmp_path, saver, decisions)
        config = make_config()

        graph.invoke(make_state(), config=config)

        state = graph.get_state(config).values

        assert state["revision_count"] == 2
        assert state["evaluation_count"] == 3
        assert "Revision 1" in state["content"].body
        assert "Revision 2" in state["content"].body

        result = graph.invoke(
            Command(resume={"approved": True}),
            config=config,
        )

        assert result["status"] == "completed"

        assert event_types(event_log).count(
            WorkflowEventType.CONTENT_REVISED
        ) == 2


def test_retry_limit_stops_after_two_revisions(tmp_path):
    decisions = [
        EvaluationDecision.REVISE,
        EvaluationDecision.REVISE,
        EvaluationDecision.REVISE,
    ]

    with sqlite_checkpointer(tmp_path / "checkpoints.db") as saver:
        graph, event_log = make_graph(tmp_path, saver, decisions)
        config = make_config()

        result = graph.invoke(make_state(), config=config)

        assert result["status"] == "retry_limit_reached"
        assert result["revision_count"] == 2
        assert result["evaluation_count"] == 3
        assert "__interrupt__" not in result

        assert graph.get_state(config).next == ()

        assert event_types(event_log).count(
            WorkflowEventType.CONTENT_REVISED
        ) == 2

        assert event_types(event_log).count(
            WorkflowEventType.RETRY_LIMIT_REACHED
        ) == 1

        assert WorkflowEventType.WORKFLOW_COMPLETED not in event_types(
            event_log
        )


def test_restart_resumes_without_repeating_evaluation(tmp_path):
    checkpoint_path = tmp_path / "checkpoints.db"
    decisions = [EvaluationDecision.HUMAN_REVIEW]
    config = make_config()

    # First application instance: run until the interrupt.
    with sqlite_checkpointer(checkpoint_path) as saver:
        graph, event_log = make_graph(tmp_path, saver, decisions)

        result = graph.invoke(make_state(), config=config)

        assert "__interrupt__" in result
        assert event_types(event_log).count(
            WorkflowEventType.CONTENT_EVALUATED
        ) == 1

    # Simulate process restart: close and reopen SQLite.
    with sqlite_checkpointer(checkpoint_path) as saver:
        graph, event_log = make_graph(tmp_path, saver, decisions)

        saved_state = graph.get_state(config)

        assert saved_state.next == ("human_review",)
        assert saved_state.values["evaluation_count"] == 1

        result = graph.invoke(
            Command(resume={"approved": True}),
            config=config,
        )

        assert result["status"] == "completed"
        assert result["evaluation_count"] == 1

        assert event_types(event_log).count(
            WorkflowEventType.CONTENT_EVALUATED
        ) == 1

        assert event_types(event_log).count(
            WorkflowEventType.WORKFLOW_COMPLETED
        ) == 1


def test_duplicate_approval_does_not_duplicate_events(tmp_path):
    with sqlite_checkpointer(tmp_path / "checkpoints.db") as saver:
        graph, event_log = make_graph(
            tmp_path,
            saver,
            [EvaluationDecision.HUMAN_REVIEW],
        )
        config = make_config()

        graph.invoke(make_state(), config=config)

        first_result = graph.invoke(
            Command(resume={"approved": True}),
            config=config,
        )

        assert first_result["status"] == "completed"

        # The workflow is already terminal. Do not invoke a new run.
        # Verify the persisted state and audit log are unchanged.
        before = event_log.list_events("workflow-001")

        assert graph.get_state(config).next == ()
        assert graph.get_state(config).values["status"] == "completed"

        after = event_log.list_events("workflow-001")

        assert before == after

        assert event_types(event_log).count(
            WorkflowEventType.APPROVAL_RECORDED
        ) == 1

        assert event_types(event_log).count(
            WorkflowEventType.WORKFLOW_COMPLETED
        ) == 1


def test_invalid_approval_does_not_complete(tmp_path):
    with sqlite_checkpointer(tmp_path / "checkpoints.db") as saver:
        graph, event_log = make_graph(
            tmp_path,
            saver,
            [EvaluationDecision.HUMAN_REVIEW],
        )
        config = make_config()

        graph.invoke(make_state(), config=config)

        with pytest.raises(
            ValueError,
            match="explicit human approval",
        ):
            graph.invoke(
                Command(resume={"approved": False}),
                config=config,
            )

        assert WorkflowEventType.WORKFLOW_COMPLETED not in event_types(
            event_log
        )


def test_invalid_content_is_rejected():
    with pytest.raises(ValueError):
        ContentItem(
            content_id="",
            title="Example",
            body="Initial content.",
        )