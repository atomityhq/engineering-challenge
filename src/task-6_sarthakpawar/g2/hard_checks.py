"""Mandatory hard checks evaluated before any scoring.

Hard checks enforce non-negotiable policy boundaries:
1. Material claims must be supported by evidence.
2. Evidence must not be superseded.
3. Competitor product promotion is prohibited.

A failure in any hard check immediately disqualifies a case from passing,
regardless of how high any hypothetical weighted score would be.
"""

from __future__ import annotations

from g2.models import HardChecksResult, Metadata


def evaluate_hard_checks(metadata: Metadata) -> HardChecksResult:
    """Evaluate non-negotiable hard checks from metadata.

    Args:
        metadata: The case's evidence metadata.

    Returns:
        HardChecksResult containing the status of each check.
    """
    return HardChecksResult(
        material_claim_supported=metadata.supported,
        evidence_superseded=metadata.superseded,
        competitor_promotion=metadata.competitor_product_claim,
    )

