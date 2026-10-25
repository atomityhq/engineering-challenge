"""Pydantic data models for the G2 Content-Quality Gate.

Defines schemas for metadata, cases, fixture envelopes, freshness assessments,
criterion scores, hard check outcomes, and evaluation reports.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SourceType = Literal["primary_authority", "secondary", "competitor"]
ContentType = Literal["news", "regulation"]
CurrentStatus = Literal["current", "superseded", "adopted_not_applicable"]
DecisionType = Literal["reject", "revise", "human_review", "pass"]
FreshnessStatus = Literal[
    "current", "stale", "superseded", "adopted_not_applicable", "unknown"
]
SupportLevel = Literal["full", "partial", "none"]


class Metadata(BaseModel):
    """Case metadata representing trusted evidence assertions."""

    model_config = ConfigDict(extra="forbid")

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

    # Optional qualifiers used for nuanced cases (e.g. sensitivity analysis)
    support_level: SupportLevel | None = None
    timing_uncertain: bool = False


class Case(BaseModel):
    """A single content candidate to evaluate.

    The statement text is treated as untrusted data; the evaluator never
    branches on statement text or executes instructions inside it.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str
    metadata: Metadata
    expected_decision: DecisionType | None = None


class DemoPolicy(BaseModel):
    """Demo freshness and evaluation policy parameters from fixture envelope."""

    model_config = ConfigDict(extra="allow")

    news_max_event_age_days: int = 30
    regulation_rule: str | None = None
    unknown_required_temporal_metadata: str | None = None
    weights_and_threshold: str | None = None


class FixtureEnvelope(BaseModel):
    """Envelope wrapping a set of test cases."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    synthetic: bool
    as_of: date
    instructions: str | None = None
    demo_policy: DemoPolicy
    cases: list[Case]


class HardChecksResult(BaseModel):
    """Results of mandatory hard checks."""

    model_config = ConfigDict(extra="forbid")

    material_claim_supported: bool
    evidence_superseded: bool
    competitor_promotion: bool

    def all_passed(self) -> bool:
        """Return True only if all hard checks pass."""
        return (
            self.material_claim_supported
            and not self.evidence_superseded
            and not self.competitor_promotion
        )


class CriteriaScores(BaseModel):
    """Scores for individual evaluation criteria.

    Scores are either 0.0, 0.5, 1.0, or None if unknown.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_support: float | None = None
    source_authority: float | None = None
    temporal_validity: float | None = None

    def has_unknown(self) -> bool:
        """Check if any criterion score is unknown (None)."""
        return (
            self.evidence_support is None
            or self.source_authority is None
            or self.temporal_validity is None
        )


class FreshnessAssessment(BaseModel):
    """Detailed freshness and applicability assessment."""

    model_config = ConfigDict(extra="forbid")

    status: FreshnessStatus
    date_type: Literal["event_date", "effective_from", "published_at"] | None = None
    date_used: date | None = None
    reason: str


class Weights(BaseModel):
    """Normalized criterion weights for weighted scoring."""

    model_config = ConfigDict(extra="forbid")

    evidence_support: float = Field(ge=0.0)
    source_authority: float = Field(ge=0.0)
    temporal_validity: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_weights_sum(self) -> Weights:
        total = self.evidence_support + self.source_authority + self.temporal_validity
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0 within tolerance, got {total}")
        return self


class EvaluationReport(BaseModel):
    """Standardized output report produced for each evaluated case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    gate: str = "G2"
    policy_version: str
    calibration_status: str

    hard_checks: HardChecksResult
    criteria: CriteriaScores
    freshness: FreshnessAssessment

    weights_version: str
    weights: Weights
    score: float | None
    decision: DecisionType
    reasons: list[str]



class EvaluationReport(BaseModel):
    """Standardized output report produced for each evaluated case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    gate: str = "G2"
    policy_version: str
    calibration_status: str

    hard_checks: HardChecksResult
    criteria: CriteriaScores
    freshness: FreshnessAssessment

    weights_version: str
    weights: Weights
    score: float | None
    decision: DecisionType
    reasons: list[str]