"""Weight sensitivity: do the chosen weights drive the outcome, or would any weights do?

Runs the same cases under several weight sets and reports score, rank and decision for
each, so a reviewer can see exactly where the weighting choice matters.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Policy
from .evaluator import evaluate_fixture
from .models import Fixture


@dataclass(frozen=True)
class Row:
    case_id: str
    scores: dict[str, float]
    ranks: dict[str, int]
    decisions: dict[str, str]

    @property
    def routing_changed(self) -> bool:
        return len(set(self.decisions.values())) > 1


def weight_sets(policy: Policy) -> dict[str, tuple]:
    sets = {"chosen": (policy.weights, policy.weights_version)}
    for name, weights in policy.alternative_weights.items():
        sets[name] = (weights, f"alt-{name}")
    return sets


def compare(fixture: Fixture, policy: Policy) -> list[Row]:
    """Compare every case that has a score under the chosen weights (the eligible ones)."""
    per_config: dict[str, dict] = {}
    for name, (weights, version) in weight_sets(policy).items():
        reports = evaluate_fixture(fixture, policy.with_weights(weights, version))
        per_config[name] = {r.case_id: r for r in reports}

    eligible = [
        cid for cid, r in per_config["chosen"].items() if r.score is not None
    ]

    ranks: dict[str, dict[str, int]] = {}
    for name, reports in per_config.items():
        ordered = sorted(eligible, key=lambda cid: -reports[cid].score)
        ranks[name] = {}
        for cid in ordered:  # ties share a rank
            better = sum(1 for o in eligible if reports[o].score > reports[cid].score)
            ranks[name][cid] = better + 1

    return [
        Row(
            case_id=cid,
            scores={n: per_config[n][cid].score for n in per_config},
            ranks={n: ranks[n][cid] for n in per_config},
            decisions={n: per_config[n][cid].decision for n in per_config},
        )
        for cid in eligible
    ]


def to_markdown(rows: list[Row], names: list[str]) -> str:
    out = ["# Weight sensitivity", ""]
    out.append(
        "Same cases, three weight sets. Only cases eligible for a score "
        "(no failed hard check, no unknown criterion) are compared."
    )
    out.append("")
    header = "| case | " + " | ".join(f"{n} score / rank / decision" for n in names) + " | routing changes? |"
    out.append(header)
    out.append("|" + "---|" * (len(names) + 2))
    for row in rows:
        cells = [
            f"{row.scores[n]:.3f} / #{row.ranks[n]} / {row.decisions[n]}" for n in names
        ]
        out.append(f"| {row.case_id} | " + " | ".join(cells) + f" | {'YES' if row.routing_changed else 'no'} |")
    out.append("")

    changed = [r.case_id for r in rows if r.routing_changed]
    rank_changed = [
        r.case_id for r in rows if len(set(r.ranks.values())) > 1
    ]
    out.append(f"- Eligible cases compared: {len(rows)}")
    out.append(f"- Cases whose routing changes with the weights: {len(changed)} {changed}")
    out.append(f"- Cases whose rank changes with the weights: {len(rank_changed)} {rank_changed}")
    unchanged = [r.case_id for r in rows if not r.routing_changed]
    out.append(f"- Routing unchanged under every weight set: {unchanged}")
    out.append("")
    out.append(
        "Limitation: cases scoring 1.0 on every criterion score 1.0 under any weights, so they "
        "cannot show weight sensitivity. The extra fixtures exist to vary the criteria."
    )
    return "\n".join(out) + "\n"
