"""Evaluator / reviser interfaces and deterministic fakes.
Content is treated as data: the fakes never read or act on its text."""
import json
from pathlib import Path
from typing import Protocol, Sequence

from workflow.models import ContentItem, Decision

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class Evaluator(Protocol):
    def evaluate(self, content: ContentItem) -> Decision: ...


class Reviser(Protocol):
    def revise(self, content: ContentItem, attempt: int) -> ContentItem: ...


class ScriptedEvaluator:
    """Returns pre-scripted decisions in order. Deterministic; fails loudly if the
    script runs out (a runaway loop, or an unexpected re-evaluation after resume,
    shows up as an error instead of a silent repeat)."""

    def __init__(self, decisions: Sequence[Decision | str]) -> None:
        self._decisions = [Decision(d) for d in decisions]
        self.calls = 0

    def evaluate(self, content: ContentItem) -> Decision:
        if self.calls >= len(self._decisions):
            raise RuntimeError("ScriptedEvaluator script exhausted")
        decision = self._decisions[self.calls]
        self.calls += 1
        return decision


class FakeReviser:
    """Deterministic revision: appends a marker. Does not interpret the body."""

    def revise(self, content: ContentItem, attempt: int) -> ContentItem:
        return content.model_copy(update={"body": f"{content.body} [revised {attempt}]"})


def load_script(name: str) -> list[str]:
    scripts = json.loads((FIXTURES / "evaluator_scripts.json").read_text(encoding="utf-8"))
    return scripts[name]


def script_names() -> list[str]:
    return list(json.loads((FIXTURES / "evaluator_scripts.json").read_text(encoding="utf-8")))


def load_content(content_id: str) -> ContentItem:
    items = json.loads((FIXTURES / "content_items.json").read_text(encoding="utf-8"))
    for raw in items:
        if raw.get("content_id") == content_id:
            return ContentItem.model_validate(raw)
    raise KeyError(f"unknown content_id: {content_id}")


def load_content_file(path: Path | str) -> ContentItem:
    """Raises pydantic.ValidationError for malformed/incomplete JSON input."""
    return ContentItem.model_validate_json(Path(path).read_text(encoding="utf-8"))
