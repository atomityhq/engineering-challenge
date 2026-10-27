"""Immutable, uncalibrated scoring preferences with strict numerical checks."""

from dataclasses import dataclass
import math
from pathlib import Path

from ._checks import require_text
from .errors import ValidationError
from .validation import parse_json, require_object

WEIGHT_SUM_TOLERANCE: float = 1e-9
CRITERIA: tuple[str, ...] = ("evidence_support", "source_authority", "temporal_validity")


def _nonnegative_number(value: object, path: str) -> float:
    if type(value) not in (int, float):
        raise ValidationError("INVALID_TYPE", path, "Expected a non-boolean number.")
    try:
        number = float(value)
    except OverflowError:
        raise ValidationError("INVALID_NUMBER", path, "Expected a finite nonnegative number.") from None
    if not math.isfinite(number) or number < 0:
        raise ValidationError("INVALID_NUMBER", path, "Expected a finite nonnegative number.")
    return number


def _unit_number(value: object, path: str) -> float:
    number = _nonnegative_number(value, path)
    if number > 1:
        raise ValidationError("INVALID_NUMBER", path, "Expected a number in [0, 1].")
    return number


@dataclass(frozen=True, slots=True)
class CriterionValues:
    """Hold exact criterion keys for weight or floor configuration."""

    evidence_support: float
    source_authority: float
    temporal_validity: float

    def __post_init__(self) -> None:
        for name in CRITERIA:
            _nonnegative_number(getattr(self, name), f"$.{name}")

    def values(self) -> tuple[float, float, float]:
        """Return values in stable evidence/authority/temporal order."""
        return (self.evidence_support, self.source_authority, self.temporal_validity)


@dataclass(frozen=True, slots=True)
class AuthorityMapping:
    """Hold provisional authority values for every recognized source category."""

    primary_authority: float
    official_indirect: float
    reputable_secondary: float
    competitor: float
    unknown: None

    def __post_init__(self) -> None:
        for name in AUTHORITY_KEYS[:-1]:
            _unit_number(getattr(self, name), f"$.authority.{name}")
        if self.unknown is not None:
            raise ValidationError("INVALID_AUTHORITY_UNKNOWN", "$.authority.unknown", "Unknown authority must remain null.")


AUTHORITY_KEYS: tuple[str, ...] = (
    "primary_authority", "official_indirect", "reputable_secondary", "competitor", "unknown"
)
POLICY_FIELDS: tuple[str, ...] = (
    "schema_version", "policy_version", "weights_version", "calibration_status",
    "rationale", "weights", "floors", "threshold", "authority",
)


@dataclass(frozen=True, slots=True)
class Policy:
    """Validate preferences without changing fixture-owned temporal rules."""

    schema_version: str
    policy_version: str
    weights_version: str
    calibration_status: str
    rationale: str
    weights: CriterionValues
    floors: CriterionValues
    threshold: float
    authority: AuthorityMapping

    def __post_init__(self) -> None:
        if type(self.schema_version) is not str or self.schema_version != "1.0":
            raise ValidationError("UNSUPPORTED_SCHEMA", "$.schema_version", "Expected policy schema 1.0.")
        for name in ("policy_version", "weights_version", "rationale"):
            require_text(getattr(self, name), f"$.{name}")
        if type(self.calibration_status) is not str or self.calibration_status != "uncalibrated":
            raise ValidationError("INVALID_CALIBRATION", "$.calibration_status", "Only uncalibrated prototype policies are supported.")
        for name in ("weights", "floors"):
            if type(getattr(self, name)) is not CriterionValues:
                raise ValidationError("INVALID_TYPE", f"$.{name}", "Expected validated criterion values.")
        for name in CRITERIA:
            _unit_number(getattr(self.floors, name), f"$.floors.{name}")
        try:
            total = math.fsum(self.weights.values())
        except OverflowError:
            raise ValidationError("INVALID_WEIGHT_SUM", "$.weights", "Weight sum exceeds the supported range.") from None
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=WEIGHT_SUM_TOLERANCE):
            raise ValidationError("INVALID_WEIGHT_SUM", "$.weights", "Weights must sum to one within absolute tolerance 1e-9.")
        _unit_number(self.threshold, "$.threshold")
        if type(self.authority) is not AuthorityMapping:
            raise ValidationError("INVALID_TYPE", "$.authority", "Expected a validated authority mapping.")


def _criterion_values(value: object, path: str) -> CriterionValues:
    data = require_object(value, CRITERIA, path)
    checker = _unit_number if path == "$.floors" else _nonnegative_number
    return CriterionValues(
        evidence_support=checker(data["evidence_support"], f"{path}.evidence_support"),
        source_authority=checker(data["source_authority"], f"{path}.source_authority"),
        temporal_validity=checker(data["temporal_validity"], f"{path}.temporal_validity"),
    )


def validate_policy(value: object) -> Policy:
    """Parse exact policy fields; reject coercion, unknown keys, and invalid sums."""
    data = require_object(value, POLICY_FIELDS, "$")
    authority = require_object(data["authority"], AUTHORITY_KEYS, "$.authority")
    if authority["unknown"] is not None:
        raise ValidationError("INVALID_AUTHORITY_UNKNOWN", "$.authority.unknown", "Unknown authority must remain null.")
    return Policy(
        schema_version=require_text(data["schema_version"], "$.schema_version"),
        policy_version=require_text(data["policy_version"], "$.policy_version"),
        weights_version=require_text(data["weights_version"], "$.weights_version"),
        calibration_status=require_text(data["calibration_status"], "$.calibration_status"),
        rationale=require_text(data["rationale"], "$.rationale"),
        weights=_criterion_values(data["weights"], "$.weights"),
        floors=_criterion_values(data["floors"], "$.floors"),
        threshold=_unit_number(data["threshold"], "$.threshold"),
        authority=AuthorityMapping(
            primary_authority=_unit_number(authority["primary_authority"], "$.authority.primary_authority"),
            official_indirect=_unit_number(authority["official_indirect"], "$.authority.official_indirect"),
            reputable_secondary=_unit_number(authority["reputable_secondary"], "$.authority.reputable_secondary"),
            competitor=_unit_number(authority["competitor"], "$.authority.competitor"),
            unknown=None,
        ),
    )


def load_policy(path: Path) -> Policy:
    """Read strict UTF-8 JSON policy with safe, explicit I/O errors."""
    if not isinstance(path, Path):
        raise ValidationError("INVALID_TYPE", "$", "Expected a filesystem Path.")
    if "\x00" in str(path):
        raise ValidationError("INVALID_PATH", "$", "Filesystem paths must not contain null bytes.")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError:
        raise ValidationError("INVALID_ENCODING", "$", "Expected UTF-8 policy text.") from None
    except OSError:
        raise ValidationError("POLICY_READ_ERROR", "$", "Could not read policy file.") from None
    return validate_policy(parse_json(text))
