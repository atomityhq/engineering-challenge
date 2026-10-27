"""Tests for JSON loading and record-level validation."""

import json
from pathlib import Path

import pytest

from source_filter.loader import load_source_records


SUBMISSION_DIR = Path(__file__).resolve().parents[1]
FIXTURE_PATH = SUBMISSION_DIR / "fixtures" / "source_records.json"


def test_fixture_loads_valid_and_invalid_records():
    records, invalid_records = load_source_records(FIXTURE_PATH)

    assert len(records) == 6
    assert len(invalid_records) == 1

    assert invalid_records[0].source_id == "source-007"
    assert invalid_records[0].reason_code == "INVALID_RECORD"
    assert any(
        "url" in error
        for error in invalid_records[0].errors
    )


def test_valid_records_are_preserved_when_another_record_is_invalid(
    tmp_path,
):
    data = [
        {
            "source_id": "valid-001",
            "url": "https://example.org/article",
        },
        {
            "source_id": "invalid-001",
        },
    ]

    path = tmp_path / "records.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    records, invalid_records = load_source_records(path)

    assert [record.source_id for record in records] == ["valid-001"]
    assert len(invalid_records) == 1


def test_non_object_record_is_reported(tmp_path):
    path = tmp_path / "records.json"
    path.write_text(
        json.dumps([
            {
                "source_id": "valid-001",
                "url": "https://example.org/article",
            },
            "not a record object",
        ]),
        encoding="utf-8",
    )

    records, invalid_records = load_source_records(path)

    assert len(records) == 1
    assert len(invalid_records) == 1
    assert "JSON object" in invalid_records[0].errors[0]


def test_malformed_json_raises_clear_error(tmp_path):
    path = tmp_path / "records.json"
    path.write_text('[{"source_id": ]', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        load_source_records(path)


def test_top_level_json_must_be_a_list(tmp_path):
    path = tmp_path / "records.json"
    path.write_text(
        json.dumps({"source_id": "source-001"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must contain a list"):
        load_source_records(path)