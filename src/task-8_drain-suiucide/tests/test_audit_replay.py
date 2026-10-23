from __future__ import annotations

import json
import socket
import urllib.request
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from workflow_audit.contracts import ContractError
from workflow_audit.workflow import replay_workflow, run_workflow, verify_integrity

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
FAKE_SECRET = "synthetic-secret-123"


class AuditReplayTests(unittest.TestCase):
    def test_successful_three_operation_run_replays_offline(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "successful-run"
            manifest = run_workflow(
                FIXTURES / "successful-run.json", run_dir, run_id="test-success-001"
            )

            self.assertEqual(manifest["status"], "success")
            self.assertEqual([row["status"] for row in manifest["operations"]], ["success"] * 3)
            self.assertEqual([row["name"] for row in manifest["operations"]], ["prepare", "enrich", "summarize"])
            self.assertEqual(verify_integrity(run_dir), [])

            # Any accidental network use makes this test fail immediately.
            with patch.object(socket, "create_connection", side_effect=AssertionError("network access attempted")), patch.object(
                urllib.request, "urlopen", side_effect=AssertionError("HTTP access attempted")
            ):
                replay = replay_workflow(run_dir)

            self.assertEqual(replay.status, "match")
            self.assertEqual(replay.operations_replayed, 3)
            self.assertEqual(replay.external_calls, 0)
            self.assertEqual(replay.differences, ())

            final_output = json.loads((run_dir / manifest["final_output_ref"]).read_text(encoding="utf-8"))
            self.assertEqual(final_output["qualification"]["category"], "high_value")
            self.assertEqual(final_output["route"], "high_value")

    def test_failed_operation_is_recorded_and_reproduced(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "failed-run"
            manifest = run_workflow(
                FIXTURES / "failed-operation.json", run_dir, run_id="test-failed-001"
            )
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(len(manifest["operations"]), 2)
            failed = manifest["operations"][-1]
            self.assertEqual(failed["name"], "enrich")
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["error_code"], "SYNTHETIC_FAILURE")
            self.assertIsNone(failed["output_ref"])
            self.assertEqual(replay_workflow(run_dir).status, "match")

    def test_fake_secret_is_present_in_fixture_but_redacted_from_audit_outputs(self) -> None:
        fixture_text = (FIXTURES / "successful-run.json").read_text(encoding="utf-8")
        self.assertIn(FAKE_SECRET, fixture_text)

        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "secret-check"
            run_workflow(FIXTURES / "successful-run.json", run_dir, run_id="test-secret-001")
            for relative in ["audit.json", "events.jsonl", "artifacts/op-001-input.json"]:
                content = (run_dir / relative).read_text(encoding="utf-8")
                self.assertNotIn(FAKE_SECRET, content, f"secret leaked into {relative}")
            self.assertIn("[REDACTED]", (run_dir / "artifacts/op-001-input.json").read_text(encoding="utf-8"))

    def test_altered_artifact_is_detected_and_replay_is_blocked(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "tamper-check"
            manifest = run_workflow(
                FIXTURES / "successful-run.json", run_dir, run_id="test-tamper-001"
            )
            artifact = run_dir / manifest["final_output_ref"]
            artifact.write_text('{"tampered": true}\n', encoding="utf-8")

            failures = verify_integrity(run_dir)
            self.assertTrue(any("ARTIFACT_HASH_MISMATCH" in failure for failure in failures))
            replay = replay_workflow(run_dir)
            self.assertEqual(replay.status, "integrity_failed")
            self.assertTrue(any("ARTIFACT_HASH_MISMATCH" in failure for failure in replay.differences))

    def test_malformed_input_fails_before_run_directory_is_created(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "should-not-exist"
            with self.assertRaises(ContractError):
                run_workflow(FIXTURES / "malformed-input.json", run_dir, run_id="test-invalid-001")
            self.assertFalse(run_dir.exists())

    def test_existing_run_is_not_overwritten(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "already-there"
            run_dir.mkdir()
            with self.assertRaises(RuntimeError):
                run_workflow(FIXTURES / "successful-run.json", run_dir, run_id="test-existing-001")

    def test_manifest_path_traversal_is_rejected(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "path-check"
            manifest = run_workflow(
                FIXTURES / "successful-run.json", run_dir, run_id="test-path-001"
            )
            manifest["operations"][0]["input_ref"] = "../../outside.json"
            (run_dir / "audit.json").write_text(json.dumps(manifest), encoding="utf-8")
            failures = verify_integrity(run_dir)
            self.assertTrue(any("INVALID_ARTIFACT_REFERENCE" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
