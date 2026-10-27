"""Duplicate detection and provenance-preserving merging."""

from typing import List, Literal

from pydantic import BaseModel, Field

from .models import ClaimKind, SourceRecord, SourceType
from .normalizer import canonical_url_for


class DuplicateReport(BaseModel):
    """Describe one record that was merged into another record."""

    canonical_url: str
    retained_source_id: str
    duplicate_source_id: str
    duplicate_type: Literal["exact_record", "canonical_url"]


class MetadataConflict(BaseModel):
    """Report conflicting non-empty metadata from duplicate records."""

    canonical_url: str
    field: str
    source_ids: List[str]
    values: List[str]
    reason_code: str = "DUPLICATE_METADATA_CONFLICT"


class DeduplicationResult(BaseModel):
    """Output of the deduplication operation."""

    records: List[SourceRecord]
    duplicates: List[DuplicateReport] = Field(default_factory=list)
    metadata_conflicts: List[MetadataConflict] = Field(default_factory=list)


def _is_known(field: str, value: object) -> bool:
    """Return whether a value contains usable metadata."""

    if value is None:
        return False

    if field == "publisher":
        return isinstance(value, str) and bool(value.strip())

    if field == "source_type":
        return value != SourceType.UNKNOWN

    if field == "claim_kind":
        return value != ClaimKind.OTHER

    return True


def _display_value(value: object) -> str:
    """Convert metadata into a readable conflict-report value."""

    if hasattr(value, "value"):
        return str(value.value)

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


def _first_known(group: List[SourceRecord], field: str):
    """Choose the first known value in input order."""

    for record in group:
        value = getattr(record, field)

        if _is_known(field, value):
            return value

    return getattr(group[0], field)


def _merge_lineage(group: List[SourceRecord]) -> List[str]:
    """Merge discovery lineage while preserving order and uniqueness."""

    merged = []
    seen = set()

    for record in group:
        for item in record.discovery_lineage:
            if item not in seen:
                seen.add(item)
                merged.append(item)

    return merged


def _find_conflicts(
    canonical_url: str,
    group: List[SourceRecord],
) -> List[MetadataConflict]:
    """Report conflicting known values instead of silently discarding them."""

    conflicts = []

    fields = (
        "publisher",
        "source_type",
        "claim_kind",
        "publication_date",
        "event_date",
    )

    for field in fields:
        observations = []

        for record in group:
            value = getattr(record, field)

            if _is_known(field, value):
                observations.append(
                    (record.source_id, _display_value(value))
                )

        distinct_values = list(
            dict.fromkeys(value for _, value in observations)
        )

        if len(distinct_values) > 1:
            conflicts.append(
                MetadataConflict(
                    canonical_url=canonical_url,
                    field=field,
                    source_ids=[
                        source_id for source_id, _ in observations
                    ],
                    values=distinct_values,
                )
            )

    return conflicts


def _merge_group(
    canonical_url: str,
    group: List[SourceRecord],
) -> SourceRecord:
    """Create one normalised record from a group of duplicates."""

    first = group[0]

    updates = {
        "canonical_url": canonical_url,
        "publisher": _first_known(group, "publisher"),
        "source_type": _first_known(group, "source_type"),
        "claim_kind": _first_known(group, "claim_kind"),
        "publication_date": _first_known(
            group, "publication_date"
        ),
        "event_date": _first_known(group, "event_date"),
        "discovery_lineage": _merge_lineage(group),
    }

    # The first record supplies the stable source ID and original URL.
    return first.copy(update=updates)


def deduplicate_records(
    records: List[SourceRecord],
) -> DeduplicationResult:
    """Deduplicate records using their normalised canonical URLs."""

    groups = {}
    duplicates = []

    for record in records:
        canonical_url = canonical_url_for(record)

        if canonical_url not in groups:
            groups[canonical_url] = [record]
            continue

        group = groups[canonical_url]

        is_exact_duplicate = any(
            existing.dict() == record.dict()
            for existing in group
        )

        duplicates.append(
            DuplicateReport(
                canonical_url=canonical_url,
                retained_source_id=group[0].source_id,
                duplicate_source_id=record.source_id,
                duplicate_type=(
                    "exact_record"
                    if is_exact_duplicate
                    else "canonical_url"
                ),
            )
        )

        group.append(record)

    normalised_records = []
    conflicts = []

    for canonical_url, group in groups.items():
        normalised_records.append(
            _merge_group(canonical_url, group)
        )
        conflicts.extend(
            _find_conflicts(canonical_url, group)
        )

    return DeduplicationResult(
        records=normalised_records,
        duplicates=duplicates,
        metadata_conflicts=conflicts,
    )