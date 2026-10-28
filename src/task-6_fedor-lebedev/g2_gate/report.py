"""Typed output contracts: the per-case G2 evaluation report and its parts."""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict

from .models import ContentType, Decision

Stage = Literal["hard_check", "freshness", "criteria", "scoring", "policy"]

SCORE_INTERPRETATION = (
    "Provisional, uncalibrated prototype index in [0, 1] used for ranking and routing. "
    "It is not a probability that the content is correct."
)

DECISION_MEANING = {
    Decision.REJECT: "Prohibited or non-remediable under the G2 policy.",
    Decision.REVISE: "A known, repairable evidence or validity defect; return for revision.",
    Decision.HUMAN_REVIEW: (
        "Cannot be routed automatically: required information is unknown or conflicting, "
        "or the result needs human judgment."
    ),
    Decision.PASS: (
        "Eligible for the next internal stage under the demo policy. "
        "Not publication approval and not a calibrated quality judgment."
    ),
}


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Reason(_Out):
    code: str
    # The decision this reason asks for; null for informational reasons.
    route: Optional[Decision]
    stage: Stage
    subject: Optional[str] = None
    message: str


class HardCheckResult(_Out):
    status: Literal["pass", "fail", "unknown"]
    # Route applied when the check does not pass; null when it passes.
    route: Optional[Decision]
    inputs: Dict[str, Any]
    detail: str


class FreshnessStatus(str, Enum):
    CURRENT = "current"
    NOT_YET_APPLICABLE = "not_yet_applicable"
    STALE = "stale"
    SUPERSEDED = "superseded"
    FUTURE_EVENT = "future_event"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"


class Applicability(str, Enum):
    APPLICABLE = "applicable"
    NOT_YET_APPLICABLE = "not_yet_applicable"
    NO_LONGER_APPLICABLE = "no_longer_applicable"
    UNKNOWN = "unknown"


class VerificationInfo(_Out):
    last_verified_at: Optional[dt.date]
    age_days: Optional[int]
    max_age_days: int
    within_window: bool
    window_note: str


class FreshnessIssue(_Out):
    code: str
    # The metadata field that triggered the issue.
    field: str


class FreshnessAssessment(_Out):
    status: FreshnessStatus
    # True: freshness rule satisfied. False: known failure (stale/superseded).
    # None: cannot be decided (unknown, conflicting or future-dated event).
    passed: Optional[bool]
    content_type: ContentType
    rule: str
    as_of: dt.date
    reference_date: Optional[dt.date]
    reference_date_type: Optional[Literal["event_date", "effective_from"]]
    reference_age_days: Optional[int]
    max_age_days: Optional[int]
    dates: Dict[str, Optional[dt.date]]
    applicability: Applicability
    currently_applicable: Optional[bool]
    applicable_from: Optional[dt.date]
    verification: VerificationInfo
    issues: List[FreshnessIssue]
    presentation_constraint: Optional[str]
    explanation: str

    @property
    def issue_codes(self) -> List[str]:
        return [issue.code for issue in self.issues]


class CriterionResult(_Out):
    score: Optional[float]
    anchor: Optional[str]
    basis: Dict[str, Any]
    unknown_reason: Optional[str]


class FloorResult(_Out):
    minimum: float
    status: str
    met: bool


class ScoreBreakdown(_Out):
    formula: str
    weights_version: str
    weights_status: str
    weights: Dict[str, float]
    contributions: Dict[str, float]
    score: float
    threshold: float
    threshold_status: str
    threshold_met: bool
    floors: Dict[str, FloorResult]


class G2Report(_Out):
    case_id: str
    gate: Literal["G2"]
    as_of: dt.date
    policy_version: str
    weights_version: str
    calibration_status: str
    config_digest: str
    input_digest: str
    hard_checks: Dict[str, HardCheckResult]
    freshness: FreshnessAssessment
    criteria: Dict[str, CriterionResult]
    weights: Dict[str, float]
    eligible_for_scoring: bool
    score: Optional[float]
    score_breakdown: Optional[ScoreBreakdown]
    score_withheld_because: List[str]
    score_interpretation: str
    decision: Decision
    decision_meaning: str
    reasons: List[Reason]

    @property
    def reason_codes(self) -> List[str]:
        return [reason.code for reason in self.reasons]
