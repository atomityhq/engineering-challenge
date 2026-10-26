"""Criterion scores and the weighted sum.

Rule that matters most: an unknown criterion stays None. It is never turned into 0
or a default, because that would quietly invent evidence in either direction.
"""

from __future__ import annotations

from typing import Optional

from .config import CRITERIA, Policy, Weights
from .models import Metadata


def score_evidence_support(meta: Metadata) -> Optional[float]:
    """0 = unsupported, 1 = directly supported, None = unknown.

    0.5 (partial support) is defined in the anchors but the starter metadata is
    true/false, so it is not produced here. Contradiction is NOT counted here; it
    has its own hard check, so the same evidence is not penalised twice.
    """
    if meta.supported is None:
        return None
    return 1.0 if meta.supported else 0.0


def score_source_authority(meta: Metadata, policy: Policy) -> Optional[float]:
    """Looked up from the policy table. A source type not in the table is unknown, not 0."""
    return policy.source_authority_scores.get(meta.source_type)


def weighted_score(criteria: dict[str, Optional[float]], weights: Weights) -> Optional[float]:
    """score = sum(weight_i * criterion_i). None if any criterion is unknown."""
    if any(criteria[name] is None for name in CRITERIA):
        return None
    w = weights.as_dict()
    return round(sum(w[name] * criteria[name] for name in CRITERIA), 4)  # type: ignore[operator]
