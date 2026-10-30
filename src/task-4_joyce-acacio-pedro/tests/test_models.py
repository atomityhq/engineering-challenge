
import pytest
from pydantic import ValidationError

from workflow.models import (
    ContentItem,
    EvaluationResult,
    WorkflowInput,
)
from workflow.nodes import evaluate_content, revise_content


def test_valid_content():
    content = ContentItem(
        content_id="content-001",
        title="Introduction to AI",
        body="Artificial intelligence is transforming education.",
    )

    assert content.content_id == "content-001"


def test_invalid_evaluation_decision():
    with pytest.raises(ValidationError):
        EvaluationResult(
            decision="maybe",
            feedback="Uncertain result",
        )


def test_valid_workflow_input():
    workflow_input = WorkflowInput(
        workflow_id="workflow-001",
        content={
            "content_id": "content-001",
            "title": "Introduction to AI",
            "body": "Artificial intelligence in education.",
        },
    )

    assert workflow_input.workflow_id == "workflow-001"
    assert workflow_input.content.content_id == "content-001"


def test_workflow_input_rejects_missing_workflow_id():
    with pytest.raises(ValidationError):
        WorkflowInput(
            content={
                "content_id": "content-001",
                "title": "Introduction to AI",
                "body": "Artificial intelligence in education.",
            },
        )


def test_workflow_input_rejects_missing_content():
    with pytest.raises(ValidationError):
        WorkflowInput(workflow_id="workflow-001")


def test_evaluator_returns_pass():
    content = ContentItem(
        content_id="content-002",
        title="AI in Education",
        body="Artificial intelligence can support learning.",
    )

    result = evaluate_content(content)

    assert result.decision == "pass"


def test_evaluator_requests_revision():
    content = ContentItem(
        content_id="content-003",
        title="AI in Education",
        body="This content needs work. [REVISE]",
    )

    result = evaluate_content(content)

    assert result.decision == "revise"


def test_evaluator_requests_human_review():
    content = ContentItem(
        content_id="content-004",
        title="AI in Education",
        body="This content requires approval. [HUMAN_REVIEW]",
    )

    result = evaluate_content(content)

    assert result.decision == "human_review"


def test_revision_removes_revision_marker():
    content = ContentItem(
        content_id="content-005",
        title="AI in Education",
        body="This content needs work. [REVISE]",
    )

    revised = revise_content(content)

    assert "[REVISE]" not in revised.body
    assert "[Improved version]" in revised.body
    assert revised.content_id == content.content_id
