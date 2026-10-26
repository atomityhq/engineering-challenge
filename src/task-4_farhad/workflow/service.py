"""Orchestration used by the CLI and the tests: start, inspect, resume/approve."""
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Optional

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from workflow.config import WorkflowConfig
from workflow.evaluator import Evaluator, Reviser
from workflow.events import EventLog, SqliteEventLog
from workflow.graph import build_graph
from workflow.models import ContentItem, Status, WorkflowState
from workflow.models import ContentItem, Status, WorkflowState

PAUSED_NODE = "await_approval"


class RunAlreadyExists(Exception):
    pass


class UnknownRun(Exception):
    pass


class NotAwaitingApproval(Exception):
    pass


@dataclass
class Runtime:
    graph: Any
    events: EventLog


_ALLOWED_TYPES = [("workflow.models", name)
                  for name in ("WorkflowState", "ContentItem", "Status", "Decision")]


@contextmanager
def open_runtime(config: WorkflowConfig, evaluator: Evaluator,
                 reviser: Reviser) -> Generator[Runtime, None, None]:
    events = SqliteEventLog(config.db_path)
    conn = sqlite3.connect(str(config.db_path), check_same_thread=False)
    try:
        saver = SqliteSaver(conn, serde=JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_TYPES))
        yield Runtime(build_graph(evaluator, reviser, events, config, checkpointer=saver), events)
    finally:
        conn.close()


def _cfg(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _as_state(values: Any) -> WorkflowState:
    return values if isinstance(values, WorkflowState) else WorkflowState.model_validate(values)


def _checkpoint_id(snapshot: Any) -> Optional[str]:
    return (snapshot.config or {}).get("configurable", {}).get("checkpoint_id")


def get_state(rt: Runtime, run_id: str) -> tuple[WorkflowState, bool]:
    """Return (state, paused_for_approval) loaded from the saved checkpoint."""
    snap = rt.graph.get_state(_cfg(run_id))
    if not snap.values:
        raise UnknownRun(run_id)
    return _as_state(snap.values), tuple(snap.next) == (PAUSED_NODE,)


def start_run(rt: Runtime, run_id: str, content: ContentItem) -> WorkflowState:
    if rt.graph.get_state(_cfg(run_id)).values:
        raise RunAlreadyExists(run_id)
    rt.events.append(run_id, "workflow_started")
    rt.graph.invoke(WorkflowState(run_id=run_id, content=content), _cfg(run_id))
    snap = rt.graph.get_state(_cfg(run_id))
    state = _as_state(snap.values)
    if tuple(snap.next) == (PAUSED_NODE,):
        # Logged only after the checkpointer has persisted the paused state.
        rt.events.append(run_id, "checkpoint_saved", state.revision_count,
                         detail=f"checkpoint_id={_checkpoint_id(snap)}")
    return state


def resume_run(rt: Runtime, run_id: str, reviewer: str = "reviewer") -> tuple[WorkflowState, str]:
    """Approve a paused run. Returns (state, outcome); outcome is one of
    completed | already_completed | stopped. Safe to call repeatedly."""
    state, paused = get_state(rt, run_id)
    if state.status == Status.COMPLETED:
        rt.events.append(run_id, "duplicate_approval_ignored", state.revision_count)
        return state, "already_completed"
    if state.status == Status.STOPPED:
        return state, "stopped"
    if not paused:
        raise NotAwaitingApproval(f"{run_id} is not waiting for approval (status={state.status.value})")
    snap = rt.graph.get_state(_cfg(run_id))
    rt.events.append(run_id, "checkpoint_loaded", state.revision_count,
                     detail=f"checkpoint_id={_checkpoint_id(snap)}")
    rt.graph.invoke(Command(resume={"reviewer": reviewer}), _cfg(run_id))
    return get_state(rt, run_id)[0], "completed"
