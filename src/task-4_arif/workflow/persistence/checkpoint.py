from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver


@contextmanager
def sqlite_checkpointer(
    database_path: str | Path,
) -> Iterator[SqliteSaver]:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    serializer = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("workflow.models.content", "ContentItem"),
            ("workflow.models.evaluation", "EvaluationDecision"),
            ("workflow.models.evaluation", "EvaluationResult"),
        ]
    )

    with SqliteSaver.from_conn_string(str(path)) as saver:
        saver.serde = serializer
        yield saver