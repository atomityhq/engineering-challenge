"""Typed contracts: input, state, events. Content is data, never instructions."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ContentItem(BaseModel):
    """Workflow input. Invalid input must fail validation before any work starts."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class Decision(str, Enum):
    REVISE = "revise"
    HUMAN_REVIEW = "human_review"


class Status(str, Enum):
    EVALUATING = "evaluating"
    REVISING = "revising"
    HUMAN_REVIEW = "human_review"      # paused, checkpoint saved
    COMPLETED = "completed"            # terminal: approved
    STOPPED = "stopped"                # terminal: e.g. max revisions reached


class WorkflowState(BaseModel):
    """State carried through the LangGraph nodes and persisted at checkpoints."""
    run_id: str
    content: ContentItem
    status: Status = Status.EVALUATING
    revision_count: int = 0
    evaluation_result: Optional[Decision] = None
    stop_reason: Optional[str] = None
    approved_by: Optional[str] = None
    checkpoint_version: int = 0


class Event(BaseModel):
    """One row of the append-only event log."""
    run_id: str
    seq: int
    event: str                          # e.g. evaluation_completed, checkpoint_saved
    revision_count: int = 0
    detail: Optional[str] = None
