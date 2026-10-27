"""CLI file boundaries and module invocation integration checks."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from g2.__main__ import DEFAULT_POLICY, STARTER_FIXTURE, main


class CLITests(unittest.TestCase):
    """Run isolated local examples without overwriting repository inputs."""

    def test_module_commands_and_deterministic_files(self) -> None:
        submission = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=submission) as directory:
            root = Path(directory)
            for command in ("evaluate", "compare"):
                outputs = []
                for index in range(2):
                    output = root / f"{command}-{index}.json"
                    result = subprocess.run([sys.executable, "-B", "-m", "g2", command,
                        "--output", str(output)], cwd=submission, capture_output=True,
                        text=True, check=False)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")
                    outputs.append(output.read_bytes())
                self.assertEqual(outputs[0], outputs[1])
                data = json.loads(outputs[0])
                if command == "evaluate":
                    self.assertEqual(len(data["reports"]), 9)
                    self.assertEqual({r["decision"] for r in data["reports"]},
                                     {"pass", "revise", "reject", "human_review"})
                else:
                    self.assertEqual(len(data["runs"]), 3)
                    self.assertEqual(data["routing_changed_case_ids"], ["secondary-transit-report"])

    def test_defaults_are_independent_of_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                self.assertEqual(main(["evaluate", "--output", "report.json"]), 0)
                self.assertEqual(len(json.loads(Path("report.json").read_text())["reports"]), 9)
            finally:
                os.chdir(previous)

    def test_malformed_missing_inputs_and_safe_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            malformed = root / "private-input.json"
            malformed.write_text('{"secret": invalid}', encoding="utf-8")
            for flag, source in (("--fixture", malformed), ("--config", malformed),
                                 ("--fixture", root / "missing.json"),
                                 ("--config", root / "missing.json")):
                output = root / "report.json"
                with self.assertLogs("g2.cli", level="ERROR") as captured:
                    self.assertEqual(main(["evaluate", flag, str(source), "--output", str(output)]), 2)
                self.assertFalse(output.exists())
                messages = " ".join(captured.output)
                self.assertNotIn(str(source), messages)
                self.assertNotIn("secret", messages)

    def test_output_conflicts_and_existing_files(self) -> None:
        originals = (STARTER_FIXTURE.read_bytes(), DEFAULT_POLICY.read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            symlink = root / "link.json"
            symlink.symlink_to(STARTER_FIXTURE)
            hardlink = root / "hard.json"
            hardlink.hardlink_to(DEFAULT_POLICY)
            for path in (STARTER_FIXTURE, DEFAULT_POLICY, symlink, hardlink):
                with self.assertLogs("g2.cli", level="ERROR") as captured:
                    self.assertEqual(main(["evaluate", "--output", str(path)]), 2)
                self.assertIn("OUTPUT_INPUT_CONFLICT", " ".join(captured.output))
            existing = root / "existing.json"
            existing.write_text("preserve", encoding="utf-8")
            with self.assertLogs("g2.cli", level="ERROR"):
                self.assertEqual(main(["evaluate", "--output", str(existing)]), 2)
            self.assertEqual(existing.read_text(), "preserve")
        self.assertEqual(originals, (STARTER_FIXTURE.read_bytes(), DEFAULT_POLICY.read_bytes()))

    def test_unwritable_output_and_missing_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing" / "report.json"
            with self.assertLogs("g2.cli", level="ERROR"):
                self.assertEqual(main(["evaluate", "--output", str(output)]), 2)
            self.assertFalse(output.parent.exists())
            with patch.object(Path, "open", side_effect=PermissionError), self.assertLogs("g2.cli", level="ERROR"):
                self.assertEqual(main(["compare", "--output", str(output)]), 2)

    def test_help_and_invalid_arguments(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream), self.assertRaises(SystemExit) as caught:
            main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("evaluate", stream.getvalue())
        self.assertIn("compare", stream.getvalue())
        for arguments in ([], ["evaluate"], ["private-secret-command"],
                          ["compare", "--output", "file", "--secret-value"]):
            with self.assertLogs("g2.cli", level="ERROR") as captured, self.assertRaises(SystemExit) as caught:
                main(arguments)
            self.assertEqual(caught.exception.code, 2)
            self.assertNotIn("secret", " ".join(captured.output))
