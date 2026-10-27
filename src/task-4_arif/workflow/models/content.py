
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContentItem(BaseModel):
    """A content entity submitted for evaluation and revision."""

    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        validate_assignment=True,
    )

    content_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("content_id", "title", "body")
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field cannot be blank")
        return value