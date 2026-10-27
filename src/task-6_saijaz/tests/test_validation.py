"""Boundary and construction tests using synthetic in-memory inputs only."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import date, datetime
import json
from typing import Callable
import unittest

from g2 import (
    ContentType, CurrentStatus, EvaluationCase, Metadata, SourceType,
    ValidationError, ValidationIssue, parse_json, validate_case, validate_metadata,
)
from g2.contracts import BOOLEAN_FIELDS, DATE_FIELDS
from g2.validation import parse_date


def sample_metadata() -> dict[str, object]:
    """Return an independent valid synthetic metadata object."""
    return {
        "source_type": "primary_authority",
        "content_type": "news",
        "published_at": "2026-10-04",
        "event_date": "2026-10-03",
        "effective_from": None,
        "last_verified_at": "2026-10-06",
        "current_status": "current",
        "supported": True,
        "superseded": False,
        "contradiction": False,
        "competitor_product_claim": False,
    }


def sample_case() -> dict[str, object]:
    """Return a label-free synthetic case, independent of the starter file."""
    return {
        "id": "synthetic-case", "statement": "A fictional announcement.",
        "metadata": sample_metadata(),
    }


class ValidationTests(unittest.TestCase):
    """Exercise strict JSON boundaries and observable error contracts."""

    def assert_issue(
        self, action: Callable[[], object], code: str, path: str
    ) -> ValidationError:
        """Check the structured error without relying on decoder wording."""
        with self.assertRaises(ValidationError) as caught:
            action()
        self.assertEqual(caught.exception.issue.code, code)
        self.assertEqual(caught.exception.issue.path, path)
        return caught.exception

    def test_valid_json_roundtrip(self) -> None:
        raw = sample_case()
        original = deepcopy(raw)
        case = validate_case(parse_json(json.dumps(raw)))
        self.assertEqual(case.id, "synthetic-case")
        self.assertEqual(case.metadata.event_date, date(2026, 10, 3))
        self.assertIs(case.metadata.source_type, SourceType.PRIMARY_AUTHORITY)
        self.assertEqual(raw, original)

    def test_every_required_case_key(self) -> None:
        for key in sample_case():
            with self.subTest(key=key):
                raw = sample_case()
                del raw[key]
                self.assert_issue(lambda: validate_case(raw), "MISSING_FIELD", f"$.{key}")

    def test_every_required_metadata_key(self) -> None:
        for key in sample_metadata():
            with self.subTest(key=key):
                raw = sample_metadata()
                del raw[key]
                self.assert_issue(
                    lambda: validate_metadata(raw), "MISSING_FIELD", f"$.metadata.{key}"
                )

    def test_null_dates_are_explicit_unknowns(self) -> None:
        for key in DATE_FIELDS:
            with self.subTest(key=key):
                raw = sample_metadata()
                raw[key] = None
                self.assertIsNone(getattr(validate_metadata(raw), key))

    def test_non_objects_rejected(self) -> None:
        for raw in (None, [], True, 1, "object"):
            with self.subTest(raw=raw):
                self.assert_issue(lambda: validate_case(raw), "INVALID_TYPE", "$")
                self.assert_issue(
                    lambda: validate_metadata(raw), "INVALID_TYPE", "$.metadata"
                )

    def test_non_string_keys_and_extra_keys_rejected(self) -> None:
        for key in (1, "expected_decision", "secret-unknown-key"):
            with self.subTest(key=key):
                raw: dict[object, object] = dict(sample_case())
                raw[key] = "secret-value"
                error = self.assert_issue(lambda: validate_case(raw), "UNKNOWN_FIELD", "$")
                self.assertNotIn("secret", str(error))
        raw_metadata = sample_metadata()
        raw_metadata["unexpected"] = True
        self.assert_issue(
            lambda: validate_metadata(raw_metadata), "UNKNOWN_FIELD", "$.metadata"
        )

    def test_text_type_and_blank_checks(self) -> None:
        for field in ("id", "statement"):
            for value in (None, 1, False, [], "", " \t\n"):
                with self.subTest(field=field, value=value):
                    raw = sample_case()
                    raw[field] = value
                    code = "EMPTY_STRING" if isinstance(value, str) else "INVALID_TYPE"
                    self.assert_issue(lambda: validate_case(raw), code, f"$.{field}")
        raw = sample_case()
        raw["statement"] = "  Preserve supplied text.  "
        self.assertEqual(validate_case(raw).statement, raw["statement"])

    def test_boolean_coercions_rejected_for_all_flags(self) -> None:
        for field in BOOLEAN_FIELDS:
            for value in (0, 1, "true", "false", None, [], {}):
                with self.subTest(field=field, value=value):
                    raw = sample_metadata()
                    raw[field] = value
                    self.assert_issue(
                        lambda: validate_metadata(raw), "INVALID_TYPE", f"$.metadata.{field}"
                    )

    def test_exact_supported_categories(self) -> None:
        for field, enum_type in (
            ("source_type", SourceType), ("content_type", ContentType),
            ("current_status", CurrentStatus),
        ):
            for member in enum_type:
                with self.subTest(field=field, member=member):
                    raw = sample_metadata()
                    raw[field] = member.value
                    self.assertIs(getattr(validate_metadata(raw), field), member)
            for value in ("unrecognized", "CURRENT", " current "):
                raw = sample_metadata()
                raw[field] = value
                self.assert_issue(
                    lambda: validate_metadata(raw), "INVALID_ENUM", f"$.metadata.{field}"
                )
            raw = sample_metadata()
            raw[field] = 1
            self.assert_issue(
                lambda: validate_metadata(raw), "INVALID_TYPE", f"$.metadata.{field}"
            )

    def test_invalid_dates_for_every_date_field(self) -> None:
        invalid = (
            "2026-02-29", "2026-13-01", "0000-01-01", "20261003",
            "2026-1-03", "2026-W40-6", "2026-10-03T00:00:00",
            " 2026-10-03", "２０２６-１０-０３", "", "2026-10-03\n",
        )
        for field in DATE_FIELDS:
            for value in invalid:
                with self.subTest(field=field, value=value):
                    raw = sample_metadata()
                    raw[field] = value
                    self.assert_issue(
                        lambda: validate_metadata(raw), "INVALID_DATE", f"$.metadata.{field}"
                    )
            for value in (True, 1, date(2026, 10, 3), []):
                raw = sample_metadata()
                raw[field] = value
                self.assert_issue(
                    lambda: validate_metadata(raw), "INVALID_TYPE", f"$.metadata.{field}"
                )
        self.assertEqual(parse_date("2024-02-29", "$"), date(2024, 2, 29))
        self.assertEqual(parse_date("9999-12-31", "$"), date.max)

    def test_temporal_conflicts_are_not_structural_errors(self) -> None:
        for content in ContentType:
            for status in CurrentStatus:
                raw = sample_metadata()
                raw.update(
                    content_type=content.value, current_status=status.value,
                    effective_from="2027-01-01", last_verified_at="2028-01-01",
                    superseded=True, contradiction=True,
                )
                result = validate_metadata(raw)
                self.assertIs(result.current_status, status)
                self.assertTrue(result.superseded)

    def test_error_paths_support_nested_adapter_context(self) -> None:
        raw = sample_case()
        raw["metadata"] = None
        self.assert_issue(
            lambda: validate_case(raw, "$.cases[2]"), "INVALID_TYPE", "$.cases[2].metadata"
        )

    def test_duplicate_keys_at_any_depth(self) -> None:
        for text in ('{"id":1,"id":2}', '{"a":[{"x":1,"x":2}]}'):
            self.assert_issue(lambda: parse_json(text), "DUPLICATE_KEY", "$")

    def test_nonfinite_tokens_and_float_overflow(self) -> None:
        for token in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999"):
            for text in (token, f'{{"a":[{token}]}}'):
                with self.subTest(text=text):
                    self.assert_issue(lambda: parse_json(text), "NON_FINITE_NUMBER", "$")
        self.assertEqual(parse_json("1e2"), 100.0)

    def test_malformed_json_and_decoder_limits_are_safe(self) -> None:
        for text in ("", "{", "[1,]", '{} {}', '"raw-secret', '[' * 10000):
            error = self.assert_issue(lambda: parse_json(text), "INVALID_JSON", "$")
            self.assertNotIn("raw-secret", str(error))
        self.assert_issue(lambda: parse_json(1), "INVALID_TYPE", "$")  # type: ignore[arg-type]
        self.assertIsNone(parse_json("null"))

    def test_construction_rejects_untyped_metadata_fields(self) -> None:
        metadata = validate_metadata(sample_metadata())
        for field in BOOLEAN_FIELDS:
            self.assert_issue(
                lambda: replace(metadata, **{field: 1}), "INVALID_TYPE", f"$.metadata.{field}"
            )
        for field in DATE_FIELDS:
            for value in ("2026-10-03", datetime(2026, 10, 3)):
                self.assert_issue(
                    lambda: replace(metadata, **{field: value}),
                    "INVALID_TYPE", f"$.metadata.{field}",
                )
        for field in ("source_type", "content_type", "current_status"):
            self.assert_issue(
                lambda: replace(metadata, **{field: "unknown"}),
                "INVALID_TYPE", f"$.metadata.{field}",
            )

    def test_case_construction_and_immutability(self) -> None:
        case = validate_case(sample_case())
        self.assert_issue(lambda: replace(case, id=""), "EMPTY_STRING", "$.id")
        self.assert_issue(
            lambda: replace(case, metadata=sample_metadata()), "INVALID_TYPE", "$.metadata"
        )
        with self.assertRaises(FrozenInstanceError):
            setattr(case, "id", "changed")
        with self.assertRaises(FrozenInstanceError):
            setattr(case.metadata, "supported", False)
        self.assertEqual({field.name for field in fields(EvaluationCase)}, {"id", "statement", "metadata"})
        with self.assertRaises(TypeError):
            EvaluationCase(**{**sample_case(), "expected_decision": "pass"})  # type: ignore[arg-type]
        self.assertEqual(len(fields(Metadata)), 11)

    def test_issue_invariants(self) -> None:
        issue = ValidationIssue("INVALID_TYPE", "$", "Expected an object.")
        with self.assertRaises(FrozenInstanceError):
            setattr(issue, "code", "changed")
        for name in ("code", "path", "message"):
            for value in ("", None, 1):
                with self.assertRaises(ValueError):
                    replace(issue, **{name: value})
