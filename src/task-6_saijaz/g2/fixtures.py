"""Load synthetic fixture inputs without returning labels or instruction prose."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ._checks import require_date, require_text
from .contracts import EvaluationCase
from .errors import ValidationError
from .validation import parse_date, parse_json, require_object, validate_case

_ENVELOPE_FIELDS = (
    "schema_version", "synthetic", "as_of", "instructions", "demo_policy", "cases"
)
_POLICY_FIELDS = (
    "news_max_event_age_days", "regulation_rule",
    "unknown_required_temporal_metadata", "weights_and_threshold",
)


@dataclass(frozen=True, slots=True)
class FixtureInputs:
    """Carry validated assessment context and label-free cases only."""

    schema_version: str
    synthetic: bool
    as_of: date
    news_max_event_age_days: int
    cases: tuple[EvaluationCase, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not str or self.schema_version != "1.0":
            raise ValidationError("UNSUPPORTED_SCHEMA", "$.schema_version", "Expected schema 1.0.")
        if self.synthetic is not True:
            raise ValidationError("INVALID_SYNTHETIC", "$.synthetic", "Expected synthetic true.")
        require_date(self.as_of, "$.as_of")
        if self.as_of is None:
            raise ValidationError("INVALID_TYPE", "$.as_of", "Assessment date is required.")
        if type(self.news_max_event_age_days) is not int or self.news_max_event_age_days < 0:
            raise ValidationError("INVALID_EVENT_AGE", "$.demo_policy.news_max_event_age_days", "Expected a nonnegative integer.")
        if type(self.cases) is not tuple or not self.cases:
            raise ValidationError("INVALID_CASES", "$.cases", "Expected non-empty immutable cases.")
        seen: set[str] = set()
        for index, case in enumerate(self.cases):
            if type(case) is not EvaluationCase:
                raise ValidationError("INVALID_TYPE", f"$.cases[{index}]", "Expected a validated case.")
            if case.id in seen:
                raise ValidationError("DUPLICATE_ID", f"$.cases[{index}].id", "Case identifiers must be unique.")
            seen.add(case.id)


def _case_object(value: object, path: str) -> dict[str, object]:
    """Recognize an optional test label without inspecting its value."""
    if type(value) is dict and "expected_decision" in value:
        return require_object(value, ("id", "statement", "metadata", "expected_decision"), path)
    return require_object(value, ("id", "statement", "metadata"), path)


def validate_fixture(value: object) -> FixtureInputs:
    """Validate the envelope and exclude labels and informational prose.

    Expected labels are deliberately not validated here: their values cannot
    affect production adaptation. Test-only validation lives in g2.testing.
    """
    data = require_object(value, _ENVELOPE_FIELDS, "$")
    require_text(data["instructions"], "$.instructions")
    policy = require_object(data["demo_policy"], _POLICY_FIELDS, "$.demo_policy")
    for name in ("regulation_rule", "weights_and_threshold"):
        require_text(policy[name], f"$.demo_policy.{name}")
    if type(policy["unknown_required_temporal_metadata"]) is not str or policy["unknown_required_temporal_metadata"] != "human_review":
        raise ValidationError("UNSUPPORTED_DEMO_POLICY", "$.demo_policy.unknown_required_temporal_metadata", "Expected human_review convention.")
    raw_cases = data["cases"]
    if type(raw_cases) is not list or not raw_cases:
        raise ValidationError("INVALID_CASES", "$.cases", "Expected a non-empty case array.")
    cases: list[EvaluationCase] = []
    for index, raw in enumerate(raw_cases):
        path = f"$.cases[{index}]"
        item = _case_object(raw, path)
        cases.append(validate_case({name: item[name] for name in ("id", "statement", "metadata")}, path))
    schema_version = require_text(data["schema_version"], "$.schema_version")
    if data["synthetic"] is not True:
        raise ValidationError("INVALID_SYNTHETIC", "$.synthetic", "Expected synthetic true.")
    as_of = parse_date(data["as_of"], "$.as_of")
    if as_of is None:
        raise ValidationError("INVALID_TYPE", "$.as_of", "Assessment date is required.")
    event_age = policy["news_max_event_age_days"]
    if type(event_age) is not int or event_age < 0:
        raise ValidationError("INVALID_EVENT_AGE", "$.demo_policy.news_max_event_age_days", "Expected a nonnegative integer.")
    return FixtureInputs(
        schema_version=schema_version,
        synthetic=True,
        as_of=as_of,
        news_max_event_age_days=event_age,
        cases=tuple(cases),
    )


def load_fixture(path: Path) -> FixtureInputs:
    """Read UTF-8 fixture data in place; preserve safe validation/I/O errors."""
    if not isinstance(path, Path):
        raise ValidationError("INVALID_TYPE", "$", "Expected a filesystem Path.")
    if "\x00" in str(path):
        raise ValidationError("INVALID_PATH", "$", "Filesystem paths must not contain null bytes.")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError:
        raise ValidationError("INVALID_ENCODING", "$", "Expected UTF-8 fixture text.") from None
    except OSError:
        raise ValidationError("FIXTURE_READ_ERROR", "$", "Could not read fixture file.") from None
    return validate_fixture(parse_json(text))
