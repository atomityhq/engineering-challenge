"""Hard checks run before scoring and cannot be overridden by it; precedence is fixed."""

import pytest

from g2_gate import codes
from g2_gate.decision import decide
from g2_gate.models import Decision
from g2_gate.report import FloorResult, Reason, ScoreBreakdown


def breakdown(score, threshold=0.8, floors_met=True):
    return ScoreBreakdown(
        formula="test",
        weights_version="provisional-v1",
        weights_status="provisional",
        weights={"evidence_support": 0.5, "source_authority": 0.3, "temporal_validity": 0.2},
        contributions={},
        score=score,
        threshold=threshold,
        threshold_status="provisional",
        threshold_met=score >= threshold,
        floors={name: FloorResult(minimum=0.5, status="provisional", met=floors_met)
                for name in ("evidence_support", "source_authority", "temporal_validity")},
    )


def hard_failure(route, code="TEST_HARD_FAILURE"):
    return Reason(code=code, route=route, stage="hard_check", subject="test", message="hard check failed")


@pytest.mark.parametrize("route", [Decision.REJECT, Decision.REVISE, Decision.HUMAN_REVIEW])
def test_failed_hard_check_with_high_score_does_not_pass(policy, route):
    decision, reasons = decide([hard_failure(route)], breakdown(0.95), policy)
    assert decision == route
    assert decision != Decision.PASS
    assert reasons[0].code == "TEST_HARD_FAILURE"


def test_high_score_alone_passes(policy):
    decision, reasons = decide([], breakdown(0.95), policy)
    assert decision == Decision.PASS
    assert codes.THRESHOLD_MET in [r.code for r in reasons]


def test_hard_failure_end_to_end_is_not_scored(make_case, evaluate):
    # Every criterion is at its best anchor, but the content promotes a competitor's product.
    report = evaluate(make_case(competitor_product_claim=True))
    assert all(result.score == 1.0 for result in report.criteria.values())
    assert report.decision.value == "reject"
    assert report.score is None and report.score_breakdown is None
    assert "hard checks not passed: no_competitor_promotion" in report.score_withheld_because


@pytest.mark.parametrize("overrides, expected", [
    ({"supported": False}, "revise"),
    ({"superseded": True, "current_status": "superseded"}, "revise"),
    ({"contradiction": True}, "human_review"),
    ({"source_type": "competitor"}, "human_review"),
])
def test_each_hard_check_blocks_a_pass(make_case, evaluate, overrides, expected):
    report = evaluate(make_case(**overrides))
    assert report.decision.value == expected
    assert report.score is None


@pytest.mark.parametrize("routes, expected", [
    ([Decision.HUMAN_REVIEW, Decision.REVISE, Decision.REJECT], Decision.REJECT),
    ([Decision.HUMAN_REVIEW, Decision.REVISE], Decision.REVISE),
    ([Decision.HUMAN_REVIEW], Decision.HUMAN_REVIEW),
])
def test_decision_precedence(policy, routes, expected):
    reasons = [hard_failure(route, code=f"R{i}") for i, route in enumerate(routes)]
    decision, ordered = decide(reasons, None, policy)
    assert decision == expected
    routed = [r.route for r in ordered if r.route is not None]
    assert routed == sorted(routed, key=[Decision.REJECT, Decision.REVISE, Decision.HUMAN_REVIEW].index)
    assert len(routed) == len(routes), "all problems are reported, not only the winning one"


def test_combined_unsupported_competitor_promotion_is_rejected(make_case, evaluate):
    report = evaluate(make_case(supported=False, competitor_product_claim=True, source_type="competitor"))
    assert report.decision.value == "reject"
    assert report.reason_codes[:3] == [
        codes.COMPETITOR_PRODUCT_PROMOTION, codes.UNSUPPORTED_MATERIAL_CLAIM, codes.COMPETITOR_SOURCE_NEEDS_JUDGMENT,
    ]


def test_below_threshold_without_known_repair_goes_to_human_review(policy):
    decision, reasons = decide([], breakdown(0.75), policy)
    assert decision == Decision.HUMAN_REVIEW
    assert reasons[0].code == codes.BELOW_THRESHOLD


def test_below_floor_routes_to_the_floor_repair(make_case, evaluate):
    report = evaluate(make_case(source_type="community"))
    assert report.eligible_for_scoring
    assert report.score_breakdown.floors["source_authority"].met is False
    assert report.decision.value == "revise"
    assert report.reasons[0].code == codes.BELOW_CRITERION_FLOOR


def test_floor_failure_beats_threshold_pass(policy):
    decision, reasons = decide([], breakdown(0.9, floors_met=False), policy)
    assert decision == Decision.REVISE
    assert {r.code for r in reasons} == {codes.BELOW_CRITERION_FLOOR}


def test_pass_is_impossible_without_a_score(policy):
    decision, reasons = decide([], None, policy)
    assert decision == Decision.HUMAN_REVIEW
    assert reasons[0].code == codes.SCORE_UNAVAILABLE


def test_policy_can_require_calibration_before_pass(make_case, evaluate, policy):
    strict = policy.model_copy(update={"require_calibration_for_pass": True})
    report = evaluate(make_case(), policy_override=strict)
    assert report.score == 1.0
    assert report.decision.value == "human_review"
    assert report.reasons[0].code == codes.CALIBRATION_REQUIRED


def test_pass_reasons_are_explicit(make_case, evaluate):
    report = evaluate(make_case())
    assert report.decision.value == "pass"
    assert report.reason_codes[:4] == [
        codes.ALL_HARD_CHECKS_PASSED, codes.FRESHNESS_PASSED, codes.ALL_CRITERIA_KNOWN, codes.THRESHOLD_MET,
    ]
    assert "Not publication approval" in report.decision_meaning


def test_floors_are_marked_provisional(make_case, evaluate):
    floors = evaluate(make_case()).score_breakdown.floors
    assert {floor.status for floor in floors.values()} == {"provisional"}
