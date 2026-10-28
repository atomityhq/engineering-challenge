"""G2 policy and weight configuration contracts.

A configuration that violates the scoring model (negative weight, weights not
summing to 1, missing or extra criterion, out-of-range threshold) fails at load
time, before any case is evaluated.
"""

from __future__ import annotations

import math
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from .models import SourceType

CRITERIA = ("evidence_support", "source_authority", "temporal_validity")
CriterionName = Literal["evidence_support", "source_authority", "temporal_validity"]

# Documented numerical tolerance for sum(weights) == 1.
WEIGHT_SUM_TOLERANCE = 1e-6

UnitInterval = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False, strict=True)]
Route = Literal["reject", "revise", "human_review"]


class _Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WeightConfig(_Config):
    version: Annotated[str, Field(min_length=1)]
    status: Literal["provisional", "comparison-only"]
    description: str
    weights: Dict[str, Annotated[float, Field(allow_inf_nan=False, strict=True)]]
    rationale: Dict[str, Annotated[str, Field(min_length=1)]]

    @model_validator(mode="after")
    def _check_weights(self) -> "WeightConfig":
        names = set(self.weights)
        missing = sorted(set(CRITERIA) - names)
        extra = sorted(names - set(CRITERIA))
        if missing or extra:
            raise ValueError(f"weights must name exactly {list(CRITERIA)}; missing={missing}, unexpected={extra}")
        negative = {name: w for name, w in self.weights.items() if w < 0}
        if negative:
            raise ValueError(f"weights must be >= 0; negative weights: {negative}")
        total = math.fsum(self.weights.values())
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"weights must sum to 1 (tolerance {WEIGHT_SUM_TOLERANCE}); got {total!r}")
        undocumented = sorted(set(CRITERIA) - set(self.rationale))
        if undocumented:
            raise ValueError(f"every weight needs a documented rationale; missing for {undocumented}")
        return self


class WeightSets(_Config):
    default: str
    configurations: Annotated[List[WeightConfig], Field(min_length=1)]

    @model_validator(mode="after")
    def _check_versions(self) -> "WeightSets":
        versions = [c.version for c in self.configurations]
        if len(versions) != len(set(versions)):
            raise ValueError(f"duplicate weight configuration versions: {versions}")
        if self.default not in versions:
            raise ValueError(f"default weight configuration {self.default!r} is not defined")
        return self

    def get(self, version: Optional[str] = None) -> WeightConfig:
        wanted = version or self.default
        for config in self.configurations:
            if config.version == wanted:
                return config
        raise KeyError(f"unknown weight configuration {wanted!r}; known: {[c.version for c in self.configurations]}")


class ThresholdConfig(_Config):
    value: UnitInterval
    status: Literal["provisional"]
    rationale: str


class FloorRule(_Config):
    minimum: UnitInterval
    status: Literal["provisional"]
    route: Route
    repair_hint: str


class AuthorityAnchor(_Config):
    # null = no defensible authority score for this source type -> criterion unknown.
    score: Optional[UnitInterval]
    anchor: str


class G2Policy(_Config):
    gate: Literal["G2"]
    policy_version: Annotated[str, Field(min_length=1)]
    calibration_status: Literal["uncalibrated", "calibrated"]
    calibration_evidence: Optional[str] = None
    require_calibration_for_pass: bool
    threshold: ThresholdConfig
    criterion_floors: Dict[CriterionName, FloorRule]
    source_authority: Dict[SourceType, AuthorityAnchor]
    verification_max_age_days: Annotated[StrictInt, Field(gt=0)]
    verification_window_note: str
    score_decimals: Annotated[StrictInt, Field(ge=2, le=10)]

    @field_validator("source_authority")
    @classmethod
    def _all_source_types_mapped(cls, mapping: Dict[SourceType, AuthorityAnchor]) -> Dict[SourceType, AuthorityAnchor]:
        missing = sorted(t.value for t in SourceType if t not in mapping)
        if missing:
            raise ValueError(f"source_authority must map every source type explicitly (use score null for unknown); missing {missing}")
        return mapping

    @field_validator("criterion_floors")
    @classmethod
    def _floors_cover_criteria(cls, floors: Dict[str, FloorRule]) -> Dict[str, FloorRule]:
        missing = sorted(set(CRITERIA) - set(floors))
        if missing:
            raise ValueError(f"criterion_floors must define a floor for every criterion; missing {missing}")
        return floors

    @model_validator(mode="after")
    def _calibration_claims_need_evidence(self) -> "G2Policy":
        if self.calibration_status == "calibrated" and not self.calibration_evidence:
            raise ValueError("calibration_status 'calibrated' requires calibration_evidence; do not claim calibration without it")
        return self
