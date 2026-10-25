"""G2 Content-Quality Gate package.

Provides automated evidence support, source authority, and temporal validity
checking for candidate publishing content.
"""

from g2.config import (
    AUTHORITY_FOCUSED_WEIGHTS,
    AUTHORITY_HEAVY_WEIGHTS,
    DEFAULT_WEIGHTS,
    EQUAL_WEIGHTS,
    GateConfig,
)
from g2.criteria import evaluate_criteria
from g2.decision import decide
from g2.evaluator import evaluate_case, evaluate_fixture, load_fixture
from g2.freshness import evaluate_freshness
from g2.hard_checks import evaluate_hard_checks
from g2.models import (
    Case,
    CriteriaScores,
    EvaluationReport,
    FixtureEnvelope,
    FreshnessAssessment,
    HardChecksResult,
    Metadata,
    Weights,
)

__all__ = [
    "AUTHORITY_FOCUSED_WEIGHTS",
    "AUTHORITY_HEAVY_WEIGHTS",
    "Case",
    "CriteriaScores",
    "DEFAULT_WEIGHTS",
    "EQUAL_WEIGHTS",
    "EvaluationReport",
    "FixtureEnvelope",
    "FreshnessAssessment",
    "GateConfig",
    "HardChecksResult",
    "Metadata",
    "Weights",
    "decide",
    "evaluate_case",
    "evaluate_criteria",
    "evaluate_fixture",
    "evaluate_freshness",
    "evaluate_hard_checks",
    "load_fixture",
]
