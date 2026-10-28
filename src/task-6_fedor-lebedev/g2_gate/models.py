"""Typed input contracts for the G2 gate.

Everything read from a fixture is validated here before any evaluation runs.
Validation is deliberately strict:

* unknown keys are rejected (a typo such as ``superseeded`` must not be ignored);
* every metadata key is required; a value may be ``null`` only where "unknown"
  is a meaningful state (dates and ``supported``);
* booleans must be real JSON booleans (``"true"`` or ``1`` are rejected);
* dates must be ISO ``YYYY-MM-DD`` strings.

Free text (``statement``, ``instructions``, ``demo_policy`` prose) is carried as
untrusted data. No code path interprets it.
"""

from __future__ import annotations

import datetime as dt
import re
from enum import Enum
from typing import Annotated, Any, List, Literal, Optional

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_iso_date(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, str) and _ISO_DATE.match(value):
        try:
            return dt.date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"invalid calendar date {value!r}") from exc
    raise ValueError(f"expected an ISO date string 'YYYY-MM-DD', got {value!r}")


IsoDate = Annotated[dt.date, BeforeValidator(_parse_iso_date)]
# Required key whose value may be null ("unknown"). No default on purpose:
# a missing key is malformed input, an explicit null is a known unknown.
NullableIsoDate = Annotated[Optional[dt.date], BeforeValidator(_parse_iso_date)]


class SourceType(str, Enum):
    PRIMARY_AUTHORITY = "primary_authority"
    SECONDARY_REPORTING = "secondary_reporting"
    COMMUNITY = "community"
    COMPETITOR = "competitor"
    UNKNOWN = "unknown"


class ContentType(str, Enum):
    NEWS = "news"
    REGULATION = "regulation"


class CurrentStatus(str, Enum):
    CURRENT = "current"
    ADOPTED_NOT_APPLICABLE = "adopted_not_applicable"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class Decision(str, Enum):
    REJECT = "reject"
    REVISE = "revise"
    HUMAN_REVIEW = "human_review"
    PASS = "pass"


# Earlier entries win. Used by the decision policy and nowhere else.
DECISION_PRECEDENCE = (Decision.REJECT, Decision.REVISE, Decision.HUMAN_REVIEW, Decision.PASS)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CaseMetadata(_Strict):
    """Trusted metadata assertions about one case (see README: fixture boundary)."""

    source_type: SourceType
    content_type: ContentType
    published_at: NullableIsoDate
    event_date: NullableIsoDate
    effective_from: NullableIsoDate
    last_verified_at: NullableIsoDate
    current_status: CurrentStatus
    # Outcome of upstream claim validation; null means "not determined".
    supported: Optional[StrictBool]
    superseded: StrictBool
    contradiction: StrictBool
    competitor_product_claim: StrictBool
    # Extension used only by this submission's fixtures: the evidence supports the
    # claim only with a stated qualification. Absent means "no qualification recorded".
    qualified_support: StrictBool = False


CaseId = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]


class G2Case(_Strict):
    """What the evaluator is allowed to see for one case."""

    id: CaseId
    statement: Annotated[str, Field(min_length=1, max_length=5000)]
    metadata: CaseMetadata


class FixtureCase(G2Case):
    """A fixture case. ``expected_decision`` is test-only and never reaches the evaluator."""

    expected_decision: Optional[Decision] = None

    def to_gate_input(self) -> G2Case:
        return G2Case(id=self.id, statement=self.statement, metadata=self.metadata)


class DemoPolicy(_Strict):
    news_max_event_age_days: Annotated[StrictInt, Field(gt=0)]
    regulation_rule: str
    unknown_required_temporal_metadata: Literal["human_review"]
    weights_and_threshold: str


class G2Fixture(_Strict):
    schema_version: Literal["1.0"]
    synthetic: StrictBool
    as_of: IsoDate
    instructions: Optional[str] = None
    demo_policy: DemoPolicy
    cases: Annotated[List[FixtureCase], Field(min_length=1)]

    @field_validator("cases")
    @classmethod
    def _unique_case_ids(cls, cases: List[FixtureCase]) -> List[FixtureCase]:
        seen: set[str] = set()
        duplicates = sorted({case.id for case in cases if case.id in seen or seen.add(case.id)})
        if duplicates:
            raise ValueError(f"duplicate case ids: {', '.join(duplicates)}")
        return cases


class EvaluationContext(_Strict):
    """Case-independent inputs: the fixed evaluation date and the fixture's demo policy."""

    as_of: IsoDate
    demo_policy: DemoPolicy

    @classmethod
    def from_fixture(cls, fixture: G2Fixture) -> "EvaluationContext":
        return cls(as_of=fixture.as_of, demo_policy=fixture.demo_policy)
