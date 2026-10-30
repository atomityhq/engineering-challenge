import sqlite3
import json
import uuid

from workflow.models import EventRecord


class EventLogger:
    def __init__(self, database_path="workflow_events.sqlite"):
        self.connection = sqlite3.connect(database_path)

        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS workflow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                details TEXT NOT NULL,
                event_key TEXT
            )
        """)

        # Support databases created with the previous table structure.
        columns = {
            row[1]
            for row in self.connection.execute(
                "PRAGMA table_info(workflow_events)"
            ).fetchall()
        }

        if "event_key" not in columns:
            self.connection.execute(
                "ALTER TABLE workflow_events ADD COLUMN event_key TEXT"
            )

        self.connection.execute("""
            UPDATE workflow_events
            SET event_key = 'legacy-' || id
            WHERE event_key IS NULL
        """)

        self.connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_workflow_event_key
            ON workflow_events(workflow_id, event_key)
        """)

        self.connection.commit()

    def log(self, event: EventRecord, event_key=None):
        key = event_key or uuid.uuid4().hex

        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO workflow_events
            (workflow_id, event_type, timestamp, details, event_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.workflow_id,
                event.event_type,
                event.timestamp.isoformat(),
                json.dumps(event.details),
                key,
            ),
        )

        self.connection.commit()

        return cursor.rowcount == 1

    def get_events(self, workflow_id: str):
        cursor = self.connection.execute(
            """
            SELECT event_type, timestamp, details
            FROM workflow_events
            WHERE workflow_id = ?
            ORDER BY id
            """,
            (workflow_id,),
        )

        return [
            {
                "event_type": row[0],
                "timestamp": row[1],
                "details": json.loads(row[2]),
            }
            for row in cursor.fetchall()
        ]

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.close()