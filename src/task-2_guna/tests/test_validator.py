
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from models import Claim, EvidenceSource
from validator import ClaimValidator


@pytest.fixture
def data():
    path = PROJECT_DIR / "fixtures" / "claims.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def validator(data):
    sources = [
        EvidenceSource(**source)
        for source in data["sources"]
    ]
    return ClaimValidator(sources)


def load_claim(data, index):
    return Claim(**data["claims"][index])


def test_directly_supported_claim(data, validator):
    result = validator.validate(load_claim(data, 0))

    assert result.status == "supported"
    assert result.evidence[0].source_id == "source-001"
    assert result.evidence[0].locator == "paragraph-1"


def test_unsupported_number(data, validator):
    result = validator.validate(load_claim(data, 1))

    assert result.status == "unsupported"
    assert "30%" in result.reason


def test_missing_source(data, validator):
    result = validator.validate(load_claim(data, 2))

    assert result.status == "unsupported"
    assert "source-missing" in result.reason


def test_conflicting_sources(data, validator):
    result = validator.validate(load_claim(data, 3))

    assert result.status == "uncertain"
    assert len(result.contradictions) >= 2
    assert {item.source_id for item in result.evidence} == {
        "source-001",
        "source-002",
    }


def test_inference_labelled_as_fact(data, validator):
    result = validator.validate(load_claim(data, 4))

    assert result.status == "uncertain"
    assert result.classification == "fact"
    assert "inference" in result.reason.lower()


def test_malformed_claim_is_rejected(data):
    with pytest.raises(ValidationError):
        Claim(**data["claims"][5])

def test_conflicting_evidence_is_preserved(data, validator):
    result = validator.validate(load_claim(data, 3))

    assert result.status == "uncertain"
    assert len(result.contradictions) == 2
    assert any("increased by 20%" in item for item in result.contradictions)
    assert any("decreased by 10%" in item for item in result.contradictions)


def test_unrelated_number_does_not_support_claim(data, validator):
    claim = Claim(
        claim_id="claim-extra-001",
        text="The regulation increased by 20%.",
        source_ids=["source-001"],
        classification="fact",
    )

    result = validator.validate(claim)

    assert result.status != "supported"


def test_unknown_source_does_not_create_evidence(data, validator):
    claim = Claim(
        claim_id="claim-extra-002",
        text="Cloud costs increased.",
        source_ids=["source-does-not-exist"],
        classification="fact",
    )

    result = validator.validate(claim)

    assert result.status == "unsupported"
    assert result.evidence == []
    assert result.unresolved_questions
    
def test_duplicate_source_ids_are_rejected(data):
    source = EvidenceSource.model_validate(data["sources"][0])

    with pytest.raises(ValueError, match="Duplicate source IDs"):
        ClaimValidator([source, source])


def test_malformed_locator_is_rejected():
    with pytest.raises(ValidationError):
        EvidenceSource(
            source_id="source-invalid",
            locator="TBD",
            excerpt="Some evidence excerpt.",
        )


def test_whitespace_only_claim_is_rejected():
    with pytest.raises(ValidationError):
        Claim(
            claim_id="claim-invalid",
            text="   ",
            source_ids=["source-001"],
            classification="fact",
        )


def test_whitespace_only_source_excerpt_is_rejected():
    with pytest.raises(ValidationError):
        EvidenceSource(
            source_id="source-invalid",
            locator="paragraph-1",
            excerpt="   ",
        )

