"""Freshness and current validity.

Different content ages differently:
  * news      -> judged by EVENT date (a recent article about an old event is still old news)
  * regulation-> judged by status + effective_from (an old law can be fully current)

Publication age is never used as a universal rule.
The 30-day news window comes from the fixture's demo policy. It is a test
convention, not a validated freshness threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from .models import Freshness, Metadata


@dataclass(frozen=True)
class FreshnessResult:
    freshness: Freshness
    temporal_score: Optional[float]  # None = unknown, never silently 0
    finding: Optional[str]  # reason code if this needs revise / human_review
    notes: tuple[str, ...] = ()


def _result(
    status: str,
    *,
    date_type: str = "none",
    date_used: Optional[date] = None,
    age_days: Optional[int] = None,
    applicability: str = "unknown",
    reason: str,
    score: Optional[float],
    finding: Optional[str] = None,
    notes: tuple[str, ...] = (),
) -> FreshnessResult:
    return FreshnessResult(
        freshness=Freshness(
            status=status,  # type: ignore[arg-type]
            date_type=date_type,  # type: ignore[arg-type]
            date_used=date_used,
            age_days=age_days,
            applicability=applicability,  # type: ignore[arg-type]
            reason=reason,
        ),
        temporal_score=score,
        finding=finding,
        notes=notes,
    )


def assess_freshness(
    meta: Metadata,
    as_of: date,
    news_max_event_age_days: int,
    verification_max_age_days: int,
) -> FreshnessResult:
    # 0. Dates that sit in the future of as_of cannot be true.
    for label in ("published_at", "event_date", "last_verified_at"):
        value = getattr(meta, label)
        if value is not None and value > as_of:
            return _result(
                "inconsistent",
                reason=f"{label} ({value}) is after the as_of date ({as_of}).",
                score=None,
                finding="INCONSISTENT_METADATA",
            )

    if meta.content_type == "news":
        base = _news(meta, as_of, news_max_event_age_days)
    elif meta.content_type == "regulation":
        base = _regulation(meta, as_of)
    else:
        return _result(
            "unknown",
            reason=f"No freshness rule for content_type {meta.content_type!r}.",
            score=None,
            finding="UNKNOWN_CONTENT_TYPE",
        )

    # Only evidence that looks usable needs a verification check.
    if base.freshness.status not in ("current", "future"):
        return base
    if meta.last_verified_at is None:
        return _result(
            "unknown",
            reason="Evidence looks usable but nobody recorded when it was last verified.",
            score=None,
            finding="UNKNOWN_VERIFICATION_DATE",
        )
    since_check = (as_of - meta.last_verified_at).days
    if since_check > verification_max_age_days:
        return FreshnessResult(
            freshness=base.freshness.model_copy(
                update={
                    "reason": base.freshness.reason
                    + f" Last verified {since_check} days before as_of "
                    f"(window {verification_max_age_days}), so timing is only partly assured."
                }
            ),
            temporal_score=0.5,
            finding=None,
            notes=base.notes + ("REVERIFY_RECOMMENDED",),
        )
    return base


def _news(meta: Metadata, as_of: date, max_age: int) -> FreshnessResult:
    if meta.event_date is None:
        return _result(
            "unknown",
            date_type="event_date",
            applicability="not_assessed_for_news",
            reason="Event date is unavailable, so freshness cannot be judged. "
            "Publication date is not used as a stand-in.",
            score=None,
            finding="UNKNOWN_EVENT_DATE",
        )
    age = (as_of - meta.event_date).days
    if age > max_age:
        return _result(
            "stale",
            date_type="event_date",
            date_used=meta.event_date,
            age_days=age,
            applicability="not_assessed_for_news",
            reason=f"Event was {age} days before as_of; demo policy allows {max_age} "
            "(published date ignored: a new article about an old event is still old news).",
            score=0.0,
            finding="STALE_EVENT",
        )
    return _result(
        "current",
        date_type="event_date",
        date_used=meta.event_date,
        age_days=age,
        applicability="not_assessed_for_news",
        reason=f"Event was {age} days before as_of, inside the {max_age}-day demo window.",
        score=1.0,
    )


def _regulation(meta: Metadata, as_of: date) -> FreshnessResult:
    status = meta.current_status
    eff = meta.effective_from

    if meta.superseded or status == "superseded":
        return _result(
            "superseded",
            applicability="not_applicable_superseded",
            reason="The rule has been replaced; it is not valid evidence for today.",
            score=0.0,
        )

    if status == "current":
        if eff is None:
            return _result(
                "unknown",
                date_type="effective_from",
                reason="Rule is marked current but has no effective date.",
                score=None,
                finding="UNKNOWN_EFFECTIVE_DATE",
            )
        if eff > as_of:
            return _result(
                "inconsistent",
                date_type="effective_from",
                date_used=eff,
                reason=f"Marked current, yet it only takes effect on {eff}, after as_of.",
                score=None,
                finding="INCONSISTENT_METADATA",
            )
        return _result(
            "current",
            date_type="effective_from",
            date_used=eff,
            age_days=(as_of - eff).days,
            applicability="applicable_now",
            reason=f"In force since {eff}. An old publication date does not make a current rule stale.",
            score=1.0,
        )

    if status == "adopted_not_applicable":
        if eff is None:
            return _result(
                "unknown",
                date_type="effective_from",
                reason="Rule is adopted but has no effective date, so applicability is unknown.",
                score=None,
                finding="UNKNOWN_EFFECTIVE_DATE",
            )
        if eff <= as_of:
            return _result(
                "inconsistent",
                date_type="effective_from",
                date_used=eff,
                reason=f"Marked 'not yet applicable' but its effective date {eff} has passed.",
                score=None,
                finding="INCONSISTENT_METADATA",
            )
        return _result(
            "future",
            date_type="effective_from",
            date_used=eff,
            applicability="not_yet_applicable",
            reason=f"Adopted but applies from {eff}. Correct to describe it as a future rule; "
            "it must not be presented as applicable today.",
            score=1.0,
            notes=("RULE_NOT_YET_APPLICABLE",),
        )

    return _result(
        "unknown",
        reason=f"Unrecognised current_status {status!r}.",
        score=None,
        finding="UNKNOWN_CURRENT_STATUS",
    )
