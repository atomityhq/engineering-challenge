import textwrap
from typing import Protocol

from data import EvaluationResult


class Evaluator(Protocol):
    def evaluate(self, text: str) -> EvaluationResult: ...


class Reviser(Protocol):
    def revise(self, text: str, revised_text: str) -> str: ...


class RuleBasedEvaluator:
    def evaluate(self, text: str) -> EvaluationResult:
        if "every post accurate" in text.casefold():
            return EvaluationResult(
                decision="revise",
                reason="The draft claims every post is accurate.",
            )
        return EvaluationResult(
            decision="human_review",
            reason="No overstrong accuracy claim was found.",
        )


class ScriptedEvaluator:
    def __init__(self, results: list[EvaluationResult]):
        self.results = results
        self.calls = 0

    def evaluate(self, text: str) -> EvaluationResult:
        if self.calls >= len(self.results):
            raise ValueError("No scripted result for this evaluation")

        result = self.results[self.calls]
        self.calls += 1
        return result


class ManualEvaluator:
    def evaluate(self, text: str) -> EvaluationResult:
        print("\n" + "=" * 60)
        print("  DRAFT TO EVALUATE")
        print("=" * 60)
        print(textwrap.fill(text, width=76))
        print("=" * 60)

        while True:
            answer = input(
                "\nReady for human review? [y/n]: "
            ).strip().lower()

            if answer in ("y", "yes"):
                return EvaluationResult(
                    decision="human_review",
                    reason="Manual evaluator sent it to human review.",
                )

            if answer in ("n", "no"):
                return EvaluationResult(
                    decision="revise",
                    reason="Manual evaluator requested revision.",
                )

            print("Please enter y or n.")


class PresetReviser:
    def revise(self, text: str, revised_text: str) -> str:
        return revised_text