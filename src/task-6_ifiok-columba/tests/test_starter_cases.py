"""Every supplied starter case, routed from its data (never from its id)."""

import pytest

from g2_gate.evaluator import evaluate_fixture


def test_all_supplied_cases_are_processed(supplied, policy):
    fixture, expectations = supplied
    reports = evaluate_fixture(fixture, policy)
    assert [r.case_id for r in reports] == [c.id for c in fixture.cases]
    assert len(reports) == 9
    assert set(expectations) == {r.case_id for r in reports}


def test_each_supplied_case_matches_expected_decision(supplied, policy):
    fixture, expectations = supplied
    for report in evaluate_fixture(fixture, policy):
        assert report.decision == expectations[report.case_id], report.case_id


def test_extra_cases_match_expected_decision(extra, policy):
    fixture, expectations = extra
    for report in evaluate_fixture(fixture, policy):
        assert report.decision == expectations[report.case_id], report.case_id


def by_id(supplied, policy):
    fixture, _ = supplied
    return {r.case_id: r for r in evaluate_fixture(fixture, policy)}


def test_old_law_is_not_penalised_for_old_publication(supplied, policy):
    r = by_id(supplied, policy)["old-law-current"]
    assert r.decision == "pass"
    assert r.freshness.status == "current"
    assert r.freshness.applicability == "applicable_now"
    assert r.criteria["temporal_validity"] == 1.0


def test_recent_article_about_old_event_is_stale(supplied, policy):
    r = by_id(supplied, policy)["recent-article-old-event"]
    assert r.decision == "revise"
    assert r.reasons == ["STALE_EVENT"]
    assert r.freshness.status == "stale"
    assert r.freshness.date_type == "event_date"
    assert r.freshness.age_days == 643


def test_future_rule_passes_but_is_never_called_applicable(supplied, policy):
    r = by_id(supplied, policy)["future-rule"]
    assert r.decision == "pass"
    assert r.freshness.status == "future"
    assert r.freshness.applicability == "not_yet_applicable"
    assert "RULE_NOT_YET_APPLICABLE" in r.notes


def test_unknown_event_date_stays_unknown(supplied, policy):
    r = by_id(supplied, policy)["unknown-date"]
    assert r.decision == "human_review"
    assert r.reasons == ["UNKNOWN_EVENT_DATE"]
    assert r.freshness.status == "unknown"
    assert r.freshness.date_used is None
    assert r.criteria["temporal_validity"] is None  # not 0, not a default
    assert r.score is None


def test_conflicting_evidence_goes_to_a_person(supplied, policy):
    r = by_id(supplied, policy)["conflicting-evidence"]
    assert r.decision == "human_review"
    assert r.reasons == ["CONFLICTING_EVIDENCE"]
    assert r.hard_checks["no_conflicting_evidence"] is False


def test_competitor_promotion_is_rejected(supplied, policy):
    r = by_id(supplied, policy)["competitor-promotion"]
    assert r.decision == "reject"
    assert r.hard_checks["no_competitor_promotion"] is False
    assert r.score is None


@pytest.mark.parametrize("case_id", ["unsupported-claim", "superseded-source"])
def test_repairable_defects_are_revise(supplied, policy, case_id):
    r = by_id(supplied, policy)[case_id]
    assert r.decision == "revise"
    assert r.score is None  # hard check failed, so no weighted result


def test_every_report_carries_policy_and_calibration(supplied, policy):
    fixture, _ = supplied
    for r in evaluate_fixture(fixture, policy):
        assert r.gate == "G2"
        assert r.policy_version == "prototype-v1"
        assert r.calibration_status == "uncalibrated"
        assert r.weights_version == "provisional-v1"
        assert r.freshness.reason
        assert "not a probability" in r.score_note
