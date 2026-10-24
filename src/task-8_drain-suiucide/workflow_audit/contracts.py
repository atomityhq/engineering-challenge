"""Typed, dependency-free contracts and validation for audit/replay."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal


OperationStatus = Literal["success", "failed"]

AuditEventType = Literal[
    "operation_started",
    "operation_succeeded",
    "operation_failed",
    "run_completed",
]


class ContractError(ValueError):
    """Raised when an input or saved record violates its contract."""


def _is_non_empty_string(value: Any) -> bool:
    """Return whether value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def _is_sha256(value: Any) -> bool:
    """Return whether value is a 64-character hexadecimal SHA-256 digest."""
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdefABCDEF" for char in value)
    )


def _is_json_value(
    value: Any,
    ancestors: set[int] | None = None,
) -> bool:
    """Return whether a value contains only strict, finite JSON values."""
    if value is None or isinstance(value, (str, bool, int)):
        return True

    if isinstance(value, float):
        return math.isfinite(value)

    active_ancestors = ancestors if ancestors is not None else set()

    if isinstance(value, list):
        identity = id(value)
        if identity in active_ancestors:
            return False

        active_ancestors.add(identity)
        try:
            return all(
                _is_json_value(item, active_ancestors)
                for item in value
            )
        finally:
            active_ancestors.remove(identity)

    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            return False

        identity = id(value)
        if identity in active_ancestors:
            return False

        active_ancestors.add(identity)
        try:
            return all(
                _is_json_value(item, active_ancestors)
                for item in value.values()
            )
        finally:
            active_ancestors.remove(identity)

    return False


@dataclass(frozen=True)
class Lead:
    name: str
    email: str
    company: str
    employees: int
    service: str
    message: str

    @classmethod
    def from_dict(cls, value: Any) -> "Lead":
        if not isinstance(value, dict):
            raise ContractError("lead must be a JSON object")

        required_strings = (
            "name",
            "email",
            "company",
            "service",
            "message",
        )

        for field in required_strings:
            if not _is_non_empty_string(value.get(field)):
                raise ContractError(
                    f"lead.{field} must be a non-empty string"
                )

        employees = value.get("employees")
        if (
            isinstance(employees, bool)
            or not isinstance(employees, int)
            or employees < 0
        ):
            raise ContractError(
                "lead.employees must be a non-negative integer"
            )

        return cls(
            name=value["name"].strip(),
            email=value["email"].strip().lower(),
            company=value["company"].strip(),
            employees=employees,
            service=value["service"].strip(),
            message=value["message"].strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "company": self.company,
            "employees": self.employees,
            "service": self.service,
            "message": self.message,
        }


@dataclass(frozen=True)
class WorkflowFixture:
    schema_version: str
    case_id: str
    lead: Lead
    metadata: dict[str, Any]

    @classmethod
    def from_dict(cls, value: Any) -> "WorkflowFixture":
        if not isinstance(value, dict):
            raise ContractError("fixture must be a JSON object")

        if value.get("schema_version") != "1.0":
            raise ContractError("schema_version must be '1.0'")

        case_id = value.get("case_id")
        if not _is_non_empty_string(case_id):
            raise ContractError("case_id must be a non-empty string")

        metadata = value.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ContractError("metadata must be a JSON object")

        simulate_failure = metadata.get("simulate_failure", False)
        if not isinstance(simulate_failure, bool):
            raise ContractError(
                "metadata.simulate_failure must be a boolean"
            )

        debug_note = metadata.get("debug_note", "")
        if not isinstance(debug_note, str):
            raise ContractError(
                "metadata.debug_note must be a string"
            )

        return cls(
            schema_version="1.0",
            case_id=case_id.strip(),
            lead=Lead.from_dict(value.get("lead")),
            metadata=dict(metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "lead": self.lead.to_dict(),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class WorkflowConfig:
    schema_version: str
    config_version: str
    high_value_min_employees: int
    operation_order: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "WorkflowConfig":
        if not isinstance(value, dict):
            raise ContractError("config must be a JSON object")

        if value.get("schema_version") != "1.0":
            raise ContractError("config.schema_version must be '1.0'")

        version = value.get("config_version")
        if not _is_non_empty_string(version):
            raise ContractError(
                "config.config_version must be a non-empty string"
            )

        threshold = value.get("high_value_min_employees")
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, int)
            or threshold < 1
        ):
            raise ContractError(
                "config.high_value_min_employees must be a positive integer"
            )

        order = value.get("operation_order")
        expected = ["prepare", "enrich", "summarize"]
        if order != expected:
            raise ContractError(
                f"config.operation_order must equal {expected!r}"
            )

        return cls(
            schema_version="1.0",
            config_version=version.strip(),
            high_value_min_employees=threshold,
            operation_order=tuple(order),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "config_version": self.config_version,
            "high_value_min_employees": self.high_value_min_employees,
            "operation_order": list(self.operation_order),
        }


@dataclass(frozen=True)
class OperationRecord:
    """Persisted audit record for one workflow operation."""

    operation_id: str
    name: str
    status: OperationStatus
    input_ref: str
    input_sha256: str
    output_ref: str | None
    output_sha256: str | None
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def from_dict(cls, value: Any) -> "OperationRecord":
        if not isinstance(value, dict):
            raise ContractError(
                "operation record must be a JSON object"
            )

        allowed_fields = {
            "operation_id",
            "name",
            "status",
            "input_ref",
            "input_sha256",
            "output_ref",
            "output_sha256",
            "error_code",
            "error_message",
        }
        unknown_fields = set(value) - allowed_fields
        if unknown_fields:
            raise ContractError(
                "operation record contains unknown fields: "
                f"{sorted(unknown_fields)!r}"
            )

        for field in ("operation_id", "name", "input_ref"):
            if not _is_non_empty_string(value.get(field)):
                raise ContractError(
                    f"operation record {field} must be a non-empty string"
                )

        status = value.get("status")
        if status not in ("success", "failed"):
            raise ContractError(
                "operation record status must be 'success' or 'failed'"
            )

        input_sha256 = value.get("input_sha256")
        if not _is_sha256(input_sha256):
            raise ContractError(
                "operation record input_sha256 must be a SHA-256 digest"
            )

        output_ref = value.get("output_ref")
        output_sha256 = value.get("output_sha256")
        error_code = value.get("error_code")
        error_message = value.get("error_message")

        if status == "success":
            if not _is_non_empty_string(output_ref):
                raise ContractError(
                    "successful operation requires output_ref"
                )

            if not _is_sha256(output_sha256):
                raise ContractError(
                    "successful operation requires a valid output_sha256"
                )

            if error_code is not None or error_message is not None:
                raise ContractError(
                    "successful operation must not contain failure details"
                )

        else:
            if output_ref is not None or output_sha256 is not None:
                raise ContractError(
                    "failed operation must not contain output artifacts"
                )

            if not _is_non_empty_string(error_code):
                raise ContractError(
                    "failed operation requires error_code"
                )

            if not _is_non_empty_string(error_message):
                raise ContractError(
                    "failed operation requires error_message"
                )

        return cls(
            operation_id=value["operation_id"],
            name=value["name"],
            status=status,
            input_ref=value["input_ref"],
            input_sha256=input_sha256,
            output_ref=output_ref,
            output_sha256=output_sha256,
            error_code=error_code,
            error_message=error_message,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "name": self.name,
            "status": self.status,
            "input_ref": self.input_ref,
            "input_sha256": self.input_sha256,
            "output_ref": self.output_ref,
            "output_sha256": self.output_sha256,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class OperationResult:
    """Typed result envelope for a successful or failed operation."""

    status: OperationStatus
    output: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Prevent invalid states, including direct dataclass construction."""
        if self.status == "success":
            if not isinstance(self.output, dict) or not _is_json_value(
                self.output
            ):
                raise ContractError(
                    "successful operation result requires a valid JSON object"
                )

            if self.error_code is not None or self.error_message is not None:
                raise ContractError(
                    "successful operation result must not contain failure details"
                )

        elif self.status == "failed":
            if self.output is not None:
                raise ContractError(
                    "failed operation result must not contain output"
                )

            if not _is_non_empty_string(self.error_code):
                raise ContractError(
                    "failed operation result requires a non-empty error_code"
                )

            if not _is_non_empty_string(self.error_message):
                raise ContractError(
                    "failed operation result requires a non-empty error_message"
                )

        else:
            raise ContractError(
                "operation result status must be 'success' or 'failed'"
            )

    @classmethod
    def success(cls, output: Any) -> "OperationResult":
        if not isinstance(output, dict) or not _is_json_value(output):
            raise ContractError(
                "successful operation result requires a valid JSON object"
            )

        return cls(
            status="success",
            output=dict(output),
        )

    @classmethod
    def failure(
        cls,
        error_code: str,
        error_message: str,
    ) -> "OperationResult":
        if not _is_non_empty_string(error_code):
            raise ContractError(
                "failed operation result requires a non-empty error_code"
            )

        if not _is_non_empty_string(error_message):
            raise ContractError(
                "failed operation result requires a non-empty error_message"
            )

        return cls(
            status="failed",
            error_code=error_code,
            error_message=error_message,
        )

    @classmethod
    def from_dict(cls, value: Any) -> "OperationResult":
        if not isinstance(value, dict):
            raise ContractError(
                "operation result must be a JSON object"
            )

        if not all(isinstance(key, str) for key in value):
            raise ContractError(
                "operation result keys must be strings"
            )

        allowed_fields = {
            "status",
            "output",
            "error_code",
            "error_message",
        }
        unknown_fields = set(value) - allowed_fields
        if unknown_fields:
            raise ContractError(
                "operation result contains unknown fields: "
                f"{sorted(unknown_fields)!r}"
            )

        status = value.get("status")

        if status == "success":
            if "error_code" in value or "error_message" in value:
                raise ContractError(
                    "successful operation result must omit failure fields"
                )

            output = value.get("output")
            if not isinstance(output, dict):
                raise ContractError(
                    "successful operation result requires object output"
                )

            return cls.success(output)

        if status == "failed":
            if "output" in value:
                raise ContractError(
                    "failed operation result must omit the output field"
                )

            error_code = value.get("error_code")
            error_message = value.get("error_message")

            if not _is_non_empty_string(error_code):
                raise ContractError(
                    "failed operation result requires a non-empty error_code"
                )

            if not _is_non_empty_string(error_message):
                raise ContractError(
                    "failed operation result requires a non-empty error_message"
                )

            return cls.failure(error_code, error_message)

        raise ContractError(
            "operation result status must be 'success' or 'failed'"
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status,
        }

        if self.output is not None:
            result["output"] = self.output

        if self.error_code is not None:
            result["error_code"] = self.error_code

        if self.error_message is not None:
            result["error_message"] = self.error_message

        return result


@dataclass(frozen=True)
class AuditManifest:
    """Typed contract for the persisted audit manifest."""

    schema_version: str
    run_id: str
    case_id: str
    status: Literal["success", "failed"]
    config_version: str
    config_ref: str
    config_sha256: str
    source_fixture_ref: str
    source_fixture_sha256: str
    final_output_ref: str | None
    operations: tuple[OperationRecord, ...]
    created_at: str
    redaction_policy: str

    @classmethod
    def from_dict(cls, value: Any) -> "AuditManifest":
        if not isinstance(value, dict):
            raise ContractError(
                "audit manifest must be a JSON object"
            )

        allowed_fields = {
            "schema_version",
            "run_id",
            "case_id",
            "status",
            "config_version",
            "config_ref",
            "config_sha256",
            "source_fixture_ref",
            "source_fixture_sha256",
            "final_output_ref",
            "operations",
            "created_at",
            "redaction_policy",
        }
        unknown_fields = set(value) - allowed_fields
        if unknown_fields:
            raise ContractError(
                "audit manifest contains unknown fields: "
                f"{sorted(unknown_fields)!r}"
            )

        if value.get("schema_version") != "1.0":
            raise ContractError(
                "audit manifest schema_version must be '1.0'"
            )

        string_fields = (
            "run_id",
            "case_id",
            "config_version",
            "config_ref",
            "source_fixture_ref",
            "created_at",
            "redaction_policy",
        )
        for field in string_fields:
            if not _is_non_empty_string(value.get(field)):
                raise ContractError(
                    f"audit manifest {field} must be a non-empty string"
                )

        status = value.get("status")
        if status not in ("success", "failed"):
            raise ContractError(
                "audit manifest status must be 'success' or 'failed'"
            )

        for field in ("config_sha256", "source_fixture_sha256"):
            if not _is_sha256(value.get(field)):
                raise ContractError(
                    f"audit manifest {field} must be a SHA-256 digest"
                )

        final_output_ref = value.get("final_output_ref")
        if final_output_ref is not None and not _is_non_empty_string(
            final_output_ref
        ):
            raise ContractError(
                "audit manifest final_output_ref must be a non-empty string or null"
            )

        raw_operations = value.get("operations")
        if not isinstance(raw_operations, list) or not raw_operations:
            raise ContractError(
                "audit manifest operations must be a non-empty list"
            )

        operations = tuple(
            OperationRecord.from_dict(item)
            for item in raw_operations
        )

        operation_ids = [item.operation_id for item in operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ContractError(
                "audit manifest operation IDs must be unique"
            )

        failed_indexes = [
            index
            for index, item in enumerate(operations)
            if item.status == "failed"
        ]

        if status == "success":
            if failed_indexes:
                raise ContractError(
                    "successful audit manifest cannot contain failed operations"
                )

            if final_output_ref != operations[-1].output_ref:
                raise ContractError(
                    "successful audit manifest final output must reference the last operation"
                )

        else:
            if not failed_indexes:
                raise ContractError(
                    "failed audit manifest must contain a failed operation"
                )

            if failed_indexes != [len(operations) - 1]:
                raise ContractError(
                    "failed audit manifest must end with exactly one failed operation"
                )

            last_successful_output = next(
                (
                    item.output_ref
                    for item in reversed(operations)
                    if item.status == "success"
                ),
                None,
            )

            if final_output_ref != last_successful_output:
                raise ContractError(
                    "failed audit manifest final output must reference the last successful output"
                )

        return cls(
            schema_version="1.0",
            run_id=value["run_id"],
            case_id=value["case_id"],
            status=status,
            config_version=value["config_version"],
            config_ref=value["config_ref"],
            config_sha256=value["config_sha256"],
            source_fixture_ref=value["source_fixture_ref"],
            source_fixture_sha256=value["source_fixture_sha256"],
            final_output_ref=final_output_ref,
            operations=operations,
            created_at=value["created_at"],
            redaction_policy=value["redaction_policy"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "run_id": self.run_id,
            "case_id": self.case_id,
            "status": self.status,
            "config_version": self.config_version,
            "config_ref": self.config_ref,
            "config_sha256": self.config_sha256,
            "source_fixture_ref": self.source_fixture_ref,
            "source_fixture_sha256": self.source_fixture_sha256,
            "final_output_ref": self.final_output_ref,
            "operations": [
                operation.to_dict() for operation in self.operations
            ],
            "created_at": self.created_at,
            "redaction_policy": self.redaction_policy,
        }


@dataclass(frozen=True)
class ReplayResult:
    run_id: str
    status: Literal[
        "match",
        "mismatch",
        "integrity_failed",
        "invalid",
    ]
    operations_replayed: int
    external_calls: int
    differences: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "operations_replayed": self.operations_replayed,
            "external_calls": self.external_calls,
            "differences": list(self.differences),
        }


@dataclass(frozen=True)
class AuditEvent:
    """Typed contract for a persisted workflow audit event."""

    run_id: str
    event: AuditEventType
    timestamp: str
    operation_id: str | None = None
    operation: str | None = None
    input_ref: str | None = None
    output_ref: str | None = None
    output_sha256: str | None = None
    status: Literal["success", "failed"] | None = None
    operation_count: int | None = None
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def from_dict(cls, value: Any) -> "AuditEvent":
        if not isinstance(value, dict):
            raise ContractError(
                "audit event must be a JSON object"
            )

        allowed_fields = {
            "run_id",
            "event",
            "timestamp",
            "operation_id",
            "operation",
            "input_ref",
            "output_ref",
            "output_sha256",
            "status",
            "operation_count",
            "error_code",
            "error_message",
        }
        unknown_fields = set(value) - allowed_fields
        if unknown_fields:
            raise ContractError(
                "audit event contains unknown fields: "
                f"{sorted(unknown_fields)!r}"
            )

        for field in ("run_id", "event", "timestamp"):
            if not _is_non_empty_string(value.get(field)):
                raise ContractError(
                    f"audit event {field} must be a non-empty string"
                )

        event_type = value["event"]
        if event_type not in (
            "operation_started",
            "operation_succeeded",
            "operation_failed",
            "run_completed",
        ):
            raise ContractError(
                "audit event has an unsupported event type"
            )

        optional_string_fields = (
            "operation_id",
            "operation",
            "input_ref",
            "output_ref",
            "output_sha256",
            "error_code",
            "error_message",
        )
        for field in optional_string_fields:
            item = value.get(field)
            if item is not None and not _is_non_empty_string(item):
                raise ContractError(
                    f"audit event {field} must be a non-empty string when provided"
                )

        event_requirements = {
            "operation_started": (
                "operation_id",
                "operation",
                "input_ref",
            ),
            "operation_succeeded": (
                "operation_id",
                "operation",
                "output_ref",
                "output_sha256",
            ),
            "operation_failed": (
                "operation_id",
                "operation",
                "error_code",
                "error_message",
            ),
        }

        for field in event_requirements.get(event_type, ()):
            if value.get(field) is None:
                raise ContractError(
                    f"{event_type} audit event requires {field}"
                )

        output_sha256 = value.get("output_sha256")
        if output_sha256 is not None and not _is_sha256(output_sha256):
            raise ContractError(
                "audit event output_sha256 must be a SHA-256 digest"
            )

        status = value.get("status")
        operation_count = value.get("operation_count")

        if event_type == "run_completed":
            if status not in ("success", "failed"):
                raise ContractError(
                    "run_completed status must be 'success' or 'failed'"
                )

            if (
                isinstance(operation_count, bool)
                or not isinstance(operation_count, int)
                or operation_count < 0
            ):
                raise ContractError(
                    "run_completed operation_count must be a non-negative integer"
                )

        return cls(
            run_id=value["run_id"],
            event=event_type,
            timestamp=value["timestamp"],
            operation_id=value.get("operation_id"),
            operation=value.get("operation"),
            input_ref=value.get("input_ref"),
            output_ref=value.get("output_ref"),
            output_sha256=output_sha256,
            status=status,
            operation_count=operation_count,
            error_code=value.get("error_code"),
            error_message=value.get("error_message"),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "run_id": self.run_id,
            "event": self.event,
            "timestamp": self.timestamp,
        }

        optional_fields = {
            "operation_id": self.operation_id,
            "operation": self.operation,
            "input_ref": self.input_ref,
            "output_ref": self.output_ref,
            "output_sha256": self.output_sha256,
            "status": self.status,
            "operation_count": self.operation_count,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }

        result.update(
            {
                key: item
                for key, item in optional_fields.items()
                if item is not None
            }
        )
        return result