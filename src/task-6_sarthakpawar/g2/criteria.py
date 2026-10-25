"""Criterion scoring with explicit, observable anchors.

Each criterion is evaluated on a discrete scale [0.0, 0.5, 1.0] or None if unknown:
- evidence_support: 1.0 (direct support), 0.5 (partial or disputed), 0.0 (unsupported).
- source_authority: 1.0 (primary authority), 0.5 (secondary), 0.0 (competitor/inappropriate).
- temporal_validity: 1.0 (current/applicable), 0.5 (timing uncertain), 0.0 (stale/superseded).
"""

from __future__ import annotations

from g2.models import CriteriaScores, FreshnessAssessment, Metadata


def score_evidence_support(metadata: Metadata) -> float | None:
    """Evaluate evidence support score based on support and contradiction flags.

    Anchors:
    - 1.0: Directly and fully supported with no contradiction.
    - 0.5: Partial support or evidence has contradictions/disputes.
    - 0.0: Material claim is unsupported.
    - None: Support metadata unavailable.
    """
    if metadata.supported is None:
        return None

    if not metadata.supported:
        return 0.0

    if metadata.contradiction or metadata.support_level == "partial":
        return 0.5

    return 1.0


def score_source_authority(metadata: Metadata) -> float | None:
    """Evaluate source authority based on publisher classification.

    Anchors:
    - 1.0: Primary regulatory or issuing authority.
    - 0.5: Secondary reporting or indirect analytical source.
    - 0.0: Competitor source or inappropriate authority.
    - None: Source type unavailable.
    """
    if metadata.source_type == "primary_authority":
        return 1.0
    if metadata.source_type == "secondary":
        return 0.5
    if metadata.source_type == "competitor":
        return 0.0
    return None


def score_temporal_validity(
    metadata: Metadata, freshness: FreshnessAssessment
) -> float | None:
    """Evaluate temporal validity based on freshness assessment and timing flags.

    Anchors:
    - 1.0: Current and in-force, or correctly represented future regulation.
    - 0.5: Provisional or uncertain timing requiring human verification.
    - 0.0: Stale event date or superseded legal authority.
    - None: Event date or effective date is unknown.
    """
    if freshness.status == "unknown":
        return None

    if freshness.status in ("stale", "superseded"):
        return 0.0

    if metadata.timing_uncertain:
        return 0.5

    if freshness.status in ("current", "adopted_not_applicable"):
        return 1.0

    return None


def evaluate_criteria(
    metadata: Metadata, freshness: FreshnessAssessment
) -> CriteriaScores:
    """Compute scores for all three G2 criteria.

    Args:
        metadata: The case's evidence metadata.
        freshness: The evaluated freshness assessment.

    Returns:
        CriteriaScores object with evidence_support, source_authority, temporal_validity.
    """
    return CriteriaScores(
        evidence_support=score_evidence_support(metadata),
        source_authority=score_source_authority(metadata),
        temporal_validity=score_temporal_validity(metadata, freshness),
    )

