"""Freshness and current-validity assessment.

Freshness is kept separate from the weighted score and is judged per content
type, never by publication age:

* news: the *event date* must be within the fixture's demo window
  (``news_max_event_age_days``) of ``as_of``. A recent article about an old
  event is stale.
* regulation: there is no age limit. Applicability comes from
  ``current_status`` and ``effective_from``; an old rule that is still in force
  is current, and an adopted rule with a future effective date is
  "not yet applicable" (it may pass, but must be presented as future).

Every date comparison uses the fixture's ``as_of``, never the system clock.
"""

from __future__ import annotations

import datetime as dt
from typing import List, Optional, Tuple

from . import codes
from .config import G2Policy
from .models import CaseMetadata, ContentType, CurrentStatus, Decision, DemoPolicy
from .report import Applicability, FreshnessAssessment, FreshnessIssue, FreshnessStatus, Reason, VerificationInfo

# Each issue is recorded with the metadata field that caused it, so reports name the right date.
Issues = List[FreshnessIssue]

_SUPERSEDED_RULE_NOTE = "Superseded evidence is invalid regardless of its dates."


def _days(as_of: dt.date, earlier: dt.date) -> int:
    return (as_of - earlier).days


def _applicability(meta: CaseMetadata, as_of: dt.date, issues: Issues, notes: List[str]
                   ) -> Tuple[Applicability, Optional[bool], Optional[dt.date], Optional[str]]:
    """Return (applicability, currently_applicable, applicable_from, presentation_constraint)."""
    status = meta.current_status
    effective = meta.effective_from

    if meta.superseded or status is CurrentStatus.SUPERSEDED:
        notes.append(
            f"The evidence is marked superseded (superseded={meta.superseded}, current_status={status.value}). "
            + _SUPERSEDED_RULE_NOTE
        )
        return Applicability.NO_LONGER_APPLICABLE, False, None, None

    if status is CurrentStatus.UNKNOWN:
        issues.append(FreshnessIssue(code=codes.UNKNOWN_CURRENT_STATUS, field="current_status"))
        notes.append("current_status is unknown, so current applicability cannot be established.")
        return Applicability.UNKNOWN, None, None, None

    if status is CurrentStatus.CURRENT:
        if effective is None:
            if meta.content_type is ContentType.REGULATION:
                issues.append(FreshnessIssue(code=codes.UNKNOWN_EFFECTIVE_DATE, field="effective_from"))
                notes.append("The rule is marked current but has no effective_from date, so its applicability date is unknown.")
                return Applicability.UNKNOWN, None, None, None
            notes.append("current_status is 'current'; news needs no separate effective date.")
            return Applicability.APPLICABLE, True, None, None
        if effective > as_of:
            issues.append(FreshnessIssue(code=codes.STATUS_DATE_CONFLICT, field="effective_from"))
            notes.append(
                f"current_status is 'current' but effective_from {effective} is after as_of {as_of}; "
                "status and date conflict."
            )
            return Applicability.UNKNOWN, None, None, None
        notes.append(f"current_status is 'current' and the evidence has applied since {effective}.")
        return Applicability.APPLICABLE, True, effective, None

    # adopted_not_applicable
    if effective is None:
        issues.append(FreshnessIssue(code=codes.UNKNOWN_EFFECTIVE_DATE, field="effective_from"))
        notes.append("The rule is adopted but not yet applicable, and its effective_from date is unknown.")
        return Applicability.UNKNOWN, None, None, None
    if effective <= as_of:
        issues.append(FreshnessIssue(code=codes.STATUS_DATE_CONFLICT, field="effective_from"))
        notes.append(
            f"current_status says 'adopted_not_applicable' but effective_from {effective} is on or before "
            f"as_of {as_of}; status and date conflict."
        )
        return Applicability.UNKNOWN, None, None, None
    issues.append(FreshnessIssue(code=codes.NOT_YET_APPLICABLE, field="effective_from"))
    notes.append(
        f"The rule is adopted and applies from {effective}, {_days(effective, as_of)} days after as_of; "
        "it is not currently applicable."
    )
    constraint = f"Present as adopted but not applicable until {effective}; do not describe it as currently in force."
    return Applicability.NOT_YET_APPLICABLE, False, effective, constraint


def assess_freshness(meta: CaseMetadata, as_of: dt.date, demo: DemoPolicy, policy: G2Policy
                     ) -> Tuple[FreshnessAssessment, List[Reason]]:
    issues: Issues = []
    notes: List[str] = []

    # Dates recording things that already happened cannot be later than as_of.
    for field_name in ("published_at", "last_verified_at"):
        value = getattr(meta, field_name)
        if value is not None and value > as_of:
            issues.append(FreshnessIssue(code=codes.DATE_AFTER_AS_OF, field=field_name))
            notes.append(f"{field_name} {value} is after as_of {as_of}, which is impossible for a past record.")

    if meta.event_date is not None and meta.event_date > as_of:
        issues.append(FreshnessIssue(code=codes.FUTURE_EVENT_DATE, field="event_date"))
        notes.append(
            f"event_date {meta.event_date} is after as_of {as_of}; whether the described event happened "
            "cannot be confirmed automatically."
        )

    applicability, currently_applicable, applicable_from, constraint = _applicability(meta, as_of, issues, notes)

    reference_age: Optional[int] = None
    if meta.content_type is ContentType.NEWS:
        max_age: Optional[int] = demo.news_max_event_age_days
        reference_type = "event_date"
        reference = meta.event_date
        rule = (
            f"news: event date must be within {max_age} days of as_of "
            "(fixture demo test convention, not a validated freshness threshold)"
        )
        if reference is None:
            issues.append(FreshnessIssue(code=codes.UNKNOWN_EVENT_DATE, field="event_date"))
            published = f" The publication date ({meta.published_at}) is not a substitute." if meta.published_at else ""
            notes.append("The event date is unavailable, so event freshness cannot be judged." + published)
        elif reference <= as_of:
            reference_age = _days(as_of, reference)
            if reference_age > max_age:
                issues.append(FreshnessIssue(code=codes.STALE_EVENT, field="event_date"))
                recent_publication = (
                    meta.published_at is not None and _days(as_of, meta.published_at) <= max_age
                )
                lead = (
                    f"The publication date {meta.published_at} is recent, but freshness is judged by event date: "
                    if recent_publication else ""
                )
                notes.append(
                    f"{lead}event {reference} is {reference_age} days before as_of, outside the {max_age}-day "
                    "demo window; coverage needs revision."
                )
            else:
                notes.append(f"Event {reference} is {reference_age} days before as_of, within the {max_age}-day demo window.")
    else:
        max_age = None
        reference_type = "effective_from"
        reference = meta.effective_from
        rule = (
            "regulation: no age limit; applicability is decided by current_status and effective_from "
            "(publication date is not used)"
        )
        if reference is not None and reference <= as_of:
            reference_age = _days(as_of, reference)
        if meta.published_at is not None:
            notes.append(f"Publication date {meta.published_at} is recorded but not used to judge a rule's validity.")

    verified = meta.last_verified_at
    verification_age = _days(as_of, verified) if verified is not None else None
    within_window = verification_age is not None and 0 <= verification_age <= policy.verification_max_age_days
    verification = VerificationInfo(
        last_verified_at=verified,
        age_days=verification_age,
        max_age_days=policy.verification_max_age_days,
        within_window=within_window,
        window_note=policy.verification_window_note,
    )
    if verified is None:
        issues.append(FreshnessIssue(code=codes.STATUS_NOT_RECENTLY_VERIFIED, field="last_verified_at"))
        notes.append("Current status has no recorded verification (last_verified_at is null).")
    elif not within_window and verification_age is not None and verification_age >= 0:
        issues.append(FreshnessIssue(code=codes.STATUS_NOT_RECENTLY_VERIFIED, field="last_verified_at"))
        notes.append(
            f"Current status was last verified {verification_age} days before as_of, outside the "
            f"{policy.verification_max_age_days}-day verification window."
        )
    elif within_window:
        notes.append(f"Current status was verified {verification_age} days before as_of.")

    status = _overall_status([issue.code for issue in issues], applicability)
    passed = {
        FreshnessStatus.CURRENT: True,
        FreshnessStatus.NOT_YET_APPLICABLE: True,
        FreshnessStatus.STALE: False,
        FreshnessStatus.SUPERSEDED: False,
    }.get(status)

    assessment = FreshnessAssessment(
        status=status,
        passed=passed,
        content_type=meta.content_type,
        rule=rule,
        as_of=as_of,
        reference_date=reference,
        reference_date_type=reference_type,
        reference_age_days=reference_age,
        max_age_days=max_age,
        dates={
            "published_at": meta.published_at,
            "event_date": meta.event_date,
            "effective_from": meta.effective_from,
            "last_verified_at": meta.last_verified_at,
        },
        applicability=applicability,
        currently_applicable=currently_applicable,
        applicable_from=applicable_from,
        verification=verification,
        issues=list(dict.fromkeys(issues)),
        presentation_constraint=constraint,
        explanation=" ".join(notes) + f" Freshness status: {status.value}.",
    )
    return assessment, _routing_reasons(assessment, demo)


def _overall_status(issues: List[str], applicability: Applicability) -> FreshnessStatus:
    if applicability is Applicability.NO_LONGER_APPLICABLE:
        return FreshnessStatus.SUPERSEDED
    if any(code in issues for code in codes.FRESHNESS_CONFLICT_CODES):
        return FreshnessStatus.CONFLICTING
    if any(code in issues for code in codes.FRESHNESS_UNKNOWN_CODES):
        return FreshnessStatus.UNKNOWN
    if codes.FUTURE_EVENT_DATE in issues:
        return FreshnessStatus.FUTURE_EVENT
    if codes.STALE_EVENT in issues:
        return FreshnessStatus.STALE
    if applicability is Applicability.NOT_YET_APPLICABLE:
        return FreshnessStatus.NOT_YET_APPLICABLE
    return FreshnessStatus.CURRENT


_UNDECIDABLE_MESSAGES = {
    codes.UNKNOWN_EVENT_DATE: "Event date unavailable; event freshness cannot be judged.",
    codes.UNKNOWN_EFFECTIVE_DATE: "Effective date unavailable; the rule's applicability cannot be judged.",
    codes.UNKNOWN_CURRENT_STATUS: "Current status unknown; current applicability cannot be judged.",
    codes.FUTURE_EVENT_DATE: "Event date is after as_of; the event cannot be confirmed as having happened.",
    codes.DATE_AFTER_AS_OF: "{field} is after as_of; a past record cannot be dated in the future, so the dates conflict.",
    codes.STATUS_DATE_CONFLICT: "current_status conflicts with effective_from.",
}


def _routing_reasons(assessment: FreshnessAssessment, demo: DemoPolicy) -> List[Reason]:
    reasons: List[Reason] = []
    unknown_route = Decision(demo.unknown_required_temporal_metadata)
    timing_valid = assessment.status in (FreshnessStatus.CURRENT, FreshnessStatus.NOT_YET_APPLICABLE)
    for issue in assessment.issues:
        code, field = issue.code, issue.field
        if code == codes.STALE_EVENT:
            reasons.append(Reason(
                code=code, route=Decision.REVISE, stage="freshness", subject=field,
                message=(
                    f"Event is {assessment.reference_age_days} days old by event date; the demo policy allows "
                    f"{assessment.max_age_days} days for news. Update the coverage to a current event."
                ),
            ))
        elif code in _UNDECIDABLE_MESSAGES:
            reasons.append(Reason(
                code=code, route=unknown_route, stage="freshness", subject=field,
                message=_UNDECIDABLE_MESSAGES[code].format(field=field),
            ))
        elif code == codes.NOT_YET_APPLICABLE:
            reasons.append(Reason(
                code=code, route=None, stage="freshness", subject=field,
                message=assessment.presentation_constraint or "Not yet applicable.",
            ))
        elif code == codes.STATUS_NOT_RECENTLY_VERIFIED:
            consequence = (
                "temporal validity is scored 0.5 instead of 1."
                if timing_valid else
                f"this does not change temporal validity, which follows the '{assessment.status.value}' freshness status."
            )
            reasons.append(Reason(
                code=code, route=None, stage="freshness", subject=field,
                message=(
                    f"Current status was not verified within the {assessment.verification.max_age_days}-day "
                    f"verification window (demo convention); {consequence}"
                ),
            ))
    return reasons
