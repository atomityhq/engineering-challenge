"""Unit tests for criterion scoring anchors and unknown value preservation."""

from datetime import date
from g2.criteria import (
    evaluate_criteria,
    score_evidence_support,
    score_source_authority,
    score_temporal_validity,
)
from g2.evaluator import evaluate_case
from g2.models import Case, FreshnessAssessment, Metadata


def test_unknown_criterion_not_converted_to_zero():
    """Verify that unknown required criteria remain None and yield null score."""
    case = Case(
        id="case-with-unknown-date",
        statement="Event date unavailable",
        metadata=Metadata(
            source_type="primary_authority",
            content_type="news",
            published_at=date(2026, 10, 4),
            event_date=None,  # Missing date
            effective_from=None,
            last_verified_at=date(2026, 10, 6),
            current_status="current",
            supported=True,
            superseded=False,
            contradiction=False,
            competitor_product_claim=False,
        ),
    )

    report = evaluate_case(case, as_of=date(2026, 10, 6))

    # Criterion must be None, NOT 0.0
    assert report.criteria.temporal_validity is None
    # Weighted score must be null (None)
    assert report.score is None
    # Must route to human_review
    assert report.decision == "human_review"
    assert "UNKNOWN_TEMPORAL_METADATA" in report.reasons


def test_evidence_support_anchors():
    base_meta = {
        "source_type": "primary_authority",
        "content_type": "news",
        "published_at": date(2026, 10, 4),
        "event_date": date(2026, 10, 3),
        "effective_from": None,
        "last_verified_at": date(2026, 10, 6),
        "current_status": "current",
        "superseded": False,
        "competitor_product_claim": False,
    }

    # 1.0 anchor: supported and no contradiction
    meta_1 = Metadata(supported=True, contradiction=False, **base_meta)
    assert score_evidence_support(meta_1) == 1.0

    # 0.5 anchor: contradiction present
    meta_05_contra = Metadata(supported=True, contradiction=True, **base_meta)
    assert score_evidence_support(meta_05_contra) == 0.5

    # 0.5 anchor: partial support
    meta_05_part = Metadata(
        supported=True, contradiction=False, support_level="partial", **base_meta
    )
    assert score_evidence_support(meta_05_part) == 0.5

    # 0.0 anchor: unsupported
    meta_0 = Metadata(supported=False, contradiction=False, **base_meta)
    assert score_evidence_support(meta_0) == 0.0


def test_source_authority_anchors():
    base_meta = {
        "content_type": "news",
        "published_at": date(2026, 10, 4),
        "event_date": date(2026, 10, 3),
        "effective_from": None,
        "last_verified_at": date(2026, 10, 6),
        "current_status": "current",
        "supported": True,
        "superseded": False,
        "contradiction": False,
        "competitor_product_claim": False,
    }

    meta_primary = Metadata(source_type="primary_authority", **base_meta)
    assert score_source_authority(meta_primary) == 1.0

    meta_secondary = Metadata(source_type="secondary", **base_meta)
    assert score_source_authority(meta_secondary) == 0.5

    meta_competitor = Metadata(source_type="competitor", **base_meta)
    assert score_source_authority(meta_competitor) == 0.0


def test_temporal_validity_anchors():
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

    f_current = FreshnessAssessment(status="current", reason="ok")
    assert score_temporal_validity(meta, f_current) == 1.0

    f_stale = FreshnessAssessment(status="stale", reason="stale")
    assert score_temporal_validity(meta, f_stale) == 0.0

    f_superseded = FreshnessAssessment(status="superseded", reason="old")
    assert score_temporal_validity(meta, f_superseded) == 0.0

    f_unknown = FreshnessAssessment(status="unknown", reason="none")
    assert score_temporal_validity(meta, f_unknown) is None

    meta_uncertain = Metadata(
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
        timing_uncertain=True,
    )
    assert score_temporal_validity(meta_uncertain, f_current) == 0.5

