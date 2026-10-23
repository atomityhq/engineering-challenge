import json
from pathlib import Path

import pytest

from review_workflow.fakes import ScriptedEvaluator
from review_workflow.service import ReviewWorkflow

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
CONTENT = json.loads((FIXTURES / "content" / "content-001.json").read_text())


def evaluator_ref(name: str) -> str:
    return str(FIXTURES / "evaluator" / f"{name}.json")


class CountingEvaluatorFactory:
    """Wraps the scripted evaluator and counts real evaluate() calls."""

    def __init__(self):
        self.calls = 0

    def __call__(self, ref: str):
        inner = ScriptedEvaluator.from_file(ref)
        factory = self

        class _Counting:
            def evaluate(self, content, revision_count):
                factory.calls += 1
                return inner.evaluate(content, revision_count)

        return _Counting()


def event_names(snap) -> list[str]:
    return [e.event for e in snap.events]


@pytest.fixture
def db(tmp_path) -> Path:
    return tmp_path / "checkpoints.sqlite"


@pytest.fixture
def counter() -> CountingEvaluatorFactory:
    return CountingEvaluatorFactory()


@pytest.fixture
def wf(db, counter):
    with ReviewWorkflow(db, evaluator_factory=counter) as w:
        yield w
