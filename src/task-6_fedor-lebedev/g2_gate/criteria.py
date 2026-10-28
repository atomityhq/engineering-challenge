"""Criterion definitions, observable anchors and scoring.

Each criterion reads a distinct part of the input so the same evidence is not
counted twice:

* evidence_support  <- supported / qualified_support / contradiction
* source_authority  <- source_type (via the policy's authority table)
* temporal_validity <- the freshness assessment (dates, status, verification)

A criterion that cannot be determined is ``None`` with a visible reason. It is
never replaced by 0 or by a default.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from . import codes
from .config import G2Policy
from .models import CaseMetadata, Decision
from .report import CriterionResult, FreshnessAssessment, FreshnessStatus, Reason

DEFINITIONS: Dict[str, Dict[str, object]] = {
    "evidence_support": {
        "question": "Does the supplied evidence support the material claim?",
        "anchors": {
            "0": "supported=false: the material claim is unsupported by the supplied evidence.",
            "0.5": "supported=true, but the support is qualified (qualified_support=true) or other supplied evidence contradicts it (contradiction=true).",
            "1": "supported=true with no qualification and no contradiction recorded: the claim is directly supported.",
            "null": "supported=null: upstream validation did not determine support.",
        },
    },
    "source_authority": {
        "question": "How authoritative is the supplied source for the claim being evaluated?",
        "anchors": {
            "0": "community or competitor source: no independent authority for the claim.",
            "0.5": "secondary_reporting: relays a primary source; useful but indirect.",
            "1": "primary_authority: the body that issued the rule or owns the announced fact.",
            "null": "source_type=unknown: authority cannot be assessed.",
        },
    },
    "temporal_validity": {
        "question": "Is the evidence temporally valid for the claim at as_of?",
        "anchors": {
            "0": "Evidence is superseded, or the news event is outside the demo freshness window.",
            "0.5": "Timing is valid (event within window, rule in force, or future rule correctly flagged), but current status was not verified within the verification window.",
            "1": "Timing is valid and current status was verified within the verification window.",
            "null": "Required temporal metadata is unknown or conflicting, or the event is future-dated.",
        },
    },
}


def _evidence_support(meta: CaseMetadata) -> CriterionResult:
    basis = {
        "supported": meta.supported,
        "qualified_support": meta.qualified_support,
        "contradiction": meta.contradiction,
    }
    anchors = DEFINITIONS["evidence_support"]["anchors"]
    if meta.supported is None:
        return CriterionResult(score=None, anchor=None, basis=basis, unknown_reason=anchors["null"])
    if meta.supported is False:
        return CriterionResult(score=0.0, anchor=anchors["0"], basis=basis, unknown_reason=None)
    if meta.qualified_support or meta.contradiction:
        return CriterionResult(score=0.5, anchor=anchors["0.5"], basis=basis, unknown_reason=None)
    return CriterionResult(score=1.0, anchor=anchors["1"], basis=basis, unknown_reason=None)


def _source_authority(meta: CaseMetadata, policy: G2Policy) -> CriterionResult:
    entry = policy.source_authority[meta.source_type]
    basis = {"source_type": meta.source_type.value}
    if entry.score is None:
        return CriterionResult(
            score=None, anchor=None, basis=basis,
            unknown_reason=f"No authority score is defined for source_type '{meta.source_type.value}': {entry.anchor}",
        )
    return CriterionResult(score=entry.score, anchor=entry.anchor, basis=basis, unknown_reason=None)


def _temporal_validity(freshness: FreshnessAssessment) -> CriterionResult:
    anchors = DEFINITIONS["temporal_validity"]["anchors"]
    basis = {
        "freshness_status": freshness.status.value,
        "verified_within_window": freshness.verification.within_window,
    }
    if freshness.status in (FreshnessStatus.SUPERSEDED, FreshnessStatus.STALE):
        return CriterionResult(score=0.0, anchor=anchors["0"], basis=basis, unknown_reason=None)
    if freshness.status in (FreshnessStatus.CURRENT, FreshnessStatus.NOT_YET_APPLICABLE):
        if freshness.verification.within_window:
            return CriterionResult(score=1.0, anchor=anchors["1"], basis=basis, unknown_reason=None)
        return CriterionResult(score=0.5, anchor=anchors["0.5"], basis=basis, unknown_reason=None)
    return CriterionResult(
        score=None, anchor=None, basis=basis,
        unknown_reason=f"Freshness is '{freshness.status.value}': {freshness.explanation}",
    )


def score_criteria(meta: CaseMetadata, freshness: FreshnessAssessment, policy: G2Policy
                   ) -> Tuple[Dict[str, CriterionResult], List[Reason]]:
    results = {
        "evidence_support": _evidence_support(meta),
        "source_authority": _source_authority(meta, policy),
        "temporal_validity": _temporal_validity(freshness),
    }
    reasons = [
        Reason(
            code=codes.UNKNOWN_CRITERION,
            route=Decision.HUMAN_REVIEW,
            stage="criteria",
            subject=name,
            message=f"Required criterion '{name}' is unknown and was not scored as 0. {result.unknown_reason}",
        )
        for name, result in results.items()
        if result.score is None
    ]
    return results, reasons
