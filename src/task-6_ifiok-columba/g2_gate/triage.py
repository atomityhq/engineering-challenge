"""Business add-on: turn gate decisions into a work queue a content team can act on.

The gate answers "can this go on?". A real team also needs "so what do I do now?".
This module is deliberately separate from the gate: it only reads finished reports and
adds the next action for each reason code (the wording lives in the policy config).
Atomity sells audit-ready decision records, so every line keeps the reason code that
produced it.
"""

from __future__ import annotations

from .config import Policy
from .models import Report

SECTIONS = [
    ("pass", "Ready for the next internal stage"),
    ("revise", "Fix and resubmit"),
    ("human_review", "Needs a person to decide"),
    ("reject", "Do not publish"),
]


def build_queue(reports: list[Report], policy: Policy) -> dict[str, list[dict]]:
    queue: dict[str, list[dict]] = {key: [] for key, _ in SECTIONS}
    for r in reports:
        actions = [
            f"{code}: {policy.next_actions[code]}"
            for code in r.reasons
            if code in policy.next_actions
        ]
        if r.decision == "pass":
            actions = []
        queue[r.decision].append(
            {
                "case_id": r.case_id,
                "statement": r.statement,
                "reasons": r.reasons,
                "next_actions": actions,
                "notes": r.notes,
            }
        )
    return queue


def to_markdown(queue: dict[str, list[dict]], total: int) -> str:
    out = ["# Content triage queue (G2)", ""]
    counts = ", ".join(f"{len(queue[k])} {k}" for k, _ in SECTIONS)
    out.append(f"{total} cases checked: {counts}.")
    out.append("")
    out.append(
        "Only 'pass' moves on. Everything else has a named next step, so reviewers spend "
        "time on real judgment calls instead of working out why something stopped."
    )
    out.append("")
    for key, title in SECTIONS:
        items = queue[key]
        out.append(f"## {title} ({len(items)})")
        out.append("")
        if not items:
            out.append("_none_")
            out.append("")
            continue
        for item in items:
            out.append(f"- **{item['case_id']}** - {item['statement']}")
            if key == "pass":
                if "RULE_NOT_YET_APPLICABLE" in item["notes"]:
                    out.append("  - Careful: this rule is not applicable yet. Say \"from <date>\", not \"now\".")
                if "REVERIFY_RECOMMENDED" in item["notes"]:
                    out.append("  - Re-verify the source soon.")
            for action in item["next_actions"]:
                out.append(f"  - {action}")
        out.append("")
    return "\n".join(out)
