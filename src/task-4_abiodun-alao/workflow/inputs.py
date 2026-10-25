import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .models import ContentItem, EvaluatorScript

M = TypeVar("M", bound=BaseModel)


class InvalidInputError(Exception):

    def __init__(self, source: str, problems: list[str]):
        self.source = source
        self.problems = problems
        super().__init__(f"Invalid input in {source}: " + "; ".join(problems))


def _load(path: Path, model: type[M]) -> M:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InvalidInputError(str(path), ["file not found"]) from None
    except json.JSONDecodeError as e:
        raise InvalidInputError(str(path), [f"not valid JSON: {e.msg} (line {e.lineno})"]) from None

    try:
        return model.model_validate(raw)
    except ValidationError as e:
        problems = [f"{'.'.join(str(p) for p in err['loc']) or '(root)'}: {err['msg']}" for err in e.errors()]
        raise InvalidInputError(str(path), problems) from None


def load_content(path: Path) -> ContentItem:
    return _load(path, ContentItem)


def load_evaluator_script(path: Path) -> EvaluatorScript:
    return _load(path, EvaluatorScript)