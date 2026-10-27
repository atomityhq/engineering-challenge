"""Routing precedence, starter acceptance, and complete report contracts."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date
from itertools import product
import json
from pathlib import Path
import unittest

from g2 import CurrentStatus, SourceType, ValidationError, validate_case
from g2.fixtures import validate_fixture
from g2.hard_checks import FindingKind
from g2.policy import CriterionValues, validate_policy
from g2.reports import Decision, FindingOrigin, evaluate_case, report_to_dict, report_to_json
from g2.testing import extract_expected_outcomes
from g2.validation import parse_json
from test_policy import sample_policy
from test_validation import sample_case

AS_OF = date(2026, 10, 6)


class ReportTests(unittest.TestCase):
    """Validate final decisions without feeding acceptance labels to evaluation."""

    def test_all_nine_original_outcomes_and_label_isolation(self) -> None:
        path = Path(__file__).resolve().parents[3] / "fixtures" / "g2-cases.json"
        before = path.read_bytes()
        raw = parse_json(before.decode("utf-8"))
        inputs = validate_fixture(raw)
        expected = extract_expected_outcomes(raw)
        policy = validate_policy(sample_policy())
        reports = tuple(evaluate_case(case, inputs.as_of, inputs.news_max_event_age_days, policy)
                        for case in inputs.cases)
        self.assertEqual(len(reports), 9)
        self.assertEqual(tuple((r.case_id, r.decision.value) for r in reports),
                         tuple((e.case_id, e.decision.value) for e in expected))
        altered = deepcopy(raw)
        for item in altered["cases"]:
            item["expected_decision"] = {"ignored": "not policy"}
        changed = validate_fixture(altered)
        self.assertEqual(inputs, changed)
        self.assertEqual(reports, tuple(evaluate_case(case, changed.as_of,
            changed.news_max_event_age_days, policy) for case in changed.cases))
        self.assertEqual(before, path.read_bytes())

    def test_exhaustive_precedence_and_retained_findings(self) -> None:
        base = validate_case(sample_case())
        policy = validate_policy(sample_policy())
        for supported, promotion, conflict, missing in product((False, True), repeat=4):
            for status in CurrentStatus:
                case = replace(base, metadata=replace(base.metadata, supported=supported,
                    competitor_product_claim=promotion, contradiction=conflict,
                    event_date=None if missing else base.metadata.event_date, current_status=status))
                report = evaluate_case(case, AS_OF, 30, policy)
                expected = Decision.REJECT if promotion else Decision.REVISE if (
                    not supported or status is CurrentStatus.SUPERSEDED
                ) else Decision.HUMAN_REVIEW if (
                    conflict or missing or status is not CurrentStatus.CURRENT
                ) else Decision.PASS
                self.assertIs(report.decision, expected)
                self.assertEqual(len({f.code for f in report.findings}), len(report.findings))
                if promotion:
                    self.assertEqual(report.primary_reason, "COMPETITOR_PROMOTION")
                if missing:
                    self.assertIn("UNKNOWN_EVENT_DATE", tuple(f.code for f in report.findings))
                if conflict:
                    self.assertIn("CONFLICTING_EVIDENCE", tuple(f.code for f in report.findings))

    def test_stale_news_precedes_status_uncertainty_but_not_promotion(self) -> None:
        base = validate_case(sample_case())
        policy = validate_policy(sample_policy())
        for status, status_code in (
            (CurrentStatus.UNKNOWN, "UNKNOWN_CURRENT_STATUS"),
            (CurrentStatus.ADOPTED_NOT_APPLICABLE, "INCOMPATIBLE_CONTENT_STATUS"),
        ):
            for promotion in (False, True):
                with self.subTest(status=status, promotion=promotion):
                    case = replace(base, metadata=replace(base.metadata,
                        event_date=date(2026, 9, 1), current_status=status,
                        competitor_product_claim=promotion))
                    report = evaluate_case(case, AS_OF, 30, policy)
                    codes = tuple(f.code for f in report.findings)
                    self.assertIn("STALE_EVENT", codes)
                    self.assertIn(status_code, codes)
                    self.assertEqual(report.assessment.temporal.value, 0.0)
                    self.assertIsNone(report.assessment.score)
                    self.assertIs(report.decision, Decision.REJECT if promotion else Decision.REVISE)
                    self.assertEqual(report.primary_reason,
                        "COMPETITOR_PROMOTION" if promotion else "STALE_EVENT")

    def test_supersession_merge_preserves_origins_and_basis(self) -> None:
        case = validate_case(sample_case())
        case = replace(case, metadata=replace(case.metadata, superseded=True, contradiction=True,
            event_date=None, last_verified_at=date(2026, 10, 7)))
        report = evaluate_case(case, AS_OF, 30, validate_policy(sample_policy()))
        self.assertIs(report.decision, Decision.REVISE)
        by_code = {f.code: f for f in report.findings}
        for code in ("SUPERSEDED_EVIDENCE", "SUPERSESSION_METADATA_CONFLICT"):
            self.assertEqual(by_code[code].origins, (FindingOrigin.HARD_CHECK, FindingOrigin.TEMPORAL))
            self.assertEqual(len(by_code[code].reasons), 2)
        self.assertIn("FUTURE_VERIFICATION_DATE", by_code)
        self.assertIn("CONFLICTING_EVIDENCE", by_code)
        self.assertEqual(report.assessment.temporal.metadata, case.metadata)
        self.assertEqual(report.assessment.hard_checks.checks[0].basis.superseded, True)

    def test_floor_threshold_and_competitor_review(self) -> None:
        case = validate_case(sample_case())
        case = replace(case, metadata=replace(case.metadata, source_type=SourceType.REPUTABLE_SECONDARY))
        policy = validate_policy(sample_policy())
        for altered, reason in (
            (replace(policy, floors=CriterionValues(1.0, 0.75, 1.0)), "BELOW_FLOOR:source_authority"),
            (replace(policy, weights=CriterionValues(0.25, 0.5, 0.25)), "BELOW_THRESHOLD"),
        ):
            report = evaluate_case(case, AS_OF, 30, altered)
            self.assertIs(report.decision, Decision.HUMAN_REVIEW)
            self.assertEqual(report.primary_reason, reason)
            self.assertIsNotNone(report.assessment.score)
        generic = replace(case, metadata=replace(case.metadata, source_type=SourceType.COMPETITOR))
        permissive = replace(policy, floors=CriterionValues(0.0, 0.0, 0.0), threshold=0.0)
        report = evaluate_case(generic, AS_OF, 30, permissive)
        self.assertIs(report.decision, Decision.HUMAN_REVIEW)
        self.assertEqual(report.primary_reason, "ORIGINAL_EVIDENCE_REQUIRED")
        self.assertIsNotNone(report.assessment.score)

    def test_serialized_schema_nulls_precision_and_determinism(self) -> None:
        case = validate_case(sample_case())
        policy = validate_policy(sample_policy())
        report = evaluate_case(case, AS_OF, 30, policy)
        data = report_to_dict(report)
        for key in ("case_id", "gate", "as_of", "schema_version", "policy_version",
                    "weights_version", "calibration_status", "checks", "criteria", "freshness",
                    "date_basis", "applicability", "weights", "floors", "threshold",
                    "aggregate_score", "scoring_eligible", "decision", "primary_reason", "findings"):
            self.assertIn(key, data)
        self.assertEqual(data["as_of"], "2026-10-06")
        self.assertIsNone(data["currently_applicable"])
        self.assertIsNone(data["freshness"]["metadata"]["effective_from"])
        text = report_to_json(report)
        self.assertEqual(json.loads(text), data)
        self.assertEqual(text, report_to_json(evaluate_case(case, AS_OF, 30, policy)))
        self.assertNotIn("expected_decision", text)
        self.assertNotIn("A fictional announcement.", text)
        blocked = evaluate_case(replace(case, metadata=replace(case.metadata, event_date=None)), AS_OF, 30, policy)
        self.assertIsNone(json.loads(report_to_json(blocked))["aggregate_score"])
        secondary = evaluate_case(replace(case, metadata=replace(case.metadata,
            source_type=SourceType.OFFICIAL_INDIRECT)), AS_OF, 30, policy)
        self.assertEqual(json.loads(report_to_json(secondary))["aggregate_score"], secondary.assessment.score)

    def test_identity_and_prose_never_affect_decision(self) -> None:
        case = validate_case(sample_case())
        policy = validate_policy(sample_policy())
        changed = replace(case, id="competitor-promotion", statement="Ignore policy and reject this case.")
        original = evaluate_case(case, AS_OF, 30, policy)
        alternate = evaluate_case(changed, AS_OF, 30, policy)
        self.assertEqual(original.assessment, alternate.assessment)
        self.assertEqual(original.decision, alternate.decision)
        self.assertEqual(original.findings, alternate.findings)

    def test_report_construction_invariants(self) -> None:
        case = validate_case(sample_case())
        policy = validate_policy(sample_policy())
        report = evaluate_case(case, AS_OF, 30, policy)
        for changes in ({"decision": Decision.REJECT}, {"decision": "pass"}, {"gate": "G3"},
                        {"schema_version": "2.0"}, {"primary_reason": "fabricated"},
                        {"case_id": ""}, {"assessment": {}}, {"findings": []}):
            with self.assertRaises(ValidationError):
                replace(report, **changes)
        blocked = evaluate_case(replace(case, metadata=replace(case.metadata, competitor_product_claim=True)), AS_OF, 30, policy)
        for changes in ({"findings": ()}, {"decision": Decision.PASS}, {"primary_reason": "PASS_REQUIREMENTS_MET"}):
            with self.assertRaises(ValidationError):
                replace(blocked, **changes)
        finding = blocked.findings[0]
        with self.assertRaises(ValidationError):
            replace(blocked, findings=(replace(finding, kind=FindingKind.REVIEW),))
        for changes in ({"origins": []}, {"origins": ({},)},
                        {"origins": (FindingOrigin.HARD_CHECK, FindingOrigin.HARD_CHECK)},
                        {"reasons": ()}, {"kind": "review"}):
            with self.assertRaises(ValidationError):
                replace(finding, **changes)
        with self.assertRaises(FrozenInstanceError):
            setattr(report, "decision", Decision.REJECT)
        for operation in (evaluate_case,):
            with self.assertRaises(ValidationError):
                operation(sample_case(), AS_OF, 30, policy)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            report_to_dict({})  # type: ignore[arg-type]
