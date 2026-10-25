"""Tests for input validation and malformed data boundaries (Test F).

Verifies:
1. Missing, empty, or whitespace-only content IDs fail validation before processing.
2. Invalid ID characters are rejected.
3. Empty or whitespace-only titles and bodies are rejected.
4. Negative bounds (max_revisions, revision_count) raise validation errors.
5. Inconsistent content_id and content.id raise validation errors.
"""

import pytest
from pydantic import ValidationError

from fixtures.content_fixtures import INVALID_CONTENT_CASES
from workflow.graph import ReviewWorkflowEngine
from workflow.models import (
    ContentItem,
    WorkflowState,
    WorkflowStatus,
)
from workflow.persistence import WorkflowDatabase


@pytest.mark.parametrize("case", INVALID_CONTENT_CASES)
def test_malformed_content_item_rejections(case: dict) -> None:
    """Test F: Invalid or incomplete input results in predictable validation failures before execution."""
    with pytest.raises(ValidationError) as exc_info:
        ContentItem(**case["data"])
    assert case["expected_error"] in str(exc_info.value)


def test_workflow_engine_rejects_empty_id(workflow_db: WorkflowDatabase) -> None:
    """Ensure engine cannot start processing an invalid content item."""
    engine = ReviewWorkflowEngine(db=workflow_db)
    with pytest.raises(ValidationError):
        invalid_content = ContentItem(id="", title="Title", body="Body")
        engine.run(invalid_content)


def test_state_validation_rejects_id_mismatch() -> None:
    """WorkflowState must enforce consistency between content_id and content.id."""
    content = ContentItem(id="content-real", title="Title", body="Body")
    with pytest.raises(ValidationError, match="Mismatch between content_id"):
        WorkflowState(
            run_id="run-1",
            content_id="content-mismatch",
            content=content,
        )


def test_state_validation_rejects_negative_revisions() -> None:
    """Negative revision numbers are strictly prohibited."""
    content = ContentItem(id="content-valid", title="Title", body="Body")
    with pytest.raises(ValidationError):
        WorkflowState(
            run_id="run-1",
            content_id="content-valid",
            content=content,
            revision_count=-1,
        )


def test_state_validation_rejects_negative_max_revisions() -> None:
    """Negative max revision budget is strictly prohibited."""
    content = ContentItem(id="content-valid", title="Title", body="Body")
    with pytest.raises(ValidationError):
        WorkflowState(
            run_id="run-1",
            content_id="content-valid",
            content=content,
            max_revisions=-5,
        )
