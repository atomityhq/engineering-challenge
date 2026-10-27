"""Tests for configurable source and competitor policies."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from source_filter.models import SourceRecord, SourceType
from source_filter.policy import (
    PolicyConfig,
    apply_policy,
    load_policy,
)


SUBMISSION_DIR = Path(__file__).resolve().parents[1]
POLICY_PATH = SUBMISSION_DIR / "policy.json"


def make_record(
    source_type="primary",
    claim_kind="other",
):
    return SourceRecord(
        source_id="source-001",
        url="https://example.org/news",
        source_type=source_type,
        claim_kind=claim_kind,
    )


def test_policy_configuration_loads():
    policy = load_policy(POLICY_PATH)

    assert SourceType.PRIMARY in policy.approved_source_types
    assert SourceType.AUTHORITATIVE in policy.approved_source_types


def test_primary_source_is_eligible():
    policy = load_policy(POLICY_PATH)

    result = apply_policy(make_record("primary"), policy)

    assert result.eligibility == "eligible"
    assert result.reason_codes == ["SOURCE_POLICY_ACCEPTED"]


def test_low_quality_source_is_excluded():
    policy = load_policy(POLICY_PATH)

    result = apply_policy(make_record("low_quality"), policy)

    assert result.eligibility == "excluded"
    assert result.reason_codes == ["SOURCE_LOW_QUALITY"]


def test_competitor_product_claim_is_excluded():
    policy = load_policy(POLICY_PATH)

    result = apply_policy(
        make_record("competitor", "product_promotional"),
        policy,
    )

    assert result.eligibility == "excluded"
    assert result.reason_codes == [
        "COMPETITOR_PROMOTIONAL_CLAIM"
    ]
    assert result.verification_required is False


def test_competitor_generic_claim_requires_verification():
    policy = load_policy(POLICY_PATH)

    result = apply_policy(
        make_record("competitor", "generic_industry"),
        policy,
    )

    assert result.eligibility == "excluded"
    assert result.reason_codes == [
        "COMPETITOR_GENERIC_CLAIM_NEEDS_VERIFICATION"
    ]
    assert result.verification_required is True


def test_unapproved_source_is_not_automatically_accepted():
    policy = load_policy(POLICY_PATH)

    result = apply_policy(make_record("secondary"), policy)

    assert result.eligibility == "excluded"
    assert result.reason_codes == [
        "SOURCE_NOT_APPROVED_BY_POLICY"
    ]


def test_policy_can_change_approved_source_types():
    policy = PolicyConfig(
        approved_source_types=["primary", "secondary"],
        excluded_source_types=["low_quality"],
    )

    result = apply_policy(make_record("secondary"), policy)

    assert result.eligibility == "eligible"


def test_overlapping_source_policies_are_rejected():
    with pytest.raises(ValidationError):
        PolicyConfig(
            approved_source_types=["primary"],
            excluded_source_types=["primary"],
        )