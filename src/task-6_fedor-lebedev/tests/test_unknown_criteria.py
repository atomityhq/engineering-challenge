"""A required unknown criterion is never silently turned into 0 or a default."""

import pytest

from g2_gate import codes
from g2_gate.evaluator import evaluate_fixture
from g2_gate.scoring import weighted_score


@pytest.mark.parametrize("overrides, criterion", [
    ({"supported": None}, "evidence_support"),
    ({"source_type": "unknown"}, "source_authority"),
    ({"event_date": None}, "temporal_validity"),
    ({"current_status": "unknown"}, "temporal_validity"),
    ({"content_type": "regulation", "effective_from": None}, "temporal_validity"),
])
def test_unknown_criterion_is_null_and_routes_to_human_review(make_case, evaluate, overrides, criterion):
    report = evaluate(make_case(**overrides))
    result = report.criteria[criterion]
    assert result.score is None, "unknown must stay null, never 0"
    assert result.unknown_reason, "the reason for the unknown value must be visible"
    assert report.score is None
    assert report.eligible_for_scoring is False
    assert any(f"unknown criteria: {criterion}" in w for w in report.score_withheld_because)
    assert report.decision.value == "human_review"
    unknown = [r for r in report.reasons if r.code == codes.UNKNOWN_CRITERION]
    assert [r.subject for r in unknown] == [criterion]
    assert "not scored as 0" in unknown[0].message


def test_other_criteria_are_still_reported_when_one_is_unknown(make_case, evaluate):
    report = evaluate(make_case(event_date=None))
    assert report.criteria["evidence_support"].score == 1.0
    assert report.criteria["source_authority"].score == 1.0


def test_unknown_with_a_known_defect_still_routes_to_the_defect(make_case, evaluate):
    # revise outranks human_review: the known repair is reported, and so is the unknown.
    report = evaluate(make_case(supported=False, event_date=None))
    assert report.decision.value == "revise"
    assert {codes.UNSUPPORTED_MATERIAL_CLAIM, codes.UNKNOWN_EVENT_DATE, codes.UNKNOWN_CRITERION} <= set(report.reason_codes)
    assert report.criteria["temporal_validity"].score is None


def test_scoring_refuses_unknown_criteria(policy, weights):
    with pytest.raises(ValueError, match="unknown criteria"):
        weighted_score({"evidence_support": 1.0, "source_authority": None, "temporal_validity": 1.0}, weights, policy)


def test_no_unknown_criterion_becomes_zero_across_all_fixtures(starter, edge_fixture, weighting_fixture, policy, weights):
    checked = 0
    for fixture in (starter, edge_fixture, weighting_fixture):
        for case, report in zip(fixture.cases, evaluate_fixture(fixture, policy, weights)):
            meta = case.metadata
            if meta.supported is None:
                assert report.criteria["evidence_support"].score is None
                checked += 1
            if meta.source_type.value == "unknown":
                assert report.criteria["source_authority"].score is None
                checked += 1
            if meta.content_type.value == "news" and meta.event_date is None:
                assert report.criteria["temporal_validity"].score is None
                checked += 1
            if any(result.score is None for result in report.criteria.values()):
                assert report.score is None
                assert report.decision.value in {"human_review", "revise", "reject"}
    assert checked >= 4
