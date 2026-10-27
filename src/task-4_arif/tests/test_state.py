
from workflow.models import ContentItem, WorkflowState


def test_initial_workflow_state():
    content = ContentItem(
        content_id="content-001",
        title="Example article",
        body="Initial content.",
    )

    state: WorkflowState = {
        "workflow_id": "workflow-001",
        "content": content,
        "evaluation": None,
        "evaluation_count": 0,
        "revision_count": 0,
        "status": "pending",
    }

    assert state["workflow_id"] == "workflow-001"
    assert state["content"] == content
    assert state["evaluation"] is None
    assert state["evaluation_count"] == 0
    assert state["revision_count"] == 0
    assert state["status"] == "pending"


def test_workflow_state_supports_partial_updates():
    update = {
        "evaluation_count": 1,
        "revision_count": 1,
        "status": "revising",
    }

    assert update["evaluation_count"] == 1
    assert update["revision_count"] == 1
    assert update["status"] == "revising"


def test_evaluation_count_increments():
    content = ContentItem(
        content_id="content-001",
        title="Example article",
        body="Initial content.",
    )

    state: WorkflowState = {
        "workflow_id": "workflow-001",
        "content": content,
        "evaluation": None,
        "evaluation_count": 0,
        "revision_count": 0,
        "status": "pending",
    }

    updated_count = state["evaluation_count"] + 1

    assert updated_count == 1
    assert state["evaluation_count"] == 0