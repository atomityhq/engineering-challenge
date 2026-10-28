"""G2 evaluation pipeline.

    case -> hard checks -> freshness / current validity -> criteria
         -> weighted score (only when eligible) -> decision precedence -> report

The evaluator sees only :class:`G2Case` (id, statement, metadata) plus the
fixture's ``as_of`` and demo policy. It never reads ``expected_decision``,
never inspects case ids or statement text, and never reads the system clock.
"""

from __future__ import annotations

import hashlib
import json
from typing import List

from .config import CRITERIA, G2Policy, WeightConfig
from .criteria import score_criteria
from .decision import decide
from .freshness import assess_freshness
from .hard_checks import run_hard_checks
from .models import EvaluationContext, FixtureCase, G2Case, G2Fixture
from .report import DECISION_MEANING, SCORE_INTERPRETATION, G2Report
from .scoring import weighted_score


def _digest(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def config_digest(policy: G2Policy, weights: WeightConfig) -> str:
    return _digest({"policy": policy.model_dump(mode="json"), "weights": weights.model_dump(mode="json")})


def evaluate_case(case: G2Case, context: EvaluationContext, policy: G2Policy, weights: WeightConfig) -> G2Report:
    if isinstance(case, FixtureCase):
        # Keep test-only expectations out of the evaluator by construction.
        raise TypeError("evaluate_case takes a G2Case; call FixtureCase.to_gate_input() first")

    meta = case.metadata
    hard_checks, hard_reasons = run_hard_checks(meta)
    freshness, freshness_reasons = assess_freshness(meta, context.as_of, context.demo_policy, policy)
    criteria, criteria_reasons = score_criteria(meta, freshness, policy)

    withheld: List[str] = []
    failed_checks = [name for name, check in hard_checks.items() if check.status != "pass"]
    if failed_checks:
        withheld.append(f"hard checks not passed: {', '.join(failed_checks)}")
    if freshness.passed is not True:
        withheld.append(f"freshness status is '{freshness.status.value}'")
    unknown = [name for name in CRITERIA if criteria[name].score is None]
    if unknown:
        withheld.append(f"unknown criteria: {', '.join(unknown)}")

    breakdown = None
    if not withheld:
        breakdown = weighted_score({name: criteria[name].score for name in CRITERIA}, weights, policy)

    decision, reasons = decide(hard_reasons + freshness_reasons + criteria_reasons, breakdown, policy)

    return G2Report(
        case_id=case.id,
        gate="G2",
        as_of=context.as_of,
        policy_version=policy.policy_version,
        weights_version=weights.version,
        calibration_status=policy.calibration_status,
        config_digest=config_digest(policy, weights),
        input_digest=_digest({"context": context.model_dump(mode="json"), "case": case.model_dump(mode="json")}),
        hard_checks=hard_checks,
        freshness=freshness,
        criteria=criteria,
        weights=dict(weights.weights),
        eligible_for_scoring=breakdown is not None,
        score=breakdown.score if breakdown else None,
        score_breakdown=breakdown,
        score_withheld_because=withheld,
        score_interpretation=SCORE_INTERPRETATION,
        decision=decision,
        decision_meaning=DECISION_MEANING[decision],
        reasons=reasons,
    )


def evaluate_fixture(fixture: G2Fixture, policy: G2Policy, weights: WeightConfig) -> List[G2Report]:
    context = EvaluationContext.from_fixture(fixture)
    return [evaluate_case(case.to_gate_input(), context, policy, weights) for case in fixture.cases]
