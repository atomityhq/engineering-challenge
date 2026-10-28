"""Mandatory hard checks, evaluated before any scoring.

Each check passes, fails, or is unknown. A check that does not pass carries the
route it requires; the decision policy applies precedence across all routes, so
no weighted score can override a failed check.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from . import codes
from .models import CaseMetadata, CurrentStatus, Decision, SourceType
from .report import HardCheckResult, Reason


def run_hard_checks(meta: CaseMetadata) -> Tuple[Dict[str, HardCheckResult], List[Reason]]:
    checks: Dict[str, HardCheckResult] = {}
    reasons: List[Reason] = []

    def record(name: str, result: HardCheckResult, code: str) -> None:
        checks[name] = result
        if result.status != "pass":
            reasons.append(Reason(code=code, route=result.route, stage="hard_check", subject=name, message=result.detail))

    # Competitor promotion is a policy prohibition, not a repairable defect.
    if meta.competitor_product_claim:
        promo = HardCheckResult(
            status="fail",
            route=Decision.REJECT,
            inputs={"competitor_product_claim": True},
            detail="Content promotes a competitor's product claim; G2 policy does not allow it to proceed.",
        )
    else:
        promo = HardCheckResult(
            status="pass", route=None, inputs={"competitor_product_claim": False},
            detail="No competitor product claim is promoted.",
        )
    record("no_competitor_promotion", promo, codes.COMPETITOR_PRODUCT_PROMOTION)

    if meta.supported is None:
        support = HardCheckResult(
            status="unknown",
            route=Decision.HUMAN_REVIEW,
            inputs={"supported": None},
            detail="Upstream validation did not determine whether the material claim is supported (supported=null).",
        )
        support_code = codes.UNKNOWN_EVIDENCE_SUPPORT
    elif meta.supported:
        support = HardCheckResult(
            status="pass", route=None, inputs={"supported": True},
            detail="The material claim is supported by the supplied evidence.",
        )
        support_code = codes.UNSUPPORTED_MATERIAL_CLAIM
    else:
        support = HardCheckResult(
            status="fail",
            route=Decision.REVISE,
            inputs={"supported": False},
            detail="The material claim is not supported by the supplied evidence; remove it or add supporting evidence.",
        )
        support_code = codes.UNSUPPORTED_MATERIAL_CLAIM
    record("material_claim_supported", support, support_code)

    status_says_superseded = meta.current_status is CurrentStatus.SUPERSEDED
    superseded_inputs = {"superseded": meta.superseded, "current_status": meta.current_status.value}
    if meta.superseded or status_says_superseded:
        detail = "Evidence has been superseded; replace it with the evidence currently in force."
        if meta.superseded != status_says_superseded:
            # Either signal is enough to fail; the disagreement itself is reported for the upstream owner.
            reasons.append(
                Reason(
                    code=codes.SUPERSESSION_METADATA_INCONSISTENT,
                    route=None,
                    stage="hard_check",
                    subject="evidence_not_superseded",
                    message=(
                        f"Metadata disagrees about supersession (superseded={meta.superseded}, "
                        f"current_status={meta.current_status.value}); treated as superseded."
                    ),
                )
            )
        superseded = HardCheckResult(status="fail", route=Decision.REVISE, inputs=superseded_inputs, detail=detail)
    else:
        superseded = HardCheckResult(
            status="pass", route=None, inputs=superseded_inputs, detail="Evidence is not marked superseded.",
        )
    record("evidence_not_superseded", superseded, codes.SUPERSEDED_EVIDENCE)

    if meta.contradiction:
        contradiction = HardCheckResult(
            status="fail",
            route=Decision.HUMAN_REVIEW,
            inputs={"contradiction": True},
            detail="Supplied evidence materially conflicts; a person must decide which evidence governs.",
        )
    else:
        contradiction = HardCheckResult(
            status="pass", route=None, inputs={"contradiction": False}, detail="No material contradiction recorded.",
        )
    record("no_material_contradiction", contradiction, codes.CONFLICTING_EVIDENCE)

    if meta.source_type is SourceType.COMPETITOR:
        competitor_source = HardCheckResult(
            status="fail",
            route=Decision.HUMAN_REVIEW,
            inputs={"source_type": meta.source_type.value},
            detail="Evidence comes from a competitor; using it requires an explicit human-approved exception.",
        )
    else:
        competitor_source = HardCheckResult(
            status="pass", route=None, inputs={"source_type": meta.source_type.value},
            detail="Evidence does not come from a competitor.",
        )
    record("source_not_competitor", competitor_source, codes.COMPETITOR_SOURCE_NEEDS_JUDGMENT)

    return checks, reasons
