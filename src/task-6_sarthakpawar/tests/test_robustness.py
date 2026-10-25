"""Robustness, decision precedence, case-ID independence, and bad input tests."""

import json
from datetime import date
from pathlib import Path
import pytest
from pydantic import ValidationError

from g2.config import GateConfig
from g2.evaluator import evaluate_case, evaluate_fixture, load_fixture
from g2.models import Case, FixtureEnvelope, Metadata


def test_decision_precedence_competitor_and_stale_gives_reject():
    """Verify that a case that is BOTH competitor promotion AND stale yields reject.

    Precedence 1 (reject) must override Precedence 2 (revise).
    """
    case = Case(
        id="competitor-and-stale",
        statement="Competitor ad with ancient event date",
        metadata=Metadata(
            source_type="competitor",
            content_type="news",
            published_at=date(2026, 10, 4),
            event_date=date(2020, 1, 1),  # Stale: > 30 days
            effective_from=None,
            last_verified_at=date(2026, 10, 6),
            current_status="current",
            supported=True,
            superseded=False,
            contradiction=False,
            competitor_product_claim=True,  # Prohibited competitor promotion
        ),
    )

    report = evaluate_case(case, as_of=date(2026, 10, 6))

    # Reject must take precedence over revise
    assert report.decision == "reject"
    assert "COMPETITOR_PROMOTION" in report.reasons
    assert report.score is None


def test_case_id_independence():
    """Verify that renaming all case IDs does not alter decisions or scores.

    Proves the evaluator relies strictly on metadata, not hard-coded ID matching.
    """
    test_dir = Path(__file__).resolve().parent
    workspace_root = test_dir.parent.parent.parent
    fixture_path = workspace_root / "fixtures" / "g2-cases.json"
    envelope = load_fixture(fixture_path)
    config = GateConfig()

    original_reports = [evaluate_case(c, envelope.as_of, config) for c in envelope.cases]

    # Create mutated cases with arbitrary synthetic IDs
    mutated_cases = []
    for idx, c in enumerate(envelope.cases):
        mutated_c = Case(
            id=f"arbitrary-anonymous-id-{idx:04d}",
            statement=c.statement,
            metadata=c.metadata,
        )
        mutated_cases.append(mutated_c)

    mutated_reports = [evaluate_case(c, envelope.as_of, config) for c in mutated_cases]

    assert len(original_reports) == len(mutated_reports)
    for orig, mut in zip(original_reports, mutated_reports):
        assert orig.decision == mut.decision
        assert orig.score == mut.score
        assert orig.reasons == mut.reasons
        assert orig.hard_checks == mut.hard_checks
        assert orig.criteria == mut.criteria


def test_edge_dates():
    """Test date boundary conditions: future news event and regulation with null effective date."""
    as_of = date(2026, 10, 6)

    # 1. News event in the future relative to as_of
    future_news = Case(
        id="future-news-event",
        statement="A news event dated tomorrow",
        metadata=Metadata(
            source_type="primary_authority",
            content_type="news",
            published_at=date(2026, 10, 5),
            event_date=date(2026, 10, 20),  # Future date
            effective_from=None,
            last_verified_at=as_of,
            current_status="current",
            supported=True,
            superseded=False,
            contradiction=False,
            competitor_product_claim=False,
        ),
    )
    rep_future_news = evaluate_case(future_news, as_of)
    assert rep_future_news.freshness.status == "unknown"
    assert rep_future_news.decision == "human_review"
    assert rep_future_news.score is None

    # 2. Regulation with null effective_from date
    null_eff_reg = Case(
        id="regulation-null-effective-date",
        statement="Regulation with missing effective date",
        metadata=Metadata(
            source_type="primary_authority",
            content_type="regulation",
            published_at=date(2025, 1, 1),
            event_date=date(2025, 1, 1),
            effective_from=None,  # Missing effective date
            last_verified_at=as_of,
            current_status="current",
            supported=True,
            superseded=False,
            contradiction=False,
            competitor_product_claim=False,
        ),
    )
    rep_null_reg = evaluate_case(null_eff_reg, as_of)
    assert rep_null_reg.freshness.status == "unknown"
    assert rep_null_reg.decision == "human_review"
    assert rep_null_reg.score is None


def test_bad_input_files(tmp_path: Path):
    """Test error handling on missing, malformed, or invalid fixture envelopes."""
    # 1. Missing file path
    non_existent = tmp_path / "does-not-exist.json"
    with pytest.raises(FileNotFoundError):
        load_fixture(non_existent)

    # 2. Malformed JSON syntax
    bad_json = tmp_path / "malformed.json"
    bad_json.write_text("{ this is not valid json }", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_fixture(bad_json)

    # 3. Invalid schema envelope (missing required fields)
    invalid_envelope = tmp_path / "bad_envelope.json"
    invalid_envelope.write_text(
        json.dumps({"synthetic": True, "cases": []}), encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        load_fixture(invalid_envelope)


def test_expected_decision_isolation():
    """Verify evaluator operates correctly when expected_decision is completely absent."""
    as_of = date(2026, 10, 6)
    case_dict = {
        "id": "case-without-expected-decision",
        "statement": "Normal primary authority news item",
        "metadata": {
            "source_type": "primary_authority",
            "content_type": "news",
            "published_at": "2026-10-04",
            "event_date": "2026-10-03",
            "effective_from": None,
            "last_verified_at": "2026-10-06",
            "current_status": "current",
            "supported": True,
            "superseded": False,
            "contradiction": False,
            "competitor_product_claim": False,
        },
        # No 'expected_decision' key
    }
    case = Case.model_validate(case_dict)
    assert case.expected_decision is None

    report = evaluate_case(case, as_of)
    assert report.decision == "pass"
    assert report.score == 1.0

