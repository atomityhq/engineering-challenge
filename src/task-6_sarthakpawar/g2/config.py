"""Configuration, policy definitions, and calibration parameters for the G2 gate."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from g2.models import Weights


# Baseline provisional weights:
# - Evidence support (0.50): Heaviest weight. Unsubstantiated claims pose the highest
#   factual, reputational, and compliance risk.
# - Source authority (0.25): Verifies credibility and provenance.
# - Temporal validity (0.25): Ensures freshness and currency under the demo policy.
DEFAULT_WEIGHTS = Weights(
    evidence_support=0.50,
    source_authority=0.25,
    temporal_validity=0.25,
)

# Alternative weight configuration 1: Neutral baseline (Equal weights, 1/3 each)
EQUAL_WEIGHTS = Weights(
    evidence_support=1.0 / 3.0,
    source_authority=1.0 / 3.0,
    temporal_validity=1.0 - (2.0 / 3.0),  # Exactly 1.0 within tolerance
)

# Alternative weight configuration 2: Strict Provenance / Authority-Focused
# Plausible scenario: Legal and regulatory intelligence teams where secondary reporting
# is strictly discounted and primary institutional provenance is critical (0.45 weight),
# while temporal validity of established statutory frameworks is weighted at 0.20.
AUTHORITY_FOCUSED_WEIGHTS = Weights(
    evidence_support=0.35,
    source_authority=0.45,
    temporal_validity=0.20,
)

# Retained alias for backwards compatibility
AUTHORITY_HEAVY_WEIGHTS = AUTHORITY_FOCUSED_WEIGHTS


class GateConfig(BaseModel):
    """Complete G2 gate policy configuration."""

    model_config = ConfigDict(extra="forbid")

    gate_name: str = "G2"
    policy_version: str = "prototype-v1"
    weights_version: str = "provisional-v1"
    calibration_status: str = "uncalibrated"

    weights: Weights = Field(default_factory=lambda: DEFAULT_WEIGHTS)

    # Threshold for composite passing score (must meet or exceed)
    threshold: float = 0.80

    # Criterion floor: no individual scored criterion may fall below this to pass
    criterion_floor: float = 0.50

    # Demo policy: news older than 30 days by event_date is considered stale
    news_max_event_age_days: int = 30

    # Float comparison tolerance
    tolerance: float = 1e-6
