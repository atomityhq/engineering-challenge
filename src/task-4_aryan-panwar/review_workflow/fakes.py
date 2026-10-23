"""Replaceable evaluator/reviser interfaces and their deterministic offline fakes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models import ContentItem, EvaluationResult, EvaluatorScript


class Evaluator(Protocol):
    def evaluate(self, content: ContentItem, revision_count: int) -> EvaluationResult: ...


class Reviser(Protocol):
    def revise(self, content: ContentItem, feedback: str, attempt: int) -> ContentItem: ...


class ScriptedEvaluator:
    """Returns the response for the current revision count.

    The answer depends only on `revision_count`, never on call order or content text, so
    re-executing a node (e.g. after a crash) yields the same decision.
    """

    def __init__(self, script: EvaluatorScript):
        self._responses = script.responses

    @classmethod
    def from_file(cls, path: str | Path) -> "ScriptedEvaluator":
        return cls(EvaluatorScript.model_validate(json.loads(Path(path).read_text())))

    def evaluate(self, content: ContentItem, revision_count: int) -> EvaluationResult:
        return self._responses[min(revision_count, len(self._responses) - 1)]


class AppendingReviser:
    """Deterministic stand-in for a content-generation step."""

    def revise(self, content: ContentItem, feedback: str, attempt: int) -> ContentItem:
        return content.model_copy(
            update={"body": f"{content.body}\n\n[revision {attempt}] addressed: {feedback}"}
        )
