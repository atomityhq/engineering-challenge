"""Invalid weight and policy configurations are rejected at load time."""

import copy
import json
import math

import pytest
from pydantic import ValidationError

from g2_gate.cli import main
from g2_gate.config import WEIGHT_SUM_TOLERANCE, G2Policy, WeightConfig, WeightSets
from g2_gate.loading import InputValidationError, load_weight_sets
from g2_gate.paths import POLICY_CONFIG

RATIONALE = {"evidence_support": "r", "source_authority": "r", "temporal_validity": "r"}


def weight_config(**weights):
    return {"version": "test", "status": "provisional", "description": "test", "weights": weights, "rationale": RATIONALE}


def test_committed_weight_sets_are_valid(weight_sets):
    assert weight_sets.default == "provisional-v1"
    assert [c.version for c in weight_sets.configurations] == ["provisional-v1", "equal-v1", "freshness-weighted-v1"]
    for config in weight_sets.configurations:
        assert abs(math.fsum(config.weights.values()) - 1) <= WEIGHT_SUM_TOLERANCE


@pytest.mark.parametrize("weights", [
    {"evidence_support": 0.5, "source_authority": 0.3, "temporal_validity": 0.3},
    {"evidence_support": 0.5, "source_authority": 0.3, "temporal_validity": 0.1},
    {"evidence_support": 0.0, "source_authority": 0.0, "temporal_validity": 0.0},
])
def test_invalid_weight_sum_is_rejected(weights):
    with pytest.raises(ValidationError, match="must sum to 1"):
        WeightConfig.model_validate(weight_config(**weights))


def test_weight_sum_tolerance_is_documented_and_applied():
    inside = WeightConfig.model_validate(weight_config(
        evidence_support=0.5, source_authority=0.3, temporal_validity=0.2 + WEIGHT_SUM_TOLERANCE / 2))
    assert inside.weights["temporal_validity"] > 0.2
    with pytest.raises(ValidationError, match="must sum to 1"):
        WeightConfig.model_validate(weight_config(
            evidence_support=0.5, source_authority=0.3, temporal_validity=0.2 + WEIGHT_SUM_TOLERANCE * 2))


def test_negative_weight_is_rejected_even_when_sum_is_one():
    # The example from the task: sums to exactly 1.0 but contains a negative weight.
    with pytest.raises(ValidationError, match="negative"):
        WeightConfig.model_validate(weight_config(evidence_support=0.8, source_authority=0.3, temporal_validity=-0.1))


@pytest.mark.parametrize("weights, message", [
    ({"evidence_support": 0.6, "source_authority": 0.4}, "missing=\\['temporal_validity'\\]"),
    ({"evidence_support": 0.4, "source_authority": 0.3, "temporal_validity": 0.2, "visual_quality": 0.1},
     "unexpected=\\['visual_quality'\\]"),
])
def test_weights_must_name_exactly_the_g2_criteria(weights, message):
    with pytest.raises(ValidationError, match=message):
        WeightConfig.model_validate(weight_config(**weights))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "0.2"])
def test_non_numeric_or_non_finite_weight_is_rejected(bad):
    with pytest.raises(ValidationError):
        WeightConfig.model_validate(weight_config(evidence_support=0.5, source_authority=0.3, temporal_validity=bad))


def test_every_weight_needs_a_rationale():
    data = weight_config(evidence_support=0.5, source_authority=0.3, temporal_validity=0.2)
    data["rationale"] = {"evidence_support": "r"}
    with pytest.raises(ValidationError, match="rationale"):
        WeightConfig.model_validate(data)
    data["rationale"] = {**RATIONALE, "temporal_validity": ""}
    with pytest.raises(ValidationError, match="rationale"):
        WeightConfig.model_validate(data)


def test_weight_sets_reject_unknown_default_and_duplicates():
    good = weight_config(evidence_support=0.5, source_authority=0.3, temporal_validity=0.2)
    with pytest.raises(ValidationError, match="not defined"):
        WeightSets.model_validate({"default": "missing", "configurations": [good]})
    with pytest.raises(ValidationError, match="duplicate"):
        WeightSets.model_validate({"default": "test", "configurations": [good, good]})


@pytest.fixture
def policy_raw():
    return copy.deepcopy(json.loads(POLICY_CONFIG.read_text(encoding="utf-8")))


@pytest.mark.parametrize("mutate, message", [
    (lambda p: p["threshold"].update(value=1.2), "less than or equal to 1"),
    (lambda p: p["threshold"].update(status="calibrated"), "provisional"),
    (lambda p: p["source_authority"].pop("community"), "missing \\['community'\\]"),
    (lambda p: p["source_authority"]["primary_authority"].update(score=-0.5), "greater than or equal to 0"),
    (lambda p: p["criterion_floors"].pop("temporal_validity"), "missing \\['temporal_validity'\\]"),
    (lambda p: p["criterion_floors"]["source_authority"].update(route="pass"), "route"),
    (lambda p: p["criterion_floors"]["source_authority"].pop("status"), "status"),
    (lambda p: p.update(calibration_status="calibrated"), "requires calibration_evidence"),
])
def test_invalid_policy_is_rejected(policy_raw, mutate, message):
    mutate(policy_raw)
    with pytest.raises(ValidationError, match=message):
        G2Policy.model_validate(policy_raw)


def test_cli_refuses_an_invalid_weight_file(tmp_path, capsys):
    bad = tmp_path / "weights.json"
    bad.write_text(json.dumps({
        "default": "test",
        "configurations": [weight_config(evidence_support=0.8, source_authority=0.3, temporal_validity=-0.1)],
    }))
    with pytest.raises(InputValidationError):
        load_weight_sets(bad)
    assert main(["--weights-config", str(bad), "evaluate"]) == 2
    assert "negative" in capsys.readouterr().err
