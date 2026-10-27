"""Tests for duplicate detection and provenance preservation."""

from source_filter.models import SourceRecord, SourceType
from source_filter.deduplicator import deduplicate_records


def test_exact_duplicate_records_are_identified():
    first = SourceRecord(
        source_id="source-001",
        url="https://example.org/news",
        discovery_lineage=["feed-a"],
    )

    second = SourceRecord(
        source_id="source-001",
        url="https://example.org/news",
        discovery_lineage=["feed-a"],
    )

    result = deduplicate_records([first, second])

    assert len(result.records) == 1
    assert len(result.duplicates) == 1
    assert result.duplicates[0].duplicate_type == "exact_record"


def test_canonical_duplicates_merge_discovery_lineage():
    first = SourceRecord(
        source_id="source-001",
        url="https://example.org/news?utm_source=feed",
        discovery_lineage=["feed-a"],
    )

    second = SourceRecord(
        source_id="source-002",
        url="https://example.org/news",
        discovery_lineage=["feed-b"],
    )

    result = deduplicate_records([first, second])

    assert len(result.records) == 1

    merged = result.records[0]

    assert merged.source_id == "source-001"
    assert merged.canonical_url == "https://example.org/news"
    assert merged.discovery_lineage == ["feed-a", "feed-b"]

    assert result.duplicates[0].duplicate_type == "canonical_url"


def test_different_meaningful_query_parameters_are_not_merged():
    first = SourceRecord(
        source_id="source-001",
        url="https://example.org/news?id=100",
    )

    second = SourceRecord(
        source_id="source-002",
        url="https://example.org/news?id=200",
    )

    result = deduplicate_records([first, second])

    assert len(result.records) == 2
    assert len(result.duplicates) == 0


def test_conflicting_metadata_is_reported():
    first = SourceRecord(
        source_id="source-001",
        url="https://example.org/news",
        publisher="Publisher A",
        source_type="primary",
    )

    second = SourceRecord(
        source_id="source-002",
        url="https://example.org/news?utm_source=feed",
        publisher="Publisher B",
        source_type="competitor",
    )

    result = deduplicate_records([first, second])

    conflict_fields = {
        conflict.field for conflict in result.metadata_conflicts
    }

    assert "publisher" in conflict_fields
    assert "source_type" in conflict_fields

    # The conflict must be visible, not silently overwritten.
    assert result.records[0].source_type == SourceType.PRIMARY


def test_empty_input_returns_empty_result():
    result = deduplicate_records([])

    assert result.records == []
    assert result.duplicates == []
    assert result.metadata_conflicts == []