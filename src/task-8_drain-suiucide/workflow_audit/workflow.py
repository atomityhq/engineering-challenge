"""Deterministic three-operation workflow with local audit records and replay."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    ContractError,
    OperationRecord,
    ReplayResult,
    WorkflowConfig,
    WorkflowFixture,
)
from .security import redact

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": "1.0",
    "config_version": "demo-v1",
    "high_value_min_employees": 100,
    "operation_order": ["prepare", "enrich", "summarize"],
}

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class RunAlreadyExistsError(RuntimeError):
    """Raised rather than overwriting a previous run."""


class WorkflowOperationError(RuntimeError):
    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = canonical_json_bytes(value)
    path.write_bytes(content)
    return sha256_bytes(content)


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Could not load valid JSON from {path.name}: {exc.__class__.__name__}") from exc


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _contained_path(run_dir: Path, relative_ref: str) -> Path:
    """Resolve a manifest path while preventing path traversal outside the run."""
    if not isinstance(relative_ref, str) or not relative_ref.strip():
        raise ContractError("artifact reference must be a non-empty relative path")
    relative = Path(relative_ref)
    if relative.is_absolute():
        raise ContractError("artifact reference must be relative")
    root = run_dir.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContractError("artifact reference escapes the run directory") from exc
    return resolved


def validate_fixture_dict(value: Any) -> WorkflowFixture:
    return WorkflowFixture.from_dict(value)


def _prepare(payload: dict[str, Any], config: WorkflowConfig) -> dict[str, Any]:
    fixture = WorkflowFixture.from_dict(payload)
    lead = fixture.lead.to_dict()
    # Normalisation is deterministic and intentionally small.
    lead["name"] = " ".join(lead["name"].split())
    lead["company"] = " ".join(lead["company"].split())
    return {"lead": lead, "case_id": fixture.case_id}


def _enrich(payload: dict[str, Any], config: WorkflowConfig) -> dict[str, Any]:
    if payload.get("simulate_failure") is True:
        raise WorkflowOperationError("SYNTHETIC_FAILURE", "Synthetic failure requested by fixture.")
    lead = payload.get("lead")
    if not isinstance(lead, dict):
        raise WorkflowOperationError("INVALID_OPERATION_INPUT", "Enrichment input did not contain a lead object.")
    employees = lead.get("employees")
    if not isinstance(employees, int) or isinstance(employees, bool):
        raise WorkflowOperationError("INVALID_OPERATION_INPUT", "Enrichment input had an invalid employee count.")
    is_high_value = employees >= config.high_value_min_employees
    qualification = {
        "score": 85 if is_high_value else 55,
        "category": "high_value" if is_high_value else "standard",
        "priority": "high" if is_high_value else "normal",
        "reason": (
            f"Employee count meets the configured threshold ({config.high_value_min_employees})."
            if is_high_value
            else f"Employee count is below the configured threshold ({config.high_value_min_employees})."
        ),
    }
    return {
        "case_id": payload.get("case_id"),
        "lead": lead,
        "qualification": qualification,
    }


def _summarize(payload: dict[str, Any], config: WorkflowConfig) -> dict[str, Any]:
    lead = payload.get("lead")
    qualification = payload.get("qualification")
    if not isinstance(lead, dict) or not isinstance(qualification, dict):
        raise WorkflowOperationError("INVALID_OPERATION_INPUT", "Summary input is missing required fields.")
    if not all(key in lead for key in ("company", "name", "service")):
        raise WorkflowOperationError("INVALID_OPERATION_INPUT", "Summary input is missing lead fields.")
    return {
        "case_id": payload.get("case_id"),
        "company": lead["company"],
        "contact": lead["name"],
        "service": lead["service"],
        "qualification": qualification,
        "route": "high_value" if qualification["category"] == "high_value" else "standard",
        "summary": (
            f"{lead['company']} requested {lead['service']}. "
            f"Route: {qualification['category']} (score {qualification['score']})."
        ),
    }


OPERATIONS: dict[str, Callable[[dict[str, Any], WorkflowConfig], dict[str, Any]]] = {
    "prepare": _prepare,
    "enrich": _enrich,
    "summarize": _summarize,
}


def _append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_event = redact(event)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(safe_event, ensure_ascii=False, sort_keys=True) + "\n")


def _write_run(
    fixture_dict: dict[str, Any],
    config_dict: dict[str, Any],
    run_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    fixture = WorkflowFixture.from_dict(fixture_dict)
    config = WorkflowConfig.from_dict(config_dict)
    run_dir.mkdir(parents=True, exist_ok=False)

    fixture_ref = "source_fixture.json"
    config_ref = "config.json"
    fixture_sha = write_json(run_dir / fixture_ref, fixture.to_dict())
    config_sha = write_json(run_dir / config_ref, config.to_dict())
    event_path = run_dir / "events.jsonl"
    operations: list[dict[str, Any]] = []
    current: dict[str, Any] = fixture.to_dict()
    previous_output_ref: str | None = None
    run_status = "success"

    for index, name in enumerate(config.operation_order, start=1):
        op_id = f"op-{index:03d}"
        if index == 1:
            raw_input: dict[str, Any] = current
        elif name == "enrich":
            raw_input = {
                "case_id": current["case_id"],
                "lead": current["lead"],
                "simulate_failure": fixture.metadata.get("simulate_failure", False),
            }
        else:
            raw_input = current

        input_ref = f"artifacts/{op_id}-input.json"
        input_sha = write_json(run_dir / input_ref, redact(raw_input))
        started = {
            "run_id": run_id,
            "operation_id": op_id,
            "event": "operation_started",
            "operation": name,
            "input_ref": input_ref,
            "timestamp": utc_now(),
        }
        _append_event(event_path, started)

        try:
            output = OPERATIONS[name](raw_input, config)
        except WorkflowOperationError as exc:
            run_status = "failed"
            operations.append(
                OperationRecord(
                    operation_id=op_id,
                    name=name,
                    status="failed",
                    input_ref=input_ref,
                    input_sha256=input_sha,
                    output_ref=None,
                    output_sha256=None,
                    error_code=exc.code,
                    error_message=exc.public_message,
                ).to_dict()
            )
            _append_event(
                event_path,
                {
                    "run_id": run_id,
                    "operation_id": op_id,
                    "event": "operation_failed",
                    "operation": name,
                    "error_code": exc.code,
                    "error_message": exc.public_message,
                    "timestamp": utc_now(),
                },
            )
            break
        except Exception as exc:  # Defensive boundary: never dump raw tracebacks/data to audit.
            run_status = "failed"
            safe_message = f"Unexpected operation error ({exc.__class__.__name__})."
            operations.append(
                OperationRecord(
                    operation_id=op_id,
                    name=name,
                    status="failed",
                    input_ref=input_ref,
                    input_sha256=input_sha,
                    output_ref=None,
                    output_sha256=None,
                    error_code="UNEXPECTED_OPERATION_ERROR",
                    error_message=safe_message,
                ).to_dict()
            )
            _append_event(
                event_path,
                {
                    "run_id": run_id,
                    "operation_id": op_id,
                    "event": "operation_failed",
                    "operation": name,
                    "error_code": "UNEXPECTED_OPERATION_ERROR",
                    "error_message": safe_message,
                    "timestamp": utc_now(),
                },
            )
            break

        output_ref = f"artifacts/{op_id}-output.json"
        output_sha = write_json(run_dir / output_ref, redact(output))
        operations.append(
            OperationRecord(
                operation_id=op_id,
                name=name,
                status="success",
                input_ref=input_ref,
                input_sha256=input_sha,
                output_ref=output_ref,
                output_sha256=output_sha,
            ).to_dict()
        )
        _append_event(
            event_path,
            {
                "run_id": run_id,
                "operation_id": op_id,
                "event": "operation_succeeded",
                "operation": name,
                "output_ref": output_ref,
                "output_sha256": output_sha,
                "timestamp": utc_now(),
            },
        )
        current = output
        previous_output_ref = output_ref

    manifest = {
        "schema_version": "1.0",
        "run_id": run_id,
        "case_id": fixture.case_id,
        "status": run_status,
        "config_version": config.config_version,
        "config_ref": config_ref,
        "config_sha256": config_sha,
        "source_fixture_ref": fixture_ref,
        "source_fixture_sha256": fixture_sha,
        "final_output_ref": previous_output_ref,
        "operations": operations,
        "created_at": utc_now(),
        "redaction_policy": "credential-assignment-v1",
    }
    write_json(run_dir / "audit.json", manifest)
    _append_event(
        event_path,
        {
            "run_id": run_id,
            "event": "run_completed",
            "status": run_status,
            "operation_count": len(operations),
            "timestamp": utc_now(),
        },
    )
    return manifest


def run_workflow(
    fixture_path: Path,
    run_dir: Path,
    run_id: str | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Execute the workflow and persist inputs, outputs, hashes and audit data."""
    fixture_path = Path(fixture_path)
    run_dir = Path(run_dir)
    if run_id is None:
        run_id = f"run-{uuid.uuid4().hex[:12]}"
    if not RUN_ID_RE.fullmatch(run_id):
        raise ContractError("run_id must be 1-64 safe alphanumeric, dot, underscore or hyphen characters")
    if run_dir.exists():
        raise RunAlreadyExistsError(f"Run directory already exists; refusing to overwrite: {run_dir}")

    fixture_dict = read_json(fixture_path)
    WorkflowFixture.from_dict(fixture_dict)  # Validate before creating a run directory.
    config_dict = read_json(config_path) if config_path else DEFAULT_CONFIG
    WorkflowConfig.from_dict(config_dict)
    return _write_run(fixture_dict, config_dict, run_dir, run_id)


def verify_integrity(run_dir: Path) -> list[str]:
    """Return integrity failures for the manifest, config, fixture and operation artifacts."""
    run_dir = Path(run_dir)
    manifest_path = run_dir / "audit.json"
    if not manifest_path.is_file():
        return ["AUDIT_MANIFEST_MISSING"]
    try:
        manifest = read_json(manifest_path)
    except ContractError:
        return ["AUDIT_MANIFEST_INVALID"]
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0":
        return ["AUDIT_MANIFEST_INVALID"]

    failures: list[str] = []
    refs: list[tuple[str, str | None]] = [
        (manifest.get("config_ref", ""), manifest.get("config_sha256")),
        (manifest.get("source_fixture_ref", ""), manifest.get("source_fixture_sha256")),
    ]
    operations = manifest.get("operations")
    if not isinstance(operations, list):
        return ["AUDIT_OPERATIONS_INVALID"]
    for record in operations:
        if not isinstance(record, dict):
            failures.append("AUDIT_OPERATION_RECORD_INVALID")
            continue
        refs.append((record.get("input_ref", ""), record.get("input_sha256")))
        if record.get("output_ref") is not None:
            refs.append((record.get("output_ref", ""), record.get("output_sha256")))

    for relative_ref, expected_hash in refs:
        try:
            path = _contained_path(run_dir, relative_ref)
        except ContractError:
            failures.append(f"INVALID_ARTIFACT_REFERENCE:{relative_ref}")
            continue
        if not path.is_file():
            failures.append(f"ARTIFACT_MISSING:{relative_ref}")
            continue
        if not isinstance(expected_hash, str) or sha256_file(path) != expected_hash:
            failures.append(f"ARTIFACT_HASH_MISMATCH:{relative_ref}")
    return failures


def replay_workflow(run_dir: Path) -> ReplayResult:
    """Replay from the saved fixture/config, checking artifact integrity and outputs."""
    run_dir = Path(run_dir)
    differences = verify_integrity(run_dir)
    if differences:
        return ReplayResult(
            run_id=run_dir.name,
            status="integrity_failed",
            operations_replayed=0,
            external_calls=0,
            differences=tuple(differences),
        )

    try:
        manifest = read_json(run_dir / "audit.json")
        fixture_value = read_json(_contained_path(run_dir, manifest["source_fixture_ref"]))
        config_value = read_json(_contained_path(run_dir, manifest["config_ref"]))
        fixture = WorkflowFixture.from_dict(fixture_value)
        config = WorkflowConfig.from_dict(config_value)
    except (ContractError, KeyError, TypeError) as exc:
        return ReplayResult(
            run_id=run_dir.name,
            status="invalid",
            operations_replayed=0,
            external_calls=0,
            differences=(f"INVALID_REPLAY_INPUT:{exc.__class__.__name__}",),
        )

    if manifest.get("config_version") != config.config_version:
        return ReplayResult(
            run_id=manifest.get("run_id", run_dir.name),
            status="invalid",
            operations_replayed=0,
            external_calls=0,
            differences=("CONFIG_VERSION_MISMATCH",),
        )

    current: dict[str, Any] = fixture.to_dict()
    replay_count = 0
    differences = []
    records = manifest["operations"]
    for index, name in enumerate(config.operation_order):
        if index >= len(records):
            differences.append(f"MISSING_OPERATION_RECORD:{name}")
            break
        record = records[index]
        if record.get("name") != name:
            differences.append(f"OPERATION_ORDER_MISMATCH:{name}")
            break
        if index == 0:
            operation_input = current
        elif name == "enrich":
            operation_input = {
                "case_id": current["case_id"],
                "lead": current["lead"],
                "simulate_failure": fixture.metadata.get("simulate_failure", False),
            }
        else:
            operation_input = current

        try:
            replay_output = OPERATIONS[name](operation_input, config)
        except WorkflowOperationError as exc:
            replay_count += 1
            if record.get("status") != "failed" or record.get("error_code") != exc.code:
                differences.append(f"FAILURE_REPLAY_MISMATCH:{name}")
            break
        except Exception as exc:
            replay_count += 1
            expected_code = "UNEXPECTED_OPERATION_ERROR"
            if record.get("status") != "failed" or record.get("error_code") != expected_code:
                differences.append(f"FAILURE_REPLAY_MISMATCH:{name}:{exc.__class__.__name__}")
            break

        replay_count += 1
        if record.get("status") != "success":
            differences.append(f"EXPECTED_FAILURE_NOT_REPRODUCED:{name}")
            break
        if record.get("output_ref") is None:
            differences.append(f"OUTPUT_REFERENCE_MISSING:{name}")
            break
        saved_output = read_json(_contained_path(run_dir, record["output_ref"]))
        # Hash verification already ran; comparing canonical objects makes the decision readable.
        if replay_output != saved_output:
            differences.append(f"OUTPUT_MISMATCH:{name}")
            break
        current = replay_output

    if not differences:
        if manifest.get("status") == "success" and replay_count != len(config.operation_order):
            differences.append("INCOMPLETE_SUCCESSFUL_REPLAY")
        elif manifest.get("status") == "failed" and (not records or records[-1].get("status") != "failed"):
            differences.append("FAILED_RUN_NOT_REPRODUCED")

    return ReplayResult(
        run_id=manifest.get("run_id", run_dir.name),
        status="match" if not differences else "mismatch",
        operations_replayed=replay_count,
        external_calls=0,
        differences=tuple(differences),
    )


def create_demo_fixture_copy(source: Path, destination: Path) -> None:
    """Utility for examples only: copy a fixture without transforming its contents."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
