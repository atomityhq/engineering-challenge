"""Pure evidence checks that retain every defect without scoring or routing."""

from dataclasses import dataclass
from enum import Enum

from ._checks import require_enum, require_text
from .contracts import CurrentStatus, Metadata
from .errors import ValidationError


class CheckStatus(str, Enum):
    """A check passes, fails, or remains unresolved."""

    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class CheckName(str, Enum):
    """Positive names for the mandatory evidence checks."""

    SUPPORT = "material_claim_supported"
    SUPERSESSION = "evidence_not_superseded"
    PROMOTION = "competitor_promotion_absent"
    CONFLICT = "evidence_conflict_absent"


class FindingKind(str, Enum):
    """Classify a problem without choosing the final decision."""

    PROHIBITED = "prohibited"
    REPAIRABLE = "repairable"
    REVIEW = "review"


class FindingCode(str, Enum):
    """Stable evidence finding codes for downstream composition."""

    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    UNRESOLVED_SUPPORT = "UNRESOLVED_SUPPORT"
    SUPERSEDED_EVIDENCE = "SUPERSEDED_EVIDENCE"
    SUPERSESSION_METADATA_CONFLICT = "SUPERSESSION_METADATA_CONFLICT"
    COMPETITOR_PROMOTION = "COMPETITOR_PROMOTION"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"


@dataclass(frozen=True, slots=True)
class MetadataBasis:
    """Expose only the metadata assertions relevant to hard checks."""

    supported: bool
    superseded: bool
    current_status: CurrentStatus
    contradiction: bool
    competitor_product_claim: bool

    def __post_init__(self) -> None:
        require_enum(self.current_status, CurrentStatus, "$.basis.current_status")
        for name in ("supported", "superseded", "contradiction", "competitor_product_claim"):
            if type(getattr(self, name)) is not bool:
                raise ValidationError("INVALID_TYPE", f"$.basis.{name}", "Expected a boolean.")


@dataclass(frozen=True, slots=True)
class HardCheck:
    """Describe one named check and its safe, metadata-derived explanation."""

    name: CheckName
    status: CheckStatus
    reason: str
    basis: MetadataBasis

    def __post_init__(self) -> None:
        require_enum(self.name, CheckName, "$.check.name")
        require_enum(self.status, CheckStatus, "$.check.status")
        require_text(self.reason, "$.check.reason")
        if type(self.basis) is not MetadataBasis:
            raise ValidationError("INVALID_TYPE", "$.check.basis", "Expected a validated metadata basis.")
        expected = _statuses(self.basis)[list(CheckName).index(self.name)]
        if self.status is not expected:
            raise ValidationError("INCONSISTENT_CHECK", "$.check.status", "Status contradicts its metadata basis.")


@dataclass(frozen=True, slots=True)
class Finding:
    """Retain a typed problem, its classification, and explanatory basis."""

    code: FindingCode
    kind: FindingKind
    reason: str
    basis: MetadataBasis

    def __post_init__(self) -> None:
        require_enum(self.code, FindingCode, "$.finding.code")
        require_enum(self.kind, FindingKind, "$.finding.kind")
        require_text(self.reason, "$.finding.reason")
        if type(self.basis) is not MetadataBasis:
            raise ValidationError("INVALID_TYPE", "$.finding.basis", "Expected a validated metadata basis.")
        expected = dict(_finding_specs(self.basis))
        if expected.get(self.code) is not self.kind:
            raise ValidationError("INCONSISTENT_FINDING", "$.finding", "Finding contradicts its metadata basis.")


@dataclass(frozen=True, slots=True)
class HardCheckAssessment:
    """Return all four checks and every finding in deterministic order."""

    checks: tuple[HardCheck, ...]
    findings: tuple[Finding, ...]

    def __post_init__(self) -> None:
        if type(self.checks) is not tuple or len(self.checks) != 4:
            raise ValidationError("INVALID_CHECKS", "$.checks", "Expected all four immutable checks.")
        if any(type(check) is not HardCheck for check in self.checks):
            raise ValidationError("INVALID_TYPE", "$.checks", "Expected validated checks.")
        if tuple(check.name for check in self.checks) != tuple(CheckName):
            raise ValidationError("INVALID_CHECKS", "$.checks", "Expected unique checks in declared order.")
        basis = self.checks[0].basis
        if any(check.basis != basis for check in self.checks):
            raise ValidationError("INCONSISTENT_CHECK", "$.checks", "Checks must share one metadata basis.")
        if type(self.findings) is not tuple or any(type(item) is not Finding for item in self.findings):
            raise ValidationError("INVALID_TYPE", "$.findings", "Expected immutable validated findings.")
        specs = tuple((item.code, item.kind) for item in self.findings)
        if specs != _finding_specs(basis) or any(item.basis != basis for item in self.findings):
            raise ValidationError("INCONSISTENT_FINDINGS", "$.findings", "All metadata-derived findings must be retained in order.")


def _statuses(basis: MetadataBasis) -> tuple[CheckStatus, ...]:
    support = CheckStatus.FAIL if not basis.supported else (
        CheckStatus.UNKNOWN if basis.contradiction else CheckStatus.PASS
    )
    replaced = basis.superseded or basis.current_status is CurrentStatus.SUPERSEDED
    return (
        support,
        CheckStatus.FAIL if replaced else CheckStatus.PASS,
        CheckStatus.FAIL if basis.competitor_product_claim else CheckStatus.PASS,
        CheckStatus.FAIL if basis.contradiction else CheckStatus.PASS,
    )


def _finding_specs(basis: MetadataBasis) -> tuple[tuple[FindingCode, FindingKind], ...]:
    result: list[tuple[FindingCode, FindingKind]] = []
    if not basis.supported:
        result.append((FindingCode.UNSUPPORTED_CLAIM, FindingKind.REPAIRABLE))
    elif basis.contradiction:
        result.append((FindingCode.UNRESOLVED_SUPPORT, FindingKind.REVIEW))
    status_replaced = basis.current_status is CurrentStatus.SUPERSEDED
    if basis.superseded or status_replaced:
        result.append((FindingCode.SUPERSEDED_EVIDENCE, FindingKind.REPAIRABLE))
    if basis.superseded != status_replaced:
        result.append((FindingCode.SUPERSESSION_METADATA_CONFLICT, FindingKind.REVIEW))
    if basis.competitor_product_claim:
        result.append((FindingCode.COMPETITOR_PROMOTION, FindingKind.PROHIBITED))
    if basis.contradiction:
        result.append((FindingCode.CONFLICTING_EVIDENCE, FindingKind.REVIEW))
    return tuple(result)


_CHECK_REASONS = {
    CheckName.SUPPORT: {
        CheckStatus.PASS: "Metadata asserts material support without unresolved contradiction.",
        CheckStatus.FAIL: "Metadata explicitly asserts missing material support.",
        CheckStatus.UNKNOWN: "Asserted support is unresolved because evidence contradicts the claim.",
    },
    CheckName.SUPERSESSION: {
        CheckStatus.PASS: "Neither supersession assertion reports replacement.",
        CheckStatus.FAIL: "At least one supersession assertion reports replacement.",
    },
    CheckName.PROMOTION: {
        CheckStatus.PASS: "Metadata asserts no competitor product promotion.",
        CheckStatus.FAIL: "Metadata asserts prohibited competitor product promotion.",
    },
    CheckName.CONFLICT: {
        CheckStatus.PASS: "Metadata asserts no unresolved evidence conflict.",
        CheckStatus.FAIL: "Metadata asserts unresolved evidence disagreement, not proven falsehood.",
    },
}
_FINDING_REASONS = {
    FindingCode.UNSUPPORTED_CLAIM: "Restore material evidence support before further approval.",
    FindingCode.UNRESOLVED_SUPPORT: "Resolve contradictory evidence before treating support as known.",
    FindingCode.SUPERSEDED_EVIDENCE: "Replace superseded evidence before further approval.",
    FindingCode.SUPERSESSION_METADATA_CONFLICT: "Supersession flag and status disagree; retain the explicit replacement assertion.",
    FindingCode.COMPETITOR_PROMOTION: "Product promotion is prohibited irrespective of source authority or weights.",
    FindingCode.CONFLICTING_EVIDENCE: "Human review must resolve the asserted evidence disagreement.",
}


def assess_hard_checks(metadata: Metadata) -> HardCheckAssessment:
    """Assess all metadata checks without I/O, policy weights, or early exit."""
    if type(metadata) is not Metadata:
        raise ValidationError("INVALID_TYPE", "$.metadata", "Expected validated metadata.")
    basis = MetadataBasis(
        supported=metadata.supported, superseded=metadata.superseded,
        current_status=metadata.current_status, contradiction=metadata.contradiction,
        competitor_product_claim=metadata.competitor_product_claim,
    )
    checks = tuple(
        HardCheck(name, status, _CHECK_REASONS[name][status], basis)
        for name, status in zip(CheckName, _statuses(basis))
    )
    findings = tuple(
        Finding(code, kind, _FINDING_REASONS[code], basis)
        for code, kind in _finding_specs(basis)
    )
    return HardCheckAssessment(checks=checks, findings=findings)
