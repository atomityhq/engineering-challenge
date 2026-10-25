"""Durable SQLite persistence and checkpointer management for the Resumable Review Workflow.

Provides local storage for LangGraph checkpoints, workflow run metadata, and
append-only audit event logs, enabling reliable recovery across process restarts.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, Generator, List, Optional

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from workflow.models import (
    EventType,
    WorkflowEvent,
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
)

DEFAULT_DB_PATH = os.environ.get("WORKFLOW_DB_PATH", "workflow_data.db")

ALLOWLIST = [
    ("workflow.models", "ContentItem"),
    ("workflow.models", "WorkflowStatus"),
    ("workflow.models", "WorkflowStage"),
    ("workflow.models", "HumanReviewStatus"),
    ("workflow.models", "EvaluatorDecision"),
    ("workflow.models", "EvaluationResult"),
    ("workflow.models", "RevisionRecord"),
    ("workflow.models", "ApprovalMetadata"),
    ("workflow.models", "EventType"),
    ("workflow.models", "WorkflowEvent"),
    ("workflow.models", "WorkflowState"),
]


class WorkflowDatabase:
    """Manages SQLite storage for workflow metadata, checkpoints, and event logs."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        # Ensure parent directory exists if path contains directories
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Create and return an SQLite connection configured with proper pragmas."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        """Initialize the database schema for workflow metadata and event logs."""
        with self.get_connection() as conn:
            # LangGraph checkpointer setup
            cp = SqliteSaver(conn)
            cp.setup()

            # Metadata table for workflow runs
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    content_id TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    revision_count INTEGER NOT NULL DEFAULT 0,
                    evaluation_count INTEGER NOT NULL DEFAULT 0,
                    max_revisions INTEGER NOT NULL DEFAULT 2,
                    checkpoint_version INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            # Persistent append-only event log
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_events (
                    event_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    revision_count INTEGER NOT NULL,
                    decision TEXT,
                    explanation TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_workflow_id 
                ON workflow_events (workflow_id, timestamp);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_content_id 
                ON workflow_events (content_id, timestamp);
                """
            )
            conn.commit()

    @contextmanager
    def checkpointer(self) -> Generator[SqliteSaver, None, None]:
        """Yield a LangGraph SqliteSaver checkpointer sharing the database."""
        conn = self.get_connection()
        try:
            serde = JsonPlusSerializer(allowed_msgpack_modules=ALLOWLIST)
            saver = SqliteSaver(conn, serde=serde)
            yield saver
        finally:
            conn.close()

    def get_checkpointer(self) -> SqliteSaver:
        """Return a persistent checkpointer instance."""
        conn = self.get_connection()
        serde = JsonPlusSerializer(allowed_msgpack_modules=ALLOWLIST)
        return SqliteSaver(conn, serde=serde)

    def save_run(self, state: WorkflowState) -> None:
        """Insert or update a workflow run metadata record."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_runs (
                    run_id, content_id, status, stage, revision_count,
                    evaluation_count, max_revisions, checkpoint_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    stage = excluded.stage,
                    revision_count = excluded.revision_count,
                    evaluation_count = excluded.evaluation_count,
                    max_revisions = excluded.max_revisions,
                    checkpoint_version = excluded.checkpoint_version,
                    updated_at = excluded.updated_at;
                """,
                (
                    state.run_id,
                    state.content_id,
                    state.status.value,
                    state.stage.value,
                    state.revision_count,
                    state.evaluation_count,
                    state.max_revisions,
                    state.checkpoint_version,
                    state.created_at.isoformat(),
                    now_str,
                ),
            )
            conn.commit()

    def get_run_by_content_id(self, content_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve run metadata by content ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_runs WHERE content_id = ? LIMIT 1;",
                (content_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_run_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve run metadata by run ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_runs WHERE run_id = ? LIMIT 1;",
                (run_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_runs(self) -> List[Dict[str, Any]]:
        """List all workflow runs."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_runs ORDER BY updated_at DESC;"
            )
            return [dict(row) for row in cursor.fetchall()]

    def save_event(self, event: WorkflowEvent) -> None:
        """Persist an event to the append-only event log. Idempotent on event_id."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO workflow_events (
                    event_id, workflow_id, content_id, event_type,
                    stage, revision_count, decision, explanation,
                    metadata_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.event_id,
                    event.workflow_id,
                    event.content_id,
                    event.event_type.value,
                    event.stage.value,
                    event.revision_count,
                    event.decision,
                    event.explanation,
                    json.dumps(event.metadata),
                    event.timestamp.isoformat(),
                ),
            )
            conn.commit()

    def get_events(self, workflow_id: str) -> List[WorkflowEvent]:
        """Fetch all events for a workflow in chronological order."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_events WHERE workflow_id = ? ORDER BY timestamp ASC;",
                (workflow_id,),
            )
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]

    def get_events_for_content(self, content_id: str) -> List[WorkflowEvent]:
        """Fetch all events for a content ID in chronological order."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM workflow_events WHERE content_id = ? ORDER BY timestamp ASC;",
                (content_id,),
            )
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> WorkflowEvent:
        return WorkflowEvent(
            event_id=row["event_id"],
            workflow_id=row["workflow_id"],
            content_id=row["content_id"],
            event_type=EventType(row["event_type"]),
            stage=WorkflowStage(row["stage"]),
            revision_count=row["revision_count"],
            decision=row["decision"],
            explanation=row["explanation"],
            metadata=json.loads(row["metadata_json"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
