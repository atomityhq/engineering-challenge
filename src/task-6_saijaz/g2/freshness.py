"""Pure temporal assessment using explicit dates and fixture-owned age limits."""

from dataclasses import dataclass
from datetime import date
from enum import Enum

from .contracts import ContentType, CurrentStatus, Metadata
from .errors import ValidationError
from .hard_checks import FindingKind


class Applicability(str, Enum):
    """Separate legal applicability from temporal coverage validity."""

    CURRENT = "currently_applicable"
    FUTURE = "not_yet_applicable"
    INACTIVE = "not_currently_applicable"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class TemporalCode(str, Enum):
    """Stable temporal findings, not final routing decisions."""

    SUPERSEDED = "SUPERSEDED_EVIDENCE"
    SUPERSESSION_CONFLICT = "SUPERSESSION_METADATA_CONFLICT"
    UNKNOWN_STATUS = "UNKNOWN_CURRENT_STATUS"
    INCOMPATIBLE_STATUS = "INCOMPATIBLE_CONTENT_STATUS"
    MISSING_EVENT = "UNKNOWN_EVENT_DATE"
    FUTURE_EVENT = "FUTURE_EVENT_DATE"
    STALE_EVENT = "STALE_EVENT"
    MISSING_EFFECTIVE = "UNKNOWN_EFFECTIVE_DATE"
    INCONSISTENT_EFFECTIVE = "INCONSISTENT_EFFECTIVE_STATUS"
    FUTURE_VERIFICATION = "FUTURE_VERIFICATION_DATE"


@dataclass(frozen=True, slots=True)
class TemporalFinding:
    """Explain a temporal defect or uncertainty without exposing prose."""

    code: TemporalCode
    kind: FindingKind
    reason: str

    def __post_init__(self) -> None:
        if type(self.code) is not TemporalCode:
            raise ValidationError("INVALID_TYPE", "$.temporal.finding.code", "Expected a temporal code.")
        expected = FindingKind.REPAIRABLE if self.code in (
            TemporalCode.SUPERSEDED, TemporalCode.STALE_EVENT
        ) else FindingKind.REVIEW
        if self.kind is not expected or self.reason != _REASONS[self.code]:
            raise ValidationError("INCONSISTENT_FINDING", "$.temporal.finding", "Expected the declared classification and explanation.")


_REASONS: dict[TemporalCode, str] = {
    TemporalCode.SUPERSEDED: "A supersession assertion establishes replaced evidence.",
    TemporalCode.SUPERSESSION_CONFLICT: "Supersession flag and status disagree; replacement remains established.",
    TemporalCode.UNKNOWN_STATUS: "Required current status is explicitly unknown.",
    TemporalCode.INCOMPATIBLE_STATUS: "Adopted-not-applicable status is incompatible with ordinary news coverage.",
    TemporalCode.MISSING_EVENT: "News event date is unknown; publication and verification cannot substitute.",
    TemporalCode.FUTURE_EVENT: "News event occurs after the supplied assessment date.",
    TemporalCode.STALE_EVENT: "News event age exceeds the fixture-owned coverage limit.",
    TemporalCode.MISSING_EFFECTIVE: "Required regulation effective date is unknown.",
    TemporalCode.INCONSISTENT_EFFECTIVE: "Regulation status contradicts effective-date applicability at assessment.",
    TemporalCode.FUTURE_VERIFICATION: "Verification date occurs after the supplied assessment date.",
}


@dataclass(frozen=True, slots=True)
class _TemporalFacts:
    value: float | None
    event_age_days: int | None
    date_basis: str
    applicability: Applicability
    currently_applicable: bool | None
    findings: tuple[TemporalFinding, ...]
    explanation: str


def _facts(metadata: Metadata, as_of: date, max_age: int) -> _TemporalFacts:
    codes: list[TemporalCode] = []
    replaced_status = metadata.current_status is CurrentStatus.SUPERSEDED
    replaced = metadata.superseded or replaced_status
    news = metadata.content_type is ContentType.NEWS
    age = (as_of - metadata.event_date).days if news and metadata.event_date is not None else None
    if replaced:
        codes.append(TemporalCode.SUPERSEDED)
    if metadata.superseded != replaced_status:
        codes.append(TemporalCode.SUPERSESSION_CONFLICT)
    if metadata.current_status is CurrentStatus.UNKNOWN:
        codes.append(TemporalCode.UNKNOWN_STATUS)
    if news:
        applicability = Applicability.NOT_APPLICABLE
        current = None
        basis = "event_date"
        if metadata.current_status is CurrentStatus.ADOPTED_NOT_APPLICABLE:
            codes.append(TemporalCode.INCOMPATIBLE_STATUS)
        if age is None:
            codes.append(TemporalCode.MISSING_EVENT)
        elif age < 0:
            codes.append(TemporalCode.FUTURE_EVENT)
        elif age > max_age:
            codes.append(TemporalCode.STALE_EVENT)
    else:
        basis = "effective_from"
        applicability = Applicability.UNKNOWN
        current = None
        if replaced:
            applicability, current = Applicability.INACTIVE, False
        if metadata.effective_from is None:
            codes.append(TemporalCode.MISSING_EFFECTIVE)
        elif metadata.current_status is CurrentStatus.CURRENT:
            if metadata.effective_from > as_of:
                codes.append(TemporalCode.INCONSISTENT_EFFECTIVE)
            elif not replaced:
                applicability, current = Applicability.CURRENT, True
        elif metadata.current_status is CurrentStatus.ADOPTED_NOT_APPLICABLE:
            if metadata.effective_from <= as_of:
                codes.append(TemporalCode.INCONSISTENT_EFFECTIVE)
            elif not replaced:
                applicability, current = Applicability.FUTURE, False
    if metadata.last_verified_at is not None and metadata.last_verified_at > as_of:
        codes.append(TemporalCode.FUTURE_VERIFICATION)
        if not news and not replaced:
            applicability, current = Applicability.UNKNOWN, None
    findings = tuple(
        TemporalFinding(code, FindingKind.REPAIRABLE if code in (
            TemporalCode.SUPERSEDED, TemporalCode.STALE_EVENT
        ) else FindingKind.REVIEW, _REASONS[code]) for code in codes
    )
    value = 0.0 if any(item.kind is FindingKind.REPAIRABLE for item in findings) else (
        None if findings else 1.0
    )
    explanation = (
        "Known temporal invalidity takes precedence; all uncertainties are retained."
        if value == 0.0 else "Required temporal assertions are unresolved or inconsistent."
        if value is None else "Event coverage is current under the supplied age limit."
        if news else "Regulation timing is appropriate under trusted status/effective-date assertions; current applicability is reported separately."
    )
    return _TemporalFacts(value, age, basis, applicability, current, findings, explanation)


@dataclass(frozen=True, slots=True)
class TemporalAssessment:
    """Expose timing, date context, applicability, and retained findings.

    The immutable metadata basis preserves publication, event, effective, and
    verification dates. Output invariants are checked against that basis.
    """

    metadata: Metadata
    as_of: date
    news_max_event_age_days: int
    value: float | None
    event_age_days: int | None
    date_basis: str
    applicability: Applicability
    currently_applicable: bool | None
    findings: tuple[TemporalFinding, ...]
    explanation: str

    def __post_init__(self) -> None:
        _validate_inputs(self.metadata, self.as_of, self.news_max_event_age_days)
        expected = _facts(self.metadata, self.as_of, self.news_max_event_age_days)
        for name in _TemporalFacts.__dataclass_fields__:
            actual = getattr(self, name)
            correct = getattr(expected, name)
            if type(actual) is not type(correct) or actual != correct:
                raise ValidationError("INCONSISTENT_TEMPORAL_OUTPUT", f"$.temporal.{name}", "Output contradicts its temporal basis.")


def _validate_inputs(metadata: Metadata, as_of: date, max_age: int) -> None:
    if type(metadata) is not Metadata or type(as_of) is not date:
        raise ValidationError("INVALID_TYPE", "$.temporal", "Expected validated metadata and an exact assessment date.")
    if type(max_age) is not int or max_age < 0:
        raise ValidationError("INVALID_EVENT_AGE", "$.temporal.news_max_event_age_days", "Expected a nonnegative integer.")


def assess_freshness(
    metadata: Metadata, as_of: date, news_max_event_age_days: int
) -> TemporalAssessment:
    """Assess temporal appropriateness without clocks, I/O, scores, or labels."""
    _validate_inputs(metadata, as_of, news_max_event_age_days)
    facts = _facts(metadata, as_of, news_max_event_age_days)
    return TemporalAssessment(
        metadata=metadata, as_of=as_of, news_max_event_age_days=news_max_event_age_days,
        value=facts.value, event_age_days=facts.event_age_days, date_basis=facts.date_basis,
        applicability=facts.applicability, currently_applicable=facts.currently_applicable,
        findings=facts.findings, explanation=facts.explanation,
    )
