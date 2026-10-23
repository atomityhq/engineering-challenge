import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from models import ContentInput


@contextmanager
def open_sqlite_checkpointer(
    database_path: str | Path,
) -> Iterator[SqliteSaver]:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    serializer = JsonPlusSerializer(
        pickle_fallback=False,
        allowed_msgpack_modules=[ContentInput],
    )
    connection = sqlite3.connect(path, check_same_thread=False)
    try:
        yield SqliteSaver(connection, serde=serializer)
    finally:
        connection.close()
