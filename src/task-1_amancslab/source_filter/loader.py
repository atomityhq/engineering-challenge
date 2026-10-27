"""Load and validate saved source records from JSON."""

import json
from pathlib import Path
from typing import Any, List, Optional, Tuple

from pydantic import BaseModel, ValidationError

from .models import SourceRecord


class InvalidSourceRecord(BaseModel):
    """A record that could not pass input validation."""

    index: int
    source_id: Optional[str] = None
    raw_record: Any
    reason_code: str = "INVALID_RECORD"
    errors: List[str]


def load_source_records(
    path: str | Path,
) -> Tuple[List[SourceRecord], List[InvalidSourceRecord]]:
    """Load valid records and report individual invalid records.

    Invalid JSON syntax or an unexpected top-level JSON structure
    raises ValueError. Invalid individual records are collected
    separately so other valid records can still be processed.
    """

    input_path = Path(path)

    try:
        payload = json.loads(
            input_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {input_path}: {exc}"
        ) from exc

    if not isinstance(payload, list):
        raise ValueError(
            "Input JSON must contain a list of source records"
        )

    valid_records: List[SourceRecord] = []
    invalid_records: List[InvalidSourceRecord] = []

    for index, raw_record in enumerate(payload, start=1):
        source_id = None

        if isinstance(raw_record, dict):
            candidate_id = raw_record.get("source_id")

            if isinstance(candidate_id, str):
                source_id = candidate_id

        if not isinstance(raw_record, dict):
            invalid_records.append(
                InvalidSourceRecord(
                    index=index,
                    source_id=source_id,
                    raw_record=raw_record,
                    errors=[
                        "Each source record must be a JSON object"
                    ],
                )
            )
            continue

        try:
            record = SourceRecord.parse_obj(raw_record)
        except ValidationError as exc:
            errors = [
                f"{'.'.join(str(part) for part in error['loc'])}: "
                f"{error['msg']}"
                for error in exc.errors()
            ]

            invalid_records.append(
                InvalidSourceRecord(
                    index=index,
                    source_id=source_id,
                    raw_record=raw_record,
                    errors=errors,
                )
            )
            continue

        valid_records.append(record)

    return valid_records, invalid_records