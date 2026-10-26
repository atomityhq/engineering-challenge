"""Typed contracts: what goes into the gate and what comes out."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

Decision = Literal["pass", "revise", "human_review", "reject"]


class Strict(BaseModel):
    """Unknown fields are errors, so a typo in a fixture cannot go unnoticed."""

    model_config = ConfigDict(extra="forbid")


# ---------- Input ----------


class Metadata(Strict):
    """Trusted metadata for one case (the gate does not re-verify it)."""

    source_type: str
    content_type: str
    published_at: Optional[date]
    event_date: Optional[date]
    effective_from: Optional[date]
    last_verified_at: Optional[date]
    current_status: str
    supported: Optional[bool]
    superseded: bool
    contradiction: bool
    competitor_product_claim: bool


class Case(Strict):
    id: str
    statement: str  # shown in reports only; never used to make a decision
    metadata: Metadata


class DemoPolicy(Strict):
    news_max_event_age_days: int
    regulation_rule: str
    unknown_required_temporal_metadata: str
    weights_and_threshold: str

    @field_validator("news_max_event_age_days")
    @classmethod
    def _positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("news_max_event_age_days must be positive")
        return v


class Fixture(Strict):
    schema_version: str
    synthetic: bool
    as_of: date
    instructions: str
    demo_policy: DemoPolicy
    cases: list[Case]

    @field_validator("schema_version")
    @classmethod
    def _version(cls, v: str) -> str:
        if v != "1.0":
            raise ValueError(f"unsupported schema_version {v!r}; expected '1.0'")
        return v

    @model_validator(mode="after")
    def _unique_ids(self) -> "Fixture":
        ids = [c.id for c in self.cases]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate case ids: {dupes}")
        if not ids:
            raise ValueError("fixture has no cases")
        return self


# ---------- Output ----------


class Freshness(BaseModel):
    """Why the evidence is (or is not) current. Kept separate from the score."""

    status: Literal["current", "future", "stale", "superseded", "unknown", "inconsistent"]
    date_type: Literal["event_date", "effective_from", "none"]
    date_used: Optional[date]
    age_days: Optional[int]
    applicability: Literal[
        "applicable_now",
        "not_yet_applicable",
        "not_applicable_superseded",
        "not_assessed_for_news",
        "unknown",
    ]
    reason: str


class Report(BaseModel):
    case_id: str
    gate: str
    statement: str
    policy_version: str
    calibration_status: str
    as_of: date
    hard_checks: dict[str, Optional[bool]]  # True = passed, False = failed, None = unknown
    criteria: dict[str, Optional[float]]
    freshness: Freshness
    weights_version: str
    weights: dict[str, float]
    score: Optional[float]
    score_note: str
    decision: Decision
    reasons: list[str]
    additional_findings: list[str]
    notes: list[str]
