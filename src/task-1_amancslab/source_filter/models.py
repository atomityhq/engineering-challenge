"""Typed input models for source normalisation and filtering."""

from datetime import date
from enum import Enum
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, validator


class SourceType(str, Enum):
    """Classification of the source that published a record."""

    PRIMARY = "primary"
    AUTHORITATIVE = "authoritative"
    SECONDARY = "secondary"
    COMPETITOR = "competitor"
    LOW_QUALITY = "low_quality"
    UNKNOWN = "unknown"


class ClaimKind(str, Enum):
    """Classification of the claim described by a source."""

    PRODUCT_PROMOTIONAL = "product_promotional"
    GENERIC_INDUSTRY = "generic_industry"
    OTHER = "other"


class SourceRecord(BaseModel):
    """Validated representation of one saved source record."""

    source_id: str
    url: str

    publisher: Optional[str] = None
    source_type: SourceType = SourceType.UNKNOWN
    claim_kind: ClaimKind = ClaimKind.OTHER

    publication_date: Optional[date] = None
    event_date: Optional[date] = None

    canonical_url: Optional[str] = None

    discovery_lineage: List[str] = Field(default_factory=list)

    @validator("source_id")
    def validate_source_id(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("source_id must not be empty")

        return value

    @validator("url", "canonical_url")
    def validate_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("URL must not be empty")

        try:
            parsed = urlparse(value)
            hostname = parsed.hostname

            # Accessing port validates its syntax and range.
            _ = parsed.port

        except ValueError as exc:
            raise ValueError("URL is malformed") from exc

        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("URL must use HTTP or HTTPS")

        if not hostname:
            raise ValueError("URL must contain a hostname")

        if parsed.username is not None or parsed.password is not None:
            raise ValueError(
                "URLs containing credentials are not supported"
            )

        return value

    @validator("discovery_lineage", each_item=True)
    def validate_lineage_item(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Discovery lineage entries must not be empty"
            )

        return value

    class Config:
        extra = "forbid"
