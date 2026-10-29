"""Storage: the event log, and the SQLite file that holds checkpoints and events.

Every event has an operation key. Writing the same (run_id, op_key) twice is ignored,
so a step that runs again after a crash or a repeated command never logs twice.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "workflow.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EventLog(ABC):
    @abstractmethod
    def record(self, run_id: str, op_key: str, event: str, **details: Any) -> bool:
        """Store one event. Return False if this (run_id, op_key) was already stored."""

    @abstractmethod
    def events(self, run_id: str) -> list[dict[str, Any]]:
        """Return the run's events in the order they were stored."""


class InMemoryEventLog(EventLog):
    """Event log for tests. It is lost when the process ends."""

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []
        self._keys: set[tuple[str, str]] = set()

    def record(self, run_id: str, op_key: str, event: str, **details: Any) -> bool:
        key = (run_id, op_key)
        if key in self._keys:
            return False
        self._keys.add(key)
        self._rows.append({"run_id": run_id, "event": event, **details, "at": _now()})
        return True

    def events(self, run_id: str) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k != "run_id"}
            for row in self._rows
            if row["run_id"] == run_id
        ]


class SqliteEventLog(EventLog):
    """Event log in an `events` table. Each record() is committed at once."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                seq        INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id     TEXT NOT NULL,
                op_key     TEXT NOT NULL,
                event      TEXT NOT NULL,
                details    TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (run_id, op_key)
            )
            """
        )
        self._conn.commit()

    def record(self, run_id: str, op_key: str, event: str, **details: Any) -> bool:
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO events (run_id, op_key, event, details, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (run_id, op_key, event, json.dumps(details), _now()),
        )
        self._conn.commit()
        return cursor.rowcount == 1

    def events(self, run_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT event, details, created_at FROM events WHERE run_id = ? ORDER BY seq",
            (run_id,),
        ).fetchall()
        return [{"event": event, **json.loads(details), "at": at} for event, details, at in rows]


@dataclass
class Storage:
    checkpointer: SqliteSaver
    events: SqliteEventLog


@contextmanager
def open_storage(db_path: Path = DEFAULT_DB_PATH) -> Iterator[Storage]:
    """Open the SQLite file for checkpoints and events, and close it afterwards.

    Checkpoints and events use separate connections, so a commit of one never
    commits half of the other's work.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_conn = sqlite3.connect(db_path, check_same_thread=False)
    events_conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        yield Storage(checkpointer=SqliteSaver(checkpoint_conn), events=SqliteEventLog(events_conn))
    finally:
        events_conn.close()
        checkpoint_conn.close()
