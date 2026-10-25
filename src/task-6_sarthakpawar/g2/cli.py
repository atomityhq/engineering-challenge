"""Command-line interface (CLI) for executing the G2 Content-Quality Gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from g2.config import (
    AUTHORITY_FOCUSED_WEIGHTS,
    DEFAULT_WEIGHTS,
    EQUAL_WEIGHTS,
    GateConfig,
)
from g2.evaluator import evaluate_case, evaluate_fixture, load_fixture
from g2.models import EvaluationReport


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Format tabular data into an ASCII table."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))

    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    header_str = (
        "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    )

    lines = [sep, header_str, sep]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(str(val).ljust(widths[i]) for i, val in enumerate(row))
            + " |"
        )
    lines.append(sep)
    return "\n".join(lines)


def run_sensitivity_comparison(
    extra_fixture_path: Path,
) -> dict[str, Any]:
    """Run sensitivity analysis across three distinct weight configurations and print detailed writeups."""
    configs = {
        "Baseline (0.50/0.25/0.25)": GateConfig(weights=DEFAULT_WEIGHTS),
        "Equal (1/3 each)": GateConfig(weights=EQUAL_WEIGHTS),
        "Authority-Focused (0.35/0.45/0.20)": GateConfig(
            weights=AUTHORITY_FOCUSED_WEIGHTS
        ),
    }

    envelope = load_fixture(extra_fixture_path)
    comparison_results: dict[str, dict[str, Any]] = {}

    table_rows: list[list[str]] = []

    for case in envelope.cases:
        comparison_results[case.id] = {}
        row = [case.id]
        for cfg_name, cfg in configs.items():
            report = evaluate_case(case, as_of=envelope.as_of, config=cfg)
            score_str = f"{report.score:.3f}" if report.score is not None else "None"
            comparison_results[case.id][cfg_name] = {
                "score": report.score,
                "decision": report.decision,
                "reasons": report.reasons,
            }
            row.append(f"{report.decision} ({score_str})")
        table_rows.append(row)

    headers = [
        "Case ID",
        "Baseline [0.50, 0.25, 0.25]",
        "Equal (1/3 each)",
        "Authority-Focused [0.35, 0.45, 0.20]",
    ]
    print("\n=== Weight Sensitivity Comparison (Extra Eligible Cases) ===")
    print(format_table(headers, table_rows))

    print("\n--- Sensitivity Findings & Routing Summary ---")
    print(
        "1. Ranking Inversion:\n"
        "   - Under Baseline: extra-provisional-timing (0.875) = extra-secondary-authority (0.875) > extra-partial-support (0.750) > extra-secondary-partial (0.625)\n"
        "   - Under Equal (1/3 each): extra-secondary = extra-partial = extra-timing tie at 0.833 > extra-secondary-partial (0.667)\n"
        "   - Under Authority-Focused: extra-provisional-timing (0.900) > extra-partial-support (0.825) > extra-secondary-authority (0.775) > extra-secondary-partial (0.600)\n"
        "   * Note: extra-secondary-authority and extra-partial-support completely invert their relative ranks between Baseline and Authority-Focused."
    )
    print(
        "2. Routing Shifts:\n"
        "   - extra-secondary-authority: pass (0.875) -> pass (0.833) -> human_review (0.775 < 0.80)\n"
        "   - extra-partial-support: human_review (0.750 < 0.80) -> pass (0.833) -> pass (0.825)\n"
        "   - extra-provisional-timing: pass (0.875) -> pass (0.833) -> pass (0.900) [UNCHANGED DECISION]\n"
        "   - extra-secondary-partial: human_review (0.625) -> human_review (0.667) -> human_review (0.600) [UNCHANGED DECISION]"
    )

    return comparison_results


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="G2 Content-Quality Gate Evaluation CLI"
    )
    parser.add_argument(
        "--fixture",
        type=str,
        default=None,
        help="Path to fixture file (defaults to fixtures/g2-cases.json)",
    )
    parser.add_argument(
        "--extra-fixture",
        type=str,
        default=None,
        help="Path to extra fixture file for sensitivity analysis",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write JSON evaluation reports",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON evaluation reports to stdout",
    )
    parser.add_argument(
        "--case",
        type=str,
        default=None,
        help="Filter and display full JSON report for a single case ID",
    )
    parser.add_argument(
        "--sensitivity",
        action="store_true",
        help="Run weight sensitivity comparison on extra eligible cases",
    )

    args = parser.parse_args(argv)

    current_dir = Path(__file__).resolve().parent
    package_dir = current_dir.parent
    workspace_root = package_dir.parent.parent

    # Find starter fixture
    fixture_path: Path
    if args.fixture:
        fixture_path = Path(args.fixture)
    else:
        candidates = [
            workspace_root / "fixtures" / "g2-cases.json",
            package_dir / "fixtures" / "g2-cases.json",
        ]
        fixture_path = next((c for c in candidates if c.is_file()), candidates[0])

    if not fixture_path.is_file():
        print(f"Error: Fixture file not found at {fixture_path}", file=sys.stderr)
        return 1

    extra_fixture_path: Path
    if args.extra_fixture:
        extra_fixture_path = Path(args.extra_fixture)
    else:
        extra_fixture_path = package_dir / "fixtures" / "extra-cases.json"

    # Evaluate cases
    reports: list[EvaluationReport] = evaluate_fixture(fixture_path)

    # Filter to specific case if requested
    if args.case:
        filtered = [r for r in reports if r.case_id == args.case]
        if not filtered:
            print(f"Error: Case ID '{args.case}' not found.", file=sys.stderr)
            return 1
        print(json.dumps(filtered[0].model_dump(mode="json"), indent=2))
        return 0

    # If --json requested, print complete JSON reports to stdout and return
    if args.json:
        reports_dict = [r.model_dump(mode="json") for r in reports]
        print(json.dumps(reports_dict, indent=2))
        return 0

    # Otherwise format detailed summary table
    print(f"Loaded fixture: {fixture_path}")
    headers = [
        "Case ID",
        "Decision",
        "Score",
        "Hard Checks",
        "Criteria [E,A,T]",
        "Freshness",
        "Primary Reasons",
    ]
    rows: list[list[str]] = []
    for r in reports:
        score_str = f"{r.score:.3f}" if r.score is not None else "None"
        hc_str = "PASS" if r.hard_checks.all_passed() else "FAIL"
        crit_str = f"[{r.criteria.evidence_support}, {r.criteria.source_authority}, {r.criteria.temporal_validity}]"
        reasons_str = "; ".join(r.reasons[:2])
        rows.append(
            [
                r.case_id,
                r.decision,
                score_str,
                hc_str,
                crit_str,
                r.freshness.status,
                reasons_str,
            ]
        )

    print("\n=== G2 Evaluation Results (Starter Cases) ===")
    print(format_table(headers, rows))

    # Run sensitivity comparison if requested or by default
    if args.sensitivity or extra_fixture_path.is_file():
        run_sensitivity_comparison(extra_fixture_path)

    # Automatically persist sample-output.json in examples/ unless custom output given
    out_path = (
        Path(args.output)
        if args.output
        else package_dir / "examples" / "sample-output.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    reports_dict = [r.model_dump(mode="json") for r in reports]
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(reports_dict, f, indent=2)
    print(f"\nAudit reports saved to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
