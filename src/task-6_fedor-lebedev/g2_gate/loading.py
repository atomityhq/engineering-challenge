"""Load and validate fixtures and configuration files.

Every failure surfaces as :class:`InputValidationError` with the file and the
offending field paths, so malformed input fails predictably and early.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .config import G2Policy, WeightSets
from .models import G2Fixture
from .paths import POLICY_CONFIG, WEIGHTS_CONFIG, display_path

M = TypeVar("M", bound=BaseModel)


class InputValidationError(ValueError):
    """A fixture or configuration file is missing, unreadable or invalid."""

    def __init__(self, source: str, problems: List[str]):
        self.source = source
        self.problems = problems
        super().__init__(f"{source}: " + "; ".join(problems))


def _format_errors(error: ValidationError) -> List[str]:
    problems = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        problems.append(f"{location}: {item['msg']}")
    return problems


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    # json.loads would silently keep the last value; a repeated key is ambiguous input.
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _load(path: Path, model: Type[M]) -> M:
    source = display_path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InputValidationError(source, [f"cannot read file: {exc.strerror or exc}"]) from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputValidationError(source, [f"file is not valid UTF-8 (byte offset {exc.start})"]) from exc
    try:
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise InputValidationError(source, [f"invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}"]) from exc
    except _DuplicateKeyError as exc:
        raise InputValidationError(source, [f"duplicate JSON key {exc.args[0]!r}"]) from exc
    except RecursionError as exc:
        raise InputValidationError(source, ["JSON is nested too deeply to parse"]) from exc
    except ValueError as exc:
        # e.g. an integer literal beyond Python's int-string conversion limit.
        raise InputValidationError(source, [f"JSON cannot be parsed: {exc}"]) from exc
    return validate(data, model, source)


def validate(data: object, model: Type[M], source: str) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise InputValidationError(source, _format_errors(exc)) from exc


def load_fixture(path: Path) -> G2Fixture:
    return _load(Path(path), G2Fixture)


def load_policy(path: Path = POLICY_CONFIG) -> G2Policy:
    return _load(Path(path), G2Policy)


def load_weight_sets(path: Path = WEIGHTS_CONFIG) -> WeightSets:
    return _load(Path(path), WeightSets)
