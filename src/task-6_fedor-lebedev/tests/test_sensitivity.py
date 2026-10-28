"""Weight sensitivity: at least three eligible cases under three weight configurations."""

import pytest

from g2_gate.paths import STARTER_FIXTURE, WEIGHTING_FIXTURE
from g2_gate.sensitivity import compare_weights, render_markdown


@pytest.fixture(scope="module")
def report(starter, weighting_fixture, policy, weight_sets):
    return compare_weights([(starter, "starter"), (weighting_fixture, "weighting")], policy, weight_sets)


def test_compares_three_configurations_over_at_least_three_eligible_cases(report):
    assert [c.version for c in report.configurations] == ["provisional-v1", "equal-v1", "freshness-weighted-v1"]
    assert len(report.rows) >= 3
    additional = [row for row in report.rows if row.fixture == "weighting"]
    assert len(additional) >= 3, "the submission must add at least three eligible cases of its own"
    for row in report.rows:
        assert set(row.outcomes) == {"provisional-v1", "equal-v1", "freshness-weighted-v1"}


def test_additional_eligible_cases_are_not_copies_of_the_starter_profile(report):
    profiles = {tuple(row.criteria.values()) for row in report.rows if row.fixture == "weighting"}
    assert len(profiles) >= 4


def test_scores_follow_the_weighted_sum(report, weight_sets):
    for row in report.rows:
        for version, outcome in row.outcomes.items():
            weights = weight_sets.get(version).weights
            expected = sum(weights[name] * row.criteria[name] for name in weights)
            assert outcome.score == pytest.approx(expected, abs=1e-6)


def test_ranking_and_routing_changes_are_detected(report):
    rows = {row.case_id: row for row in report.rows}
    qualified = rows["w-qualified-rule"].outcomes
    assert qualified["provisional-v1"].decision.value == "human_review"
    assert qualified["equal-v1"].decision.value == "pass"
    unverified = rows["w-rule-status-unverified"].outcomes
    assert unverified["provisional-v1"].decision.value == "pass"
    assert unverified["freshness-weighted-v1"].decision.value == "human_review"
    assert set(report.decision_changes) == {"w-qualified-rule", "w-rule-status-unverified"}
    flips = {(c.configuration, c.baseline, c.alternative) for c in report.order_changes}
    assert ("freshness-weighted-v1", "w-rule-status-unverified > w-secondary-news",
            "w-secondary-news > w-rule-status-unverified") in flips


def test_cases_without_change_are_listed(report):
    assert set(report.unchanged) == {"current-news", "old-law-current", "future-rule", "w-primary-news-verified"}
    assert any("score the same under every configuration" in note for note in report.notes)


def test_ineligible_cases_are_excluded_with_reasons(report):
    excluded = {item.case_id: item for item in report.excluded}
    assert set(excluded) == {
        "recent-article-old-event", "unknown-date", "unsupported-claim", "superseded-source",
        "competitor-promotion", "conflicting-evidence",
    }
    assert "unknown criteria: temporal_validity" in excluded["unknown-date"].reason


def test_starter_cases_alone_cannot_show_weight_effects(starter, policy, weight_sets):
    alone = compare_weights([(starter, "starter")], policy, weight_sets)
    assert len(alone.rows) == 3
    assert alone.order_changes == [] and alone.decision_changes == []
    assert any("No ranking or routing changes occurred" in note for note in alone.notes)


def test_markdown_report_lists_every_section(report):
    text = render_markdown(report)
    for heading in ("## Configurations", "## Eligible cases", "## Ranking per configuration",
                    "## Pairwise order changes", "## Routing changes", "## No change under any configuration",
                    "## Not compared", "## Notes and limitations"):
        assert heading in text
    assert "not probabilities" in text


def test_duplicate_case_ids_across_fixtures_are_refused(starter, policy, weight_sets):
    with pytest.raises(ValueError, match="more than one fixture"):
        compare_weights([(starter, "a"), (starter, "b")], policy, weight_sets)


def test_default_cli_fixtures_exist():
    assert STARTER_FIXTURE.is_file() and WEIGHTING_FIXTURE.is_file()


def test_unchanged_cases_take_part_in_no_order_change(weighting_fixture, policy, weight_sets):
    subset = weighting_fixture.model_copy(update={"cases": [
        c for c in weighting_fixture.cases if c.id in {"w-primary-news-verified", "w-rule-status-unverified"}
    ]})
    report = compare_weights([(subset, "subset")], policy, weight_sets)
    reordered = {case_id for change in report.order_changes for case_id in change.pair}
    assert not reordered & set(report.unchanged)
