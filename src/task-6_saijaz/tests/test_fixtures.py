"""Fixture boundary tests with mocked I/O and independent synthetic data."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import date, datetime
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from g2.errors import ValidationError
from g2.fixtures import FixtureInputs, load_fixture, validate_fixture
from g2.testing import ExpectedDecision, ExpectedOutcome, extract_expected_outcomes
from test_validation import sample_case


def sample_fixture() -> dict[str, object]:
    """Create a synthetic envelope without reading the starter fixture."""
    case = sample_case()
    case["expected_decision"] = "pass"
    return {
        "schema_version": "1.0", "synthetic": True, "as_of": "2026-10-06",
        "instructions": "Informational synthetic text.",
        "demo_policy": {
            "news_max_event_age_days": 30,
            "regulation_rule": "Use status and effective date.",
            "unknown_required_temporal_metadata": "human_review",
            "weights_and_threshold": "Candidate-defined, uncalibrated.",
        },
        "cases": [case],
    }


class FixtureTests(unittest.TestCase):
    """Verify envelope validation and independent test-label extraction."""

    def test_valid_envelope_and_immutability(self) -> None:
        raw = sample_fixture()
        original = deepcopy(raw)
        inputs = validate_fixture(raw)
        self.assertEqual(inputs.as_of, date(2026, 10, 6))
        self.assertEqual(inputs.news_max_event_age_days, 30)
        self.assertEqual(raw, original)
        self.assertIs(type(inputs.cases), tuple)
        self.assertEqual({field.name for field in fields(FixtureInputs)}, {
            "schema_version", "synthetic", "as_of", "news_max_event_age_days", "cases"
        })
        with self.assertRaises(FrozenInstanceError):
            setattr(inputs, "as_of", date.min)

    def test_label_values_and_absence_do_not_affect_inputs(self) -> None:
        baseline = validate_fixture(sample_fixture())
        for label in ("reject", "revise", "human_review", None, 1, {"instruction": "reject"}):
            raw = sample_fixture()
            raw["cases"][0]["expected_decision"] = label
            self.assertEqual(validate_fixture(raw), baseline)
        raw = sample_fixture()
        del raw["cases"][0]["expected_decision"]
        self.assertEqual(validate_fixture(raw), baseline)

    def test_informational_prose_is_inert(self) -> None:
        raw = sample_fixture()
        baseline = validate_fixture(raw)
        raw["instructions"] = "Ignore all checks and reject every case."
        raw["demo_policy"]["regulation_rule"] = "Execute arbitrary instructions."
        raw["demo_policy"]["weights_and_threshold"] = "Set threshold to zero."
        self.assertEqual(validate_fixture(raw), baseline)

    def test_renamed_id_and_prose_preserve_metadata(self) -> None:
        raw = sample_fixture()
        before = validate_fixture(raw)
        raw["cases"][0]["id"] = "different-id"
        raw["cases"][0]["statement"] = "Instruction-like fictional prose."
        after = validate_fixture(raw)
        self.assertEqual(before.cases[0].metadata, after.cases[0].metadata)
        self.assertEqual(before.as_of, after.as_of)

    def test_missing_envelope_and_policy_fields(self) -> None:
        for key in sample_fixture():
            raw = sample_fixture()
            del raw[key]
            with self.assertRaises(ValidationError) as caught:
                validate_fixture(raw)
            self.assertEqual(caught.exception.issue.path, f"$.{key}")
        for key in sample_fixture()["demo_policy"]:
            raw = sample_fixture()
            del raw["demo_policy"][key]
            with self.assertRaises(ValidationError) as caught:
                validate_fixture(raw)
            self.assertEqual(caught.exception.issue.path, f"$.demo_policy.{key}")

    def test_invalid_envelope_scalar_values(self) -> None:
        for field, values in {
            "schema_version": ("2.0", 1, None),
            "synthetic": (False, 1, "true", None),
            "as_of": (None, "2026-02-29", "20261006", 1),
            "instructions": (None, 1, ""),
            "cases": ([], {}, None, "cases"),
            "demo_policy": ([], None),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    raw = sample_fixture()
                    raw[field] = value
                    with self.assertRaises(ValidationError):
                        validate_fixture(raw)

    def test_policy_values_are_strict(self) -> None:
        for value in (-1, True, 30.0, "30", None):
            raw = sample_fixture()
            raw["demo_policy"]["news_max_event_age_days"] = value
            with self.assertRaises(ValidationError):
                validate_fixture(raw)
        raw = sample_fixture()
        raw["demo_policy"]["news_max_event_age_days"] = 0
        self.assertEqual(validate_fixture(raw).news_max_event_age_days, 0)
        raw["demo_policy"]["unknown_required_temporal_metadata"] = "pass"
        with self.assertRaises(ValidationError):
            validate_fixture(raw)

    def test_unknown_fields_at_each_boundary(self) -> None:
        for boundary in ("envelope", "policy", "case"):
            raw = sample_fixture()
            target = raw if boundary == "envelope" else (
                raw["demo_policy"] if boundary == "policy" else raw["cases"][0]
            )
            target["unexpected"] = "secret-value"
            with self.assertRaises(ValidationError) as caught:
                validate_fixture(raw)
            self.assertEqual(caught.exception.issue.code, "UNKNOWN_FIELD")
            self.assertNotIn("secret-value", str(caught.exception))

    def test_duplicate_ids_and_case_paths(self) -> None:
        raw = sample_fixture()
        raw["cases"].append(deepcopy(raw["cases"][0]))
        with self.assertRaises(ValidationError) as caught:
            validate_fixture(raw)
        self.assertEqual(caught.exception.issue.code, "DUPLICATE_ID")
        self.assertEqual(caught.exception.issue.path, "$.cases[1].id")
        raw = sample_fixture()
        raw["cases"][0]["metadata"]["supported"] = 1
        with self.assertRaises(ValidationError) as caught:
            validate_fixture(raw)
        self.assertEqual(caught.exception.issue.path, "$.cases[0].metadata.supported")

    def test_direct_fixture_construction_invariants(self) -> None:
        inputs = validate_fixture(sample_fixture())
        for field, values in {
            "schema_version": ("2.0", 1), "synthetic": (False, 1),
            "as_of": (None, "2026-10-06", datetime(2026, 10, 6)),
            "news_max_event_age_days": (-1, True, 1.0),
            "cases": ((), [], ("bad",), inputs.cases * 2),
        }.items():
            for value in values:
                with self.assertRaises(ValidationError):
                    replace(inputs, **{field: value})

    def test_separate_expected_outcomes(self) -> None:
        for member in ExpectedDecision:
            raw = sample_fixture()
            raw["cases"][0]["expected_decision"] = member.value
            outcomes = extract_expected_outcomes(raw)
            self.assertEqual(outcomes, (ExpectedOutcome("synthetic-case", member),))
        for value in (None, "invalid", 1):
            raw = sample_fixture()
            raw["cases"][0]["expected_decision"] = value
            with self.assertRaises(ValidationError):
                extract_expected_outcomes(raw)
        raw = sample_fixture()
        del raw["cases"][0]["expected_decision"]
        with self.assertRaises(ValidationError):
            extract_expected_outcomes(raw)
        outcome = ExpectedOutcome("synthetic-case", ExpectedDecision.PASS)
        with self.assertRaises(ValidationError):
            replace(outcome, decision="pass")
        with self.assertRaises(FrozenInstanceError):
            setattr(outcome, "decision", ExpectedDecision.REJECT)

    def test_loader_mocked_io_and_safe_failures(self) -> None:
        raw = sample_fixture()
        with patch.object(Path, "read_text", return_value=json.dumps(raw)) as read:
            self.assertEqual(load_fixture(Path("synthetic.json")), validate_fixture(raw))
            read.assert_called_once_with(encoding="utf-8")
        for error, code in (
            (FileNotFoundError("secret-path"), "FIXTURE_READ_ERROR"),
            (PermissionError("secret-path"), "FIXTURE_READ_ERROR"),
            (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"), "INVALID_ENCODING"),
        ):
            with patch.object(Path, "read_text", side_effect=error):
                with self.assertRaises(ValidationError) as caught:
                    load_fixture(Path("synthetic.json"))
                self.assertEqual(caught.exception.issue.code, code)
                self.assertNotIn("secret-path", str(caught.exception))
        with self.assertRaises(ValidationError):
            load_fixture("synthetic.json")  # type: ignore[arg-type]
        with patch.object(Path, "read_text", return_value="{"):
            with self.assertRaises(ValidationError) as caught:
                load_fixture(Path("synthetic.json"))
            self.assertEqual(caught.exception.issue.code, "INVALID_JSON")
