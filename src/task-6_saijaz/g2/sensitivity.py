"""Offline weight-only comparisons with exact ties and validated ranks."""

from dataclasses import dataclass, replace
import json

from .errors import ValidationError
from .fixtures import FixtureInputs
from .policy import CriterionValues, Policy
from .reports import Decision, EvaluationReport, evaluate_case, report_to_dict
from .validation import JSONValue


def _ranks(reports: tuple[EvaluationReport, ...]) -> tuple[int | None, ...]:
    scores = tuple(report.assessment.score for report in reports)
    # Competition rank: 1 + number strictly above; exact ties share rank.
    # Blocked/null scores are unranked, not treated as zero.
    return tuple(None if score is None else 1 + sum(
        other is not None and other > score for other in scores
    ) for score in scores)


@dataclass(frozen=True, slots=True)
class ComparisonRun:
    """One policy's complete reports and input-order competition ranks."""

    policy: Policy
    reports: tuple[EvaluationReport, ...]
    ranks: tuple[int | None, ...]

    def __post_init__(self) -> None:
        if type(self.policy) is not Policy or type(self.reports) is not tuple or not self.reports:
            raise ValidationError("INVALID_COMPARISON_RUN", "$.run", "Expected policy and nonempty immutable reports.")
        if any(type(report) is not EvaluationReport or report.assessment.policy != self.policy for report in self.reports):
            raise ValidationError("INCONSISTENT_POLICY", "$.run.reports", "All reports must use this run's policy.")
        if len({report.case_id for report in self.reports}) != len(self.reports):
            raise ValidationError("DUPLICATE_ID", "$.run.reports", "Case identifiers must be unique.")
        expected = _ranks(self.reports)
        if type(self.ranks) is not tuple or len(self.ranks) != len(expected) or any(
            type(actual) is not type(correct) or actual != correct
            for actual, correct in zip(self.ranks, expected)
        ):
            raise ValidationError("INCONSISTENT_RANKS", "$.run.ranks", "Ranks must reflect exact unrounded scores; null is unranked.")


@dataclass(frozen=True, slots=True)
class CaseComparison:
    """Input-order score/rank/route vectors across the comparison policies."""

    case_id: str
    scores: tuple[float | None, ...]
    ranks: tuple[int | None, ...]
    decisions: tuple[Decision, ...]

    @property
    def routing_changed(self) -> bool:
        """Whether any alternative differs from the first baseline route."""
        return any(decision is not self.decisions[0] for decision in self.decisions[1:])

    @property
    def ranking_changed(self) -> bool:
        """Whether any alternative changes this case's competition rank."""
        return any(rank != self.ranks[0] for rank in self.ranks[1:])

    def __post_init__(self) -> None:
        from ._checks import require_text
        from .policy import _unit_number

        require_text(self.case_id, "$.comparison.case_id")
        if any(type(values) is not tuple for values in (self.scores, self.ranks, self.decisions)) or len(self.scores) < 2 or not len(self.scores) == len(self.ranks) == len(self.decisions):
            raise ValidationError("INVALID_COMPARISON_VECTOR", "$.comparison", "Expected aligned immutable vectors for at least two policies.")
        for score, rank, decision in zip(self.scores, self.ranks, self.decisions):
            if score is not None:
                if type(score) is not float:
                    raise ValidationError("INVALID_TYPE", "$.comparison.scores", "Expected float or null.")
                _unit_number(score, "$.comparison.scores")
            if (score is None) != (rank is None) or (rank is not None and (type(rank) is not int or rank < 1)) or type(decision) is not Decision:
                raise ValidationError("INVALID_COMPARISON_VECTOR", "$.comparison", "Expected valid score, rank, and route types.")


@dataclass(frozen=True, slots=True)
class SensitivityComparison:
    """Validate identical inputs and non-weight settings across all runs."""

    inputs: FixtureInputs
    runs: tuple[ComparisonRun, ...]

    def __post_init__(self) -> None:
        if type(self.inputs) is not FixtureInputs or type(self.runs) is not tuple or len(self.runs) < 2 or any(type(run) is not ComparisonRun for run in self.runs):
            raise ValidationError("INVALID_COMPARISON", "$.comparison", "Expected fixture inputs and at least two validated runs.")
        baseline = self.runs[0].policy
        if len({run.policy.weights_version for run in self.runs}) != len(self.runs):
            raise ValidationError("DUPLICATE_WEIGHTS_VERSION", "$.runs", "Weight configurations require unique version identifiers.")
        for run in self.runs:
            if replace(run.policy, weights=baseline.weights, weights_version=baseline.weights_version) != baseline:
                raise ValidationError("NON_WEIGHT_POLICY_CHANGE", "$.runs", "Only weights and their version may vary.")
            if len(run.reports) != len(self.inputs.cases):
                raise ValidationError("INCONSISTENT_CASES", "$.runs", "Every run must assess all identical cases in input order.")
            for case, report in zip(self.inputs.cases, run.reports):
                temporal = report.assessment.temporal
                if report.case_id != case.id or temporal.metadata != case.metadata or temporal.as_of != self.inputs.as_of or temporal.news_max_event_age_days != self.inputs.news_max_event_age_days:
                    raise ValidationError("INCONSISTENT_CASES", "$.runs", "Every run must use identical metadata and temporal context.")

    @property
    def cases(self) -> tuple[CaseComparison, ...]:
        """Derive aligned comparison vectors without mutable cached summaries."""
        return tuple(CaseComparison(
            case.id, tuple(run.reports[index].assessment.score for run in self.runs),
            tuple(run.ranks[index] for run in self.runs),
            tuple(run.reports[index].decision for run in self.runs),
        ) for index, case in enumerate(self.inputs.cases))


def compare_policies(inputs: FixtureInputs, policies: tuple[Policy, ...]) -> SensitivityComparison:
    """Compare weight-only policies, keeping all fixture context unchanged."""
    if type(inputs) is not FixtureInputs or type(policies) is not tuple or len(policies) < 2 or any(type(policy) is not Policy for policy in policies):
        raise ValidationError("INVALID_COMPARISON", "$.comparison", "Expected validated fixture and immutable policies.")
    baseline = policies[0]
    if len({policy.weights_version for policy in policies}) != len(policies):
        raise ValidationError("DUPLICATE_WEIGHTS_VERSION", "$.policies", "Weight versions must be unique.")
    if any(replace(policy, weights=baseline.weights, weights_version=baseline.weights_version) != baseline for policy in policies):
        raise ValidationError("NON_WEIGHT_POLICY_CHANGE", "$.policies", "Only weights and their version may vary.")
    runs: list[ComparisonRun] = []
    for policy in policies:
        reports = tuple(evaluate_case(case, inputs.as_of, inputs.news_max_event_age_days, policy) for case in inputs.cases)
        runs.append(ComparisonRun(policy, reports, _ranks(reports)))
    return SensitivityComparison(inputs, tuple(runs))


def compare_weights(inputs: FixtureInputs, baseline: Policy) -> SensitivityComparison:
    """Compare chosen, equal, and authority-heavy preferences without calibration."""
    if type(baseline) is not Policy:
        raise ValidationError("INVALID_TYPE", "$.policy", "Expected validated baseline policy.")
    return compare_policies(inputs, (
        baseline,
        replace(baseline, weights=CriterionValues(1 / 3, 1 / 3, 1 / 3),
                weights_version=baseline.weights_version + ":equal-v1"),
        replace(baseline, weights=CriterionValues(0.25, 0.50, 0.25),
                weights_version=baseline.weights_version + ":authority-heavy-v1"),
    ))


def comparison_to_dict(comparison: SensitivityComparison) -> dict[str, JSONValue]:
    """Expose full reports plus scores, rankings, ties, and routing changes."""
    if type(comparison) is not SensitivityComparison:
        raise ValidationError("INVALID_TYPE", "$.comparison", "Expected a validated sensitivity comparison.")
    runs: list[JSONValue] = []
    for run in comparison.runs:
        ranked = sorted((report for report in run.reports if report.assessment.score is not None),
                        key=lambda report: (-report.assessment.score, report.case_id))
        ties: list[JSONValue] = []
        for rank in sorted({rank for rank in run.ranks if rank is not None}):
            members = sorted(report.case_id for report, position in zip(run.reports, run.ranks) if position == rank)
            if len(members) > 1:
                ties.append(members)
        runs.append({"weights_version": run.policy.weights_version,
                     "reports": [report_to_dict(report) for report in run.reports],
                     "ranks": list(run.ranks), "ranked_case_ids": [report.case_id for report in ranked],
                     "tie_groups": ties})
    cases: list[JSONValue] = [{"case_id": case.case_id, "scores": list(case.scores),
        "ranks": list(case.ranks), "decisions": [decision.value for decision in case.decisions],
        "routing_changed": case.routing_changed, "ranking_changed": case.ranking_changed}
        for case in comparison.cases]
    return {"schema_version": "1.0", "gate": "G2", "as_of": comparison.inputs.as_of.isoformat(),
            "baseline_weights_version": comparison.runs[0].policy.weights_version,
            "rank_convention": "Competition ranks by exact full-precision score; exact ties share rank, lexical IDs order tied display, null scores are unranked.",
            "runs": runs, "cases": cases,
            "routing_changed_case_ids": [case.case_id for case in comparison.cases if case.routing_changed],
            "routing_unchanged_case_ids": [case.case_id for case in comparison.cases if not case.routing_changed],
            "ranking_changed": any(case.ranking_changed for case in comparison.cases),
            "limitations": "Weight-only synthetic preference analysis, not calibration or independent evidence. Cases with fixed support/timing vary on authority only; unchanged rankings are possible and must not be presented as reversals."}


def comparison_to_json(comparison: SensitivityComparison) -> str:
    """Produce deterministic comparison JSON preserving nulls and score precision."""
    return json.dumps(comparison_to_dict(comparison), ensure_ascii=False, allow_nan=False,
                      sort_keys=True, indent=2) + "\n"
