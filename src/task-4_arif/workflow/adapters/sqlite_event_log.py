
import json
import sqlite3
from pathlib import Path

from workflow.models.event import WorkflowEvent
from workflow.ports.event_log import EventConflictError


class SQLiteEventLog:
    """Durable, idempotent workflow event log."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    workflow_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_events_workflow
                ON workflow_events (workflow_id, sequence)
                """
            )

    @staticmethod
    def _logical_data(event: WorkflowEvent) -> tuple[str, str, str]:
        return (
            event.workflow_id,
            event.event_type.value,
            json.dumps(
                event.payload,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    def append(self, event: WorkflowEvent) -> bool:
        workflow_id, event_type, payload = self._logical_data(event)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO workflow_events (
                    event_id, workflow_id, event_type, timestamp, payload
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    workflow_id,
                    event_type,
                    event.timestamp.isoformat(),
                    payload,
                ),
            )

            if cursor.rowcount == 1:
                return True

            existing = connection.execute(
                """
                SELECT workflow_id, event_type, payload
                FROM workflow_events
                WHERE event_id = ?
                """,
                (event.event_id,),
            ).fetchone()

            if existing is None:
                raise RuntimeError(
                    "Event insert was ignored without a matching event"
                )

            if (
                existing["workflow_id"],
                existing["event_type"],
                existing["payload"],
            ) != (workflow_id, event_type, payload):
                raise EventConflictError(
                    f"Conflicting event with ID: {event.event_id}"
                )

            return False

    def get_event(self, event_id: str) -> WorkflowEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT event_id, workflow_id, event_type, timestamp, payload
                FROM workflow_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

        return self._to_event(row) if row is not None else None

    def list_events(self, workflow_id: str) -> list[WorkflowEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, workflow_id, event_type, timestamp, payload
                FROM workflow_events
                WHERE workflow_id = ?
                ORDER BY sequence ASC
                """,
                (workflow_id,),
            ).fetchall()

        return [self._to_event(row) for row in rows]

    @staticmethod
    def _to_event(row: sqlite3.Row) -> WorkflowEvent:
        return WorkflowEvent.model_validate_json(
            json.dumps(
                {
                    "event_id": row["event_id"],
                    "workflow_id": row["workflow_id"],
                    "event_type": row["event_type"],
                    "timestamp": row["timestamp"],
                    "payload": json.loads(row["payload"]),
                }
            )
        )
