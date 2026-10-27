"""Test-only expected-label extraction; never imported by evaluator inputs."""

from dataclasses import dataclass
from enum import Enum

from ._checks import require_enum, require_text
from .errors import ValidationError
from .fixtures import validate_fixture
from .validation import require_object


class ExpectedDecision(str, Enum):
    """Allowed acceptance labels, not evaluation policy or calibration data."""

    PASS = "pass"
    REVISE = "revise"
    HUMAN_REVIEW = "human_review"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ExpectedOutcome:
    """Bind an acceptance label to a case ID outside evaluation inputs."""

    case_id: str
    decision: ExpectedDecision

    def __post_init__(self) -> None:
        require_text(self.case_id, "$.id")
        require_enum(self.decision, ExpectedDecision, "$.expected_decision")


def extract_expected_outcomes(value: object) -> tuple[ExpectedOutcome, ...]:
    """Validate a test fixture and require a recognized label for each case."""
    inputs = validate_fixture(value)
    data = require_object(
        value, ("schema_version", "synthetic", "as_of", "instructions", "demo_policy", "cases"), "$"
    )
    raw_cases = data["cases"]
    if type(raw_cases) is not list:
        raise ValidationError("INVALID_CASES", "$.cases", "Expected a case array.")
    outcomes: list[ExpectedOutcome] = []
    for index, case in enumerate(inputs.cases):
        path = f"$.cases[{index}]"
        item = require_object(raw_cases[index], ("id", "statement", "metadata", "expected_decision"), path)
        text = require_text(item["expected_decision"], f"{path}.expected_decision")
        try:
            decision = ExpectedDecision(text)
        except ValueError:
            raise ValidationError("INVALID_ENUM", f"{path}.expected_decision", "Unrecognized acceptance label.") from None
        outcomes.append(ExpectedOutcome(case_id=case.id, decision=decision))
    return tuple(outcomes)
