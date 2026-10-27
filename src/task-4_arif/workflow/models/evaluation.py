
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvaluationDecision(str, Enum):
    REVISE = "revise"
    HUMAN_REVIEW = "human_review"


class EvaluationResult(BaseModel):
    """Immutable result of evaluating a content item."""

    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
    )

    decision: EvaluationDecision
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def reject_blank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Evaluation reason cannot be blank")
        return value
