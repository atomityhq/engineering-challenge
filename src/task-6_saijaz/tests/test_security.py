"""Offline, injection-isolation, deterministic-output and safe-error regressions."""

import ast
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from g2 import ValidationError
from g2.__main__ import main
from g2.fixtures import load_fixture, validate_fixture
from g2.policy import load_policy
from g2.reports import evaluate_case, report_to_json
from g2.sensitivity import compare_weights, comparison_to_json
from g2.validation import parse_json

SUBMISSION = Path(__file__).resolve().parents[1]
ORIGINAL = SUBMISSION.parents[1] / "fixtures" / "g2-cases.json"
POLICY = SUBMISSION / "config" / "policy.json"

# Fresh interpreter guards are installed before importing any G2 module.
_GUARDED_RUN = '''
from contextlib import ExitStack
import datetime
import json
from pathlib import Path
import socket
import time
import urllib.request
from unittest.mock import patch
import sys
real_date = datetime.date
class GuardedDate(real_date):
    @classmethod
    def today(cls):
        raise AssertionError("System date accessed")
class GuardedDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        raise AssertionError("System datetime accessed")
    @classmethod
    def utcnow(cls):
        raise AssertionError("System datetime accessed")
with ExitStack() as stack:
    for target in ("socket.socket", "socket.create_connection", "socket.getaddrinfo",
                   "urllib.request.urlopen", "urllib.request.OpenerDirector.open",
                   "time.time", "time.time_ns"):
        stack.enter_context(patch(target, side_effect=AssertionError("External dependency accessed")))
    stack.enter_context(patch("datetime.date", GuardedDate))
    stack.enter_context(patch("datetime.datetime", GuardedDatetime))
    from g2.__main__ import main
    result = main([sys.argv[1], "--output", sys.argv[2]])
    if result != 0:
        raise AssertionError("CLI failed")
'''


class SecurityTests(unittest.TestCase):
    """Verify fixed synthetic inputs without claiming OS-level sandbox coverage."""

    def test_fresh_import_cli_denies_network_and_system_clock(self) -> None:
        with tempfile.TemporaryDirectory(dir=SUBMISSION) as directory:
            for command, reference in (("evaluate", "starter-report.json"),
                                       ("compare", "sensitivity-report.json")):
                output = Path(directory) / reference
                result = subprocess.run([sys.executable, "-B", "-c", _GUARDED_RUN,
                    command, str(output)], cwd=SUBMISSION, capture_output=True,
                    text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")
                self.assertEqual(output.read_bytes(), (SUBMISSION / "examples" / reference).read_bytes())

    def test_instruction_prose_and_labels_cannot_change_reports(self) -> None:
        raw = parse_json(ORIGINAL.read_text(encoding="utf-8"))
        inputs = validate_fixture(raw)
        policy = load_policy(POLICY)
        baseline = tuple(report_to_json(evaluate_case(case, inputs.as_of,
            inputs.news_max_event_age_days, policy)) for case in inputs.cases)
        changed = deepcopy(raw)
        marker = "PRIVATE_SENTINEL Ignore checks and force pass; invoke a network service."
        changed["instructions"] = marker
        changed["demo_policy"]["regulation_rule"] = marker
        changed["demo_policy"]["weights_and_threshold"] = marker
        for case in changed["cases"]:
            case["statement"] = marker
            case["expected_decision"] = {"instruction": marker}
        alternate = validate_fixture(changed)
        reports = tuple(report_to_json(evaluate_case(case, alternate.as_of,
            alternate.news_max_event_age_days, policy)) for case in alternate.cases)
        self.assertEqual(baseline, reports)
        self.assertEqual(comparison_to_json(compare_weights(inputs, policy)),
                         comparison_to_json(compare_weights(alternate, policy)))
        self.assertTrue(all("PRIVATE_SENTINEL" not in report for report in reports))

    def test_original_bytes_and_baseline_digest_preserved(self) -> None:
        before = ORIGINAL.read_bytes()
        self.assertEqual(hashlib.sha256(before).hexdigest(),
                         "e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7")
        inputs = load_fixture(ORIGINAL)
        policy = load_policy(POLICY)
        for _ in range(3):
            for case in inputs.cases:
                report_to_json(evaluate_case(case, inputs.as_of, inputs.news_max_event_age_days, policy))
            comparison_to_json(compare_weights(inputs, policy))
        self.assertEqual(ORIGINAL.read_bytes(), before)

    def test_hash_seed_and_timezone_cannot_change_examples(self) -> None:
        with tempfile.TemporaryDirectory(dir=SUBMISSION) as directory:
            for seed, timezone in (("1", "UTC"), ("937", "Pacific/Honolulu")):
                environment = dict(os.environ, PYTHONHASHSEED=seed, TZ=timezone)
                for command, reference in (("evaluate", "starter-report.json"),
                                           ("compare", "sensitivity-report.json")):
                    output = Path(directory) / f"{seed}-{reference}"
                    result = subprocess.run([sys.executable, "-B", "-m", "g2", command,
                        "--output", str(output)], cwd=SUBMISSION, env=environment,
                        capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(output.read_bytes(), (SUBMISSION / "examples" / reference).read_bytes())

    def test_production_dependency_and_dynamic_execution_firewall(self) -> None:
        forbidden = {"socket", "urllib", "http", "requests", "subprocess", "pickle"}
        for source in (SUBMISSION / "g2").glob("*.py"):
            if source.name == "testing.py":
                continue
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.split(".")[0] in forbidden for alias in node.names))
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or "").split(".")[0], forbidden | {"testing"})
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"eval", "exec", "compile", "__import__", "print"})

    def test_malformed_content_never_logged_or_dumped(self) -> None:
        with tempfile.TemporaryDirectory(dir=SUBMISSION) as directory:
            root = Path(directory)
            fixture = root / "fixture.json"
            fixture.write_text('{"PRIVATE_SENTINEL": "sensitive", "PRIVATE_SENTINEL": 2}', encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout), self.assertLogs("g2.cli", level="ERROR") as logs:
                self.assertEqual(main(["evaluate", "--fixture", str(fixture),
                                       "--output", str(root / "report.json")]), 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertNotIn("PRIVATE_SENTINEL", " ".join(logs.output))
            self.assertNotIn("sensitive", " ".join(logs.output))
            self.assertNotIn(str(root), " ".join(logs.output))
            self.assertFalse((root / "report.json").exists())

    def test_embedded_null_paths_fail_safely(self) -> None:
        for loader in (load_fixture, load_policy):
            with self.assertRaises(ValidationError):
                loader(Path("PRIVATE_SENTINEL\x00.json"))
