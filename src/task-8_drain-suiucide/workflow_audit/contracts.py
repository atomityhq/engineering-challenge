"""Typed, dependency-free contracts and validation for the audit/replay demo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

OperationStatus = Literal["success", "failed"]


class ContractError(ValueError):
    """Raised when an input fixture or saved manifest violates its contract."""


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
        required_strings = ("name", "email", "company", "service", "message")
        for field in required_strings:
            if not isinstance(value.get(field), str) or not value[field].strip():
                raise ContractError(f"lead.{field} must be a non-empty string")
        employees = value.get("employees")
        if isinstance(employees, bool) or not isinstance(employees, int) or employees < 0:
            raise ContractError("lead.employees must be a non-negative integer")
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
        if not isinstance(case_id, str) or not case_id.strip():
            raise ContractError("case_id must be a non-empty string")
        metadata = value.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ContractError("metadata must be a JSON object")
        simulate_failure = metadata.get("simulate_failure", False)
        if not isinstance(simulate_failure, bool):
            raise ContractError("metadata.simulate_failure must be a boolean")
        debug_note = metadata.get("debug_note", "")
        if not isinstance(debug_note, str):
            raise ContractError("metadata.debug_note must be a string")
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
        if not isinstance(version, str) or not version.strip():
            raise ContractError("config.config_version must be a non-empty string")
        threshold = value.get("high_value_min_employees")
        if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
            raise ContractError("config.high_value_min_employees must be a positive integer")
        order = value.get("operation_order")
        expected = ["prepare", "enrich", "summarize"]
        if order != expected:
            raise ContractError(f"config.operation_order must equal {expected!r}")
        return cls("1.0", version.strip(), threshold, tuple(order))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "config_version": self.config_version,
            "high_value_min_employees": self.high_value_min_employees,
            "operation_order": list(self.operation_order),
        }


@dataclass(frozen=True)
class OperationRecord:
    operation_id: str
    name: str
    status: OperationStatus
    input_ref: str
    input_sha256: str
    output_ref: str | None
    output_sha256: str | None
    error_code: str | None = None
    error_message: str | None = None

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
class ReplayResult:
    run_id: str
    status: Literal["match", "mismatch", "integrity_failed", "invalid"]
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
