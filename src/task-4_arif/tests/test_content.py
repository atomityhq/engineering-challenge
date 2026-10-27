
import pytest
from pydantic import ValidationError

from workflow.models import ContentItem


def test_create_valid_content():
    content = ContentItem(
        content_id="content-001",
        title="AI in Healthcare",
        body="AI can support clinical workflows.",
    )

    assert content.content_id == "content-001"
    assert content.title == "AI in Healthcare"
    assert content.metadata == {}


@pytest.mark.parametrize("field", ["content_id", "title", "body"])
@pytest.mark.parametrize("invalid_value", ["", "   "])
def test_reject_blank_required_fields(field, invalid_value):
    data = {
        "content_id": "content-001",
        "title": "Valid title",
        "body": "Valid body",
    }
    data[field] = invalid_value

    with pytest.raises(ValidationError):
        ContentItem(**data)


def test_reject_missing_required_field():
    with pytest.raises(ValidationError):
        ContentItem(
            content_id="content-001",
            title="Valid title",
        )


def test_reject_incorrect_type():
    with pytest.raises(ValidationError):
        ContentItem(
            content_id=123,
            title="Valid title",
            body="Valid body",
        )


def test_reject_unexpected_fields():
    with pytest.raises(ValidationError):
        ContentItem(
            content_id="content-001",
            title="Valid title",
            body="Valid body",
            unknown="unexpected",
        )


def test_metadata_is_not_shared():
    first = ContentItem(
        content_id="content-001",
        title="First",
        body="First body",
    )
    second = ContentItem(
        content_id="content-002",
        title="Second",
        body="Second body",
    )

    first.metadata["source"] = "test"

    assert second.metadata == {}


def test_assignment_validation():
    content = ContentItem(
        content_id="content-001",
        title="Valid title",
        body="Valid body",
    )

    with pytest.raises(ValidationError):
        content.title = "   "
