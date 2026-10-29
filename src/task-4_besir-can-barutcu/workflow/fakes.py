"""Evaluator and reviser interfaces, with deterministic scripted fakes.

The graph depends only on the abstract classes, so a real model can replace a fake later.
The fakes choose their answer by `step` (the saved revision_count), never by an
in-memory call counter, so a restarted process gets the same answers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import ContentItem, EvalResult, Scenario


class ScriptExhaustedError(RuntimeError):
    """The scenario has no scripted answer or text for the requested step."""


class Evaluator(ABC):
    @abstractmethod
    def evaluate(self, item: ContentItem, step: int) -> EvalResult:
        """Return a decision for `item` after `step` revisions."""


class Reviser(ABC):
    @abstractmethod
    def revise(self, item: ContentItem, step: int) -> ContentItem:
        """Return a new item for revision number `step + 1`. Must not change `item`."""


class ScriptedEvaluator(Evaluator):
    """Returns `scenario.responses[step]`. It does not read the content."""

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario

    def evaluate(self, item: ContentItem, step: int) -> EvalResult:
        responses = self.scenario.responses
        if not 0 <= step < len(responses):
            raise ScriptExhaustedError(
                f"scenario {self.scenario.id!r} has no evaluator response for step {step}"
            )
        return responses[step].model_copy()


class ScriptedReviser(Reviser):
    """Replaces the body with `scenario.revised_content[step]`."""

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario

    def revise(self, item: ContentItem, step: int) -> ContentItem:
        texts = self.scenario.revised_content
        if not 0 <= step < len(texts):
            raise ScriptExhaustedError(
                f"scenario {self.scenario.id!r} has no revised text for step {step}"
            )
        return item.model_copy(update={"body": texts[step]})
