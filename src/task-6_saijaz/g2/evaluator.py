"""Pure criterion and score assessment; final routing belongs to Stage 7."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
import math

from ._checks import require_enum, require_text
from .contracts import Metadata, SourceType
from .errors import ValidationError
from .freshness import TemporalAssessment, assess_freshness
from .hard_checks import CheckName, CheckStatus, HardCheckAssessment, assess_hard_checks
from .policy import CRITERIA, Policy, _unit_number


class CriterionName(str, Enum):
    """The three required dimensions, in stable policy order."""

    SUPPORT = "evidence_support"
    AUTHORITY = "source_authority"
    TEMPORAL = "temporal_validity"


@dataclass(frozen=True, slots=True)
class CriterionAssessment:
    """A known or unknown criterion with its independent floor assessment."""

    name: CriterionName
    value: float | None
    floor: float
    floor_met: bool | None
    explanation: str

    def __post_init__(self) -> None:
        require_enum(self.name, CriterionName, "$.criterion.name")
        require_text(self.explanation, "$.criterion.explanation")
        _unit_number(self.floor, "$.criterion.floor")
        if self.value is not None:
            if type(self.value) is not float:
                raise ValidationError("INVALID_TYPE", "$.criterion.value", "Expected a float or null.")
            _unit_number(self.value, "$.criterion.value")
        expected = None if self.value is None else self.value >= self.floor
        if type(self.floor_met) is not type(expected) or self.floor_met != expected:
            raise ValidationError("INCONSISTENT_FLOOR", "$.criterion.floor_met", "Floor assessment must use the unrounded value.")


@dataclass(frozen=True, slots=True)
class _ScoreFacts:
    criteria: tuple[CriterionAssessment, ...]
    scoring_eligible: bool
    blocking_reasons: tuple[str, ...]
    score: float | None
    floors_met: bool
    threshold_met: bool | None
    original_evidence_required: bool
    pass_requirements_met: bool
    explanation: str


def _score_facts(
    hard: HardCheckAssessment, temporal: TemporalAssessment, policy: Policy
) -> _ScoreFacts:
    metadata = temporal.metadata
    support_check = next(check for check in hard.checks if check.name is CheckName.SUPPORT)
    support = 0.0 if support_check.status is CheckStatus.FAIL else (
        None if support_check.status is CheckStatus.UNKNOWN else 1.0
    )
    authority_raw = getattr(policy.authority, metadata.source_type.value)
    authority = None if authority_raw is None else float(authority_raw)
    values = (support, authority, temporal.value)
    explanations = (
        support_check.reason + " Partial-support anchor 0.5 is not representable in this schema.",
        "Authority follows the configured, uncalibrated source relationship mapping; unknown remains null.",
        temporal.explanation + " Qualified-scope anchor 0.5 is not representable in this schema.",
    )
    criteria = tuple(
        CriterionAssessment(name, value, float(getattr(policy.floors, name.value)),
                            None if value is None else value >= getattr(policy.floors, name.value), reason)
        for name, value, reason in zip(CriterionName, values, explanations)
    )
    blockers: list[str] = []
    for check in hard.checks:
        if check.status is not CheckStatus.PASS:
            blockers.append("CHECK_BLOCKED:" + check.name.value)
    for finding in temporal.findings:
        blockers.append("TEMPORAL_BLOCKED:" + finding.code.value)
    for criterion in criteria:
        if criterion.value is None:
            blockers.append("UNKNOWN_CRITERION:" + criterion.name.value)
    eligible = not blockers
    score = None
    if eligible:
        # Required unknowns block even zero weights; never drop or renormalize them.
        score = math.fsum(
            float(getattr(policy.weights, criterion.name.value)) * criterion.value
            for criterion in criteria if criterion.value is not None
        )
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValidationError("AGGREGATE_OUT_OF_RANGE", "$.score", "Raw weighted aggregate exceeds [0, 1]; weights are not normalized or clipped.")
    floors_met = all(criterion.floor_met is True for criterion in criteria)
    threshold_met = None if score is None else score >= policy.threshold
    original_required = metadata.source_type is SourceType.COMPETITOR
    pass_met = eligible and floors_met and threshold_met is True and not original_required
    explanation = (
        "Aggregate withheld: every listed blocker is retained; weights cannot repair missing or disallowed evidence."
        if not eligible else
        "Unrounded weighted sum is a diagnostic preference score, not a probability; floors, threshold, and original-evidence requirements are separate."
    )
    return _ScoreFacts(criteria, eligible, tuple(blockers), score, floors_met,
                       threshold_met, original_required, pass_met, explanation)


@dataclass(frozen=True, slots=True)
class ScoreAssessment:
    """Preserve inputs, checks, timing, criteria, and numerical eligibility.

    This is not a final gate decision or complete report. Construction verifies
    every computed field and prevents a score from bypassing evidence blockers.
    """

    hard_checks: HardCheckAssessment
    temporal: TemporalAssessment
    policy: Policy
    criteria: tuple[CriterionAssessment, ...]
    scoring_eligible: bool
    blocking_reasons: tuple[str, ...]
    score: float | None
    floors_met: bool
    threshold_met: bool | None
    original_evidence_required: bool
    pass_requirements_met: bool
    explanation: str

    def __post_init__(self) -> None:
        if type(self.hard_checks) is not HardCheckAssessment or type(self.temporal) is not TemporalAssessment or type(self.policy) is not Policy:
            raise ValidationError("INVALID_TYPE", "$.assessment", "Expected validated checks, timing, and policy.")
        if self.hard_checks != assess_hard_checks(self.temporal.metadata):
            raise ValidationError("INCONSISTENT_BASIS", "$.hard_checks", "Checks must assess the same metadata as timing.")
        expected = _score_facts(self.hard_checks, self.temporal, self.policy)
        for name in _ScoreFacts.__dataclass_fields__:
            actual, correct = getattr(self, name), getattr(expected, name)
            if type(actual) is not type(correct) or actual != correct:
                raise ValidationError("INCONSISTENT_SCORE_OUTPUT", f"$.{name}", "Output contradicts its validated evidence and policy basis.")
        if tuple(item.name.value for item in self.criteria) != CRITERIA:
            raise ValidationError("INVALID_CRITERIA", "$.criteria", "Expected all required criteria in declared order.")


def assess_score(
    metadata: Metadata, as_of: date, news_max_event_age_days: int, policy: Policy
) -> ScoreAssessment:
    """Run checks and timing before criteria and aggregate calculation."""
    if type(policy) is not Policy:
        raise ValidationError("INVALID_TYPE", "$.policy", "Expected a validated policy.")
    hard = assess_hard_checks(metadata)
    temporal = assess_freshness(metadata, as_of, news_max_event_age_days)
    facts = _score_facts(hard, temporal, policy)
    return ScoreAssessment(
        hard, temporal, policy, facts.criteria, facts.scoring_eligible,
        facts.blocking_reasons, facts.score, facts.floors_met, facts.threshold_met,
        facts.original_evidence_required, facts.pass_requirements_met, facts.explanation,
    )
