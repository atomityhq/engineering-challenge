"""Append-only event log. SQLite implementation shares the workflow's local DB file.

Idempotency backstop: a partial UNIQUE index allows 'human_approved' and
'workflow_completed' at most once per run, so even a retried/duplicated approval
cannot write a second completion event (INSERT OR IGNORE in append_once)."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Protocol

from workflow.models import Event

ONCE_EVENTS = ("human_approved", "workflow_completed")


class EventLog(Protocol):
    def append(self, run_id: str, event: str, revision_count: int = 0,
               detail: Optional[str] = None) -> None: ...

    def append_once(self, run_id: str, event: str, revision_count: int = 0,
                    detail: Optional[str] = None) -> bool: ...

    def list(self, run_id: str) -> list[Event]: ...


class InMemoryEventLog:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, run_id: str, event: str, revision_count: int = 0,
               detail: Optional[str] = None) -> None:
        seq = sum(1 for e in self._events if e.run_id == run_id) + 1
        self._events.append(Event(run_id=run_id, seq=seq, event=event,
                                  revision_count=revision_count, detail=detail))

    def append_once(self, run_id: str, event: str, revision_count: int = 0,
                    detail: Optional[str] = None) -> bool:
        if any(e.run_id == run_id and e.event == event for e in self._events):
            return False
        self.append(run_id, event, revision_count, detail)
        return True

    def list(self, run_id: str) -> list[Event]:
        return [e for e in self._events if e.run_id == run_id]


class SqliteEventLog:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS events (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       run_id TEXT NOT NULL,
                       seq INTEGER NOT NULL,
                       event TEXT NOT NULL,
                       revision_count INTEGER NOT NULL DEFAULT 0,
                       detail TEXT,
                       UNIQUE (run_id, seq))"""
            )
            quoted = ", ".join(f"'{e}'" for e in ONCE_EVENTS)
            c.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS uq_events_once "
                f"ON events (run_id, event) WHERE event IN ({quoted})"
            )

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        try:
            with conn:  # commit on success, rollback on error
                yield conn
        finally:
            conn.close()

    _INSERT = ("INTO events (run_id, seq, event, revision_count, detail) "
               "SELECT ?, COALESCE(MAX(seq), 0) + 1, ?, ?, ? FROM events WHERE run_id = ?")

    def append(self, run_id: str, event: str, revision_count: int = 0,
               detail: Optional[str] = None) -> None:
        with self._conn() as c:
            c.execute("INSERT " + self._INSERT, (run_id, event, revision_count, detail, run_id))

    def append_once(self, run_id: str, event: str, revision_count: int = 0,
                    detail: Optional[str] = None) -> bool:
        with self._conn() as c:
            cur = c.execute("INSERT OR IGNORE " + self._INSERT,
                            (run_id, event, revision_count, detail, run_id))
            return cur.rowcount == 1

    def list(self, run_id: str) -> list[Event]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT run_id, seq, event, revision_count, detail FROM events "
                "WHERE run_id = ? ORDER BY seq", (run_id,)).fetchall()
        return [Event(run_id=r[0], seq=r[1], event=r[2], revision_count=r[3], detail=r[4])
                for r in rows]
