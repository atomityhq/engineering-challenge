"""Immutable, runtime-validated inputs for the G2 evidence gate.

Contracts carry metadata assertions, not independently verified evidence.
Temporal inconsistencies are structurally valid and assessed in later stages.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum

from ._checks import require_bool, require_date, require_enum, require_text
from .errors import ValidationError


class SourceType(str, Enum):
    """Recognized asserted relationships between a source and its claim."""

    PRIMARY_AUTHORITY = "primary_authority"
    OFFICIAL_INDIRECT = "official_indirect"
    REPUTABLE_SECONDARY = "reputable_secondary"
    COMPETITOR = "competitor"
    UNKNOWN = "unknown"


class ContentType(str, Enum):
    """Content families with distinct temporal rules."""

    NEWS = "news"
    REGULATION = "regulation"


class CurrentStatus(str, Enum):
    """Recognized source status, including explicit uncertainty."""

    CURRENT = "current"
    SUPERSEDED = "superseded"
    ADOPTED_NOT_APPLICABLE = "adopted_not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Metadata:
    """Hold validated source assertions; every nullable date is explicit."""

    source_type: SourceType
    content_type: ContentType
    published_at: date | None
    event_date: date | None
    effective_from: date | None
    last_verified_at: date | None
    current_status: CurrentStatus
    supported: bool
    superseded: bool
    contradiction: bool
    competitor_product_claim: bool

    def __post_init__(self) -> None:
        require_enum(self.source_type, SourceType, "$.metadata.source_type")
        require_enum(self.content_type, ContentType, "$.metadata.content_type")
        require_enum(self.current_status, CurrentStatus, "$.metadata.current_status")
        for name in DATE_FIELDS:
            require_date(getattr(self, name), f"$.metadata.{name}")
        for name in BOOLEAN_FIELDS:
            require_bool(getattr(self, name), f"$.metadata.{name}")


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """Label-free evaluator input; identity and prose do not encode routing."""

    id: str
    statement: str
    metadata: Metadata

    def __post_init__(self) -> None:
        require_text(self.id, "$.id")
        require_text(self.statement, "$.statement")
        if type(self.metadata) is not Metadata:
            raise ValidationError(
                "INVALID_TYPE", "$.metadata", "Expected validated metadata."
            )


DATE_FIELDS: tuple[str, ...] = (
    "published_at", "event_date", "effective_from", "last_verified_at"
)
BOOLEAN_FIELDS: tuple[str, ...] = (
    "supported", "superseded", "contradiction", "competitor_product_claim"
)
