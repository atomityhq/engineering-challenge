"""Unit tests for temporal freshness and applicability evaluation."""

from datetime import date
from g2.freshness import evaluate_freshness
from g2.models import Metadata


def test_news_within_policy_limit():
    as_of = date(2026, 10, 6)
    meta = Metadata(
        source_type="primary_authority",
        content_type="news",
        published_at=date(2026, 10, 4),
        event_date=date(2026, 10, 3),  # 3 days old <= 30
        effective_from=None,
        last_verified_at=date(2026, 10, 6),
        current_status="current",
        supported=True,
        superseded=False,
        contradiction=False,
        competitor_product_claim=False,
    )
    res = evaluate_freshness(meta, as_of=as_of, max_event_age_days=30)
    assert res.status == "current"
    assert res.date_type == "event_date"
    assert res.date_used == date(2026, 10, 3)
    assert "falls within demo policy limit" in res.reason


def test_news_exceeding_policy_limit():
    as_of = date(2026, 10, 6)
    meta = Metadata(
        source_type="primary_authority",
        content_type="news",
        published_at=date(2026, 10, 5),
        event_date=date(2025, 1, 1),  # > 30 days old
        effective_from=None,
        last_verified_at=date(2026, 10, 6),
        current_status="current",
        supported=True,
        superseded=False,
        contradiction=False,
        competitor_product_claim=False,
    )
    res = evaluate_freshness(meta, as_of=as_of, max_event_age_days=30)
    assert res.status == "stale"
    assert res.date_type == "event_date"
    assert res.date_used == date(2025, 1, 1)
    assert "exceeds demo policy limit" in res.reason


def test_news_missing_event_date():
    as_of = date(2026, 10, 6)
    meta = Metadata(
        source_type="primary_authority",
        content_type="news",
        published_at=date(2026, 10, 4),
        event_date=None,
        effective_from=None,
        last_verified_at=date(2026, 10, 6),
        current_status="current",
        supported=True,
        superseded=False,
        contradiction=False,
        competitor_product_claim=False,
    )
    res = evaluate_freshness(meta, as_of=as_of, max_event_age_days=30)
    assert res.status == "unknown"
    assert res.date_used is None
    assert "unavailable" in res.reason


def test_old_regulation_currently_applicable():
    as_of = date(2026, 10, 6)
    meta = Metadata(
        source_type="primary_authority",
        content_type="regulation",
        published_at=date(2021, 1, 1),  # Published 5+ years ago
        event_date=date(2021, 1, 1),
        effective_from=date(2021, 6, 1),
        last_verified_at=date(2026, 10, 6),
        current_status="current",
        supported=True,
        superseded=False,
        contradiction=False,
        competitor_product_claim=False,
    )
    res = evaluate_freshness(meta, as_of=as_of)
    assert res.status == "current"
    assert res.date_type == "effective_from"
    assert res.date_used == date(2021, 6, 1)
    assert "remains currently applicable" in res.reason


def test_future_regulation_not_yet_applicable():
    as_of = date(2026, 10, 6)
    meta = Metadata(
        source_type="primary_authority",
        content_type="regulation",
        published_at=date(2026, 10, 4),
        event_date=date(2026, 10, 3),
        effective_from=date(2027, 1, 1),  # Future date
        last_verified_at=date(2026, 10, 6),
        current_status="adopted_not_applicable",
        supported=True,
        superseded=False,
        contradiction=False,
        competitor_product_claim=False,
    )
    res = evaluate_freshness(meta, as_of=as_of)
    assert res.status == "adopted_not_applicable"
    assert res.date_type == "effective_from"
    assert res.date_used == date(2027, 1, 1)
    assert "not yet in force" in res.reason


def test_superseded_regulation():
    as_of = date(2026, 10, 6)
    meta = Metadata(
        source_type="primary_authority",
        content_type="regulation",
        published_at=date(2026, 10, 4),
        event_date=date(2026, 10, 3),
        effective_from=date(2026, 10, 1),
        last_verified_at=date(2026, 10, 6),
        current_status="superseded",
        supported=True,
        superseded=True,
        contradiction=False,
        competitor_product_claim=False,
    )
    res = evaluate_freshness(meta, as_of=as_of)
    assert res.status == "superseded"
    assert "superseded" in res.reason

