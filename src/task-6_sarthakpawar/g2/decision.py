"""Decision engine implementing strict hierarchical precedence.

Evaluation follows a strict, non-overlapping precedence order:
1. reject: Prohibited or fatal violations (e.g. competitor promotion).
2. revise: Known, repairable defects (unsupported claims, superseded sources, stale dates).
3. human_review: Ambiguities, unknown metadata, contradictions, or sub-threshold scores.
4. pass: All checks satisfied, threshold met, and criteria above floor.
"""

from __future__ import annotations

from g2.config import GateConfig
from g2.models import (
    CriteriaScores,
    DecisionType,
    FreshnessAssessment,
    HardChecksResult,
    Metadata,
)


def decide(
    metadata: Metadata,
    hard_checks: HardChecksResult,
    freshness: FreshnessAssessment,
    criteria: CriteriaScores,
    score: float | None,
    config: GateConfig,
) -> tuple[DecisionType, list[str]]:
    """Determine final gate decision and collect all triggering reasons.

    Args:
        metadata: Raw case metadata.
        hard_checks: Results of hard checks.
        freshness: Temporal validity and freshness assessment.
        criteria: Individual criterion scores.
        score: Weighted composite score (or None if ineligible).
        config: Gate configuration with thresholds and floors.

    Returns:
        Tuple of (DecisionType, list[str] of explanatory reason codes).
    """
    # 1. Reject (Fatal, non-remediable violations)
    if hard_checks.competitor_promotion:
        return "reject", ["COMPETITOR_PROMOTION"]

    # 2. Revise (Identified, remediable evidence defects)
    revise_reasons: list[str] = []
    if not hard_checks.material_claim_supported:
        revise_reasons.append("UNSUPPORTED_CLAIM")

    if hard_checks.evidence_superseded or metadata.current_status == "superseded":
        revise_reasons.append("SUPERSEDED_EVIDENCE")

    if freshness.status == "stale":
        revise_reasons.append("STALE_EVENT_DATE")

    if revise_reasons:
        return "revise", revise_reasons

    # 3. Human Review (Missing info, conflicts, or sub-threshold performance)
    review_reasons: list[str] = []

    if freshness.status == "unknown" or criteria.temporal_validity is None:
        review_reasons.append("UNKNOWN_TEMPORAL_METADATA")

    if criteria.evidence_support is None:
        review_reasons.append("UNKNOWN_EVIDENCE_SUPPORT")

    if criteria.source_authority is None:
        review_reasons.append("UNKNOWN_SOURCE_AUTHORITY")

    if metadata.contradiction:
        review_reasons.append("CONFLICTING_EVIDENCE")

    # If eligible and scored, check threshold and floor
    if score is not None:
        if score < config.threshold:
            review_reasons.append(
                f"SCORE_BELOW_THRESHOLD (score={score:.4f} < {config.threshold})"
            )
        scored_vals = [
            v
            for v in (
                criteria.evidence_support,
                criteria.source_authority,
                criteria.temporal_validity,
            )
            if v is not None
        ]
        if any(v < config.criterion_floor for v in scored_vals):
            review_reasons.append(
                f"CRITERION_BELOW_FLOOR (minimum criterion score < {config.criterion_floor})"
            )

    if review_reasons:
        return "human_review", review_reasons

    # 4. Pass (Eligible for next internal workflow stage)
    pass_reasons = ["ALL_CHECKS_PASSED"]
    if freshness.status == "adopted_not_applicable":
        pass_reasons.append("ADOPTED_FUTURE_REGULATION_NOT_CURRENTLY_APPLICABLE")

    return "pass", pass_reasons

