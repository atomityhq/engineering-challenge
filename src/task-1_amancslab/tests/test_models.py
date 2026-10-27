"""Tests for the source record input model."""

import pytest
from pydantic import ValidationError

from source_filter.models import SourceRecord, SourceType


def test_valid_source_record_is_accepted():
    record = SourceRecord(
        source_id="source-001",
        url="https://example.org/news?id=123",
        publisher="Example Research Institute",
        source_type="primary",
        discovery_lineage=["feed-a"],
    )

    assert record.source_id == "source-001"
    assert record.source_type == SourceType.PRIMARY
    assert record.discovery_lineage == ["feed-a"]


def test_unknown_dates_remain_none():
    record = SourceRecord(
        source_id="source-002",
        url="https://example.org/report",
    )

    assert record.publication_date is None
    assert record.event_date is None


def test_empty_source_id_is_rejected():
    with pytest.raises(ValidationError):
        SourceRecord(
            source_id="   ",
            url="https://example.org/news",
        )


def test_invalid_url_scheme_is_rejected():
    with pytest.raises(ValidationError):
        SourceRecord(
            source_id="source-003",
            url="javascript:alert(1)",
        )


def test_unexpected_fields_are_rejected():
    with pytest.raises(ValidationError):
        SourceRecord(
            source_id="source-004",
            url="https://example.org/news",
            unexpected_field="not allowed",
        )


def test_empty_discovery_lineage_entry_is_rejected():
    with pytest.raises(ValidationError):
        SourceRecord(
            source_id="source-005",
            url="https://example.org/news",
            discovery_lineage=["   "],
        )

def test_invalid_url_port_is_rejected():
    with pytest.raises(ValidationError):
        SourceRecord(
            source_id="source-bad-port",
            url="https://example.org:99999/news",
        )


def test_url_with_embedded_credentials_is_rejected():
    with pytest.raises(ValidationError):
        SourceRecord(
            source_id="source-credentials",
            url="https://user:password@example.org/news",
        )