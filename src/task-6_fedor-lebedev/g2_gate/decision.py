"""Decision precedence: reject > revise > human_review > pass.

Every stage contributes reasons; a reason with a route asks for that decision.
The final decision is the highest-precedence route requested by any reason.
``pass`` is never requested: it is what remains when nothing else is, and only
when a score exists. A weighted score therefore cannot override a failed hard
check, an unknown criterion or a freshness problem.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from . import codes
from .config import G2Policy
from .models import DECISION_PRECEDENCE, Decision
from .report import Reason, ScoreBreakdown
from .scoring import scoring_reasons


def decide(gate_reasons: Sequence[Reason], breakdown: Optional[ScoreBreakdown], policy: G2Policy
           ) -> Tuple[Decision, List[Reason]]:
    """Apply decision precedence.

    ``gate_reasons`` come from hard checks, freshness and criteria. ``breakdown``
    is the weighted score, or None when the case was not eligible for scoring.
    """
    routing, info = [], []
    for reason in gate_reasons:
        (routing if reason.route is not None else info).append(reason)

    score_routing, score_info = scoring_reasons(breakdown, policy)
    routing.extend(score_routing)

    if breakdown is not None and policy.require_calibration_for_pass and policy.calibration_status != "calibrated":
        routing.append(Reason(
            code=codes.CALIBRATION_REQUIRED, route=Decision.HUMAN_REVIEW, stage="policy", subject="calibration_status",
            message="The policy requires calibrated weights before an automatic pass; calibration is unavailable.",
        ))

    if breakdown is None and not routing:
        # Defensive: a pass needs a score. This should be unreachable.
        routing.append(Reason(
            code=codes.SCORE_UNAVAILABLE, route=Decision.HUMAN_REVIEW, stage="scoring", subject="score",
            message="No weighted score is available, so the case cannot pass automatically.",
        ))

    requested = {reason.route for reason in routing}
    decision = next(d for d in DECISION_PRECEDENCE if d in requested or d is Decision.PASS)

    routing.sort(key=lambda reason: DECISION_PRECEDENCE.index(reason.route))
    if decision is Decision.PASS:
        info = _pass_reasons() + score_info + info
    return decision, routing + info


def _pass_reasons() -> List[Reason]:
    return [
        Reason(code=codes.ALL_HARD_CHECKS_PASSED, route=None, stage="hard_check",
               message="All mandatory hard checks passed."),
        Reason(code=codes.FRESHNESS_PASSED, route=None, stage="freshness",
               message="The freshness and current-validity rule for this content type is satisfied."),
        Reason(code=codes.ALL_CRITERIA_KNOWN, route=None, stage="criteria",
               message="All required criteria are known and meet their floors."),
    ]
