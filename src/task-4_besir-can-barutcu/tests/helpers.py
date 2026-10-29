"""Test doubles shared by several test files."""

from workflow.fakes import ScriptedEvaluator, ScriptedReviser


class CountingEvaluator(ScriptedEvaluator):
    """A scripted evaluator that also counts how often it is called."""

    def __init__(self, scenario):
        super().__init__(scenario)
        self.calls = 0

    def evaluate(self, item, step):
        self.calls += 1
        return super().evaluate(item, step)


class CountingReviser(ScriptedReviser):
    """A scripted reviser that also counts how often it is called."""

    def __init__(self, scenario):
        super().__init__(scenario)
        self.calls = 0

    def revise(self, item, step):
        self.calls += 1
        return super().revise(item, step)
