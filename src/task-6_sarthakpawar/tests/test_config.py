"""Unit tests for configuration, weights validation, and tolerance handling."""

import pytest
from pydantic import ValidationError

from g2.config import GateConfig
from g2.models import Weights


def test_valid_weights():
    w = Weights(evidence_support=0.5, source_authority=0.25, temporal_validity=0.25)
    assert w.evidence_support == 0.5
    assert w.source_authority == 0.25
    assert w.temporal_validity == 0.25


def test_weights_sum_not_equal_one_fails():
    with pytest.raises(ValidationError, match="Weights must sum to 1.0"):
        Weights(evidence_support=0.5, source_authority=0.5, temporal_validity=0.5)


def test_negative_weight_rejected():
    with pytest.raises(ValidationError):
        Weights(evidence_support=0.8, source_authority=0.3, temporal_validity=-0.1)


def test_weights_floating_point_tolerance():
    # 1/3 + 1/3 + 1/3 in float
    w = Weights(
        evidence_support=1.0 / 3.0,
        source_authority=1.0 / 3.0,
        temporal_validity=1.0 - (2.0 / 3.0),
    )
    assert abs(w.evidence_support + w.source_authority + w.temporal_validity - 1.0) <= 1e-6


def test_config_extra_field_forbidden():
    with pytest.raises(ValidationError):
        GateConfig.model_validate({"unknown_param": 123})

