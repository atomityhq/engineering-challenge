from __future__ import annotations

import json
import socket
import urllib.request
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import workflow_audit.workflow as workflow_module
from workflow_audit.contracts import ContractError
from workflow_audit.workflow import (
    replay_workflow,
    run_workflow,
    verify_integrity,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
FAKE_SECRET = "synthetic-secret-123"


class AuditReplayTests(unittest.TestCase):
    def test_successful_three_operation_run_replays_offline(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "successful-run"
            manifest = run_workflow(
                FIXTURES / "successful-run.json",
                run_dir,
                run_id="test-success-001",
            )

            self.assertEqual(manifest["status"], "success")
            self.assertEqual(
                [row["status"] for row in manifest["operations"]],
                ["success"] * 3,
            )
            self.assertEqual(
                [row["name"] for row in manifest["operations"]],
                ["prepare", "enrich", "summarize"],
            )
            self.assertEqual(verify_integrity(run_dir), [])

            # Replay must not make network or HTTP calls.
            with (
                patch.object(
                    socket,
                    "create_connection",
                    side_effect=AssertionError("network access attempted"),
                ),
                patch.object(
                    socket.socket,
                    "connect",
                    side_effect=AssertionError("socket connection attempted"),
                ),
                patch.object(
                    urllib.request,
                    "urlopen",
                    side_effect=AssertionError("HTTP access attempted"),
                ),
            ):
                replay = replay_workflow(run_dir)

            self.assertEqual(replay.status, "match", replay.to_dict())
            self.assertEqual(replay.operations_replayed, 3)
            self.assertEqual(replay.external_calls, 0)
            self.assertEqual(replay.differences, ())

            final_output = json.loads(
                (run_dir / manifest["final_output_ref"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                final_output["qualification"]["category"],
                "high_value",
            )
            self.assertEqual(final_output["route"], "high_value")

    def test_failed_operation_is_recorded_and_reproduced(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "failed-run"
            manifest = run_workflow(
                FIXTURES / "failed-operation.json",
                run_dir,
                run_id="test-failed-001",
            )

            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(len(manifest["operations"]), 2)

            failed = manifest["operations"][-1]
            self.assertEqual(failed["name"], "enrich")
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["error_code"], "SYNTHETIC_FAILURE")
            self.assertIsNone(failed["output_ref"])

            replay = replay_workflow(run_dir)
            self.assertEqual(replay.status, "match", replay.to_dict())

    def test_fake_secret_is_present_in_fixture_but_redacted_from_audit_outputs(
        self,
    ) -> None:
        fixture_text = (
            FIXTURES / "successful-run.json"
        ).read_text(encoding="utf-8")
        self.assertIn(FAKE_SECRET, fixture_text)

        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "secret-check"
            run_workflow(
                FIXTURES / "successful-run.json",
                run_dir,
                run_id="test-secret-001",
            )

            # The planted secret must not appear in any saved run file.
            for path in run_dir.rglob("*"):
                if path.is_file():
                    content = path.read_text(encoding="utf-8")
                    self.assertNotIn(
                        FAKE_SECRET,
                        content,
                        f"secret leaked into {path}",
                    )

            source_fixture = (
                run_dir / "source_fixture.json"
            ).read_text(encoding="utf-8")
            self.assertIn("[REDACTED]", source_fixture)

            saved_input = (
                run_dir / "artifacts" / "op-001-input.json"
            ).read_text(encoding="utf-8")
            self.assertIn("[REDACTED]", saved_input)

            replay = replay_workflow(run_dir)
            self.assertEqual(replay.status, "match", replay.to_dict())

    def test_secret_in_operation_output_is_redacted_and_replays(
        self,
    ) -> None:
        original_prepare = workflow_module.OPERATIONS["prepare"]

        def prepare_with_secret(payload, config):
            output = original_prepare(payload, config)
            output["debug_note"] = f"FAKE_API_KEY={FAKE_SECRET}"
            return output

        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "secret-output-run"

            # Use the instrumented operation for both execution and replay.
            with patch.dict(
                workflow_module.OPERATIONS,
                {"prepare": prepare_with_secret},
            ):
                manifest = run_workflow(
                    FIXTURES / "successful-run.json",
                    run_dir,
                    run_id="test-secret-output-001",
                )

                output_path = (
                    run_dir / "artifacts" / "op-001-output.json"
                )
                output_text = output_path.read_text(encoding="utf-8")

                self.assertNotIn(FAKE_SECRET, output_text)
                self.assertIn("[REDACTED]", output_text)

                for relative in ("audit.json", "events.jsonl"):
                    content = (run_dir / relative).read_text(
                        encoding="utf-8"
                    )
                    self.assertNotIn(FAKE_SECRET, content, relative)

                replay = replay_workflow(run_dir)

            self.assertEqual(manifest["status"], "success")
            self.assertEqual(replay.status, "match", replay.to_dict())
            self.assertEqual(replay.operations_replayed, 3)

    def test_altered_artifact_is_detected_and_replay_is_blocked(
        self,
    ) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "tamper-check"
            manifest = run_workflow(
                FIXTURES / "successful-run.json",
                run_dir,
                run_id="test-tamper-001",
            )

            artifact = run_dir / manifest["final_output_ref"]
            artifact.write_text(
                '{"tampered": true}\n',
                encoding="utf-8",
            )

            failures = verify_integrity(run_dir)
            self.assertTrue(
                any(
                    "ARTIFACT_HASH_MISMATCH" in failure
                    for failure in failures
                ),
                failures,
            )

            replay = replay_workflow(run_dir)
            self.assertEqual(
                replay.status,
                "integrity_failed",
                replay.to_dict(),
            )
            self.assertTrue(
                any(
                    "ARTIFACT_HASH_MISMATCH" in failure
                    for failure in replay.differences
                ),
                replay.to_dict(),
            )

    def test_invalid_audit_manifest_is_rejected(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "invalid-manifest-run"
            run_workflow(
                FIXTURES / "successful-run.json",
                run_dir,
                run_id="test-invalid-manifest-001",
            )

            manifest_path = run_dir / "audit.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )

            # A malformed digest must fail the typed manifest contract.
            manifest["config_sha256"] = "not-a-valid-sha256"
            manifest_path.write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
            )

            failures = verify_integrity(run_dir)
            self.assertEqual(failures, ["AUDIT_MANIFEST_INVALID"])

            replay = replay_workflow(run_dir)
            self.assertEqual(
                replay.status,
                "integrity_failed",
                replay.to_dict(),
            )
            self.assertIn(
                "AUDIT_MANIFEST_INVALID",
                replay.differences,
            )

    def test_malformed_input_fails_before_run_directory_is_created(
        self,
    ) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "should-not-exist"

            with self.assertRaises(ContractError):
                run_workflow(
                    FIXTURES / "malformed-input.json",
                    run_dir,
                    run_id="test-invalid-001",
                )

            self.assertFalse(run_dir.exists())

    def test_existing_run_is_not_overwritten(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "already-there"
            run_dir.mkdir()

            with self.assertRaises(RuntimeError):
                run_workflow(
                    FIXTURES / "successful-run.json",
                    run_dir,
                    run_id="test-existing-001",
                )

    def test_manifest_path_traversal_is_rejected(self) -> None:
        with TemporaryDirectory() as temp:
            run_dir = Path(temp) / "path-check"
            manifest = run_workflow(
                FIXTURES / "successful-run.json",
                run_dir,
                run_id="test-path-001",
            )

            manifest["operations"][0]["input_ref"] = "../../outside.json"
            (run_dir / "audit.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            failures = verify_integrity(run_dir)
            self.assertTrue(
                any(
                    "INVALID_ARTIFACT_REFERENCE" in failure
                    for failure in failures
                ),
                failures,
            )


if __name__ == "__main__":
    unittest.main()