import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id        TEXT PRIMARY KEY,
    content_id    TEXT NOT NULL,
    scenario      TEXT NOT NULL,     -- which evaluator fixture drives this run
    max_revisions INTEGER NOT NULL,
    created_at    TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    content_id: str
    scenario: str
    max_revisions: int


class RunRegistry:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.executescript(SCHEMA)

    def create(self, record: RunRecord) -> bool:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO workflow_runs VALUES (?, ?, ?, ?, ?)",
            (record.run_id, record.content_id, record.scenario, record.max_revisions, datetime.now(UTC).isoformat()),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def get(self, run_id: str) -> RunRecord | None:
        row = self.conn.execute(
            "SELECT run_id, content_id, scenario, max_revisions FROM workflow_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return RunRecord(*row) if row else None