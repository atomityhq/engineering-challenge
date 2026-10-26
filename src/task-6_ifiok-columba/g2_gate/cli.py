"""Command line: evaluate cases, compare weights, build the triage queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import sensitivity, triage
from .config import DEFAULT_POLICY_PATH, load_policy
from .evaluator import evaluate_fixture
from .loader import FixtureError, load_fixture, merge_fixtures
from .models import Fixture, Report

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SUPPLIED_FIXTURE = REPO_ROOT / "fixtures" / "g2-cases.json"
EXTRA_FIXTURE = PACKAGE_ROOT / "fixtures" / "extra-eligible-cases.json"
DEFAULT_OUT = PACKAGE_ROOT / "examples"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="g2_gate", description="G2 evidence and current-validity gate")
    p.add_argument("--policy", default=str(DEFAULT_POLICY_PATH), help="policy/weights JSON")
    sub = p.add_subparsers(dest="command", required=True)

    for name, help_text in [
        ("evaluate", "evaluate cases and write one report per case"),
        ("sensitivity", "compare scores and routing under different weights"),
        ("triage", "plain-English work queue with next actions"),
        ("all", "run evaluate, sensitivity and triage and write everything to --out"),
    ]:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--fixture", action="append", help="fixture file (repeatable)")
        sp.add_argument("--out", default=str(DEFAULT_OUT), help="output folder")
    return p


def _fixtures(args: argparse.Namespace, default: list[Path]) -> list[tuple[Path, Fixture]]:
    paths = [Path(f) for f in args.fixture] if args.fixture else default
    return [(path, load_fixture(path)[0]) for path in paths]


def _print_table(reports: list[Report]) -> None:
    print(f"{'case':32} {'decision':13} {'score':>6}  reasons")
    for r in reports:
        score = "-" if r.score is None else f"{r.score:.3f}"
        print(f"{r.case_id:32} {r.decision:13} {score:>6}  {', '.join(r.reasons)}")


def _write_json(path: Path, reports: list[Report]) -> None:
    payload = [json.loads(r.model_dump_json()) for r in reports]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        policy = load_policy(args.policy)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)

        if args.command in ("evaluate", "all"):
            for path, fixture in _fixtures(args, [SUPPLIED_FIXTURE]):
                reports = evaluate_fixture(fixture, policy)
                print(f"\n== {path.name} (as_of {fixture.as_of}) ==")
                _print_table(reports)
                _write_json(out / f"reports-{path.stem}.json", reports)

        if args.command in ("sensitivity", "all"):
            combined = merge_fixtures([f for _, f in _fixtures(args, [SUPPLIED_FIXTURE, EXTRA_FIXTURE])])
            rows = sensitivity.compare(combined, policy)
            text = sensitivity.to_markdown(rows, list(sensitivity.weight_sets(policy)))
            (out / "weight-sensitivity.md").write_text(text, encoding="utf-8")
            print("\n" + text)

        if args.command in ("triage", "all"):
            combined = merge_fixtures([f for _, f in _fixtures(args, [SUPPLIED_FIXTURE, EXTRA_FIXTURE])])
            reports = evaluate_fixture(combined, policy)
            text = triage.to_markdown(triage.build_queue(reports, policy), len(reports))
            (out / "triage-queue.md").write_text(text, encoding="utf-8")
            print("\n" + text)
    except (FixtureError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
