"""Transparent weighted-sum scoring: score = sum(weight_i * criterion_i)."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from . import codes
from .config import CRITERIA, G2Policy, WeightConfig
from .models import Decision
from .report import FloorResult, Reason, ScoreBreakdown

FORMULA = "score = sum(weight_i * criterion_i) over evidence_support, source_authority, temporal_validity"


def weighted_score(criteria: Dict[str, float], weights: WeightConfig, policy: G2Policy) -> ScoreBreakdown:
    """Score a case whose criteria are all known. Callers must not pass unknown criteria."""
    unknown = [name for name in CRITERIA if criteria.get(name) is None]
    if unknown:
        raise ValueError(f"cannot score with unknown criteria {unknown}; route to human_review instead")
    contributions = {name: weights.weights[name] * criteria[name] for name in CRITERIA}
    # Rounded before the threshold comparison so binary floating-point artefacts
    # (0.7999999999999999) cannot flip a decision. A score equal to the threshold passes.
    score = round(math.fsum(contributions.values()), policy.score_decimals)
    floors = {
        name: FloorResult(minimum=rule.minimum, status=rule.status, met=criteria[name] >= rule.minimum)
        for name, rule in policy.criterion_floors.items()
    }
    return ScoreBreakdown(
        formula=FORMULA,
        weights_version=weights.version,
        weights_status=weights.status,
        weights=dict(weights.weights),
        contributions={name: round(value, policy.score_decimals) for name, value in contributions.items()},
        score=score,
        threshold=policy.threshold.value,
        threshold_status=policy.threshold.status,
        threshold_met=score >= policy.threshold.value,
        floors=floors,
    )


def scoring_reasons(breakdown: Optional[ScoreBreakdown], policy: G2Policy) -> Tuple[List[Reason], List[Reason]]:
    """Return (routing reasons, informational reasons) produced by the score."""
    if breakdown is None:
        return [], []
    routing: List[Reason] = []
    for name, floor in breakdown.floors.items():
        if not floor.met:
            rule = policy.criterion_floors[name]
            routing.append(Reason(
                code=codes.BELOW_CRITERION_FLOOR, route=Decision(rule.route), stage="scoring", subject=name,
                message=f"'{name}' is below its floor of {floor.minimum}. {rule.repair_hint}",
            ))
    if not breakdown.threshold_met:
        routing.append(Reason(
            code=codes.BELOW_THRESHOLD, route=Decision.HUMAN_REVIEW, stage="scoring", subject="score",
            message=(
                f"Score {breakdown.score} is below the provisional threshold {breakdown.threshold} and no "
                "automatic repair is known."
            ),
        ))
    info: List[Reason] = []
    if breakdown.threshold_met:
        info.append(Reason(
            code=codes.THRESHOLD_MET, route=None, stage="scoring", subject="score",
            message=f"Score {breakdown.score} meets the provisional, uncalibrated threshold {breakdown.threshold}.",
        ))
    return routing, info
