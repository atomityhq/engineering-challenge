"""Unit tests for hard checks and immunity against high scores."""

from datetime import date
from g2.config import GateConfig
from g2.decision import decide
from g2.evaluator import evaluate_case
from g2.hard_checks import evaluate_hard_checks
from g2.models import (
    Case,
    CriteriaScores,
    FreshnessAssessment,
    HardChecksResult,
    Metadata,
)


def test_hard_check_evaluation():
    meta = Metadata(
        source_type="primary_authority",
        content_type="news",
        published_at=date(2026, 10, 4),
        event_date=date(2026, 10, 3),
        effective_from=None,
        last_verified_at=date(2026, 10, 6),
        current_status="current",
        supported=True,
        superseded=False,
        contradiction=False,
        competitor_product_claim=False,
    )
    res = evaluate_hard_checks(meta)
    assert res.all_passed() is True
    assert res.material_claim_supported is True
    assert res.evidence_superseded is False
    assert res.competitor_promotion is False


def test_hard_failure_cannot_pass_with_high_score():
    """Verify that a case failing hard checks CANNOT pass, even if score is 0.95."""
    meta = Metadata(
        source_type="primary_authority",
        content_type="news",
        published_at=date(2026, 10, 4),
        event_date=date(2026, 10, 3),
        effective_from=None,
        last_verified_at=date(2026, 10, 6),
        current_status="current",
        supported=False,  # Fails hard check
        superseded=False,
        contradiction=False,
        competitor_product_claim=False,
    )

    hard = evaluate_hard_checks(meta)
    assert hard.all_passed() is False

    freshness = FreshnessAssessment(
        status="current",
        date_type="event_date",
        date_used=date(2026, 10, 3),
        reason="Current",
    )
    criteria = CriteriaScores(
        evidence_support=1.0,
        source_authority=1.0,
        temporal_validity=1.0,
    )
    config = GateConfig()

    # Artificially inject a high hypothetical score of 0.95
    decision, reasons = decide(
        metadata=meta,
        hard_checks=hard,
        freshness=freshness,
        criteria=criteria,
        score=0.95,
        config=config,
    )

    # Must route to revise due to UNSUPPORTED_CLAIM, never pass
    assert decision != "pass"
    assert decision == "revise"
    assert "UNSUPPORTED_CLAIM" in reasons


def test_competitor_promotion_hard_check_rejects():
    """Verify that competitor promotion hard failure results in reject."""
    case = Case(
        id="test-competitor",
        statement="Competitor ad",
        metadata=Metadata(
            source_type="competitor",
            content_type="news",
            published_at=date(2026, 10, 4),
            event_date=date(2026, 10, 3),
            effective_from=None,
            last_verified_at=date(2026, 10, 6),
            current_status="current",
            supported=True,
            superseded=False,
            contradiction=False,
            competitor_product_claim=True,
        ),
    )
    report = evaluate_case(case, as_of=date(2026, 10, 6))
    assert report.decision == "reject"
    assert report.score is None
    assert "COMPETITOR_PROMOTION" in report.reasons

