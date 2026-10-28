"""Every supplied starter case, routed from its data alone.

Expected decisions are read from the fixture after evaluation; the evaluator
never receives them.
"""

import datetime as dt
import json

import pytest

from g2_gate import codes
from g2_gate.evaluator import evaluate_fixture
from g2_gate.paths import STARTER_FIXTURE

STARTER_IDS = [case["id"] for case in json.loads(STARTER_FIXTURE.read_text(encoding="utf-8"))["cases"]]


@pytest.fixture(scope="module")
def reports(starter, policy, weights):
    return {report.case_id: report for report in evaluate_fixture(starter, policy, weights)}


def test_every_starter_case_is_evaluated(starter, reports):
    assert len(starter.cases) == 9
    assert sorted(reports) == sorted(case.id for case in starter.cases)


@pytest.mark.parametrize("case_id", STARTER_IDS)
def test_starter_routing_matches_expected_decision(case_id, starter, reports):
    expected = {case.id: case.expected_decision for case in starter.cases}[case_id]
    assert reports[case_id].decision == expected


@pytest.mark.parametrize("case_id", STARTER_IDS)
def test_report_exposes_every_required_section(case_id, reports):
    report = reports[case_id]
    assert report.gate == "G2"
    assert report.as_of == dt.date(2026, 10, 6)
    assert report.policy_version == "g2-prototype-v1"
    assert report.weights_version == "provisional-v1"
    assert report.calibration_status == "uncalibrated"
    assert set(report.hard_checks) == {
        "no_competitor_promotion", "material_claim_supported", "evidence_not_superseded",
        "no_material_contradiction", "source_not_competitor",
    }
    assert set(report.criteria) == {"evidence_support", "source_authority", "temporal_validity"}
    assert report.freshness.status and report.freshness.explanation
    assert report.weights == {"evidence_support": 0.5, "source_authority": 0.3, "temporal_validity": 0.2}
    assert report.reasons, "every decision must carry reasons"
    assert "not a probability" in report.score_interpretation
    if report.eligible_for_scoring:
        assert report.score is not None and report.score_breakdown is not None
        assert report.score_withheld_because == []
    else:
        assert report.score is None and report.score_breakdown is None
        assert report.score_withheld_because


def test_current_news_passes_on_event_date(reports):
    report = reports["current-news"]
    assert report.freshness.status.value == "current"
    assert report.freshness.reference_date_type == "event_date"
    assert report.freshness.reference_age_days == 3
    assert report.score == 1.0
    assert report.score_breakdown.threshold_met


def test_old_regulation_still_in_force_is_current(reports):
    report = reports["old-law-current"]
    assert report.decision.value == "pass"
    assert report.freshness.status.value == "current"
    assert report.freshness.reference_date_type == "effective_from"
    assert report.freshness.max_age_days is None, "no universal age penalty for regulation"
    assert report.freshness.currently_applicable is True
    assert "not used" in report.freshness.explanation


def test_recent_article_about_old_event_is_stale_by_event_date(reports):
    report = reports["recent-article-old-event"]
    assert report.freshness.status.value == "stale"
    assert report.freshness.reference_date == dt.date(2025, 1, 1)
    assert report.freshness.reference_age_days == 643
    assert report.freshness.dates["published_at"] == dt.date(2026, 10, 5)
    assert "publication date 2026-10-05 is recent" in report.freshness.explanation
    assert [r.code for r in report.reasons if r.route] == [codes.STALE_EVENT]
    assert report.criteria["temporal_validity"].score == 0.0


def test_unknown_event_date_is_null_not_zero(reports):
    report = reports["unknown-date"]
    assert report.criteria["temporal_validity"].score is None
    assert report.criteria["temporal_validity"].unknown_reason
    assert report.score is None
    assert report.freshness.status.value == "unknown"
    assert codes.UNKNOWN_EVENT_DATE in report.reason_codes


def test_unsupported_claim_fails_hard_check(reports):
    report = reports["unsupported-claim"]
    assert report.hard_checks["material_claim_supported"].status == "fail"
    assert report.reason_codes[0] == codes.UNSUPPORTED_MATERIAL_CLAIM


def test_superseded_source_fails_hard_check(reports):
    report = reports["superseded-source"]
    assert report.hard_checks["evidence_not_superseded"].status == "fail"
    assert report.freshness.status.value == "superseded"
    assert report.freshness.currently_applicable is False
    assert report.criteria["temporal_validity"].score == 0.0


def test_competitor_promotion_is_rejected_first(reports):
    report = reports["competitor-promotion"]
    assert report.hard_checks["no_competitor_promotion"].status == "fail"
    assert report.reasons[0].code == codes.COMPETITOR_PRODUCT_PROMOTION
    assert report.reasons[0].route.value == "reject"


def test_conflicting_evidence_goes_to_human_review(reports):
    report = reports["conflicting-evidence"]
    assert report.hard_checks["no_material_contradiction"].status == "fail"
    assert report.criteria["evidence_support"].score == 0.5
    assert report.score is None


def test_future_rule_passes_but_is_not_presented_as_applicable(reports):
    report = reports["future-rule"]
    assert report.decision.value == "pass"
    assert report.freshness.status.value == "not_yet_applicable"
    assert report.freshness.passed is True
    assert report.freshness.currently_applicable is False
    assert report.freshness.applicable_from == dt.date(2027, 1, 1)
    assert "not applicable until 2027-01-01" in report.freshness.presentation_constraint
    assert codes.NOT_YET_APPLICABLE in report.reason_codes
