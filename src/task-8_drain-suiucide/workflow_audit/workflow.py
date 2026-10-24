"""Deterministic workflow with local audit records, integrity checks, and replay."""

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
    AuditEvent,
    AuditManifest,
    ContractError,
    OperationRecord,
    OperationResult,
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
    """An expected workflow operation failure with a safe public message."""

    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically for repeatable artifact hashing."""
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    return (text + "\n").encode("utf-8")


def sha256_bytes(content: bytes) -> str:
    """Calculate the SHA-256 digest of bytes."""
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    """Calculate the SHA-256 digest of the actual file contents."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> str:
    """Write canonical JSON and return the hash of the written bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = canonical_json_bytes(value)
    path.write_bytes(content)
    return sha256_bytes(content)


def read_json(path: Path) -> Any:
    """Load JSON and convert malformed or inaccessible files to ContractError."""
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(
            f"Could not load valid JSON from {path.name}: "
            f"{exc.__class__.__name__}"
        ) from exc


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _contained_path(run_dir: Path, relative_ref: str) -> Path:
    """Resolve an artifact reference without permitting path traversal."""
    if not isinstance(relative_ref, str) or not relative_ref.strip():
        raise ContractError(
            "artifact reference must be a non-empty relative path"
        )

    relative = Path(relative_ref)
    if relative.is_absolute():
        raise ContractError("artifact reference must be relative")

    root = run_dir.resolve()
    resolved = (root / relative).resolve()

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContractError(
            "artifact reference escapes the run directory"
        ) from exc

    return resolved


def validate_fixture_dict(value: Any) -> WorkflowFixture:
    """Validate a fixture dictionary using the typed fixture contract."""
    return WorkflowFixture.from_dict(value)


def _prepare(
    payload: dict[str, Any],
    config: WorkflowConfig,
) -> dict[str, Any]:
    """Normalise the lead deterministically."""
    fixture = WorkflowFixture.from_dict(payload)
    lead = fixture.lead.to_dict()

    lead["name"] = " ".join(lead["name"].split())
    lead["company"] = " ".join(lead["company"].split())

    return {
        "lead": lead,
        "case_id": fixture.case_id,
    }


def _enrich(
    payload: dict[str, Any],
    config: WorkflowConfig,
) -> dict[str, Any]:
    """Assign a deterministic qualification based on the configured threshold."""
    if payload.get("simulate_failure") is True:
        raise WorkflowOperationError(
            "SYNTHETIC_FAILURE",
            "Synthetic failure requested by fixture.",
        )

    lead = payload.get("lead")
    if not isinstance(lead, dict):
        raise WorkflowOperationError(
            "INVALID_OPERATION_INPUT",
            "Enrichment input did not contain a lead object.",
        )

    employees = lead.get("employees")
    if not isinstance(employees, int) or isinstance(employees, bool):
        raise WorkflowOperationError(
            "INVALID_OPERATION_INPUT",
            "Enrichment input had an invalid employee count.",
        )

    is_high_value = employees >= config.high_value_min_employees

    qualification = {
        "score": 85 if is_high_value else 55,
        "category": "high_value" if is_high_value else "standard",
        "priority": "high" if is_high_value else "normal",
        "reason": (
            "Employee count meets the configured threshold "
            f"({config.high_value_min_employees})."
            if is_high_value
            else "Employee count is below the configured threshold "
            f"({config.high_value_min_employees})."
        ),
    }

    return {
        "case_id": payload.get("case_id"),
        "lead": lead,
        "qualification": qualification,
    }


def _summarize(
    payload: dict[str, Any],
    config: WorkflowConfig,
) -> dict[str, Any]:
    """Create the final deterministic workflow result."""
    lead = payload.get("lead")
    qualification = payload.get("qualification")

    if not isinstance(lead, dict) or not isinstance(qualification, dict):
        raise WorkflowOperationError(
            "INVALID_OPERATION_INPUT",
            "Summary input is missing required fields.",
        )

    if not all(key in lead for key in ("company", "name", "service")):
        raise WorkflowOperationError(
            "INVALID_OPERATION_INPUT",
            "Summary input is missing lead fields.",
        )

    category = qualification["category"]
    score = qualification["score"]

    return {
        "case_id": payload.get("case_id"),
        "company": lead["company"],
        "contact": lead["name"],
        "service": lead["service"],
        "qualification": qualification,
        "route": "high_value" if category == "high_value" else "standard",
        "summary": (
            f"{lead['company']} requested {lead['service']}. "
            f"Route: {category} (score {score})."
        ),
    }


OPERATIONS: dict[
    str,
    Callable[[dict[str, Any], WorkflowConfig], dict[str, Any]],
] = {
    "prepare": _prepare,
    "enrich": _enrich,
    "summarize": _summarize,
}


def _execute_operation(
    name: str,
    payload: dict[str, Any],
    config: WorkflowConfig,
) -> OperationResult:
    """Execute an operation and normalise its outcome into a typed result."""
    try:
        output = OPERATIONS[name](payload, config)
        return OperationResult.success(output)

    except WorkflowOperationError as exc:
        return OperationResult.failure(
            error_code=exc.code,
            error_message=exc.public_message,
        )

    except Exception as exc:
        # Do not persist raw exception text, payloads, or tracebacks.
        return OperationResult.failure(
            error_code="UNEXPECTED_OPERATION_ERROR",
            error_message=(
                f"Unexpected operation error ({exc.__class__.__name__})."
            ),
        )


def _append_event(
    path: Path,
    event: dict[str, Any] | AuditEvent,
) -> None:
    """Validate, redact, and append a structured JSON audit event."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(event, AuditEvent):
        typed_event = event
    else:
        typed_event = AuditEvent.from_dict(event)

    safe_event = redact(typed_event.to_dict())

    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps(
                safe_event,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )


def _write_run(
    fixture_dict: dict[str, Any],
    config_dict: dict[str, Any],
    run_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    """Execute operations and persist typed audit records and artifacts."""
    fixture = WorkflowFixture.from_dict(fixture_dict)
    config = WorkflowConfig.from_dict(config_dict)

    run_dir.mkdir(parents=True, exist_ok=False)

    fixture_ref = "source_fixture.json"
    config_ref = "config.json"

    # Persist a redacted fixture copy; its hash describes these exact bytes.
    fixture_sha = write_json(
        run_dir / fixture_ref,
        redact(fixture.to_dict()),
    )
    config_sha = write_json(run_dir / config_ref, config.to_dict())

    event_path = run_dir / "events.jsonl"
    operations: list[dict[str, Any]] = []
    current: dict[str, Any] = fixture.to_dict()
    previous_output_ref: str | None = None
    run_status = "success"

    for index, name in enumerate(config.operation_order, start=1):
        operation_id = f"op-{index:03d}"

        if index == 1:
            raw_input: dict[str, Any] = current
        elif name == "enrich":
            raw_input = {
                "case_id": current["case_id"],
                "lead": current["lead"],
                "simulate_failure": fixture.metadata.get(
                    "simulate_failure",
                    False,
                ),
            }
        else:
            raw_input = current

        input_ref = f"artifacts/{operation_id}-input.json"
        input_sha = write_json(
            run_dir / input_ref,
            redact(raw_input),
        )

        _append_event(
            event_path,
            {
                "run_id": run_id,
                "operation_id": operation_id,
                "event": "operation_started",
                "operation": name,
                "input_ref": input_ref,
                "timestamp": utc_now(),
            },
        )

        result = _execute_operation(name, raw_input, config)

        if result.status == "failed":
            run_status = "failed"

            operation_record = OperationRecord(
                operation_id=operation_id,
                name=name,
                status="failed",
                input_ref=input_ref,
                input_sha256=input_sha,
                output_ref=None,
                output_sha256=None,
                error_code=result.error_code,
                error_message=result.error_message,
            )
            operations.append(operation_record.to_dict())

            _append_event(
                event_path,
                {
                    "run_id": run_id,
                    "operation_id": operation_id,
                    "event": "operation_failed",
                    "operation": name,
                    "error_code": result.error_code,
                    "error_message": result.error_message,
                    "timestamp": utc_now(),
                },
            )
            break

        output = result.output
        if output is None:
            # OperationResult should prevent this state. Keep the guard here
            # so a future contract change cannot create a false success.
            raise ContractError(
                "successful operation result must contain an output object"
            )

        output_ref = f"artifacts/{operation_id}-output.json"
        output_sha = write_json(
            run_dir / output_ref,
            redact(output),
        )

        operation_record = OperationRecord(
            operation_id=operation_id,
            name=name,
            status="success",
            input_ref=input_ref,
            input_sha256=input_sha,
            output_ref=output_ref,
            output_sha256=output_sha,
        )
        operations.append(operation_record.to_dict())

        _append_event(
            event_path,
            {
                "run_id": run_id,
                "operation_id": operation_id,
                "event": "operation_succeeded",
                "operation": name,
                "output_ref": output_ref,
                "output_sha256": output_sha,
                "timestamp": utc_now(),
            },
        )

        # Pass the original, unredacted result to the next operation.
        current = output
        previous_output_ref = output_ref

    manifest_data = {
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

    # Validate the complete manifest before persisting it.
    manifest_model = AuditManifest.from_dict(manifest_data)
    manifest = manifest_model.to_dict()
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
    """Execute a validated fixture-driven workflow."""
    fixture_path = Path(fixture_path)
    run_dir = Path(run_dir)

    if run_id is None:
        run_id = f"run-{uuid.uuid4().hex[:12]}"

    if not RUN_ID_RE.fullmatch(run_id):
        raise ContractError(
            "run_id must be 1-64 safe alphanumeric, dot, underscore or hyphen characters"
        )

    if run_dir.exists():
        raise RunAlreadyExistsError(
            f"Run directory already exists; refusing to overwrite: {run_dir}"
        )

    fixture_dict = read_json(fixture_path)
    WorkflowFixture.from_dict(fixture_dict)

    config_dict = read_json(config_path) if config_path else DEFAULT_CONFIG
    WorkflowConfig.from_dict(config_dict)

    return _write_run(fixture_dict, config_dict, run_dir, run_id)


def verify_integrity(run_dir: Path) -> list[str]:
    """Validate the audit manifest and hashes of all referenced artifacts."""
    run_dir = Path(run_dir)
    manifest_path = run_dir / "audit.json"

    if not manifest_path.is_file():
        return ["AUDIT_MANIFEST_MISSING"]

    try:
        raw_manifest = read_json(manifest_path)
        manifest_model = AuditManifest.from_dict(raw_manifest)
        manifest = manifest_model.to_dict()
    except ContractError:
        return ["AUDIT_MANIFEST_INVALID"]

    failures: list[str] = []

    refs: list[tuple[str, str | None]] = [
        (
            manifest["config_ref"],
            manifest["config_sha256"],
        ),
        (
            manifest["source_fixture_ref"],
            manifest["source_fixture_sha256"],
        ),
    ]

    for record in manifest["operations"]:
        refs.append(
            (
                record["input_ref"],
                record["input_sha256"],
            )
        )

        if record["output_ref"] is not None:
            refs.append(
                (
                    record["output_ref"],
                    record["output_sha256"],
                )
            )

    for relative_ref, expected_hash in refs:
        try:
            path = _contained_path(run_dir, relative_ref)
        except ContractError:
            failures.append(
                f"INVALID_ARTIFACT_REFERENCE:{relative_ref}"
            )
            continue

        if not path.is_file():
            failures.append(f"ARTIFACT_MISSING:{relative_ref}")
            continue

        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            failures.append(
                f"ARTIFACT_HASH_MISMATCH:{relative_ref}"
            )

    return failures


def replay_workflow(run_dir: Path) -> ReplayResult:
    """Replay saved local data, verify integrity, and compare outputs."""
    run_dir = Path(run_dir)

    integrity_failures = verify_integrity(run_dir)
    if integrity_failures:
        return ReplayResult(
            run_id=run_dir.name,
            status="integrity_failed",
            operations_replayed=0,
            external_calls=0,
            differences=tuple(integrity_failures),
        )

    try:
        manifest = AuditManifest.from_dict(
            read_json(run_dir / "audit.json")
        ).to_dict()

        fixture_value = read_json(
            _contained_path(
                run_dir,
                manifest["source_fixture_ref"],
            )
        )
        config_value = read_json(
            _contained_path(
                run_dir,
                manifest["config_ref"],
            )
        )

        fixture = WorkflowFixture.from_dict(fixture_value)
        config = WorkflowConfig.from_dict(config_value)

    except (ContractError, KeyError, TypeError):
        return ReplayResult(
            run_id=run_dir.name,
            status="invalid",
            operations_replayed=0,
            external_calls=0,
            differences=("INVALID_REPLAY_INPUT",),
        )

    if manifest["config_version"] != config.config_version:
        return ReplayResult(
            run_id=manifest["run_id"],
            status="invalid",
            operations_replayed=0,
            external_calls=0,
            differences=("CONFIG_VERSION_MISMATCH",),
        )

    records = manifest["operations"]
    expected_order = list(config.operation_order)

    # A valid replay can contain at most one record per configured operation.
    if len(records) > len(expected_order):
        return ReplayResult(
            run_id=manifest["run_id"],
            status="invalid",
            operations_replayed=0,
            external_calls=0,
            differences=("EXTRA_OPERATION_RECORDS",),
        )

    recorded_names = [record["name"] for record in records]
    expected_prefix = expected_order[:len(records)]

    if recorded_names != expected_prefix:
        return ReplayResult(
            run_id=manifest["run_id"],
            status="mismatch",
            operations_replayed=0,
            external_calls=0,
            differences=("OPERATION_ORDER_MISMATCH",),
        )

    if (
        manifest["status"] == "success"
        and len(records) != len(expected_order)
    ):
        return ReplayResult(
            run_id=manifest["run_id"],
            status="mismatch",
            operations_replayed=0,
            external_calls=0,
            differences=("INCOMPLETE_SUCCESSFUL_REPLAY",),
        )

    current: dict[str, Any] = fixture.to_dict()
    replay_count = 0
    differences: list[str] = []

    for index, name in enumerate(config.operation_order):
        if index >= len(records):
            differences.append(f"MISSING_OPERATION_RECORD:{name}")
            break

        record = records[index]

        if index == 0:
            operation_input = current
        elif name == "enrich":
            operation_input = {
                "case_id": current["case_id"],
                "lead": current["lead"],
                "simulate_failure": fixture.metadata.get(
                    "simulate_failure",
                    False,
                ),
            }
        else:
            operation_input = current

        result = _execute_operation(name, operation_input, config)
        replay_count += 1

        if result.status == "failed":
            if (
                record["status"] != "failed"
                or record["error_code"] != result.error_code
                or record["error_message"] != result.error_message
            ):
                differences.append(f"FAILURE_REPLAY_MISMATCH:{name}")
            break

        if record["status"] != "success":
            differences.append(
                f"EXPECTED_FAILURE_NOT_REPRODUCED:{name}"
            )
            break

        if record["output_ref"] is None:
            differences.append(
                f"OUTPUT_REFERENCE_MISSING:{name}"
            )
            break

        replay_output = result.output
        if replay_output is None:
            differences.append(
                f"REPLAY_OUTPUT_MISSING:{name}"
            )
            break

        try:
            saved_output = read_json(
                _contained_path(run_dir, record["output_ref"])
            )
        except ContractError:
            differences.append(
                f"SAVED_OUTPUT_UNREADABLE:{name}"
            )
            break

        # The saved output is redacted; compare the redacted replay output.
        if redact(replay_output) != saved_output:
            differences.append(f"OUTPUT_MISMATCH:{name}")
            break

        # Pass the original, unredacted result to the next operation.
        current = replay_output

    if not differences:
        if (
            manifest["status"] == "success"
            and replay_count != len(config.operation_order)
        ):
            differences.append("INCOMPLETE_SUCCESSFUL_REPLAY")

        elif (
            manifest["status"] == "failed"
            and (
                not records
                or records[-1]["status"] != "failed"
            )
        ):
            differences.append("FAILED_RUN_NOT_REPRODUCED")

    return ReplayResult(
        run_id=manifest["run_id"],
        status="match" if not differences else "mismatch",
        operations_replayed=replay_count,
        external_calls=0,
        differences=tuple(differences),
    )


def create_demo_fixture_copy(source: Path, destination: Path) -> None:
    """Copy a fixture unchanged; intended only for demonstration utilities."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)