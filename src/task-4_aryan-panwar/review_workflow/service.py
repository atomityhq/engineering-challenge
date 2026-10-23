"""Start / resume / inspect runs. Owns the SQLite checkpointer and the idempotency guards."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import ValidationError

from .fakes import AppendingReviser, Evaluator, Reviser, ScriptedEvaluator
from .graph import build_graph
from .models import ContentItem, HumanDecision, WorkflowConfig, WorkflowSnapshot


class WorkflowError(Exception):
    pass


class WorkflowInputError(WorkflowError):
    """Invalid content, evaluator fixture or config. Raised before any node runs."""


class RunNotFound(WorkflowError):
    pass


class RunAlreadyExists(WorkflowError):
    pass


@dataclass
class ResumeOutcome:
    action: Literal["resumed", "already_finished", "decision_required"]
    snapshot: WorkflowSnapshot


class ReviewWorkflow:
    def __init__(
        self,
        db_path: str | Path,
        evaluator_factory: Callable[[str], Evaluator] = ScriptedEvaluator.from_file,
        reviser: Reviser | None = None,
    ):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._evaluator_factory = evaluator_factory
        graph = build_graph(evaluator_factory, reviser or AppendingReviser())
        self.app = graph.compile(checkpointer=SqliteSaver(self._conn))

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ReviewWorkflow":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @staticmethod
    def _cfg(run_id: str) -> dict:
        return {"configurable": {"thread_id": run_id}}

    def start(
        self,
        content: dict,
        evaluator_ref: str,
        run_id: str | None = None,
        config: WorkflowConfig | None = None,
    ) -> WorkflowSnapshot:
        try:
            item = ContentItem.model_validate(content)
            config = config or WorkflowConfig()
            self._evaluator_factory(evaluator_ref)  # fail fast on a bad evaluator fixture
        except (ValidationError, ValueError, OSError) as exc:
            raise WorkflowInputError(str(exc)) from exc

        run_id = run_id or item.content_id
        if self.app.get_state(self._cfg(run_id)).values:
            raise RunAlreadyExists(f"run '{run_id}' already exists; use resume")

        initial = {
            "run_id": run_id,
            "content_id": item.content_id,
            "content": item.model_dump(),
            "evaluator_ref": evaluator_ref,
            "max_revisions": config.max_revisions,
            "status": "evaluating",
            "revision_count": 0,
            "evaluation_result": None,
            "review": None,
            "events": [],
        }
        self.app.invoke(initial, self._cfg(run_id), durability="sync")
        return self.snapshot(run_id)

    def resume(self, run_id: str, decision: HumanDecision | None = None) -> ResumeOutcome:
        state = self.app.get_state(self._cfg(run_id))
        if not state.values:
            raise RunNotFound(f"no saved run '{run_id}'")
        if not state.next:
            # Already terminal: do nothing, so a repeated approval cannot complete twice.
            return ResumeOutcome("already_finished", self.snapshot(run_id))
        if "await_review" in state.next:
            if decision is None:
                return ResumeOutcome("decision_required", self.snapshot(run_id))
            self.app.invoke(Command(resume=decision.model_dump()), self._cfg(run_id), durability="sync")
        else:
            # Process died mid-run: continue from the last completed step's checkpoint.
            self.app.invoke(None, self._cfg(run_id), durability="sync")
        return ResumeOutcome("resumed", self.snapshot(run_id))

    def snapshot(self, run_id: str) -> WorkflowSnapshot:
        state = self.app.get_state(self._cfg(run_id))
        if not state.values:
            raise RunNotFound(f"no saved run '{run_id}'")
        v = state.values
        return WorkflowSnapshot(
            run_id=v["run_id"],
            content_id=v["content_id"],
            status=v["status"],
            revision_count=v["revision_count"],
            max_revisions=v["max_revisions"],
            evaluation_result=v["evaluation_result"],
            review=v["review"],
            content=v["content"],
            evaluator_ref=v["evaluator_ref"],
            next_nodes=list(state.next),
            checkpoint_id=state.config["configurable"].get("checkpoint_id"),
            events=v["events"],
        )
