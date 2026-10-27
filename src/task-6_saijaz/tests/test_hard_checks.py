"""Exhaustive evidence flag combinations and output-construction checks."""

from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest

from g2 import CurrentStatus, SourceType, ValidationError, validate_metadata
from g2.hard_checks import (
    CheckName, CheckStatus, FindingCode, FindingKind,
    HardCheckAssessment, assess_hard_checks,
)
from test_validation import sample_metadata


class HardCheckTests(unittest.TestCase):
    """Validate pure checks independently of fixture labels and scoring."""

    def test_clean_metadata(self) -> None:
        result = assess_hard_checks(validate_metadata(sample_metadata()))
        self.assertEqual(tuple(item.name for item in result.checks), tuple(CheckName))
        self.assertTrue(all(item.status is CheckStatus.PASS for item in result.checks))
        self.assertEqual(result.findings, ())

    def test_exhaustive_flag_status_combinations(self) -> None:
        for supported, superseded, contradiction, promotion in product((False, True), repeat=4):
            for status in CurrentStatus:
                with self.subTest(flags=(supported, superseded, contradiction, promotion), status=status):
                    raw = sample_metadata()
                    raw.update(supported=supported, superseded=superseded,
                               contradiction=contradiction, competitor_product_claim=promotion,
                               current_status=status.value)
                    result = assess_hard_checks(validate_metadata(raw))
                    by_name = {check.name: check for check in result.checks}
                    expected_support = CheckStatus.FAIL if not supported else (
                        CheckStatus.UNKNOWN if contradiction else CheckStatus.PASS
                    )
                    self.assertIs(by_name[CheckName.SUPPORT].status, expected_support)
                    replaced = superseded or status is CurrentStatus.SUPERSEDED
                    self.assertIs(by_name[CheckName.SUPERSESSION].status,
                                  CheckStatus.FAIL if replaced else CheckStatus.PASS)
                    self.assertIs(by_name[CheckName.PROMOTION].status,
                                  CheckStatus.FAIL if promotion else CheckStatus.PASS)
                    self.assertIs(by_name[CheckName.CONFLICT].status,
                                  CheckStatus.FAIL if contradiction else CheckStatus.PASS)
                    expected: dict[FindingCode, FindingKind] = {}
                    if not supported:
                        expected[FindingCode.UNSUPPORTED_CLAIM] = FindingKind.REPAIRABLE
                    elif contradiction:
                        expected[FindingCode.UNRESOLVED_SUPPORT] = FindingKind.REVIEW
                    if replaced:
                        expected[FindingCode.SUPERSEDED_EVIDENCE] = FindingKind.REPAIRABLE
                    if superseded != (status is CurrentStatus.SUPERSEDED):
                        expected[FindingCode.SUPERSESSION_METADATA_CONFLICT] = FindingKind.REVIEW
                    if promotion:
                        expected[FindingCode.COMPETITOR_PROMOTION] = FindingKind.PROHIBITED
                    if contradiction:
                        expected[FindingCode.CONFLICTING_EVIDENCE] = FindingKind.REVIEW
                    self.assertEqual({item.code: item.kind for item in result.findings}, expected)
                    self.assertEqual(len(result.findings), len(expected))
                    for check in result.checks:
                        self.assertTrue(check.reason.strip())
                        self.assertEqual(check.basis.supported, supported)
                        self.assertEqual(check.basis.superseded, superseded)
                        self.assertEqual(check.basis.current_status, status)

    def test_promotion_independent_of_source_category(self) -> None:
        for source in SourceType:
            raw = sample_metadata()
            raw.update(source_type=source.value, competitor_product_claim=True)
            result = assess_hard_checks(validate_metadata(raw))
            self.assertEqual([(item.code, item.kind) for item in result.findings], [
                (FindingCode.COMPETITOR_PROMOTION, FindingKind.PROHIBITED)
            ])

    def test_all_findings_retained_and_deterministic(self) -> None:
        raw = sample_metadata()
        raw.update(supported=False, superseded=True, contradiction=True,
                   competitor_product_claim=True)
        metadata = validate_metadata(raw)
        result = assess_hard_checks(metadata)
        self.assertEqual(result, assess_hard_checks(metadata))
        self.assertEqual(tuple(item.code for item in result.findings), (
            FindingCode.UNSUPPORTED_CLAIM, FindingCode.SUPERSEDED_EVIDENCE,
            FindingCode.SUPERSESSION_METADATA_CONFLICT,
            FindingCode.COMPETITOR_PROMOTION, FindingCode.CONFLICTING_EVIDENCE,
        ))

    def test_unrelated_metadata_does_not_change_checks(self) -> None:
        metadata = validate_metadata(sample_metadata())
        alternate = replace(metadata, source_type=SourceType.COMPETITOR,
                            event_date=None, published_at=None, last_verified_at=None)
        self.assertEqual(assess_hard_checks(metadata), assess_hard_checks(alternate))

    def test_input_and_output_type_checks(self) -> None:
        with self.assertRaises(ValidationError):
            assess_hard_checks(sample_metadata())  # type: ignore[arg-type]
        result = assess_hard_checks(validate_metadata(sample_metadata()))
        with self.assertRaises(FrozenInstanceError):
            setattr(result.checks[0], "status", CheckStatus.FAIL)
        for change in ({"checks": []}, {"checks": ()}, {"checks": result.checks[::-1]},
                       {"findings": []}, {"checks": ("bad",) * 4}):
            with self.assertRaises(ValidationError):
                replace(result, **change)
        check = result.checks[0]
        for change in ({"status": "pass"}, {"status": CheckStatus.FAIL},
                       {"name": "bad"}, {"basis": {}}, {"reason": ""}):
            with self.assertRaises(ValidationError):
                replace(check, **change)
        with self.assertRaises(ValidationError):
            replace(check.basis, supported=1)

    def test_findings_cannot_be_removed_or_reclassified(self) -> None:
        raw = sample_metadata()
        raw["competitor_product_claim"] = True
        result = assess_hard_checks(validate_metadata(raw))
        finding = result.findings[0]
        with self.assertRaises(ValidationError):
            replace(result, findings=())
        for change in ({"kind": FindingKind.REVIEW}, {"kind": "prohibited"},
                       {"basis": {}}, {"code": FindingCode.UNSUPPORTED_CLAIM},
                       {"reason": ""}):
            with self.assertRaises(ValidationError):
                replace(finding, **change)
        with self.assertRaises(FrozenInstanceError):
            setattr(finding, "kind", FindingKind.REVIEW)

    def test_assessment_requires_consistent_basis(self) -> None:
        clean = assess_hard_checks(validate_metadata(sample_metadata()))
        raw = sample_metadata()
        raw["contradiction"] = True
        disputed = assess_hard_checks(validate_metadata(raw))
        with self.assertRaises(ValidationError):
            HardCheckAssessment((clean.checks[0], *disputed.checks[1:]), disputed.findings)
