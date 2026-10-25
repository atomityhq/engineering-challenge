from typing import Protocol

from .models import ContentItem, EvaluationResult, EvaluatorScript


class Evaluator(Protocol):
    def evaluate(self, content: ContentItem, attempt: int) -> EvaluationResult: ...


class Reviser(Protocol):
    def revise(self, content: ContentItem, feedback: list[str], attempt: int) -> ContentItem: ...


class ScriptedEvaluator:
    def __init__(self, script: EvaluatorScript):
        self.script = script
        self.calls: list[int] = []

    def evaluate(self, content: ContentItem, attempt: int) -> EvaluationResult:
        self.calls.append(attempt)
        index = min(attempt, len(self.script.responses)) - 1
        return self.script.responses[index]


class FakeReviser:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def revise(self, content: ContentItem, feedback: list[str], attempt: int) -> ContentItem:
        self.calls.append(attempt)
        note = f"\n\n[Revision {attempt}] Addressed: " + ("; ".join(feedback) or "general feedback")
        return content.model_copy(update={"body": content.body + note})