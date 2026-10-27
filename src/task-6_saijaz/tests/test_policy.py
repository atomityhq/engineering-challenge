"""Numerical and boundary checks for uncalibrated policy preferences."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from g2.errors import ValidationError
from g2.policy import (
    AUTHORITY_KEYS, CRITERIA, POLICY_FIELDS, WEIGHT_SUM_TOLERANCE,
    CriterionValues, load_policy, validate_policy,
)


def sample_policy() -> dict[str, object]:
    """Build an independent valid policy without file I/O."""
    return {
        "schema_version": "1.0", "policy_version": "demo-v1",
        "weights_version": "weights-v1", "calibration_status": "uncalibrated",
        "rationale": "Declared prototype preference; not calibrated.",
        "weights": dict(zip(CRITERIA, (0.45, 0.30, 0.25))),
        "floors": dict(zip(CRITERIA, (1.0, 0.5, 1.0))),
        "threshold": 0.8,
        "authority": dict(zip(AUTHORITY_KEYS, (1.0, 0.75, 0.5, 0.0, None))),
    }


class PolicyTests(unittest.TestCase):
    """Exercise strict policy parsing, construction, and safe I/O errors."""

    def test_valid_policy_preserves_inputs_and_precision(self) -> None:
        raw = sample_policy()
        original = deepcopy(raw)
        policy = validate_policy(raw)
        self.assertEqual(policy.weights.values(), (0.45, 0.30, 0.25))
        self.assertEqual(policy.floors.values(), (1.0, 0.5, 1.0))
        self.assertEqual(policy.threshold, 0.8)
        self.assertIsNone(policy.authority.unknown)
        self.assertEqual(raw, original)
        with self.assertRaises(FrozenInstanceError):
            setattr(policy.weights, "source_authority", 0.9)
        with self.assertRaises(FrozenInstanceError):
            setattr(policy, "threshold", 0.0)

    def test_required_fields_and_exact_criterion_keys(self) -> None:
        for key in POLICY_FIELDS:
            raw = sample_policy()
            del raw[key]
            with self.assertRaises(ValidationError) as caught:
                validate_policy(raw)
            self.assertEqual(caught.exception.issue.path, f"$.{key}")
        for section, keys in (("weights", CRITERIA), ("floors", CRITERIA), ("authority", AUTHORITY_KEYS)):
            for key in keys:
                raw = sample_policy()
                del raw[section][key]
                with self.assertRaises(ValidationError) as caught:
                    validate_policy(raw)
                self.assertEqual(caught.exception.issue.path, f"$.{section}.{key}")
            raw = sample_policy()
            raw[section]["extra"] = 0
            with self.assertRaises(ValidationError) as caught:
                validate_policy(raw)
            self.assertEqual(caught.exception.issue.code, "UNKNOWN_FIELD")

    def test_freshness_override_and_tolerance_override_rejected(self) -> None:
        for field in ("news_max_event_age_days", "as_of", "demo_policy", "weight_sum_tolerance"):
            raw = sample_policy()
            raw[field] = 0
            with self.assertRaises(ValidationError) as caught:
                validate_policy(raw)
            self.assertEqual(caught.exception.issue.code, "UNKNOWN_FIELD")

    def test_invalid_weight_values(self) -> None:
        for key in CRITERIA:
            for value in (-0.1, True, False, "0.45", None, math.nan, math.inf, -math.inf, 10 ** 1000):
                with self.subTest(key=key, value_type=type(value)):
                    raw = sample_policy()
                    raw["weights"][key] = value
                    with self.assertRaises(ValidationError) as caught:
                        validate_policy(raw)
                    self.assertEqual(caught.exception.issue.path, f"$.weights.{key}")

    def test_invalid_sums_and_overflow(self) -> None:
        for values in ((0, 0, 0), (0.45, 0.30, 0.30), (1e308, 1e308, 0)):
            raw = sample_policy()
            raw["weights"] = dict(zip(CRITERIA, values))
            with self.assertRaises(ValidationError) as caught:
                validate_policy(raw)
            self.assertEqual(caught.exception.issue.code, "INVALID_WEIGHT_SUM")

    def test_absolute_tolerance_boundary_without_normalization(self) -> None:
        limit = 1.0 + WEIGHT_SUM_TOLERANCE
        inside = math.nextafter(limit, 1.0)
        outside = math.nextafter(limit, math.inf)
        self.assertLessEqual(abs(inside - 1), WEIGHT_SUM_TOLERANCE)
        self.assertGreater(abs(outside - 1), WEIGHT_SUM_TOLERANCE)
        raw = sample_policy()
        raw["weights"] = dict(zip(CRITERIA, (inside, 0, 0)))
        policy = validate_policy(raw)
        self.assertEqual(policy.weights.evidence_support, inside)
        raw["weights"]["evidence_support"] = outside
        with self.assertRaises(ValidationError):
            validate_policy(raw)
        lower_limit = 1.0 - WEIGHT_SUM_TOLERANCE
        raw["weights"]["evidence_support"] = math.nextafter(lower_limit, 1.0)
        validate_policy(raw)
        raw["weights"]["evidence_support"] = math.nextafter(lower_limit, 0.0)
        with self.assertRaises(ValidationError):
            validate_policy(raw)

    def test_floors_threshold_and_authority_unit_interval(self) -> None:
        for section, keys in (("floors", CRITERIA), ("authority", AUTHORITY_KEYS[:-1])):
            for key in keys:
                for value in (-0.01, 1.01, True, "1", None, math.nan, math.inf):
                    raw = sample_policy()
                    raw[section][key] = value
                    with self.assertRaises(ValidationError):
                        validate_policy(raw)
        for value in (-0.01, 1.01, True, "1", None, math.nan, math.inf):
            raw = sample_policy()
            raw["threshold"] = value
            with self.assertRaises(ValidationError):
                validate_policy(raw)
        for boundary in (0, 1):
            raw = sample_policy()
            raw["threshold"] = boundary
            raw["floors"] = dict.fromkeys(CRITERIA, boundary)
            self.assertEqual(validate_policy(raw).threshold, boundary)

    def test_unknown_authority_stays_null(self) -> None:
        for value in (0, 0.5, "unknown", False):
            raw = sample_policy()
            raw["authority"]["unknown"] = value
            with self.assertRaises(ValidationError) as caught:
                validate_policy(raw)
            self.assertEqual(caught.exception.issue.code, "INVALID_AUTHORITY_UNKNOWN")

    def test_schema_versions_and_calibration_claims(self) -> None:
        for field, values in {
            "schema_version": ("2.0", 1, None),
            "calibration_status": ("calibrated", "unknown", None),
            "policy_version": ("", 1), "weights_version": ("", None),
            "rationale": ("", " \n", 1),
        }.items():
            for value in values:
                raw = sample_policy()
                raw[field] = value
                with self.assertRaises(ValidationError):
                    validate_policy(raw)

    def test_direct_construction_invariants(self) -> None:
        policy = validate_policy(sample_policy())
        for field, value in (
            ("threshold", True), ("weights", {}), ("floors", {}),
            ("authority", {}), ("calibration_status", "calibrated"),
            ("weights", CriterionValues(0.2, 0.2, 0.2)),
            ("floors", CriterionValues(1.1, 0.5, 1.0)),
        ):
            with self.assertRaises(ValidationError):
                replace(policy, **{field: value})
        with self.assertRaises(ValidationError):
            replace(policy.authority, unknown=0)
        with self.assertRaises(ValidationError):
            replace(policy.weights, evidence_support=True)

    def test_loader_and_strict_json_failures(self) -> None:
        raw = sample_policy()
        with patch.object(Path, "read_text", return_value=json.dumps(raw)) as read:
            self.assertEqual(load_policy(Path("policy.json")), validate_policy(raw))
            read.assert_called_once_with(encoding="utf-8")
        for text, code in (('{"x":1,"x":2}', "DUPLICATE_KEY"), ('{"x":NaN}', "NON_FINITE_NUMBER"), ("{", "INVALID_JSON")):
            with patch.object(Path, "read_text", return_value=text):
                with self.assertRaises(ValidationError) as caught:
                    load_policy(Path("policy.json"))
                self.assertEqual(caught.exception.issue.code, code)
        for error, code in ((PermissionError("secret"), "POLICY_READ_ERROR"), (UnicodeError("secret"), "INVALID_ENCODING")):
            with patch.object(Path, "read_text", side_effect=error):
                with self.assertRaises(ValidationError) as caught:
                    load_policy(Path("policy.json"))
                self.assertEqual(caught.exception.issue.code, code)
                self.assertNotIn("secret", str(caught.exception))
        with self.assertRaises(ValidationError):
            load_policy("policy.json")  # type: ignore[arg-type]
