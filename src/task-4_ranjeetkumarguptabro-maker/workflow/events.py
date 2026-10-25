"""Event recording, auditing, and formatting for the Resumable Review Workflow.

Provides structured lifecycle event generation, persistent audit logging,
and validation helpers to inspect workflow execution history.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from workflow.models import (
    EventType,
    WorkflowEvent,
    WorkflowStage,
)
from workflow.persistence import WorkflowDatabase


def create_event(
    workflow_id: str,
    content_id: str,
    event_type: EventType,
    stage: WorkflowStage,
    revision_count: int,
    explanation: str,
    decision: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[WorkflowDatabase] = None,
) -> WorkflowEvent:
    """Create a structured workflow event and optionally persist it immediately."""
    event = WorkflowEvent(
        workflow_id=workflow_id,
        content_id=content_id,
        event_type=event_type,
        stage=stage,
        revision_count=revision_count,
        decision=decision,
        explanation=explanation,
        metadata=metadata or {},
        timestamp=datetime.now(timezone.utc),
    )

    if db is not None:
        try:
            db.save_event(event)
        except Exception:
            # Persistent event saving should not crash runtime if DB is busy;
            # state snapshotting in LangGraph preserves events regardless.
            pass

    return event


def format_events_table(events: List[WorkflowEvent]) -> str:
    """Format events as an ASCII / terminal table for inspection."""
    if not events:
        return "No events recorded."

    lines = []
    header = f"{'TIMESTAMP':<24} | {'EVENT':<24} | {'STAGE':<16} | {'REV':<4} | {'EXPLANATION'}"
    sep = "-" * len(header) + "-" * 20
    lines.append(sep)
    lines.append(header)
    lines.append(sep)

    for evt in events:
        ts_str = evt.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(
            f"{ts_str:<24} | {evt.event_type.value:<24} | {evt.stage.value:<16} | {evt.revision_count:<4} | {evt.explanation}"
        )
    lines.append(sep)
    return "\n".join(lines)


def format_events_json(events: List[WorkflowEvent], indent: int = 2) -> str:
    """Format events as structured JSON."""
    return json.dumps([e.model_dump(mode="json") for e in events], indent=indent)


def get_event_type_sequence(events: List[WorkflowEvent]) -> List[EventType]:
    """Extract list of event types in order for test assertions."""
    return [e.event_type for e in events]
