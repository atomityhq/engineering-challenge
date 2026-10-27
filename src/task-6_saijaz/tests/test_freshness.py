"""Temporal boundary, status matrix, and immutable output tests."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta
from itertools import product
import unittest

from g2 import ContentType, CurrentStatus, Metadata, SourceType, ValidationError, validate_metadata
from g2.freshness import Applicability, TemporalCode, assess_freshness
from g2.hard_checks import FindingKind
from test_validation import sample_metadata

AS_OF = date(2026, 10, 6)


def metadata(**changes: object) -> Metadata:
    """Build trusted synthetic assertions with explicit overridden fields."""
    raw = sample_metadata()
    raw.update(changes)
    return validate_metadata(raw)


class FreshnessTests(unittest.TestCase):
    """Exercise temporal facts independently of labels, scoring, and routing."""

    def test_news_age_boundaries(self) -> None:
        for age, value, codes in (
            (0, 1.0, ()), (30, 1.0, ()),
            (31, 0.0, (TemporalCode.STALE_EVENT,)),
            (-1, None, (TemporalCode.FUTURE_EVENT,)),
        ):
            with self.subTest(age=age):
                case = metadata(event_date=(AS_OF - timedelta(days=age)).isoformat())
                result = assess_freshness(case, AS_OF, 30)
                self.assertEqual(result.value, value)
                self.assertEqual(result.event_age_days, age)
                self.assertEqual(tuple(f.code for f in result.findings), codes)
                self.assertEqual(result.date_basis, "event_date")
                self.assertIs(result.applicability, Applicability.NOT_APPLICABLE)
                self.assertIsNone(result.currently_applicable)

    def test_supplied_age_limit_and_date(self) -> None:
        case = metadata(event_date=AS_OF.isoformat(), last_verified_at=None)
        self.assertEqual(assess_freshness(case, AS_OF, 0).value, 1.0)
        later = assess_freshness(case, AS_OF + timedelta(days=1), 0)
        self.assertEqual(later.value, 0.0)
        self.assertEqual(later.event_age_days, 1)
        self.assertEqual(assess_freshness(case, AS_OF + timedelta(days=1), 1).value, 1.0)

    def test_unknown_event_not_replaced_by_context_dates(self) -> None:
        case = metadata(event_date=None, published_at=AS_OF.isoformat(),
                        last_verified_at=AS_OF.isoformat())
        result = assess_freshness(case, AS_OF, 30)
        self.assertIsNone(result.value)
        self.assertIsNone(result.event_age_days)
        self.assertEqual(tuple(f.code for f in result.findings), (TemporalCode.MISSING_EVENT,))
        self.assertEqual(result.metadata.published_at, AS_OF)
        self.assertEqual(result.metadata.last_verified_at, AS_OF)

    def test_regulation_effective_boundaries(self) -> None:
        for status, offset, value, applicability, current in (
            (CurrentStatus.CURRENT, -1, 1.0, Applicability.CURRENT, True),
            (CurrentStatus.CURRENT, 0, 1.0, Applicability.CURRENT, True),
            (CurrentStatus.CURRENT, 1, None, Applicability.UNKNOWN, None),
            (CurrentStatus.ADOPTED_NOT_APPLICABLE, -1, None, Applicability.UNKNOWN, None),
            (CurrentStatus.ADOPTED_NOT_APPLICABLE, 0, None, Applicability.UNKNOWN, None),
            (CurrentStatus.ADOPTED_NOT_APPLICABLE, 1, 1.0, Applicability.FUTURE, False),
        ):
            with self.subTest(status=status, offset=offset):
                case = metadata(content_type="regulation", current_status=status.value,
                                effective_from=(AS_OF + timedelta(days=offset)).isoformat(),
                                published_at="1900-01-01", event_date=None)
                result = assess_freshness(case, AS_OF, 30)
                self.assertEqual(result.value, value)
                self.assertIs(result.applicability, applicability)
                self.assertIs(result.currently_applicable, current)
                self.assertIsNone(result.event_age_days)
                self.assertEqual(result.date_basis, "effective_from")
                self.assertEqual(tuple(f.code for f in result.findings),
                                 (TemporalCode.INCONSISTENT_EFFECTIVE,) if value is None else ())

    def test_missing_effective_date_for_each_status(self) -> None:
        for status in CurrentStatus:
            with self.subTest(status=status):
                result = assess_freshness(metadata(content_type="regulation",
                    current_status=status.value, effective_from=None), AS_OF, 30)
                self.assertEqual(result.value, 0.0 if status is CurrentStatus.SUPERSEDED else None)
                self.assertIn(TemporalCode.MISSING_EFFECTIVE, tuple(f.code for f in result.findings))
                self.assertIs(result.applicability,
                              Applicability.INACTIVE if status is CurrentStatus.SUPERSEDED else Applicability.UNKNOWN)

    def test_exhaustive_content_status_supersession_matrix(self) -> None:
        for content, status, replaced_flag in product(ContentType, CurrentStatus, (False, True)):
            with self.subTest(content=content, status=status, flag=replaced_flag):
                case = metadata(content_type=content.value, current_status=status.value,
                                superseded=replaced_flag, effective_from="2026-10-07")
                result = assess_freshness(case, AS_OF, 30)
                replaced = replaced_flag or status is CurrentStatus.SUPERSEDED
                expected = 0.0 if replaced else (
                    1.0 if content is ContentType.NEWS and status is CurrentStatus.CURRENT else
                    1.0 if content is ContentType.REGULATION and status is CurrentStatus.ADOPTED_NOT_APPLICABLE else None
                )
                self.assertEqual(result.value, expected)
                codes = tuple(f.code for f in result.findings)
                self.assertEqual(TemporalCode.SUPERSEDED in codes, replaced)
                self.assertEqual(TemporalCode.SUPERSESSION_CONFLICT in codes,
                                 replaced_flag != (status is CurrentStatus.SUPERSEDED))
                self.assertEqual(TemporalCode.UNKNOWN_STATUS in codes, status is CurrentStatus.UNKNOWN)
                self.assertEqual(TemporalCode.INCOMPATIBLE_STATUS in codes,
                                 content is ContentType.NEWS and status is CurrentStatus.ADOPTED_NOT_APPLICABLE)
                if content is ContentType.REGULATION and status is CurrentStatus.CURRENT:
                    self.assertIn(TemporalCode.INCONSISTENT_EFFECTIVE, codes)

    def test_stale_news_retains_invalidity_for_every_status(self) -> None:
        for status in CurrentStatus:
            with self.subTest(status=status):
                result = assess_freshness(metadata(current_status=status.value,
                    event_date="2026-09-01"), AS_OF, 30)
                codes = tuple(f.code for f in result.findings)
                self.assertEqual(result.event_age_days, 35)
                self.assertEqual(result.value, 0.0)
                self.assertIn(TemporalCode.STALE_EVENT, codes)
                if status is CurrentStatus.UNKNOWN:
                    self.assertIn(TemporalCode.UNKNOWN_STATUS, codes)
                if status is CurrentStatus.ADOPTED_NOT_APPLICABLE:
                    self.assertIn(TemporalCode.INCOMPATIBLE_STATUS, codes)
                if status is CurrentStatus.SUPERSEDED:
                    self.assertIn(TemporalCode.SUPERSEDED, codes)
                    self.assertIn(TemporalCode.SUPERSESSION_CONFLICT, codes)

    def test_verification_not_an_invented_expiry(self) -> None:
        for verification in (None, "1900-01-01", AS_OF.isoformat()):
            result = assess_freshness(metadata(last_verified_at=verification), AS_OF, 30)
            self.assertEqual(result.value, 1.0)
        for content in ContentType:
            result = assess_freshness(metadata(content_type=content.value,
                effective_from="2020-01-01", last_verified_at="2026-10-07"), AS_OF, 30)
            self.assertIsNone(result.value)
            self.assertEqual(tuple(f.code for f in result.findings), (TemporalCode.FUTURE_VERIFICATION,))
            self.assertIsNone(result.currently_applicable)

    def test_known_invalidity_preserves_uncertainty(self) -> None:
        for changes, expected_codes in (
            ({"event_date": "2026-09-01"}, (TemporalCode.STALE_EVENT, TemporalCode.FUTURE_VERIFICATION)),
            ({"superseded": True, "event_date": None}, (TemporalCode.SUPERSEDED,
             TemporalCode.SUPERSESSION_CONFLICT, TemporalCode.MISSING_EVENT, TemporalCode.FUTURE_VERIFICATION)),
            ({"superseded": True, "content_type": "regulation", "effective_from": "2026-10-07"},
             (TemporalCode.SUPERSEDED, TemporalCode.SUPERSESSION_CONFLICT,
              TemporalCode.INCONSISTENT_EFFECTIVE, TemporalCode.FUTURE_VERIFICATION)),
        ):
            result = assess_freshness(metadata(last_verified_at="2026-10-07", **changes), AS_OF, 30)
            self.assertEqual(result.value, 0.0)
            self.assertEqual(tuple(f.code for f in result.findings), expected_codes)
            self.assertTrue(any(f.kind is FindingKind.REPAIRABLE for f in result.findings))
            self.assertTrue(any(f.kind is FindingKind.REVIEW for f in result.findings))

    def test_unrelated_evidence_and_date_ordering(self) -> None:
        original = metadata(published_at="2026-10-01", event_date="2026-10-03")
        for content in ContentType:
            base = replace(original, content_type=content, effective_from=date(2020, 1, 1))
            alternative = replace(base, source_type=SourceType.UNKNOWN, supported=False,
                                  contradiction=True, competitor_product_claim=True,
                                  published_at=None)
            first = assess_freshness(base, AS_OF, 30)
            second = assess_freshness(alternative, AS_OF, 30)
            self.assertEqual(first.value, 1.0)
            for name in ("value", "event_age_days", "date_basis", "applicability",
                         "currently_applicable", "findings", "explanation"):
                self.assertEqual(getattr(first, name), getattr(second, name))

    def test_input_types_and_no_coercion(self) -> None:
        case = metadata()
        for bad_date in (None, "2026-10-06", datetime(2026, 10, 6)):
            with self.assertRaises(ValidationError):
                assess_freshness(case, bad_date, 30)  # type: ignore[arg-type]
        for bad_age in (-1, True, 30.0, "30", None):
            with self.assertRaises(ValidationError):
                assess_freshness(case, AS_OF, bad_age)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            assess_freshness(sample_metadata(), AS_OF, 30)  # type: ignore[arg-type]
        self.assertEqual(assess_freshness(case, AS_OF, 10**100).value, 1.0)

    def test_output_invariants_and_determinism(self) -> None:
        case = metadata(event_date="2026-09-01", last_verified_at="2026-10-07")
        result = assess_freshness(case, AS_OF, 30)
        self.assertEqual(result, assess_freshness(case, AS_OF, 30))
        for changes in ({"value": 1.0}, {"value": False}, {"value": None},
                        {"findings": ()}, {"findings": list(result.findings)},
                        {"event_age_days": True}, {"date_basis": "published_at"},
                        {"applicability": "not_applicable"}, {"currently_applicable": False},
                        {"explanation": ""}):
            with self.assertRaises(ValidationError):
                replace(result, **changes)
        finding = result.findings[0]
        for changes in ({"kind": FindingKind.REVIEW}, {"code": "STALE_EVENT"}, {"reason": ""}):
            with self.assertRaises(ValidationError):
                replace(finding, **changes)
        with self.assertRaises(FrozenInstanceError):
            setattr(result, "value", 1.0)
