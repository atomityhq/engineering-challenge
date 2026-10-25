import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langgraph.types import Command

from .components import FakeReviser, ScriptedEvaluator
from .graph import build_graph
from .inputs import InvalidInputError, load_evaluator_script
from .models import TERMINAL_STATUSES, ContentItem, ReviewDecision, Status, WorkflowState
from .runs import RunRecord
from .storage import open_storage

REVIEW_NODE = "human_review"


class RunNotFoundError(Exception):
    pass


class RunExistsError(Exception):
    pass


class NotResumableError(Exception):
    pass


@dataclass
class RunView:
    run_id: str
    status: Status
    revision_count: int
    evaluation_count: int
    paused_for_review: bool
    stop_reason: str | None
    new_events: list[dict[str, Any]] = field(default_factory=list)
    already_finished: bool = False


class WorkflowService:
    def __init__(self, db_path: Path, fixtures_dir: Path):
        self.storage = open_storage(db_path)
        self.fixtures_dir = fixtures_dir

    def close(self) -> None:
        self.storage.close()

    # ── helpers ──

    def _graph_for(self, scenario: str):
        available = sorted(p.stem for p in (self.fixtures_dir / "evaluator").glob("*.json"))
        if scenario not in available:
            raise InvalidInputError(f"--scenario {scenario}", [f"unknown scenario; choose one of: {', '.join(available)}"])
        script = load_evaluator_script(self.fixtures_dir / "evaluator" / f"{scenario}.json")
        return build_graph(ScriptedEvaluator(script), FakeReviser(), self.storage.events, self.storage.checkpointer)

    @staticmethod
    def _config(run_id: str) -> dict:
        return {"configurable": {"thread_id": run_id}}

    def _view(self, app, run_id: str, since_seq: int, already_finished: bool = False) -> RunView:
        snapshot = app.get_state(self._config(run_id))
        state = WorkflowState.model_validate(snapshot.values)
        return RunView(
            run_id=run_id,
            status=state.status,
            revision_count=state.revision_count,
            evaluation_count=state.evaluation_count,
            paused_for_review=snapshot.next == (REVIEW_NODE,),
            stop_reason=state.stop_reason,
            new_events=self.storage.events.for_run(run_id, after_seq=since_seq),
            already_finished=already_finished,
        )

    def _record_checkpoint_if_paused(self, app, run_id: str) -> None:
        snapshot = app.get_state(self._config(run_id))
        if snapshot.next == (REVIEW_NODE,):
            version = snapshot.values["checkpoint_version"]
            self.storage.events.record(
                run_id, "checkpoint_saved", key=f"checkpoint_saved:{version}",
                checkpoint_version=version, checkpoint_id=snapshot.config["configurable"]["checkpoint_id"],
                next_node=REVIEW_NODE,
            )

    def start(self, content: ContentItem, scenario: str, run_id: str, max_revisions: int = 2) -> RunView:
        app = self._graph_for(scenario)
        state = WorkflowState(run_id=run_id, content=content, max_revisions=max_revisions)

        if not self.storage.runs.create(RunRecord(run_id, content.content_id, scenario, max_revisions)):
            raise RunExistsError(f"Run {run_id} already exists. Use 'resume' or 'status' instead.")

        since = self.storage.events.last_seq(run_id)
        self.storage.events.record(run_id, "run_started", key="run_started",
                                   content_id=content.content_id, scenario=scenario, max_revisions=max_revisions)
        app.invoke(state, self._config(run_id))
        self._record_checkpoint_if_paused(app, run_id)
        return self._view(app, run_id, since)

    def resume(self, run_id: str, decision: ReviewDecision) -> RunView:
        run = self.storage.runs.get(run_id)
        if run is None:
            raise RunNotFoundError(f"No run named {run_id}")

        app = self._graph_for(run.scenario)
        since = self.storage.events.last_seq(run_id)
        snapshot = app.get_state(self._config(run_id))
        status = Status(snapshot.values["status"])

        if status in TERMINAL_STATUSES:
            self.storage.events.record(
                run_id, "duplicate_approval_ignored" if status == Status.COMPLETED else "resume_ignored",
                key=f"ignored:{uuid.uuid4().hex}", status=status.value, decision=decision.decision,
                reviewer=decision.reviewer,
            )
            return self._view(app, run_id, since, already_finished=True)

        if snapshot.next != (REVIEW_NODE,):
            raise NotResumableError(f"Run {run_id} is not waiting for review (next step: {snapshot.next or 'none'})")

        self.storage.events.record(
            run_id, "checkpoint_loaded", key=f"checkpoint_loaded:{uuid.uuid4().hex}",
            checkpoint_id=snapshot.config["configurable"]["checkpoint_id"],
            checkpoint_version=snapshot.values["checkpoint_version"], stage=REVIEW_NODE,
        )
        app.invoke(Command(resume=decision.model_dump()), self._config(run_id))
        return self._view(app, run_id, since)

    def status(self, run_id: str) -> RunView:
        run = self.storage.runs.get(run_id)
        if run is None:
            raise RunNotFoundError(f"No run named {run_id}")
        return self._view(self._graph_for(run.scenario), run_id, since_seq=self.storage.events.last_seq(run_id))

    def events(self, run_id: str) -> list[dict[str, Any]]:
        if self.storage.runs.get(run_id) is None:
            raise RunNotFoundError(f"No run named {run_id}")
        return self.storage.events.for_run(run_id)


__all__ = ["WorkflowService", "RunView", "RunNotFoundError", "RunExistsError", "NotResumableError", "InvalidInputError"]