"""Freshness and current-validity assessment module.

Distinguishes among publication date, event date, effective date, and current applicability.
Does not use a crude publication-age heuristic:
- For news: evaluated by event_date against the demo policy threshold (default 30 days).
- For regulations: evaluated by current_status and effective_from, preserving old laws that
  remain in active force.
"""

from __future__ import annotations

from datetime import date
from g2.models import FreshnessAssessment, Metadata


def evaluate_freshness(
    metadata: Metadata,
    as_of: date,
    max_event_age_days: int = 30,
) -> FreshnessAssessment:
    """Evaluate temporal freshness and applicability relative to as_of date.

    Args:
        metadata: Metadata associated with the case.
        as_of: The reference 'today' date from the fixture.
        max_event_age_days: Maximum allowable age in days for news events under demo policy.

    Returns:
        FreshnessAssessment with status, date_type, date_used, and descriptive reason.
    """
    if metadata.content_type == "news":
        if metadata.event_date is None:
            return FreshnessAssessment(
                status="unknown",
                date_type="event_date",
                date_used=None,
                reason="News event date is unavailable; temporal validity cannot be established.",
            )

        if metadata.event_date > as_of:
            return FreshnessAssessment(
                status="unknown",
                date_type="event_date",
                date_used=metadata.event_date,
                reason=(
                    f"News event date {metadata.event_date} is in the future "
                    f"relative to evaluation date {as_of}."
                ),
            )

        age_days = (as_of - metadata.event_date).days
        if age_days <= max_event_age_days:
            return FreshnessAssessment(
                status="current",
                date_type="event_date",
                date_used=metadata.event_date,
                reason=(
                    f"Event date {metadata.event_date} ({age_days} days old) "
                    f"falls within demo policy limit of {max_event_age_days} days."
                ),
            )
        return FreshnessAssessment(
            status="stale",
            date_type="event_date",
            date_used=metadata.event_date,
            reason=(
                f"Event date {metadata.event_date} ({age_days} days old) "
                f"exceeds demo policy limit of {max_event_age_days} days."
            ),
        )

    if metadata.content_type == "regulation":
        if metadata.superseded or metadata.current_status == "superseded":
            return FreshnessAssessment(
                status="superseded",
                date_type="effective_from",
                date_used=metadata.effective_from,
                reason="Regulation is superseded and no longer in force.",
            )

        if metadata.effective_from is None:
            return FreshnessAssessment(
                status="unknown",
                date_type="effective_from",
                date_used=None,
                reason="Regulation effective date is unavailable; applicability cannot be established.",
            )

        if metadata.effective_from > as_of:
            return FreshnessAssessment(
                status="adopted_not_applicable",
                date_type="effective_from",
                date_used=metadata.effective_from,
                reason=(
                    f"Regulation is adopted with future effective date {metadata.effective_from}; "
                    f"not yet in force as of {as_of}."
                ),
            )

        if metadata.effective_from <= as_of and metadata.current_status == "current":
            return FreshnessAssessment(
                status="current",
                date_type="effective_from",
                date_used=metadata.effective_from,
                reason=(
                    f"Regulation has been in force since {metadata.effective_from} "
                    f"and remains currently applicable as of {as_of}."
                ),
            )

        return FreshnessAssessment(
            status="unknown",
            date_type="effective_from",
            date_used=metadata.effective_from,
            reason=f"Regulation status '{metadata.current_status}' is unhandled or ambiguous.",
        )

    # Fallback for unexpected content types
    return FreshnessAssessment(
        status="unknown",
        date_type=None,
        date_used=None,
        reason=f"Unsupported content type: {metadata.content_type}",
    )

