"""Typed contracts for the workflow: content items, evaluator scripts and graph state.

Pydantic validates data where it enters the program (the fixture files).
Inside the graph, the state is a plain TypedDict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
CONTENT_FILE = FIXTURES_DIR / "content.json"
SCENARIOS_FILE = FIXTURES_DIR / "scenarios.json"

DEFAULT_MAX_REVISIONS = 2

Decision = Literal["revise", "human_review"]
Status = Literal["EVALUATING", "WAITING_FOR_REVIEW", "COMPLETED", "REVISION_LIMIT_REACHED"]


class FixtureNotFoundError(LookupError):
    """A content id or scenario id does not exist in its fixture file."""


class ContentItem(BaseModel):
    """One mock content item. The body is data only and is never executed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class EvalResult(BaseModel):
    """One scripted evaluator answer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Decision
    reason: str = Field(min_length=1)


class Scenario(BaseModel):
    """A script for the fake evaluator and fake reviser.

    `responses[i]` is the answer to the evaluation after i revisions.
    `revised_content[i]` is the body produced by revision i + 1.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    responses: list[EvalResult] = Field(min_length=1)
    revised_content: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _revised_texts_are_real_changes(self) -> Scenario:
        for i, text in enumerate(self.revised_content):
            if not text:
                raise ValueError(f"revised_content[{i}] is empty")
            if i > 0 and text == self.revised_content[i - 1]:
                raise ValueError(f"revised_content[{i}] is the same as revised_content[{i - 1}]")
        return self


class ScenarioFile(BaseModel):
    """The whole scenarios.json file. Every scenario in it must be valid."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1)
    synthetic: bool
    scenarios: list[Scenario] = Field(min_length=1)

    @model_validator(mode="after")
    def _scenario_ids_are_unique(self) -> ScenarioFile:
        ids = [s.id for s in self.scenarios]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate scenario ids: {duplicates}")
        return self


class WorkflowState(TypedDict):
    """The data LangGraph carries between nodes and saves in each checkpoint."""

    run_id: str
    content_id: str
    scenario_id: str
    title: str
    body: str
    revision_count: int
    max_revisions: int
    decision: Decision | None
    reason: str | None
    status: Status


def load_content(content_id: str, path: Path = CONTENT_FILE) -> ContentItem:
    """Find one item by id and validate only that item.

    The file holds a malformed item on purpose, so the file is not validated as a whole.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    for item in raw.get("items", []):
        if isinstance(item, dict) and item.get("content_id") == content_id:
            return ContentItem.model_validate(item)
    raise FixtureNotFoundError(f"no content item with content_id {content_id!r} in {path.name}")


def load_scenarios(path: Path = SCENARIOS_FILE) -> ScenarioFile:
    return ScenarioFile.model_validate_json(path.read_text(encoding="utf-8"))


def load_scenario(scenario_id: str, path: Path = SCENARIOS_FILE) -> Scenario:
    for scenario in load_scenarios(path).scenarios:
        if scenario.id == scenario_id:
            return scenario
    raise FixtureNotFoundError(f"no scenario with id {scenario_id!r} in {path.name}")


def check_run_inputs(
    item: ContentItem, scenario: Scenario, max_revisions: int = DEFAULT_MAX_REVISIONS
) -> None:
    """Checks that need both the content item and the scenario, run before the graph starts."""
    if max_revisions < 0:
        raise ValueError("max_revisions must be 0 or more")

    if scenario.revised_content and scenario.revised_content[0] == item.body:
        raise ValueError(f"scenario {scenario.id!r}: the first revised text is the same as the original body")

    revise_answers = sum(1 for r in scenario.responses if r.decision == "revise")
    needed = min(revise_answers, max_revisions)
    if len(scenario.revised_content) < needed:
        raise ValueError(
            f"scenario {scenario.id!r} needs {needed} revised text(s) "
            f"but has {len(scenario.revised_content)}"
        )
