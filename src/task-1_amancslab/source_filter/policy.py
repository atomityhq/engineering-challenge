"""Configurable source and competitor policy evaluation."""

import json
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, root_validator

from .models import ClaimKind, SourceRecord, SourceType


class PolicyConfig(BaseModel):
    """Validated source filtering configuration."""

    approved_source_types: List[SourceType]
    excluded_source_types: List[SourceType]

    competitor_product_claim_action: Literal[
        "exclude",
        "exclude_and_require_verification",
    ] = "exclude"

    competitor_generic_claim_action: Literal[
        "exclude_and_require_verification"
    ] = "exclude_and_require_verification"

    competitor_other_claim_action: Literal[
        "exclude",
        "exclude_and_require_verification",
    ] = "exclude"

    @root_validator
    def source_lists_must_not_overlap(cls, values):
        approved = set(values.get("approved_source_types") or [])
        excluded = set(values.get("excluded_source_types") or [])

        overlap = approved & excluded

        if overlap:
            names = sorted(item.value for item in overlap)
            raise ValueError(
                f"Source types cannot be both approved and excluded: "
                f"{names}"
            )

        return values


class FilteredSourceRecord(SourceRecord):
    """Source record enriched with a policy decision."""

    eligibility: Literal["eligible", "excluded"]
    reason_codes: List[str] = Field(default_factory=list)
    verification_required: bool = False


def load_policy(path: str | Path) -> PolicyConfig:
    """Load and validate policy configuration from a JSON file."""

    policy_path = Path(path)

    try:
        data = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid policy JSON in {policy_path}: {exc}"
        ) from exc

    return PolicyConfig.parse_obj(data)


def apply_policy(
    record: SourceRecord,
    policy: PolicyConfig,
) -> FilteredSourceRecord:
    """Evaluate one record against the configured policy."""

    eligibility: Literal["eligible", "excluded"] = "excluded"
    reason_code = "SOURCE_NOT_APPROVED_BY_POLICY"
    verification_required = False

    if record.source_type == SourceType.COMPETITOR:
        # Competitor sources are never accepted as publication evidence
        # solely because their content appears factual.
        if record.claim_kind == ClaimKind.PRODUCT_PROMOTIONAL:
            reason_code = "COMPETITOR_PROMOTIONAL_CLAIM"
            action = policy.competitor_product_claim_action

        elif record.claim_kind == ClaimKind.GENERIC_INDUSTRY:
            reason_code = (
                "COMPETITOR_GENERIC_CLAIM_NEEDS_VERIFICATION"
            )
            action = policy.competitor_generic_claim_action

        else:
            reason_code = "COMPETITOR_CLAIM_TYPE_UNCLASSIFIED"
            action = policy.competitor_other_claim_action

        verification_required = (
            action == "exclude_and_require_verification"
        )

    elif record.source_type in policy.excluded_source_types:
        if record.source_type == SourceType.LOW_QUALITY:
            reason_code = "SOURCE_LOW_QUALITY"
        else:
            reason_code = "SOURCE_TYPE_EXPLICITLY_EXCLUDED"

    elif record.source_type in policy.approved_source_types:
        eligibility = "eligible"
        reason_code = "SOURCE_POLICY_ACCEPTED"

    return FilteredSourceRecord(
        **record.dict(),
        eligibility=eligibility,
        reason_codes=[reason_code],
        verification_required=verification_required,
    )