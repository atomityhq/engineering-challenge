
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceSource(BaseModel):
    """A source passage supplied for checking claims."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)

    @field_validator("source_id", "locator", "excerpt")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        """Reject empty strings and whitespace-only values."""
        value = value.strip()

        if not value:
            raise ValueError("must not be empty or whitespace only")

        return value

    @field_validator("locator")
    @classmethod
    def validate_locator(cls, value: str) -> str:
        """Reject placeholder values instead of real evidence locations."""
        placeholders = {"unknown", "n/a", "na", "none", "null", "tbd"}

        if value.lower() in placeholders:
            raise ValueError(
                "locator must identify a source location, not a placeholder"
            )

        if not re.search(r"[A-Za-z0-9#:/._-]", value):
            raise ValueError(
                "locator must contain a recognizable location identifier"
            )

        return value


class Claim(BaseModel):
    """A claim that needs evidence validation."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    classification: Literal["fact", "inference"]

    @field_validator("claim_id", "text")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        """Reject empty or whitespace-only claim fields."""
        value = value.strip()

        if not value:
            raise ValueError("must not be empty or whitespace only")

        return value

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, values: list[str]) -> list[str]:
        """Require non-empty, unique source references."""
        cleaned_values = [value.strip() for value in values]

        if any(not value for value in cleaned_values):
            raise ValueError(
                "source IDs must not be empty or whitespace only"
            )

        if len(cleaned_values) != len(set(cleaned_values)):
            raise ValueError("source IDs must not contain duplicates")

        return cleaned_values


class EvidenceUsed(BaseModel):
    """Evidence preserved in a validation result."""

    source_id: str
    locator: str
    excerpt: str


class ValidationResult(BaseModel):
    """The final decision for a claim."""

    claim_id: str
    claim_text: str
    status: Literal["supported", "unsupported", "uncertain"]
    classification: Literal["fact", "inference"]
    assessed_classification: Literal["fact", "inference"]
    source_ids: list[str]
    evidence: list[EvidenceUsed]
    contradictions: list[str]
    unresolved_questions: list[str]
    reason: str
