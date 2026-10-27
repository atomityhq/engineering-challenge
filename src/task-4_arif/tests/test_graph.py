
from langgraph.types import Command

from workflow.adapters.fake_evaluator import FakeEvaluator
from workflow.adapters.fake_reviser import FakeReviser
from workflow.adapters.sqlite_event_log import SQLiteEventLog
from workflow.graph import build_workflow_graph
from workflow.models import (
    ContentItem,
    EvaluationDecision,
)
from workflow.persistence.checkpoint import sqlite_checkpointer


def test_immediate_human_review_and_completion(tmp_path):
    event_log = SQLiteEventLog(tmp_path / "events.db")

    evaluator = FakeEvaluator(
        decisions=[EvaluationDecision.HUMAN_REVIEW]
    )
    reviser = FakeReviser()

    initial_state = {
        "workflow_id": "workflow-001",
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

    config = {
        "configurable": {
            "thread_id": "workflow-001",
        }
    }

    with sqlite_checkpointer(tmp_path / "checkpoints.db") as saver:
        graph = build_workflow_graph(
            evaluator=evaluator,
            reviser=reviser,
            event_log=event_log,
            checkpointer=saver,
        )

        interrupted = graph.invoke(initial_state, config=config)

        assert "__interrupt__" in interrupted

        resumed = graph.invoke(
            Command(resume={"approved": True}),
            config=config,
        )

        assert resumed["status"] == "completed"
        assert resumed["evaluation_count"] == 1
        assert resumed["revision_count"] == 0

    completion_event = event_log.get_event(
        "workflow-001:completed"
    )

    assert completion_event is not None