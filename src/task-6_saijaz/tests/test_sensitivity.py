"""Independent sensitivity arithmetic, fixed-input checks, and rank semantics."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import json
from pathlib import Path
import unittest

from g2 import SourceType, ValidationError
from g2.fixtures import load_fixture, validate_fixture
from g2.policy import CriterionValues, validate_policy
from g2.reports import Decision
from g2.sensitivity import compare_policies, compare_weights, comparison_to_dict, comparison_to_json
from test_fixtures import sample_fixture
from test_policy import sample_policy


class SensitivityTests(unittest.TestCase):
    """Check three preferences without fitting labels or inventing rank reversals."""

    def test_additional_fixture_arithmetic_and_routes(self) -> None:
        inputs = load_fixture(Path(__file__).resolve().parents[1] / "fixtures" / "additional-cases.json")
        policy = validate_policy(sample_policy())
        comparison = compare_weights(inputs, policy)
        self.assertEqual(len(inputs.cases), 3)
        self.assertEqual(tuple(case.metadata.source_type for case in inputs.cases),
                         (SourceType.REPUTABLE_SECONDARY, SourceType.OFFICIAL_INDIRECT, SourceType.PRIMARY_AUTHORITY))
        for index, authority in enumerate((Decimal("0.5"), Decimal("0.75"), Decimal("1"))):
            case = comparison.cases[index]
            expected = (Decimal("0.45") + Decimal("0.30") * authority + Decimal("0.25"),
                        (Decimal("2") + authority) / Decimal("3"),
                        Decimal("0.25") + Decimal("0.50") * authority + Decimal("0.25"))
            for score, independent in zip(case.scores, expected):
                self.assertAlmostEqual(score, float(independent), places=15)
            self.assertEqual(case.ranks, (3 - index,) * 3)
            self.assertEqual(case.decisions, (Decision.PASS, Decision.PASS,
                             Decision.HUMAN_REVIEW if index == 0 else Decision.PASS))
            self.assertEqual(case.routing_changed, index == 0)
            self.assertFalse(case.ranking_changed)
        for run in comparison.runs:
            self.assertTrue(all(report.assessment.scoring_eligible for report in run.reports))
            self.assertEqual(run.policy.threshold, policy.threshold)
            self.assertEqual(run.policy.floors, policy.floors)
            self.assertEqual(run.policy.authority, policy.authority)
        data = comparison_to_dict(comparison)
        self.assertEqual(data["routing_changed_case_ids"], ["secondary-transit-report"])
        self.assertFalse(data["ranking_changed"])
        self.assertEqual(len(data["routing_unchanged_case_ids"]), 2)
        self.assertEqual(json.loads(comparison_to_json(comparison)), data)
        self.assertEqual(comparison_to_json(comparison), comparison_to_json(compare_weights(inputs, policy)))

    def test_exact_ties_and_unranked_blockers(self) -> None:
        inputs = validate_fixture(sample_fixture())
        base = inputs.cases[0]
        inputs = replace(inputs, cases=(replace(base, id="z-tied"), replace(base, id="a-tied"),
            replace(base, id="lower", metadata=replace(base.metadata, source_type=SourceType.REPUTABLE_SECONDARY)),
            replace(base, id="blocked", metadata=replace(base.metadata, event_date=None))))
        comparison = compare_weights(inputs, validate_policy(sample_policy()))
        for run in comparison.runs:
            self.assertEqual(run.ranks, (1, 1, 3, None))
        data = comparison_to_dict(comparison)
        for run in data["runs"]:
            self.assertEqual(run["ranked_case_ids"], ["a-tied", "z-tied", "lower"])
            self.assertEqual(run["tie_groups"], [["a-tied", "z-tied"]])
        blocked = comparison.cases[-1]
        self.assertEqual(blocked.scores, (None,) * 3)
        self.assertEqual(blocked.ranks, (None,) * 3)
        self.assertEqual(blocked.decisions, (Decision.HUMAN_REVIEW,) * 3)

    def test_non_weight_changes_and_duplicate_versions_rejected(self) -> None:
        inputs = validate_fixture(sample_fixture())
        policy = validate_policy(sample_policy())
        alternate = replace(policy, weights_version="other")
        for changed in (replace(alternate, threshold=0.9),
                        replace(alternate, floors=CriterionValues(0.0, 0.0, 0.0)),
                        replace(alternate, authority=replace(policy.authority, competitor=0.1)),
                        replace(alternate, policy_version="different"),
                        replace(alternate, rationale="Different non-weight setting.")):
            with self.assertRaises(ValidationError) as caught:
                compare_policies(inputs, (policy, changed))
            self.assertEqual(caught.exception.issue.code, "NON_WEIGHT_POLICY_CHANGE")
        with self.assertRaises(ValidationError):
            compare_policies(inputs, (policy, policy))
        for policies in ([policy, alternate], (policy,), (policy, {})):
            with self.assertRaises(ValidationError):
                compare_policies(inputs, policies)  # type: ignore[arg-type]

    def test_comparison_construction_invariants(self) -> None:
        inputs = validate_fixture(sample_fixture())
        comparison = compare_weights(inputs, validate_policy(sample_policy()))
        run = comparison.runs[0]
        for changes in ({"ranks": (True,)}, {"ranks": (2,)}, {"ranks": []},
                        {"reports": ()}, {"reports": []}):
            with self.assertRaises(ValidationError):
                replace(run, **changes)
        for changes in ({"runs": ()}, {"runs": list(comparison.runs)},
                        {"inputs": replace(inputs, as_of=inputs.as_of.replace(day=5))}):
            with self.assertRaises(ValidationError):
                replace(comparison, **changes)
        changed_report = replace(run.reports[0], case_id="changed")
        altered_run = replace(run, reports=(changed_report,))
        with self.assertRaises(ValidationError):
            replace(comparison, runs=(altered_run,) + comparison.runs[1:])
        case = comparison.cases[0]
        for changes in ({"ranks": (None,) * 3}, {"scores": (True,) * 3},
                        {"decisions": ("pass",) * 3}, {"scores": []}):
            with self.assertRaises(ValidationError):
                replace(case, **changes)
        with self.assertRaises(FrozenInstanceError):
            setattr(comparison, "runs", ())
        with self.assertRaises(ValidationError):
            comparison_to_dict({})  # type: ignore[arg-type]
