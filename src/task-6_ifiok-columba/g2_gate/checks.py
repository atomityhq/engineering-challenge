"""Hard checks. These run first and a failed one can never be bought back by a high score.

Each value is True (passed), False (failed) or None (unknown).
"""

from __future__ import annotations

from typing import Optional

from .models import Metadata

HARD_CHECK_NAMES = (
    "material_claim_supported",
    "evidence_not_superseded",
    "no_competitor_promotion",
    "no_conflicting_evidence",
)


def run_hard_checks(meta: Metadata) -> dict[str, Optional[bool]]:
    # If the two "superseded" signals disagree, trust the stricter one.
    superseded = meta.superseded or meta.current_status == "superseded"
    return {
        "material_claim_supported": meta.supported,
        "evidence_not_superseded": not superseded,
        "no_competitor_promotion": not meta.competitor_product_claim,
        "no_conflicting_evidence": not meta.contradiction,
    }
