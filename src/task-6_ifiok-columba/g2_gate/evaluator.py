"""Runs one case through the gate, in a fixed order:

  hard checks -> freshness -> criterion scores -> weighted score -> decision

The evaluator reads ONLY the structured metadata. It never looks at the case id or the
statement text, so renaming a case or putting instructions in a statement changes nothing.
"""

from __future__ import annotations

from typing import Optional

from . import GATE_ID
from .checks import run_hard_checks
from .config import Policy
from .decision import decide
from .freshness import assess_freshness
from .models import Case, Fixture, Report
from .scoring import score_evidence_support, score_source_authority, weighted_score

SCORE_NOTE = (
    "Prototype index, not a probability. Weights and threshold are provisional "
    "and uncalibrated."
)


def evaluate_case(
    case: Case,
    fixture: Fixture,
    policy: Policy,
) -> Report:
    meta = case.metadata

    hard = run_hard_checks(meta)

    fresh = assess_freshness(
        meta,
        fixture.as_of,
        fixture.demo_policy.news_max_event_age_days,
        policy.verification_max_age_days,
    )

    criteria: dict[str, Optional[float]] = {
        "evidence_support": score_evidence_support(meta),
        "source_authority": score_source_authority(meta, policy),
        "temporal_validity": fresh.temporal_score,
    }

    findings = _collect_findings(meta, hard, criteria, fresh.finding)

    # A failed hard check means no weighted result at all, so it cannot be "averaged away".
    hard_failed = any(v is False for v in hard.values())
    score = None if hard_failed else weighted_score(criteria, policy.weights)

    outcome = decide(findings, hard, criteria, score, policy)

    return Report(
        case_id=case.id,
        gate=GATE_ID,
        statement=case.statement,
        policy_version=policy.policy_version,
        calibration_status=policy.calibration_status,
        as_of=fixture.as_of,
        hard_checks=hard,
        criteria=criteria,
        freshness=fresh.freshness,
        weights_version=policy.weights_version,
        weights=policy.weights.as_dict(),
        score=score,
        score_note=SCORE_NOTE,
        decision=outcome.decision,
        reasons=outcome.reasons,
        additional_findings=outcome.additional_findings,
        notes=list(fresh.notes),
    )


def evaluate_fixture(fixture: Fixture, policy: Policy) -> list[Report]:
    return [evaluate_case(case, fixture, policy) for case in fixture.cases]


def _collect_findings(
    meta,
    hard: dict[str, Optional[bool]],
    criteria: dict[str, Optional[float]],
    freshness_finding: Optional[str],
) -> list[str]:
    findings: list[str] = []
    if hard["no_competitor_promotion"] is False:
        findings.append("COMPETITOR_PROMOTION")
    if hard["material_claim_supported"] is False:
        findings.append("UNSUPPORTED_CLAIM")
    if hard["material_claim_supported"] is None:
        findings.append("UNKNOWN_SUPPORT")
    if hard["evidence_not_superseded"] is False:
        findings.append("SUPERSEDED_EVIDENCE")
    if hard["no_conflicting_evidence"] is False:
        findings.append("CONFLICTING_EVIDENCE")
    if freshness_finding:
        findings.append(freshness_finding)
    if criteria["source_authority"] is None:
        findings.append("UNKNOWN_SOURCE_AUTHORITY")
    return findings
