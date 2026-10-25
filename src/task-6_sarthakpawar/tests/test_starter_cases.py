"""Automated tests validating all 9 starter cases from fixtures/g2-cases.json."""

from pathlib import Path
from g2.config import GateConfig
from g2.evaluator import evaluate_case, load_fixture


def test_all_starter_cases_match_expected_decisions():
    """Verify that every starter case from the official fixture matches expected_decision."""
    # Find fixtures/g2-cases.json at workspace root
    test_dir = Path(__file__).resolve().parent
    package_dir = test_dir.parent
    workspace_root = package_dir.parent.parent

    candidates = [
        workspace_root / "fixtures" / "g2-cases.json",
        package_dir / "fixtures" / "g2-cases.json",
    ]
    fixture_path = next((c for c in candidates if c.is_file()), candidates[0])
    assert fixture_path.is_file(), f"Starter fixture not found: {fixture_path}"

    envelope = load_fixture(fixture_path)
    config = GateConfig()

    assert len(envelope.cases) == 9

    for case in envelope.cases:
        expected = case.expected_decision
        assert expected is not None, f"Starter case {case.id} missing expected_decision"

        report = evaluate_case(case, as_of=envelope.as_of, config=config)

        assert (
            report.decision == expected
        ), f"Case '{case.id}' evaluated to '{report.decision}', expected '{expected}' (reasons: {report.reasons})"


def test_starter_case_details():
    """Verify detailed routing and reason codes for representative starter cases."""
    test_dir = Path(__file__).resolve().parent
    workspace_root = test_dir.parent.parent.parent
    fixture_path = workspace_root / "fixtures" / "g2-cases.json"
    envelope = load_fixture(fixture_path)
    config = GateConfig()

    cases_by_id = {c.id: c for c in envelope.cases}

    # 1. current-news -> pass (score=1.0)
    rep_curr = evaluate_case(cases_by_id["current-news"], envelope.as_of, config)
    assert rep_curr.decision == "pass"
    assert rep_curr.score == 1.0
    assert "ALL_CHECKS_PASSED" in rep_curr.reasons

    # 2. old-law-current -> pass (score=1.0)
    rep_law = evaluate_case(cases_by_id["old-law-current"], envelope.as_of, config)
    assert rep_law.decision == "pass"
    assert rep_law.score == 1.0

    # 3. recent-article-old-event -> revise (score=None, stale)
    rep_stale = evaluate_case(
        cases_by_id["recent-article-old-event"], envelope.as_of, config
    )
    assert rep_stale.decision == "revise"
    assert rep_stale.score is None
    assert "STALE_EVENT_DATE" in rep_stale.reasons

    # 4. competitor-promotion -> reject (score=None)
    rep_comp = evaluate_case(
        cases_by_id["competitor-promotion"], envelope.as_of, config
    )
    assert rep_comp.decision == "reject"
    assert rep_comp.score is None
    assert "COMPETITOR_PROMOTION" in rep_comp.reasons

    # 5. conflicting-evidence -> human_review
    rep_contra = evaluate_case(
        cases_by_id["conflicting-evidence"], envelope.as_of, config
    )
    assert rep_contra.decision == "human_review"
    assert "CONFLICTING_EVIDENCE" in rep_contra.reasons

    # 6. future-rule -> pass with note
    rep_future = evaluate_case(cases_by_id["future-rule"], envelope.as_of, config)
    assert rep_future.decision == "pass"
    assert rep_future.score == 1.0
    assert (
        "ADOPTED_FUTURE_REGULATION_NOT_CURRENTLY_APPLICABLE" in rep_future.reasons
    )

