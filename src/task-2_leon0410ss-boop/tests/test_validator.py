import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.models import (
    Claim,
    ClaimClassification,
    Source,
    SupportStatus,
)
from src.validator import validate_claim


FIXTURE_PATH = Path("fixtures/validation_cases.json")
MALFORMED_FIXTURE_PATH = Path("fixtures/malformed_claim.json")


def load_fixture():
    with FIXTURE_PATH.open() as file:
        data = json.load(file)

    sources = [
        Source.model_validate(source)
        for source in data["sources"]
    ]

    claims = [
        Claim.model_validate(claim)
        for claim in data["claims"]
    ]

    return sources, claims


def test_directly_supported_claim():
    sources, claims = load_fixture()

    result = validate_claim(claims[0], sources)

    assert result.claim_id == "claim-001"
    assert result.status == SupportStatus.SUPPORTED
    assert result.classification == ClaimClassification.FACT
    assert result.supporting_source_ids == ["source-001"]
    assert result.contradictions == []
    assert result.unresolved_questions == []


def test_unsupported_numerical_claim():
    sources, claims = load_fixture()

    result = validate_claim(claims[1], sources)

    assert result.claim_id == "claim-002"
    assert result.status == SupportStatus.UNSUPPORTED
    assert result.classification == ClaimClassification.FACT
    assert result.supporting_source_ids == []
    assert "numerical value" in result.reason


def test_missing_source():
    sources, claims = load_fixture()

    result = validate_claim(claims[2], sources)

    assert result.claim_id == "claim-003"
    assert result.status == SupportStatus.UNCERTAIN
    assert result.supporting_source_ids == []
    assert result.unresolved_questions == [
        "Missing source: source-999"
    ]


def test_conflicting_evidence():
    sources, claims = load_fixture()

    result = validate_claim(claims[3], sources)

    assert result.claim_id == "claim-004"
    assert result.status == SupportStatus.UNCERTAIN
    assert len(result.contradictions) == 1
    assert "source-003" in result.contradictions[0]
    assert "source-004" in result.contradictions[0]


def test_inference_presented_as_fact():
    sources, claims = load_fixture()

    result = validate_claim(claims[4], sources)

    assert result.claim_id == "claim-005"
    assert result.status == SupportStatus.UNCERTAIN
    assert result.classification == ClaimClassification.INFERENCE
    assert result.supporting_source_ids == []


def test_malformed_claim():
    with MALFORMED_FIXTURE_PATH.open() as file:
        data = json.load(file)

    with pytest.raises(ValidationError):
        Claim.model_validate(data)