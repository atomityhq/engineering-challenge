"""Decision precedence: reject > revise > human_review > pass.

Why this order: the more final or the more fixable the problem, the earlier it wins.
  reject        prohibited, not fixable (competitor promotion)
  revise        known, repairable defect (unsupported, superseded, stale)
  human_review  we cannot tell (unknown, conflicting, below the bar)
  pass          only when nothing above applies

Fail-safe: if the gate somehow cannot prove a pass, it routes to human_review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import CRITERIA, Policy
from .models import Decision

# Which reason codes belong to which tier.
REJECT_CODES = {"COMPETITOR_PROMOTION"}
REVISE_CODES = {"UNSUPPORTED_CLAIM", "SUPERSEDED_EVIDENCE", "STALE_EVENT"}
# Everything else that is a finding is a human_review code.


@dataclass(frozen=True)
class Outcome:
    decision: Decision
    reasons: list[str]
    additional_findings: list[str]


def decide(
    findings: list[str],
    hard_checks: dict[str, Optional[bool]],
    criteria: dict[str, Optional[float]],
    score: Optional[float],
    policy: Policy,
) -> Outcome:
    reject = [f for f in findings if f in REJECT_CODES]
    revise = [f for f in findings if f in REVISE_CODES]
    review = [f for f in findings if f not in REJECT_CODES | REVISE_CODES]

    # Score-based reasons only exist if a score could be computed at all.
    if score is not None:
        known = [criteria[c] for c in CRITERIA if criteria[c] is not None]
        if any(v < policy.criterion_floor for v in known):  # type: ignore[operator]
            review.append("CRITERION_BELOW_FLOOR")
        if score < policy.pass_threshold:
            review.append("BELOW_THRESHOLD")

    tiers = [("reject", reject), ("revise", revise), ("human_review", review)]
    for index, (name, codes) in enumerate(tiers):
        if codes:
            lower = [c for _, group in tiers[index + 1 :] for c in group]
            return Outcome(name, _dedupe(codes), _dedupe(lower))  # type: ignore[arg-type]

    # Nothing is wrong. Only pass when every pass condition is proven.
    proven = (
        all(v is True for v in hard_checks.values())
        and all(criteria[c] is not None for c in CRITERIA)
        and score is not None
        and score >= policy.pass_threshold
    )
    if not proven:
        return Outcome("human_review", ["INCOMPLETE_EVALUATION"], [])
    return Outcome(
        "pass",
        ["ALL_HARD_CHECKS_PASSED", "ALL_CRITERIA_KNOWN", "THRESHOLD_MET"],
        [],
    )


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
