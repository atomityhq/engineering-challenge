"""Command-line demo for the G2 gate.

    python -m g2_gate evaluate      [--fixture PATH ...] [--weights VERSION] [--format table|json] [--check-expected]
    python -m g2_gate sensitivity   [--fixture PATH ...] [--format markdown|json]
    python -m g2_gate describe
    python -m g2_gate demo          [--out-dir DIR]

Exit codes: 0 success, 1 a decision differs from expected_decision (only with
--check-expected, in either output format), 2 invalid fixture or configuration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, TextIO, Tuple

from .config import CRITERIA, G2Policy, WeightConfig, WeightSets
from .criteria import DEFINITIONS
from .evaluator import evaluate_fixture
from .loading import InputValidationError, load_fixture, load_policy, load_weight_sets
from .models import G2Fixture
from .paths import (
    EDGE_FIXTURE,
    EXAMPLES_DIR,
    POLICY_CONFIG,
    STARTER_FIXTURE,
    WEIGHTING_FIXTURE,
    WEIGHTS_CONFIG,
    display_path,
)
from .report import G2Report
from .sensitivity import compare_weights, render_markdown


def _fmt(value: Optional[float]) -> str:
    return "null" if value is None else f"{value:g}"


def expectation_mismatches(fixture: G2Fixture, reports: List[G2Report]) -> List[Dict[str, str]]:
    """Compare decisions with the test-only expected_decision, after evaluation."""
    return [
        {"case_id": report.case_id, "expected": case.expected_decision.value, "actual": report.decision.value}
        for case, report in zip(fixture.cases, reports)
        if case.expected_decision is not None and case.expected_decision != report.decision
    ]


def _expectation_summary(fixture: G2Fixture, reports: List[G2Report]) -> Dict[str, object]:
    mismatches = expectation_mismatches(fixture, reports)
    unchecked = [case.id for case in fixture.cases if case.expected_decision is None]
    checked = len(reports) - len(unchecked)
    return {"checked": checked, "matched": checked - len(mismatches), "total": len(reports),
            "mismatches": mismatches, "without_expectation": unchecked}


def render_table(fixture: G2Fixture, source: str, reports: List[G2Report], policy: G2Policy,
                 weights: WeightConfig, check_expected: bool) -> str:
    lines = [
        f"G2 gate | policy {policy.policy_version} ({policy.calibration_status}) | weights {weights.version} "
        f"({weights.status}) | threshold {policy.threshold.value} ({policy.threshold.status})",
        f"fixture {source} | as_of {fixture.as_of} (from the fixture, not the system clock) | "
        f"news window {fixture.demo_policy.news_max_event_age_days} days (demo convention)",
        "",
    ]
    header = f"{'case':38} {'decision':13} {'score':>6}  {'ES':>4} {'SA':>4} {'TV':>4}  {'freshness':19}"
    if check_expected:
        header += f" {'expected':13} {'ok':3}"
    lines += [header + " routing reasons", "-" * (len(header) + 16)]
    for case, report in zip(fixture.cases, reports):
        crit = " ".join(f"{_fmt(report.criteria[name].score):>4}" for name in CRITERIA)
        score = "  -  " if report.score is None else f"{report.score:.4f}"
        line = f"{report.case_id:38} {report.decision.value:13} {score:>6}  {crit}  {report.freshness.status.value:19}"
        if check_expected:
            expected = case.expected_decision.value if case.expected_decision else "-"
            ok = case.expected_decision is None or case.expected_decision == report.decision
            line += f" {expected:13} {'yes' if ok else 'NO':3}"
        routing = sorted({r.code for r in report.reasons if r.route is not None}, key=report.reason_codes.index)
        lines.append(line + " " + (", ".join(routing) or "-"))
    if check_expected:
        summary = _expectation_summary(fixture, reports)
        unchecked = len(summary["without_expectation"])
        lines += ["", f"{summary['matched']}/{summary['checked']} decisions match expected_decision "
                      "(compared after evaluation; the evaluator never sees it)."
                      + (f" {unchecked} case(s) have no expected_decision and were not checked." if unchecked else "")]
    return "\n".join(lines) + "\n"


def _load_fixtures(paths: Sequence[Path]) -> List[Tuple[G2Fixture, str]]:
    return [(load_fixture(path), display_path(path)) for path in paths]


def _emit(text: str, out: Optional[Path], stdout: TextIO) -> None:
    if out is None:
        stdout.write(text)
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")


def _reports_json(batches: List[Tuple[G2Fixture, str, List[G2Report]]], check_expected: bool = False) -> str:
    payload = []
    for fixture, source, reports in batches:
        entry = {"fixture": source, "as_of": fixture.as_of.isoformat(),
                 "reports": [r.model_dump(mode="json") for r in reports]}
        if check_expected:
            entry["expectation_check"] = {
                "note": "Compared after evaluation; the evaluator never sees expected_decision.",
                **_expectation_summary(fixture, reports),
            }
        payload.append(entry)
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def cmd_evaluate(args: argparse.Namespace, stdout: TextIO) -> int:
    policy, weight_sets = load_policy(args.policy), load_weight_sets(args.weights_config)
    weights = weight_sets.get(args.weights)
    batches = [(fx, src, evaluate_fixture(fx, policy, weights)) for fx, src in _load_fixtures(args.fixture or [STARTER_FIXTURE])]
    if args.format == "json":
        text = _reports_json(batches, args.check_expected)
    else:
        text = "".join(render_table(fx, src, reports, policy, weights, args.check_expected) + "\n"
                       for fx, src, reports in batches)
    _emit(text, args.out, stdout)
    failed = args.check_expected and any(expectation_mismatches(fx, reports) for fx, _, reports in batches)
    return 1 if failed else 0


def cmd_sensitivity(args: argparse.Namespace, stdout: TextIO) -> int:
    policy, weight_sets = load_policy(args.policy), load_weight_sets(args.weights_config)
    fixtures = _load_fixtures(args.fixture or [STARTER_FIXTURE, WEIGHTING_FIXTURE])
    report = compare_weights(fixtures, policy, weight_sets)
    text = report.model_dump_json(indent=2) + "\n" if args.format == "json" else render_markdown(report)
    _emit(text, args.out, stdout)
    return 0


def describe(policy: G2Policy, weight_sets: WeightSets) -> str:
    payload = {
        "policy": policy.model_dump(mode="json"),
        "weights": weight_sets.model_dump(mode="json"),
        "criteria": DEFINITIONS,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def cmd_describe(args: argparse.Namespace, stdout: TextIO) -> int:
    stdout.write(describe(load_policy(args.policy), load_weight_sets(args.weights_config)))
    return 0


def write_examples(out_dir: Path, policy_path: Path = POLICY_CONFIG, weights_path: Path = WEIGHTS_CONFIG) -> List[Path]:
    """Regenerate every committed example output. Deterministic: no timestamps, no absolute paths."""
    policy, weight_sets = load_policy(policy_path), load_weight_sets(weights_path)
    weights = weight_sets.get()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for name, path in (("starter", STARTER_FIXTURE), ("edge-cases", EDGE_FIXTURE), ("weighting-cases", WEIGHTING_FIXTURE)):
        fixture = load_fixture(path)
        source = display_path(path)
        reports = evaluate_fixture(fixture, policy, weights)
        table = render_table(fixture, source, reports, policy, weights, check_expected=True)
        for filename, text in ((f"{name}-summary.txt", table), (f"{name}-reports.json", _reports_json([(fixture, source, reports)]))):
            (out_dir / filename).write_text(text, encoding="utf-8")
            written.append(out_dir / filename)
    sensitivity = compare_weights(_load_fixtures([STARTER_FIXTURE, WEIGHTING_FIXTURE]), policy, weight_sets)
    for filename, text in (("sensitivity.md", render_markdown(sensitivity)),
                           ("sensitivity.json", sensitivity.model_dump_json(indent=2) + "\n"),
                           ("policy-and-weights.json", describe(policy, weight_sets))):
        (out_dir / filename).write_text(text, encoding="utf-8")
        written.append(out_dir / filename)
    return written


def cmd_demo(args: argparse.Namespace, stdout: TextIO) -> int:
    for path in write_examples(args.out_dir, args.policy, args.weights_config):
        stdout.write(f"wrote {display_path(path)}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m g2_gate", description="G2 evidence and current-validity gate (Task 6).")
    parser.add_argument("--policy", type=Path, default=POLICY_CONFIG, help="G2 policy config (default: config/g2_policy.json)")
    parser.add_argument("--weights-config", type=Path, default=WEIGHTS_CONFIG, help="weight sets (default: config/weights.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    ev = sub.add_parser("evaluate", help="evaluate every case in one or more fixtures")
    ev.add_argument("--fixture", type=Path, action="append", help="fixture path; repeatable (default: the supplied starter fixture)")
    ev.add_argument("--weights", help="weight configuration version (default: the configured default)")
    ev.add_argument("--format", choices=("table", "json"), default="table")
    ev.add_argument("--check-expected", action="store_true", help="compare decisions with the test-only expected_decision")
    ev.add_argument("--out", type=Path, help="write to a file instead of stdout")
    ev.set_defaults(func=cmd_evaluate)

    se = sub.add_parser("sensitivity", help="compare eligible cases under every weight configuration")
    se.add_argument("--fixture", type=Path, action="append", help="fixture path; repeatable (default: starter + weighting cases)")
    se.add_argument("--format", choices=("markdown", "json"), default="markdown")
    se.add_argument("--out", type=Path)
    se.set_defaults(func=cmd_sensitivity)

    de = sub.add_parser("describe", help="print the policy, weights and criterion anchors")
    de.set_defaults(func=cmd_describe)

    dm = sub.add_parser("demo", help="regenerate all example outputs")
    dm.add_argument("--out-dir", type=Path, default=EXAMPLES_DIR)
    dm.set_defaults(func=cmd_demo)
    return parser


def main(argv: Optional[Sequence[str]] = None, stdout: Optional[TextIO] = None, stderr: Optional[TextIO] = None) -> int:
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    args = build_parser().parse_args(argv)
    try:
        return args.func(args, stdout)
    except InputValidationError as exc:
        stderr.write(f"error: invalid input in {exc.source}\n")
        for problem in exc.problems:
            stderr.write(f"  - {problem}\n")
        return 2
    except KeyError as exc:
        stderr.write(f"error: {exc.args[0]}\n")
        return 2
