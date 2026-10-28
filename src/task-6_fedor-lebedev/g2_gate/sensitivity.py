"""Weight sensitivity comparison across eligible cases.

Every eligible case is scored under each weight configuration with the same
policy (threshold, floors, freshness rules). The report shows scores, ranks and
decisions per configuration and lists which cases changed rank, changed
routing, or did not change at all.

Eligibility does not depend on weights (hard checks, freshness and unknown
criteria are evaluated before scoring), so the compared set is identical for
every configuration.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict

from .config import CRITERIA, G2Policy, WeightConfig, WeightSets
from .evaluator import evaluate_case
from .loading import InputValidationError
from .models import Decision, EvaluationContext, G2Fixture


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConfigOutcome(_Out):
    score: float
    rank: int
    decision: Decision


class SensitivityRow(_Out):
    case_id: str
    fixture: str
    criteria: Dict[str, float]
    outcomes: Dict[str, ConfigOutcome]
    rank_changed: bool
    decision_changed: bool


class OrderChange(_Out):
    configuration: str
    pair: List[str]
    baseline: str
    alternative: str


class ExcludedCase(_Out):
    case_id: str
    fixture: str
    decision: Decision
    reason: str


class ConfigSummary(_Out):
    version: str
    status: str
    weights: Dict[str, float]


class SensitivityReport(_Out):
    policy_version: str
    calibration_status: str
    baseline: str
    threshold: float
    configurations: List[ConfigSummary]
    rows: List[SensitivityRow]
    rankings: Dict[str, List[List[str]]]
    rank_changes: List[str]
    order_changes: List[OrderChange]
    decision_changes: List[str]
    unchanged: List[str]
    excluded: List[ExcludedCase]
    notes: List[str]


def _competition_ranks(scores: Dict[str, float]) -> Dict[str, int]:
    """Standard competition ranking (1, 2, 2, 4): tied scores share a rank."""
    ordered = sorted(scores.values(), reverse=True)
    return {case_id: ordered.index(score) + 1 for case_id, score in scores.items()}


def _ranking_groups(scores: Dict[str, float]) -> List[List[str]]:
    groups: Dict[float, List[str]] = {}
    for case_id, score in scores.items():
        groups.setdefault(score, []).append(case_id)
    return [sorted(groups[score]) for score in sorted(groups, reverse=True)]


def _relation(a: str, b: str, scores: Dict[str, float]) -> str:
    if scores[a] > scores[b]:
        return f"{a} > {b}"
    if scores[b] > scores[a]:
        return f"{b} > {a}"
    return f"{a} = {b}"


def _order_changes(scores: Dict[str, Dict[str, float]], baseline: str) -> List[OrderChange]:
    """Pairs of cases whose relative order differs from the baseline (a flip, a new tie, or a broken tie)."""
    changes: List[OrderChange] = []
    case_ids = sorted(scores[baseline])
    for version, by_case in scores.items():
        if version == baseline:
            continue
        for i, a in enumerate(case_ids):
            for b in case_ids[i + 1:]:
                before, after = _relation(a, b, scores[baseline]), _relation(a, b, by_case)
                if before != after:
                    changes.append(OrderChange(configuration=version, pair=[a, b], baseline=before, alternative=after))
    return changes


def compare_weights(fixtures: Sequence[Tuple[G2Fixture, str]], policy: G2Policy, weight_sets: WeightSets,
                    versions: Optional[Sequence[str]] = None) -> SensitivityReport:
    baseline = weight_sets.get()
    requested = list(versions) if versions else [c.version for c in weight_sets.configurations]
    configs: List[WeightConfig] = [baseline] + [weight_sets.get(v) for v in requested if v != baseline.version]

    criteria: Dict[str, Dict[str, float]] = {}
    origin: Dict[str, str] = {}
    scores: Dict[str, Dict[str, float]] = {c.version: {} for c in configs}
    decisions: Dict[str, Dict[str, Decision]] = {c.version: {} for c in configs}
    excluded: List[ExcludedCase] = []

    for fixture, source in fixtures:
        context = EvaluationContext.from_fixture(fixture)
        for fixture_case in fixture.cases:
            case = fixture_case.to_gate_input()
            if case.id in origin or any(e.case_id == case.id for e in excluded):
                raise InputValidationError(source, [f"case id {case.id!r} appears in more than one fixture; ids must be unique"])
            reports = [evaluate_case(case, context, policy, config) for config in configs]
            if not reports[0].eligible_for_scoring:
                excluded.append(ExcludedCase(
                    case_id=case.id, fixture=source, decision=reports[0].decision,
                    reason="; ".join(reports[0].score_withheld_because),
                ))
                continue
            if not all(r.eligible_for_scoring for r in reports):
                raise RuntimeError(f"eligibility of {case.id!r} changed with weights; this violates the gate design")
            origin[case.id] = source
            criteria[case.id] = {name: reports[0].criteria[name].score for name in CRITERIA}
            for config, report in zip(configs, reports):
                scores[config.version][case.id] = report.score
                decisions[config.version][case.id] = report.decision

    ranks = {version: _competition_ranks(by_case) for version, by_case in scores.items()}
    rows: List[SensitivityRow] = []
    for case_id in criteria:
        outcomes = {
            config.version: ConfigOutcome(
                score=scores[config.version][case_id],
                rank=ranks[config.version][case_id],
                decision=decisions[config.version][case_id],
            )
            for config in configs
        }
        base = outcomes[baseline.version]
        rows.append(SensitivityRow(
            case_id=case_id,
            fixture=origin[case_id],
            criteria=criteria[case_id],
            outcomes=outcomes,
            rank_changed=any(o.rank != base.rank for o in outcomes.values()),
            decision_changed=any(o.decision != base.decision for o in outcomes.values()),
        ))
    rows.sort(key=lambda row: (row.outcomes[baseline.version].rank, row.case_id))
    order_changes = _order_changes(scores, baseline.version)
    reordered = {case_id for change in order_changes for case_id in change.pair}

    report = SensitivityReport(
        policy_version=policy.policy_version,
        calibration_status=policy.calibration_status,
        baseline=baseline.version,
        threshold=policy.threshold.value,
        configurations=[ConfigSummary(version=c.version, status=c.status, weights=dict(c.weights)) for c in configs],
        rows=rows,
        rankings={version: _ranking_groups(by_case) for version, by_case in scores.items()},
        rank_changes=[r.case_id for r in rows if r.rank_changed],
        order_changes=order_changes,
        decision_changes=[r.case_id for r in rows if r.decision_changed],
        unchanged=[
            r.case_id for r in rows
            if not r.rank_changed and not r.decision_changed and r.case_id not in reordered
        ],
        excluded=excluded,
        notes=[],
    )
    return report.model_copy(update={"notes": _notes(report)})


def _notes(report: SensitivityReport) -> List[str]:
    notes: List[str] = []
    if len(report.rows) < 3:
        notes.append(f"Only {len(report.rows)} eligible case(s); the comparison needs at least three to be meaningful.")
    if not report.order_changes and not report.decision_changes:
        notes.append(
            "No ranking or routing changes occurred. With these cases the chosen weights are not distinguishable "
            "from the alternatives, so this comparison cannot support any claim that the weighting matters."
        )
    flat = [r.case_id for r in report.rows if len(set(r.criteria.values())) == 1]
    if flat:
        notes.append(
            "Cases whose criteria are all equal score the same under every configuration, because weights sum "
            f"to 1; weights only matter where criteria differ: {', '.join(flat)}."
        )
    support_values = sorted({r.criteria["evidence_support"] for r in report.rows})
    notes.append(
        f"evidence_support takes only {support_values} among eligible cases: unsupported (0) and unknown support "
        "are routed by hard checks before scoring, so the score never sees them."
    )
    notes.append(
        f"The threshold ({report.threshold}) and floors are held constant. They were chosen with "
        f"{report.baseline} in mind, so part of any routing change under another configuration reflects a "
        "threshold that was not re-tuned for it."
    )
    notes.append(
        "Scores are provisional, uncalibrated prototype indices, not probabilities. Rank and routing changes show "
        "sensitivity to a preference choice; they do not show which configuration is correct."
    )
    return notes


def render_markdown(report: SensitivityReport) -> str:
    versions = [c.version for c in report.configurations]
    lines = [
        "# G2 weight sensitivity comparison",
        "",
        f"Policy `{report.policy_version}` ({report.calibration_status}). Baseline: `{report.baseline}`. "
        f"Threshold {report.threshold} (provisional) and criterion floors are held constant across configurations.",
        "",
        "## Configurations",
        "",
        "| Configuration | Status | " + " | ".join(CRITERIA) + " |",
        "| --- | --- | " + " | ".join("---:" for _ in CRITERIA) + " |",
    ]
    for config in report.configurations:
        weights = " | ".join(f"{config.weights[name]:.4g}" for name in CRITERIA)
        lines.append(f"| `{config.version}` | {config.status} | {weights} |")

    lines += [
        "",
        "## Eligible cases",
        "",
        "Each cell: score (rank) decision. ES / SA / TV = evidence support / source authority / temporal validity.",
        "",
        "| Case | ES | SA | TV | " + " | ".join(f"`{v}`" for v in versions) + " | Rank changed | Routing changed |",
        "| --- | ---: | ---: | ---: | " + " | ".join("---" for _ in versions) + " | --- | --- |",
    ]
    for row in report.rows:
        crit = " | ".join(f"{row.criteria[name]:g}" for name in CRITERIA)
        cells = " | ".join(
            f"{row.outcomes[v].score:.4f} (#{row.outcomes[v].rank}) {row.outcomes[v].decision.value}" for v in versions
        )
        lines.append(
            f"| `{row.case_id}` | {crit} | {cells} | {'yes' if row.rank_changed else 'no'} | "
            f"{'yes' if row.decision_changed else 'no'} |"
        )

    lines += ["", "## Ranking per configuration", ""]
    for version in versions:
        ranking = " > ".join(" = ".join(group) for group in report.rankings[version])
        lines.append(f"- `{version}`: {ranking}")

    by_id = {row.case_id: row for row in report.rows}
    lines += ["", "## Rank position changes (relative to the baseline; competition ranking, ties share a rank)", ""]
    if report.rank_changes:
        for case_id in report.rank_changes:
            row = by_id[case_id]
            base = row.outcomes[report.baseline].rank
            moves = ", ".join(
                f"#{base} → #{row.outcomes[v].rank} under `{v}`" for v in versions
                if row.outcomes[v].rank != base
            )
            lines.append(f"- `{case_id}`: {moves}")
    else:
        lines.append("- None.")

    lines += ["", "## Pairwise order changes (relative to the baseline)", ""]
    if report.order_changes:
        for change in report.order_changes:
            lines.append(f"- under `{change.configuration}`: {change.baseline} becomes {change.alternative}")
    else:
        lines.append("- None.")

    lines += ["", "## Routing changes (relative to the baseline)", ""]
    if report.decision_changes:
        for case_id in report.decision_changes:
            row = by_id[case_id]
            base = row.outcomes[report.baseline].decision.value
            moves = ", ".join(
                f"{base} → {row.outcomes[v].decision.value} under `{v}`" for v in versions
                if row.outcomes[v].decision.value != base
            )
            lines.append(f"- `{case_id}`: {moves}")
    else:
        lines.append("- None.")

    lines += ["", "## No change under any configuration", ""]
    lines += [f"- `{case_id}`" for case_id in report.unchanged] or ["- None."]

    lines += ["", "## Not compared (not eligible for scoring)", ""]
    if report.excluded:
        for item in report.excluded:
            lines.append(f"- `{item.case_id}` ({item.fixture}): {item.decision.value}; {item.reason}")
    else:
        lines.append("- None.")

    lines += ["", "## Notes and limitations", ""]
    lines += [f"- {note}" for note in report.notes]
    return "\n".join(lines) + "\n"
