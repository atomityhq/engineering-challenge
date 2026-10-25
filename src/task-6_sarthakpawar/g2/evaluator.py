"""Core evaluator gluing together hard checks, freshness, criteria, scoring, and decisions."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from g2.config import DEFAULT_WEIGHTS, GateConfig
from g2.criteria import evaluate_criteria
from g2.decision import decide
from g2.freshness import evaluate_freshness
from g2.hard_checks import evaluate_hard_checks
from g2.models import Case, EvaluationReport, FixtureEnvelope


def evaluate_case(
    case: Case,
    as_of: date,
    config: GateConfig | None = None,
) -> EvaluationReport:
    """Evaluate a single content candidate through the G2 gate.

    Evaluation steps strictly adhere to:
    1. Schema validation (enforced by Pydantic Case model).
    2. Hard checks (material claims supported, not superseded, no competitor promotion).
    3. Freshness & applicability (date-specific, not crude publication age).
    4. Criterion scores (evidence support, source authority, temporal validity).
    5. Weighted scoring (computed ONLY if eligible; never if hard checks fail or info is missing).
    6. Decision precedence (reject -> revise -> human_review -> pass).
    7. Standardized report generation.

    Args:
        case: Case instance containing metadata and statement text.
        as_of: The reference 'today' date from fixture.
        config: Gate configuration. Defaults to standard provisional config if omitted.

    Returns:
        EvaluationReport detailing the full audit trail and gate decision.
    """
    if config is None:
        config = GateConfig(weights=DEFAULT_WEIGHTS)

    # 1. Hard checks
    hard_checks = evaluate_hard_checks(case.metadata)

    # 2. Freshness and applicability
    freshness = evaluate_freshness(
        case.metadata, as_of=as_of, max_event_age_days=config.news_max_event_age_days
    )

    # 3. Criteria scoring
    criteria = evaluate_criteria(case.metadata, freshness)

    # 4. Weighted scoring (only eligible if hard checks pass, fresh, and no unknowns)
    score: float | None = None
    is_eligible_for_score = (
        hard_checks.all_passed()
        and freshness.status not in ("stale", "superseded")
        and not criteria.has_unknown()
    )

    if is_eligible_for_score:
        assert criteria.evidence_support is not None
        assert criteria.source_authority is not None
        assert criteria.temporal_validity is not None
        raw_score = (
            config.weights.evidence_support * criteria.evidence_support
            + config.weights.source_authority * criteria.source_authority
            + config.weights.temporal_validity * criteria.temporal_validity
        )
        score = round(raw_score, 4)

    # 5. Apply decision precedence
    decision, reasons = decide(
        metadata=case.metadata,
        hard_checks=hard_checks,
        freshness=freshness,
        criteria=criteria,
        score=score,
        config=config,
    )

    # 6. Build evaluation report
    return EvaluationReport(
        case_id=case.id,
        gate=config.gate_name,
        policy_version=config.policy_version,
        calibration_status=config.calibration_status,
        hard_checks=hard_checks,
        criteria=criteria,
        freshness=freshness,
        weights_version=config.weights_version,
        weights=config.weights,
        score=score,
        decision=decision,
        reasons=reasons,
    )


def load_fixture(fixture_path: str | Path) -> FixtureEnvelope:
    """Load and validate a fixture envelope from JSON.

    Args:
        fixture_path: File system path to the fixture JSON file.

    Returns:
        Validated FixtureEnvelope instance.
    """
    path = Path(fixture_path)
    if not path.is_file():
        raise FileNotFoundError(f"Fixture file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return FixtureEnvelope.model_validate(data)


def evaluate_fixture(
    fixture_path: str | Path,
    config: GateConfig | None = None,
) -> list[EvaluationReport]:
    """Load a fixture and evaluate all cases within it.

    Args:
        fixture_path: Path to the fixture JSON.
        config: Optional GateConfig.

    Returns:
        List of EvaluationReport objects for all cases in the fixture.
    """
    envelope = load_fixture(fixture_path)
    return [evaluate_case(case, as_of=envelope.as_of, config=config) for case in envelope.cases]

