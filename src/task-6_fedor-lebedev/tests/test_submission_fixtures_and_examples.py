"""Submission fixtures route as documented, and the committed example outputs are reproducible."""

import json

import pytest

from g2_gate.cli import main, write_examples
from g2_gate.criteria import DEFINITIONS
from g2_gate.evaluator import evaluate_fixture
from g2_gate.paths import EDGE_FIXTURE, EXAMPLES_DIR, STARTER_FIXTURE, WEIGHTING_FIXTURE


@pytest.mark.parametrize("fixture_name", ["edge_fixture", "weighting_fixture"])
def test_submission_fixture_cases_match_expected_decisions(request, fixture_name, policy, weights):
    fixture = request.getfixturevalue(fixture_name)
    assert fixture.synthetic is True
    for case, report in zip(fixture.cases, evaluate_fixture(fixture, policy, weights)):
        assert report.decision == case.expected_decision, case.id


def test_weighting_cases_are_all_eligible(weighting_fixture, policy, weights):
    reports = evaluate_fixture(weighting_fixture, policy, weights)
    assert len(reports) >= 3
    assert all(r.eligible_for_scoring for r in reports)


def test_source_authority_scores_sit_on_documented_anchors(policy):
    anchors = DEFINITIONS["source_authority"]["anchors"]
    for entry in policy.source_authority.values():
        key = "null" if entry.score is None else f"{entry.score:g}"
        assert key in anchors


@pytest.mark.parametrize("path", [STARTER_FIXTURE, EDGE_FIXTURE, WEIGHTING_FIXTURE])
def test_cli_check_expected_succeeds(path, capsys):
    assert main(["evaluate", "--fixture", str(path), "--check-expected"]) == 0
    assert "decisions match expected_decision" in capsys.readouterr().out


def test_cli_json_output_contains_reports(capsys):
    assert main(["evaluate", "--format", "json"]) == 0
    out = capsys.readouterr().out
    assert '"case_id": "future-rule"' in out and '"fixture": "fixtures/g2-cases.json"' in out


def test_cli_rejects_unknown_weight_version(capsys):
    assert main(["evaluate", "--weights", "made-up"]) == 2
    assert "unknown weight configuration" in capsys.readouterr().err


def test_cli_can_evaluate_under_an_alternative_weighting(capsys):
    assert main(["evaluate", "--fixture", str(WEIGHTING_FIXTURE), "--weights", "equal-v1"]) == 0
    assert "weights equal-v1 (comparison-only)" in capsys.readouterr().out


def test_committed_examples_are_up_to_date(tmp_path):
    written = write_examples(tmp_path)
    assert len(written) == 9
    for path in written:
        committed = EXAMPLES_DIR / path.name
        assert committed.is_file(), f"missing example {path.name}; run: python -m g2_gate demo"
        assert committed.read_text(encoding="utf-8") == path.read_text(encoding="utf-8"), (
            f"examples/{path.name} is stale; run: python -m g2_gate demo"
        )


def test_check_expected_also_fails_in_json_mode(tmp_path, starter_raw, capsys):
    starter_raw["cases"][0]["expected_decision"] = "reject"
    path = tmp_path / "wrong-expectation.json"
    path.write_text(json.dumps(starter_raw), encoding="utf-8")
    assert main(["evaluate", "--fixture", str(path), "--format", "json", "--check-expected"]) == 1
    check = json.loads(capsys.readouterr().out)[0]["expectation_check"]
    assert (check["matched"], check["checked"], check["total"]) == (8, 9, 9)
    assert check["mismatches"] == [{"case_id": "current-news", "expected": "reject", "actual": "pass"}]
    assert main(["evaluate", "--format", "json", "--check-expected"]) == 0


def test_cases_without_expectation_are_not_counted_as_matches(tmp_path, starter_raw, capsys):
    del starter_raw["cases"][1]["expected_decision"]
    path = tmp_path / "partial-expectations.json"
    path.write_text(json.dumps(starter_raw), encoding="utf-8")
    assert main(["evaluate", "--fixture", str(path), "--check-expected"]) == 0
    assert "8/8 decisions match" in capsys.readouterr().out
    assert main(["evaluate", "--fixture", str(path), "--format", "json", "--check-expected"]) == 0
    check = json.loads(capsys.readouterr().out)[0]["expectation_check"]
    assert (check["matched"], check["checked"], check["total"]) == (8, 8, 9)
    assert check["without_expectation"] == ["old-law-current"]
