"""Unit tests for the typed OperationResult contract."""

from __future__ import annotations

import unittest

from workflow_audit.contracts import ContractError, OperationResult


class OperationResultContractTests(unittest.TestCase):
    """Verify valid operation results and reject malformed states."""

    def test_success_result_round_trips(self) -> None:
        result = OperationResult.success(
            {
                "case_id": "case-001",
                "score": 85,
            }
        )

        expected = {
            "status": "success",
            "output": {
                "case_id": "case-001",
                "score": 85,
            },
        }

        self.assertEqual(result.to_dict(), expected)
        self.assertEqual(
            OperationResult.from_dict(result.to_dict()),
            result,
        )

    def test_failure_result_round_trips(self) -> None:
        result = OperationResult.failure(
            error_code="SYNTHETIC_FAILURE",
            error_message="Synthetic failure requested by fixture.",
        )

        expected = {
            "status": "failed",
            "error_code": "SYNTHETIC_FAILURE",
            "error_message": "Synthetic failure requested by fixture.",
        }

        self.assertEqual(result.to_dict(), expected)
        self.assertEqual(
            OperationResult.from_dict(result.to_dict()),
            result,
        )

    def test_success_factory_rejects_non_object_output(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.success(["not", "a", "JSON object"])

    def test_success_contract_rejects_non_object_output(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.from_dict(
                {
                    "status": "success",
                    "output": ["not", "a", "JSON object"],
                }
            )

    def test_failure_contract_rejects_output(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.from_dict(
                {
                    "status": "failed",
                    "output": {"unexpected": True},
                    "error_code": "SYNTHETIC_FAILURE",
                    "error_message": "Operation failed.",
                }
            )

    def test_failure_contract_rejects_null_output(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.from_dict(
                {
                    "status": "failed",
                    "output": None,
                    "error_code": "SYNTHETIC_FAILURE",
                    "error_message": "Operation failed.",
                }
            )

    def test_failure_contract_requires_error_code(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.from_dict(
                {
                    "status": "failed",
                    "error_message": "Operation failed.",
                }
            )

    def test_failure_contract_requires_error_message(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.from_dict(
                {
                    "status": "failed",
                    "error_code": "SYNTHETIC_FAILURE",
                }
            )

    def test_success_contract_rejects_explicit_null_failure_field(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.from_dict(
                {
                    "status": "success",
                    "output": {"score": 85},
                    "error_code": None,
                }
            )

    def test_contract_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.from_dict(
                {
                    "status": "success",
                    "output": {"score": 85},
                    "unexpected_field": "must be rejected",
                }
            )

    def test_success_factory_rejects_non_json_objects(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.success(
                {"bad_value": object()}
            )

    def test_success_factory_rejects_non_string_keys(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.success(
                {1: "JSON object keys must be strings"}
            )

    def test_success_factory_rejects_non_finite_numbers(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult.success(
                {"score": float("nan")}
            )

    def test_success_factory_rejects_circular_data(self) -> None:
        circular: dict[str, object] = {}
        circular["self"] = circular

        with self.assertRaises(ContractError):
            OperationResult.success(circular)

    def test_direct_constructor_rejects_invalid_success_state(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult(
                status="success",
                output=None,
            )

    def test_direct_constructor_rejects_invalid_failure_state(self) -> None:
        with self.assertRaises(ContractError):
            OperationResult(
                status="failed",
                output={"unexpected": True},
                error_code="SYNTHETIC_FAILURE",
                error_message="Operation failed.",
            )


if __name__ == "__main__":
    unittest.main()