"""Weight sensitivity, the triage add-on, and the command line."""

import json

from g2_gate import sensitivity, triage
from g2_gate.cli import EXTRA_FIXTURE, SUPPLIED_FIXTURE, main
from g2_gate.evaluator import evaluate_fixture
from g2_gate.loader import load_fixture, merge_fixtures

CONFIGS = ["chosen", "equal", "authority_first"]


def combined():
    return merge_fixtures([load_fixture(SUPPLIED_FIXTURE)[0], load_fixture(EXTRA_FIXTURE)[0]])


# ---- weight sensitivity ----


def test_sensitivity_covers_at_least_three_eligible_cases_under_three_configs(policy):
    rows = sensitivity.compare(combined(), policy)
    assert len(rows) >= 3
    assert list(sensitivity.weight_sets(policy)) == CONFIGS
    for row in rows:
        assert set(row.scores) == set(CONFIGS)
        assert set(row.ranks) == set(CONFIGS)
        assert set(row.decisions) == set(CONFIGS)


def test_sensitivity_only_compares_cases_that_have_a_score(policy):
    rows = {r.case_id for r in sensitivity.compare(combined(), policy)}
    assert "competitor-promotion" not in rows  # hard failure: no score
    assert "unknown-date" not in rows  # unknown criterion: no score
    assert "extra-secondary-news-recent" in rows


def test_weights_can_change_routing_and_the_report_says_where(policy):
    rows = {r.case_id: r for r in sensitivity.compare(combined(), policy)}
    moved = rows["extra-secondary-news-recent"]
    assert moved.decisions["chosen"] == "pass"
    assert moved.decisions["authority_first"] == "human_review"
    assert moved.routing_changed
    assert not rows["current-news"].routing_changed  # all-1.0 case cannot move


def test_sensitivity_markdown_states_changes_and_limits(policy):
    text = sensitivity.to_markdown(sensitivity.compare(combined(), policy), CONFIGS)
    assert "extra-secondary-news-recent" in text
    assert "Limitation" in text


def test_alternative_weights_are_valid(policy):
    for weights in policy.alternative_weights.values():
        assert abs(sum(weights.as_dict().values()) - 1) < 1e-9


# ---- triage add-on ----


def test_triage_gives_every_non_pass_case_a_next_action(policy):
    reports = evaluate_fixture(combined(), policy)
    queue = triage.build_queue(reports, policy)
    for key in ("revise", "human_review", "reject"):
        for item in queue[key]:
            assert item["next_actions"], item["case_id"]
    assert all(not item["next_actions"] for item in queue["pass"])
    assert sum(len(v) for v in queue.values()) == len(reports)


def test_triage_warns_that_future_rules_are_not_applicable_yet(policy):
    reports = evaluate_fixture(combined(), policy)
    text = triage.to_markdown(triage.build_queue(reports, policy), len(reports))
    assert "not applicable yet" in text


def test_every_reason_code_the_gate_can_emit_has_a_next_action(policy):
    codes = {
        "COMPETITOR_PROMOTION", "UNSUPPORTED_CLAIM", "SUPERSEDED_EVIDENCE", "STALE_EVENT",
        "UNKNOWN_EVENT_DATE", "UNKNOWN_EFFECTIVE_DATE", "UNKNOWN_VERIFICATION_DATE",
        "UNKNOWN_CURRENT_STATUS", "UNKNOWN_CONTENT_TYPE", "UNKNOWN_SUPPORT",
        "UNKNOWN_SOURCE_AUTHORITY", "CONFLICTING_EVIDENCE", "INCONSISTENT_METADATA",
        "CRITERION_BELOW_FLOOR", "BELOW_THRESHOLD", "INCOMPLETE_EVALUATION",
    }
    assert codes <= set(policy.next_actions)


# ---- CLI ----


def test_cli_all_writes_every_output(tmp_path, capsys):
    assert main(["all", "--out", str(tmp_path)]) == 0
    names = {p.name for p in tmp_path.iterdir()}
    assert {"reports-g2-cases.json", "weight-sensitivity.md", "triage-queue.md"} <= names
    reports = json.loads((tmp_path / "reports-g2-cases.json").read_text())
    assert len(reports) == 9
    assert {"hard_checks", "criteria", "freshness", "score", "decision", "reasons",
            "policy_version", "calibration_status"} <= set(reports[0])


def test_cli_reports_a_bad_fixture_with_exit_code_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    assert main(["evaluate", "--fixture", str(bad), "--out", str(tmp_path)]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_rejects_a_bad_policy(tmp_path, capsys):
    policy = tmp_path / "policy.json"
    policy.write_text("{}", encoding="utf-8")
    assert main(["--policy", str(policy), "evaluate", "--out", str(tmp_path)]) == 2
