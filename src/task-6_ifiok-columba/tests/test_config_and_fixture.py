"""Bad weights and bad fixtures must fail loudly and predictably."""

import copy
import json

import pytest
from pydantic import ValidationError

from g2_gate.config import DEFAULT_POLICY_PATH, Weights, load_policy
from g2_gate.loader import FixtureError, load_fixture, parse_fixture

from conftest import SUPPLIED


def test_valid_weights_accepted():
    assert Weights(evidence_support=0.5, source_authority=0.2, temporal_validity=0.3)


def test_weights_must_sum_to_one():
    with pytest.raises(ValidationError, match="sum to 1"):
        Weights(evidence_support=0.5, source_authority=0.5, temporal_validity=0.5)


def test_weights_below_one_also_rejected():
    with pytest.raises(ValidationError, match="sum to 1"):
        Weights(evidence_support=0.2, source_authority=0.2, temporal_validity=0.2)


def test_weight_sum_tolerance_is_tiny_but_not_zero():
    # rounding noise (1/3 + 1/3 + 1/3 style) is fine ...
    assert Weights(evidence_support=0.5, source_authority=0.2, temporal_validity=0.3 + 5e-10)
    # ... a real error is not
    with pytest.raises(ValidationError, match="sum to 1"):
        Weights(evidence_support=0.5, source_authority=0.2, temporal_validity=0.3 + 1e-6)


def test_negative_weight_rejected():
    with pytest.raises(ValidationError, match=">= 0"):
        Weights(evidence_support=0.8, source_authority=0.3, temporal_validity=-0.1)


def test_missing_weight_rejected():
    with pytest.raises(ValidationError):
        Weights(evidence_support=0.5, source_authority=0.5)  # type: ignore[call-arg]


def test_policy_with_bad_weights_does_not_load(tmp_path):
    data = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    data["weights"]["temporal_validity"] = -0.1
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_policy(path)


def test_every_weight_needs_a_written_rationale(tmp_path):
    data = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    del data["weight_rationale"]["source_authority"]
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError, match="rationale"):
        load_policy(path)


def test_supplied_fixture_loads_and_expected_decision_is_stripped(supplied):
    fixture, expectations = supplied
    assert str(fixture.as_of) == "2026-10-06"
    assert len(fixture.cases) == 9
    assert expectations["competitor-promotion"] == "reject"
    # the evaluator's input model has no way to carry the expectation
    assert "expected_decision" not in fixture.cases[0].model_dump()


def _raw():
    return json.loads(SUPPLIED.read_text(encoding="utf-8"))


def test_missing_required_case_field_is_a_predictable_error():
    raw = _raw()
    del raw["cases"][0]["metadata"]["supported"]
    with pytest.raises(FixtureError, match="supported"):
        parse_fixture(raw)


def test_missing_metadata_block_is_a_predictable_error():
    raw = _raw()
    del raw["cases"][0]["metadata"]
    with pytest.raises(FixtureError, match="metadata"):
        parse_fixture(raw)


def test_missing_as_of_is_a_predictable_error():
    raw = _raw()
    del raw["as_of"]
    with pytest.raises(FixtureError, match="as_of"):
        parse_fixture(raw)


def test_bad_date_is_a_predictable_error():
    raw = _raw()
    raw["cases"][0]["metadata"]["event_date"] = "not-a-date"
    with pytest.raises(FixtureError, match="event_date"):
        parse_fixture(raw)


def test_unknown_field_is_rejected_not_ignored():
    raw = _raw()
    raw["cases"][0]["metadata"]["suported"] = True  # typo must not slip through
    with pytest.raises(FixtureError):
        parse_fixture(raw)


def test_duplicate_case_ids_rejected():
    raw = _raw()
    raw["cases"].append(copy.deepcopy(raw["cases"][0]))
    with pytest.raises(FixtureError, match="duplicate"):
        parse_fixture(raw)


def test_not_json_and_missing_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(FixtureError, match="not valid JSON"):
        load_fixture(bad)
    with pytest.raises(FixtureError, match="not found"):
        load_fixture(tmp_path / "missing.json")


def test_wrong_shape_rejected():
    with pytest.raises(FixtureError):
        parse_fixture([1, 2, 3])
