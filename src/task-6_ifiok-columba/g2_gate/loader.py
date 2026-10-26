"""Load and validate a fixture. `expected_decision` is test-only and is removed here,
so the evaluator can never see it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import Fixture


class FixtureError(ValueError):
    """Raised for any malformed fixture, with a readable message."""


def load_fixture(path: Path | str) -> tuple[Fixture, dict[str, str]]:
    """Return (validated fixture, {case_id: expected_decision}).

    The expectations come back separately and are meant for tests only.
    """
    try:
        raw: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FixtureError(f"fixture not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FixtureError(f"fixture is not valid JSON: {exc}") from exc
    return parse_fixture(raw)


def parse_fixture(raw: Any) -> tuple[Fixture, dict[str, str]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("cases"), list):
        raise FixtureError("fixture must be an object with a 'cases' list")

    expectations: dict[str, str] = {}
    cleaned_cases = []
    for case in raw["cases"]:
        if not isinstance(case, dict):
            raise FixtureError("every case must be an object")
        case = dict(case)
        expected = case.pop("expected_decision", None)
        if expected is not None and isinstance(case.get("id"), str):
            expectations[case["id"]] = expected
        cleaned_cases.append(case)

    try:
        fixture = Fixture.model_validate({**raw, "cases": cleaned_cases})
    except ValidationError as exc:
        raise FixtureError(_summarise(exc)) from exc
    return fixture, expectations


def merge_fixtures(fixtures: list[Fixture]) -> Fixture:
    """Combine fixtures that share the same as_of date and demo policy."""
    first = fixtures[0]
    for other in fixtures[1:]:
        if other.as_of != first.as_of or other.demo_policy != first.demo_policy:
            raise FixtureError("cannot merge fixtures with a different as_of or demo_policy")
    try:
        return Fixture.model_validate(
            {
                **first.model_dump(mode="json"),
                "cases": [c.model_dump(mode="json") for f in fixtures for c in f.cases],
            }
        )
    except ValidationError as exc:
        raise FixtureError(_summarise(exc)) from exc


def _summarise(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        where = ".".join(str(p) for p in err["loc"]) or "fixture"
        lines.append(f"{where}: {err['msg']}")
    return "invalid fixture:\n  " + "\n  ".join(lines)
