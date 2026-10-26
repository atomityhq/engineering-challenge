"""Policy configuration. Weights are validated so a bad config cannot run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

CRITERIA = ("evidence_support", "source_authority", "temporal_validity")

# Weights must add up to 1, give or take floating-point rounding (e.g. 1/3 + 1/3 + 1/3).
WEIGHT_TOLERANCE = 1e-9

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "g2_policy.json"


class Weights(BaseModel):
    """One weight per criterion. Rules: no negatives, must add up to 1."""

    model_config = ConfigDict(extra="forbid")

    evidence_support: float
    source_authority: float
    temporal_validity: float

    @model_validator(mode="after")
    def _check(self) -> "Weights":
        values = self.as_dict()
        negative = {k: v for k, v in values.items() if v < 0}
        if negative:
            raise ValueError(f"weights must be >= 0, got {negative}")
        total = sum(values.values())
        if abs(total - 1.0) > WEIGHT_TOLERANCE:
            raise ValueError(f"weights must sum to 1 (tolerance {WEIGHT_TOLERANCE}), got {total}")
        return self

    def as_dict(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in CRITERIA}


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str
    calibration_status: str
    weights_version: str
    weights: Weights
    weight_rationale: dict[str, str]
    pass_threshold: float
    criterion_floor: float
    threshold_rationale: str
    verification_max_age_days: int
    source_authority_scores: dict[str, float]
    alternative_weights: dict[str, Weights]
    criterion_anchors: dict[str, dict[str, str]]
    next_actions: dict[str, str]

    @field_validator("pass_threshold", "criterion_floor")
    @classmethod
    def _unit_interval(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("must be between 0 and 1")
        return v

    @field_validator("source_authority_scores")
    @classmethod
    def _scores_in_range(cls, v: dict[str, float]) -> dict[str, float]:
        bad = {k: s for k, s in v.items() if not 0 <= s <= 1}
        if bad:
            raise ValueError(f"authority scores must be between 0 and 1: {bad}")
        return v

    @model_validator(mode="after")
    def _rationale_covers_weights(self) -> "Policy":
        missing = [c for c in CRITERIA if c not in self.weight_rationale]
        if missing:
            raise ValueError(f"every weight needs a written rationale; missing {missing}")
        return self

    def with_weights(self, weights: Weights, version: str) -> "Policy":
        return self.model_copy(update={"weights": weights, "weights_version": version})


def load_policy(path: Path | str = DEFAULT_POLICY_PATH) -> Policy:
    data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return Policy.model_validate(data)
