"""Ordered G2 routing and deterministic, label-free report serialization."""

from dataclasses import dataclass, fields, is_dataclass
from datetime import date
from enum import Enum
import json

from ._checks import require_enum, require_text
from .contracts import EvaluationCase
from .errors import ValidationError
from .evaluator import ScoreAssessment, assess_score
from .hard_checks import FindingKind
from .policy import Policy
from .validation import JSONValue


class Decision(str, Enum):
    """Internal next-stage routing, not publication approval."""

    REJECT = "reject"
    REVISE = "revise"
    HUMAN_REVIEW = "human_review"
    PASS = "pass"


class FindingOrigin(str, Enum):
    """Assessment responsible for a retained report finding."""

    HARD_CHECK = "hard_check"
    TEMPORAL = "temporal"
    CRITERION = "criterion"
    POLICY = "policy"


@dataclass(frozen=True, slots=True)
class ReportFinding:
    """Merge duplicate codes while retaining each origin and explanation.

    Basis is the report's immutable score assessment, exposed in serialized
    checks, freshness metadata, criteria, and policy configuration.
    """

    code: str
    kind: FindingKind
    origins: tuple[FindingOrigin, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        require_text(self.code, "$.finding.code")
        require_enum(self.kind, FindingKind, "$.finding.kind")
        if type(self.origins) is not tuple or not self.origins:
            raise ValidationError("INVALID_ORIGINS", "$.finding.origins", "Expected immutable origins.")
        for origin in self.origins:
            require_enum(origin, FindingOrigin, "$.finding.origins")
        if len(set(self.origins)) != len(self.origins):
            raise ValidationError("INVALID_ORIGINS", "$.finding.origins", "Expected unique immutable origins.")
        if type(self.reasons) is not tuple or len(self.reasons) != len(self.origins):
            raise ValidationError("INVALID_REASONS", "$.finding.reasons", "Each origin requires an explanation.")
        for origin, reason in zip(self.origins, self.reasons):
            require_enum(origin, FindingOrigin, "$.finding.origins")
            require_text(reason, "$.finding.reasons")


def _findings(assessment: ScoreAssessment) -> tuple[ReportFinding, ...]:
    result: dict[str, ReportFinding] = {}

    def add(code: str, kind: FindingKind, origin: FindingOrigin, reason: str) -> None:
        previous = result.get(code)
        if previous is None:
            result[code] = ReportFinding(code, kind, (origin,), (reason,))
        else:
            if previous.kind is not kind:
                raise ValidationError("CONFLICTING_CLASSIFICATION", "$.findings", "Duplicate finding classifications disagree.")
            result[code] = ReportFinding(code, kind, previous.origins + (origin,), previous.reasons + (reason,))

    for item in assessment.hard_checks.findings:
        add(item.code.value, item.kind, FindingOrigin.HARD_CHECK, item.reason)
    for item in assessment.temporal.findings:
        add(item.code.value, item.kind, FindingOrigin.TEMPORAL, item.reason)
    for criterion in assessment.criteria:
        if criterion.value is None:
            add("UNKNOWN_CRITERION:" + criterion.name.value, FindingKind.REVIEW,
                FindingOrigin.CRITERION, criterion.explanation)
        elif criterion.floor_met is False:
            add("BELOW_FLOOR:" + criterion.name.value, FindingKind.REVIEW,
                FindingOrigin.CRITERION, "Known criterion value is below its configured floor.")
    if assessment.original_evidence_required:
        add("ORIGINAL_EVIDENCE_REQUIRED", FindingKind.REVIEW, FindingOrigin.POLICY,
            "Competitor-origin information requires independent original evidence regardless of its diagnostic score.")
    if assessment.threshold_met is False:
        add("BELOW_THRESHOLD", FindingKind.REVIEW, FindingOrigin.POLICY,
            "Unrounded diagnostic score is below the configured threshold.")
    return tuple(result.values())


def _route(findings: tuple[ReportFinding, ...]) -> tuple[Decision, str]:
    for kind, decision in ((FindingKind.PROHIBITED, Decision.REJECT),
                           (FindingKind.REPAIRABLE, Decision.REVISE),
                           (FindingKind.REVIEW, Decision.HUMAN_REVIEW)):
        for finding in findings:
            if finding.kind is kind:
                return decision, finding.code
    return Decision.PASS, "PASS_REQUIREMENTS_MET"


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Complete validated report with a stable primary routing reason."""

    case_id: str
    assessment: ScoreAssessment
    findings: tuple[ReportFinding, ...]
    decision: Decision
    primary_reason: str
    gate: str = "G2"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        require_text(self.case_id, "$.case_id")
        require_enum(self.decision, Decision, "$.decision")
        if type(self.assessment) is not ScoreAssessment:
            raise ValidationError("INVALID_TYPE", "$.assessment", "Expected validated score assessment.")
        if type(self.gate) is not str or self.gate != "G2" or type(self.schema_version) is not str or self.schema_version != "1.0":
            raise ValidationError("INVALID_REPORT_VERSION", "$.report", "Expected G2 report schema 1.0.")
        expected_findings = _findings(self.assessment)
        if type(self.findings) is not tuple or any(type(item) is not ReportFinding for item in self.findings) or self.findings != expected_findings:
            raise ValidationError("INCONSISTENT_FINDINGS", "$.findings", "Every assessment finding must be retained with its origins.")
        decision, reason = _route(expected_findings)
        if self.decision is not decision or type(self.primary_reason) is not str or self.primary_reason != reason:
            raise ValidationError("INCONSISTENT_ROUTING", "$.decision", "Routing must follow prohibition, repair, review, then pass.")
        if (decision is Decision.PASS) != self.assessment.pass_requirements_met:
            raise ValidationError("INVALID_PASS", "$.decision", "Passing requires checks, known criteria, floors, threshold, and no policy review requirement.")


def evaluate_case(
    case: EvaluationCase, as_of: date, news_max_event_age_days: int, policy: Policy
) -> EvaluationReport:
    """Evaluate only validated metadata; identity and prose never affect routing."""
    if type(case) is not EvaluationCase:
        raise ValidationError("INVALID_TYPE", "$.case", "Expected a validated label-free case.")
    assessment = assess_score(case.metadata, as_of, news_max_event_age_days, policy)
    findings = _findings(assessment)
    decision, reason = _route(findings)
    return EvaluationReport(case.id, assessment, findings, decision, reason)


def _json_value(value: object) -> JSONValue:
    if isinstance(value, Enum):
        return _json_value(value.value)
    if type(value) is date:
        return value.isoformat()
    if value is None or type(value) in (str, bool, int, float):
        return value  # type: ignore[return-value]
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    raise ValidationError("UNSUPPORTED_SERIALIZATION", "$.report", "Report contains an unsupported value type.")


def report_to_dict(report: EvaluationReport) -> dict[str, JSONValue]:
    """Serialize the explicit report schema, preserving nulls and full precision."""
    if type(report) is not EvaluationReport:
        raise ValidationError("INVALID_TYPE", "$.report", "Expected a validated evaluation report.")
    score = report.assessment
    policy = score.policy
    temporal = score.temporal
    return {
        "case_id": report.case_id, "gate": report.gate, "schema_version": report.schema_version,
        "as_of": temporal.as_of.isoformat(), "policy_version": policy.policy_version,
        "policy_schema_version": policy.schema_version, "weights_version": policy.weights_version,
        "calibration_status": policy.calibration_status, "policy_rationale": policy.rationale,
        "checks": _json_value(score.hard_checks.checks), "criteria": _json_value(score.criteria),
        "freshness": _json_value(temporal), "date_basis": temporal.date_basis,
        "applicability": temporal.applicability.value, "currently_applicable": temporal.currently_applicable,
        "weights": _json_value(policy.weights), "floors": _json_value(policy.floors),
        "authority_mapping": _json_value(policy.authority), "threshold": float(policy.threshold),
        "aggregate_score": score.score, "scoring_eligible": score.scoring_eligible,
        "scoring_blockers": _json_value(score.blocking_reasons), "scoring_explanation": score.explanation,
        "floors_met": score.floors_met, "threshold_met": score.threshold_met,
        "original_evidence_required": score.original_evidence_required,
        "pass_requirements_met": score.pass_requirements_met, "decision": report.decision.value,
        "primary_reason": report.primary_reason, "findings": _json_value(report.findings),
        "evidence_boundary": "Trusted synthetic metadata; not independent verification, calibrated probability, or publication approval.",
    }


def report_to_json(report: EvaluationReport) -> str:
    """Produce deterministic UTF-8-compatible JSON without system timestamps."""
    return json.dumps(report_to_dict(report), ensure_ascii=False, allow_nan=False,
                      sort_keys=True, indent=2) + "\n"
