from workflow.graph import build_workflow, evaluation_node, revision_node
from workflow.models import EvaluationResult
from workflow.models import ContentItem
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from workflow.event_logger import EventLogger
import workflow.graph as workflow_graph
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer





def test_workflow_completes_after_revision():
    graph = build_workflow()

    initial_state = {
        "workflow_id": "workflow-001",
        "content": ContentItem(
            content_id="content-001",
            title="Artificial Intelligence",
            body="This article needs improvement. [REVISE]",
        ),
        "evaluation": None,
        "revision_count": 0,
        "status": "running",
    }

    result = graph.invoke(initial_state)

    assert result["status"] == "completed"
    assert result["revision_count"] == 1
    assert "[REVISE]" not in result["content"].body


def test_workflow_stops_after_two_revisions():
    graph = build_workflow()

    initial_state = {
        "workflow_id": "workflow-002",
        "content": ContentItem(
            content_id="content-002",
            title="Article requiring revisions",
            body="This article needs work. [ALWAYS_REVISE]",
        ),
        "evaluation": None,
        "revision_count": 0,
        "status": "running",
    }

    result = graph.invoke(initial_state)

    assert result["revision_count"] == 2
    assert result["status"] == "revision_limit_reached"


def test_workflow_pauses_and_resumes_after_human_approval():
    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_workflow(checkpointer=checkpointer)

        config = {
            "configurable": {
                "thread_id": "human-review-001"
            }
        }

        initial_state = {
            "workflow_id": "human-review-001",
            "content": ContentItem(
                content_id="content-003",
                title="Content requiring approval",
                body="This content needs human approval. [HUMAN_REVIEW]",
            ),
            "evaluation": None,
            "revision_count": 0,
            "status": "running",
        }

        paused_result = graph.invoke(initial_state, config=config)

        assert paused_result["status"] == "awaiting_human_review"

        resumed_result = graph.invoke(
            Command(resume="approve"),
            config=config,
        )

        assert resumed_result["status"] == "completed"


def test_workflow_logs_evaluation_event():
    logger = EventLogger(":memory:")

    try:
        graph = build_workflow(event_logger=logger)

        initial_state = {
            "workflow_id": "workflow-logging-001",
            "content": ContentItem(
                content_id="content-logging-001",
                title="Test article",
                body="This article is ready for publication.",
            ),
            "evaluation": None,
            "revision_count": 0,
            "status": "running",
        }

        graph.invoke(initial_state)

        events = logger.get_events("workflow-logging-001")

        evaluation_events = [
            event for event in events
            if event["event_type"] == "evaluation_completed"
        ]

        assert len(evaluation_events) == 1
        assert evaluation_events[0]["details"]["decision"] == "pass"

    finally:
        logger.close()


def test_workflow_logs_revision_event():
    logger = EventLogger(":memory:")

    try:
        graph = build_workflow(event_logger=logger)

        initial_state = {
            "workflow_id": "workflow-revision-001",
            "content": ContentItem(
                content_id="content-revision-001",
                title="Article requiring revision",
                body="This article needs improvement. [REVISE]",
            ),
            "evaluation": None,
            "revision_count": 0,
            "status": "running",
        }

        graph.invoke(initial_state)

        events = logger.get_events("workflow-revision-001")

        revision_events = [
            event for event in events
            if event["event_type"] == "revision_requested"
        ]

        assert len(revision_events) == 1
        assert revision_events[0]["details"]["revision_number"] == 1

    finally:
        logger.close()


def test_human_review_events_are_not_duplicated():
    logger = EventLogger(":memory:")

    try:
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            graph = build_workflow(
                checkpointer=checkpointer,
                event_logger=logger,
            )

            config = {
                "configurable": {
                    "thread_id": "human-review-duplicate-001"
                }
            }

            initial_state = {
                "workflow_id": "human-review-duplicate-001",
                "content": ContentItem(
                    content_id="content-duplicate-001",
                    title="Approval test",
                    body="Needs approval. [HUMAN_REVIEW]",
                ),
                "evaluation": None,
                "revision_count": 0,
                "status": "running",
            }

            graph.invoke(initial_state, config=config)
            graph.invoke(Command(resume="approve"), config=config)

            events = logger.get_events(
                "human-review-duplicate-001"
            )

            review_events = [
                event for event in events
                if event["event_type"] == "human_review_required"
            ]

            approval_events = [
                event for event in events
                if event["event_type"] == "human_approved"
            ]

            assert len(review_events) == 1
            assert len(approval_events) == 1

    finally:
        logger.close()


def test_workflow_logs_completion_event():
    logger = EventLogger(":memory:")

    try:
        graph = build_workflow(event_logger=logger)

        initial_state = {
            "workflow_id": "workflow-completion-001",
            "content": ContentItem(
                content_id="content-completion-001",
                title="Approved article",
                body="This content is ready.",
            ),
            "evaluation": None,
            "revision_count": 0,
            "status": "running",
        }

        result = graph.invoke(initial_state)

        events = logger.get_events("workflow-completion-001")

        completion_events = [
            event for event in events
            if event["event_type"] == "workflow_completed"
        ]

        evaluation_events = [
            event for event in events
            if event["event_type"] == "evaluation_completed"
        ]

        assert result["status"] == "completed"
        assert len(evaluation_events) == 1
        assert evaluation_events[0]["details"]["decision"] == "pass"
        assert len(completion_events) == 1

    finally:
        logger.close()


def test_workflow_resumes_after_checkpointer_restart_without_reevaluation(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "workflow_checkpoints.sqlite"
    workflow_id = "workflow-restart-001"

    config = {
        "configurable": {
            "thread_id": workflow_id
        }
    }

    initial_state = {
        "workflow_id": workflow_id,
        "content": ContentItem(
            content_id="content-restart-001",
            title="Content requiring approval",
            body="This content requires approval. [HUMAN_REVIEW]",
        ),
        "evaluation": None,
        "revision_count": 0,
        "status": "running",
    }

    evaluation_calls = []
    original_evaluator = workflow_graph.evaluate_content

    def tracked_evaluator(content):
        evaluation_calls.append(content.content_id)
        return original_evaluator(content)

    monkeypatch.setattr(
        workflow_graph,
        "evaluate_content",
        tracked_evaluator,
    )

    # First execution: evaluate and pause for human review.
    with SqliteSaver.from_conn_string(str(database_path)) as checkpointer:
        checkpointer.serde = JsonPlusSerializer(
            allowed_msgpack_modules=[
                ("workflow.models", "ContentItem"),
                ("workflow.models", "EvaluationResult"),
            ]
        )

        graph = build_workflow(checkpointer=checkpointer)

        paused_result = graph.invoke(
            initial_state,
            config=config,
        )

        assert paused_result["status"] == "awaiting_human_review"

    # The first checkpointer is now closed.
    # Open a new connection to simulate application restart.
    with SqliteSaver.from_conn_string(str(database_path)) as checkpointer:
        checkpointer.serde = JsonPlusSerializer(
            allowed_msgpack_modules=[
                ("workflow.models", "ContentItem"),
                ("workflow.models", "EvaluationResult"),
            ]
        )

        graph = build_workflow(checkpointer=checkpointer)

        resumed_result = graph.invoke(
            Command(resume="approve"),
            config=config,
        )

        assert resumed_result["status"] == "completed"

    # Evaluation must have happened only once, before the pause.
    assert len(evaluation_calls) == 1
    assert evaluation_calls[0] == "content-restart-001"

def test_repeated_evaluation_does_not_duplicate_event():
    logger = EventLogger(":memory:")

    try:
        state = {
            "workflow_id": "workflow-idempotency-001",
            "content": ContentItem(
                content_id="content-idempotency-001",
                title="Test content",
                body="Content ready for evaluation.",
            ),
            "evaluation": None,
            "revision_count": 0,
            "status": "running",
        }

        evaluation_node(state, logger)
        evaluation_node(state, logger)

        events = logger.get_events("workflow-idempotency-001")

        evaluation_events = [
            event for event in events
            if event["event_type"] == "evaluation_completed"
        ]

        assert len(evaluation_events) == 1

    finally:
        logger.close()


def test_repeated_revision_does_not_duplicate_event():
    logger = EventLogger(":memory:")

    try:
        state = {
            "workflow_id": "workflow-idempotency-002",
            "content": ContentItem(
                content_id="content-idempotency-002",
                title="Content requiring revision",
                body="Needs improvement. [REVISE]",
            ),
            "evaluation": EvaluationResult(
                decision="revise",
                feedback="Content needs improvement.",
                score=0.5,
            ),
            "revision_count": 0,
            "status": "evaluated",
        }

        revision_node(state, logger)
        revision_node(state, logger)

        events = logger.get_events("workflow-idempotency-002")

        revision_events = [
            event for event in events
            if event["event_type"] == "revision_requested"
        ]

        assert len(revision_events) == 1

    finally:
        logger.close()