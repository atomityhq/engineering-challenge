"""Independent numerical checks and evidence-blocking score invariants."""

from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal
from itertools import product
import math
import unittest

from g2 import CurrentStatus, SourceType, ValidationError, validate_metadata
from g2.evaluator import CriterionName, assess_score
from g2.policy import CriterionValues, validate_policy
from test_policy import sample_policy
from test_validation import sample_metadata

AS_OF = date(2026, 10, 6)


class ScoreTests(unittest.TestCase):
    """Keep scoring eligibility separate from floors and final routing."""

    def test_known_authority_values_and_independent_sums(self) -> None:
        policy = validate_policy(sample_policy())
        for source, authority, expected in (
            (SourceType.PRIMARY_AUTHORITY, 1.0, "1.0"),
            (SourceType.OFFICIAL_INDIRECT, 0.75, "0.925"),
            (SourceType.REPUTABLE_SECONDARY, 0.5, "0.85"),
            (SourceType.COMPETITOR, 0.0, "0.7"),
        ):
            case = replace(validate_metadata(sample_metadata()), source_type=source)
            result = assess_score(case, AS_OF, 30, policy)
            self.assertEqual(tuple(c.name for c in result.criteria), tuple(CriterionName))
            self.assertEqual(tuple(c.value for c in result.criteria), (1.0, authority, 1.0))
            self.assertTrue(result.scoring_eligible)
            independent = Decimal("0.45") + Decimal("0.30") * Decimal(str(authority)) + Decimal("0.25")
            self.assertEqual(independent, Decimal(expected))
            self.assertAlmostEqual(result.score, float(independent), places=15)
            self.assertEqual(result.pass_requirements_met, source is not SourceType.COMPETITOR)
            self.assertEqual(result.original_evidence_required, source is SourceType.COMPETITOR)

    def test_supported_conflict_mapping_and_blocking(self) -> None:
        policy = validate_policy(sample_policy())
        for supported, conflict in product((False, True), repeat=2):
            case = replace(validate_metadata(sample_metadata()), supported=supported, contradiction=conflict)
            result = assess_score(case, AS_OF, 30, policy)
            expected = 0.0 if not supported else None if conflict else 1.0
            self.assertEqual(result.criteria[0].value, expected)
            self.assertEqual(result.scoring_eligible, supported and not conflict)
            if not supported or conflict:
                self.assertIsNone(result.score)
                self.assertFalse(result.pass_requirements_met)
                self.assertTrue(result.hard_checks.findings)

    def test_all_flag_status_combinations_cannot_bypass_checks(self) -> None:
        base = validate_metadata(sample_metadata())
        policy = replace(validate_policy(sample_policy()), weights=CriterionValues(0.0, 1.0, 0.0),
                         floors=CriterionValues(0.0, 0.0, 0.0), threshold=0.0)
        for supported, superseded, conflict, promotion in product((False, True), repeat=4):
            for status in CurrentStatus:
                case = replace(base, supported=supported, superseded=superseded,
                    contradiction=conflict, competitor_product_claim=promotion, current_status=status)
                result = assess_score(case, AS_OF, 30, policy)
                eligible = supported and not superseded and not conflict and not promotion and status is CurrentStatus.CURRENT
                self.assertEqual(result.scoring_eligible, eligible)
                if not eligible:
                    self.assertIsNone(result.score)
                    self.assertFalse(result.pass_requirements_met)

    def test_unknown_required_criteria_block_zero_weights(self) -> None:
        base = validate_metadata(sample_metadata())
        policy = validate_policy(sample_policy())
        for changes, weights, name in (
            ({"source_type": SourceType.UNKNOWN}, CriterionValues(1.0, 0.0, 0.0), CriterionName.AUTHORITY),
            ({"event_date": None}, CriterionValues(1.0, 0.0, 0.0), CriterionName.TEMPORAL),
            ({"contradiction": True}, CriterionValues(0.0, 1.0, 0.0), CriterionName.SUPPORT),
        ):
            result = assess_score(replace(base, **changes), AS_OF, 30, replace(policy, weights=weights))
            self.assertIsNone(next(c.value for c in result.criteria if c.name is name))
            self.assertIn("UNKNOWN_CRITERION:" + name.value, result.blocking_reasons)
            self.assertIsNone(result.score)
            self.assertIsNone(result.threshold_met)

    def test_temporal_defects_and_uncertainties_block(self) -> None:
        for event, verification, value in (
            (date(2026, 9, 1), AS_OF, 0.0),
            (None, AS_OF, None),
            (date(2026, 10, 7), AS_OF, None),
            (date(2026, 10, 3), date(2026, 10, 7), None),
        ):
            result = assess_score(replace(validate_metadata(sample_metadata()),
                event_date=event, last_verified_at=verification), AS_OF, 30, validate_policy(sample_policy()))
            self.assertEqual(result.criteria[2].value, value)
            self.assertIsNone(result.score)
            self.assertTrue(any(code.startswith("TEMPORAL_BLOCKED:") for code in result.blocking_reasons))

    def test_floor_and_threshold_full_precision_boundaries(self) -> None:
        base = replace(validate_metadata(sample_metadata()), source_type=SourceType.REPUTABLE_SECONDARY)
        policy = validate_policy(sample_policy())
        score = assess_score(base, AS_OF, 30, policy).score
        self.assertIsNotNone(score)
        for threshold, met in ((math.nextafter(score, -math.inf), True), (score, True),
                               (math.nextafter(score, math.inf), False)):
            result = assess_score(base, AS_OF, 30, replace(policy, threshold=threshold))
            self.assertIs(result.threshold_met, met)
            self.assertEqual(result.pass_requirements_met, met)
        for floor, met in ((math.nextafter(0.5, -math.inf), True), (0.5, True),
                           (math.nextafter(0.5, math.inf), False)):
            result = assess_score(base, AS_OF, 30, replace(policy, floors=CriterionValues(1.0, floor, 1.0)))
            self.assertTrue(result.scoring_eligible)
            self.assertEqual(result.score, score)
            self.assertIs(result.criteria[1].floor_met, met)
            self.assertEqual(result.pass_requirements_met, met)

    def test_competitor_requirement_survives_permissive_policy(self) -> None:
        policy = validate_policy(sample_policy())
        policy = replace(policy, floors=CriterionValues(0.0, 0.0, 0.0), threshold=0.0,
                         authority=replace(policy.authority, competitor=1.0))
        case = replace(validate_metadata(sample_metadata()), source_type=SourceType.COMPETITOR)
        result = assess_score(case, AS_OF, 30, policy)
        self.assertEqual(result.score, 1.0)
        self.assertTrue(result.floors_met)
        self.assertTrue(result.threshold_met)
        self.assertTrue(result.original_evidence_required)
        self.assertFalse(result.pass_requirements_met)
        result = assess_score(replace(case, competitor_product_claim=True), AS_OF, 30, policy)
        self.assertIsNone(result.score)

    def test_weight_sum_tolerance_does_not_clip_aggregate(self) -> None:
        policy = validate_policy(sample_policy())
        near = replace(policy, weights=CriterionValues(0.45 + 5e-10, 0.30, 0.25))
        with self.assertRaises(ValidationError) as caught:
            assess_score(validate_metadata(sample_metadata()), AS_OF, 30, near)
        self.assertEqual(caught.exception.issue.code, "AGGREGATE_OUT_OF_RANGE")
        below = replace(policy, weights=CriterionValues(0.45 - 5e-10, 0.30, 0.25), threshold=1.0)
        result = assess_score(validate_metadata(sample_metadata()), AS_OF, 30, below)
        self.assertLess(result.score, 1.0)
        self.assertFalse(result.threshold_met)

    def test_future_regulation_is_scoring_eligible(self) -> None:
        raw = sample_metadata()
        raw.update(content_type="regulation", current_status="adopted_not_applicable",
                   effective_from="2027-01-01", event_date=None)
        result = assess_score(validate_metadata(raw), AS_OF, 30, validate_policy(sample_policy()))
        self.assertEqual(result.score, 1.0)
        self.assertIs(result.temporal.currently_applicable, False)
        self.assertTrue(result.pass_requirements_met)

    def test_output_invariants_and_mismatched_basis(self) -> None:
        policy = validate_policy(sample_policy())
        case = validate_metadata(sample_metadata())
        result = assess_score(case, AS_OF, 30, policy)
        self.assertEqual(result, assess_score(case, AS_OF, 30, policy))
        blocked = assess_score(replace(case, supported=False), AS_OF, 30, policy)
        for changes in ({"score": 0.99}, {"score": True}, {"scoring_eligible": 1},
                        {"criteria": result.criteria[::-1]}, {"blocking_reasons": []},
                        {"hard_checks": blocked.hard_checks}, {"pass_requirements_met": False}):
            with self.assertRaises(ValidationError):
                replace(result, **changes)
        for changes in ({"score": 1.0}, {"scoring_eligible": True}, {"blocking_reasons": ()}):
            with self.assertRaises(ValidationError):
                replace(blocked, **changes)
        for changes in ({"value": math.nan}, {"value": True}, {"value": 1.1},
                        {"floor_met": False}, {"explanation": ""}):
            with self.assertRaises(ValidationError):
                replace(result.criteria[0], **changes)
        with self.assertRaises(FrozenInstanceError):
            setattr(result, "score", 0.0)
        with self.assertRaises(ValidationError):
            assess_score(case, AS_OF, 30, sample_policy())  # type: ignore[arg-type]
