"""Unit tests for weight sensitivity comparison across three configurations."""

from pathlib import Path
from g2.config import (
    AUTHORITY_FOCUSED_WEIGHTS,
    DEFAULT_WEIGHTS,
    EQUAL_WEIGHTS,
    GateConfig,
)
from g2.evaluator import evaluate_case, load_fixture


def test_sensitivity_analysis_on_extra_cases():
    """Verify weight sensitivity comparison on extra cases with mixed criteria.

    Demonstrates:
    1. Score differences across configurations.
    2. Ranking changes / inversion between cases.
    3. Routing / decision changes across weight configurations.
    4. Explicit identification of unchanged cases.
    """
    test_dir = Path(__file__).resolve().parent
    package_dir = test_dir.parent
    workspace_root = package_dir.parent.parent

    candidates = [
        package_dir / "fixtures" / "extra-cases.json",
        workspace_root / "fixtures" / "extra-cases.json",
    ]
    fixture_path = next((c for c in candidates if c.is_file()), candidates[0])
    assert fixture_path.is_file(), f"Extra fixture missing: {fixture_path}"

    envelope = load_fixture(fixture_path)
    assert len(envelope.cases) >= 3

    cases = {c.id: c for c in envelope.cases}

    cfg_baseline = GateConfig(weights=DEFAULT_WEIGHTS, threshold=0.80)
    cfg_equal = GateConfig(weights=EQUAL_WEIGHTS, threshold=0.80)
    cfg_auth = GateConfig(weights=AUTHORITY_FOCUSED_WEIGHTS, threshold=0.80)

    # Evaluate extra-secondary-authority [1.0, 0.5, 1.0]
    r_sec_base = evaluate_case(cases["extra-secondary-authority"], envelope.as_of, cfg_baseline)
    r_sec_equal = evaluate_case(cases["extra-secondary-authority"], envelope.as_of, cfg_equal)
    r_sec_auth = evaluate_case(cases["extra-secondary-authority"], envelope.as_of, cfg_auth)

    # Evaluate extra-partial-support [0.5, 1.0, 1.0]
    r_part_base = evaluate_case(cases["extra-partial-support"], envelope.as_of, cfg_baseline)
    r_part_equal = evaluate_case(cases["extra-partial-support"], envelope.as_of, cfg_equal)
    r_part_auth = evaluate_case(cases["extra-partial-support"], envelope.as_of, cfg_auth)

    # Evaluate extra-provisional-timing [1.0, 1.0, 0.5]
    r_time_base = evaluate_case(cases["extra-provisional-timing"], envelope.as_of, cfg_baseline)
    r_time_equal = evaluate_case(cases["extra-provisional-timing"], envelope.as_of, cfg_equal)
    r_time_auth = evaluate_case(cases["extra-provisional-timing"], envelope.as_of, cfg_auth)

    # Evaluate extra-secondary-partial [0.5, 0.5, 1.0]
    r_multi_base = evaluate_case(cases["extra-secondary-partial"], envelope.as_of, cfg_baseline)
    r_multi_equal = evaluate_case(cases["extra-secondary-partial"], envelope.as_of, cfg_equal)
    r_multi_auth = evaluate_case(cases["extra-secondary-partial"], envelope.as_of, cfg_auth)

    # 1. Scores must be calculated for all eligible cases
    for rep in (
        r_sec_base, r_sec_equal, r_sec_auth,
        r_part_base, r_part_equal, r_part_auth,
        r_time_base, r_time_equal, r_time_auth,
        r_multi_base, r_multi_equal, r_multi_auth,
    ):
        assert rep.score is not None, f"Expected numeric score for eligible case {rep.case_id}"

    # 2. Routing change 1: extra-partial-support
    # Under Baseline: score = 0.750 < 0.80 -> human_review
    assert r_part_base.decision == "human_review"
    # Under Equal weights: score = 0.833 >= 0.80 -> pass
    assert r_part_equal.decision == "pass"
    # Under Authority-focused: score = 0.825 >= 0.80 -> pass
    assert r_part_auth.decision == "pass"

    # 3. Routing change 2: extra-secondary-authority
    # Under Baseline: score = 0.875 >= 0.80 -> pass
    assert r_sec_base.decision == "pass"
    # Under Equal weights: score = 0.833 >= 0.80 -> pass
    assert r_sec_equal.decision == "pass"
    # Under Authority-focused: score = 0.775 < 0.80 -> human_review
    assert r_sec_auth.decision == "human_review"

    # 4. Ranking inversion:
    # Under Baseline: secondary-authority (0.875) > partial-support (0.750)
    assert r_sec_base.score > r_part_base.score
    # Under Authority-focused: partial-support (0.825) > secondary-authority (0.775)
    assert r_part_auth.score > r_sec_auth.score

    # 5. Multi-defect case: extra-secondary-partial is strictly lower than single-defect cases
    assert r_multi_base.score < r_part_base.score
    assert r_multi_equal.score < r_part_equal.score
    assert r_multi_auth.score < r_sec_auth.score

    # 6. Unchanged cases:
    # extra-provisional-timing remains pass across all configurations
    assert r_time_base.decision == "pass"
    assert r_time_equal.decision == "pass"
    assert r_time_auth.decision == "pass"

    # extra-secondary-partial remains human_review across all configurations
    assert r_multi_base.decision == "human_review"
    assert r_multi_equal.decision == "human_review"
    assert r_multi_auth.decision == "human_review"
