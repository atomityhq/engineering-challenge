"""Orchestrate source loading, deduplication, filtering and export."""

import json
from pathlib import Path
from typing import Any, Dict

from .deduplicator import deduplicate_records
from .loader import load_source_records
from .policy import apply_policy, load_policy


def _to_jsonable(model: Any) -> Any:
    """Convert a Pydantic model to JSON-compatible Python data."""
    return json.loads(model.json())


def _write_json(path: Path, data: Any) -> None:
    """Write formatted JSON to a local output file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_pipeline(
    input_path: str | Path,
    policy_path: str | Path,
    output_dir: str | Path,
) -> Dict[str, Any]:
    """Process source records and export every processing result."""

    output_path = Path(output_dir)

    # 1. Load and validate individual records.
    records, invalid_records = load_source_records(input_path)

    # 2. Load the configurable source policy.
    policy = load_policy(policy_path)

    # 3. Deduplicate records and preserve discovery lineage.
    deduplication = deduplicate_records(records)

    # A group with conflicting metadata should not be trusted
    # automatically, even if its representative record looks valid.
    conflicted_urls = {
        conflict.canonical_url
        for conflict in deduplication.metadata_conflicts
    }

    eligible_records = []
    excluded_records = []

    # 4. Evaluate the source and competitor policies.
    for record in deduplication.records:
        decision = apply_policy(record, policy)

        if record.canonical_url in conflicted_urls:
            reasons = [
                code
                for code in decision.reason_codes
                if code != "SOURCE_POLICY_ACCEPTED"
            ]

            if "DUPLICATE_METADATA_CONFLICT" not in reasons:
                reasons.append("DUPLICATE_METADATA_CONFLICT")

            decision = decision.copy(
                update={
                    "eligibility": "excluded",
                    "reason_codes": reasons,
                }
            )

        if decision.eligibility == "eligible":
            eligible_records.append(_to_jsonable(decision))
        else:
            excluded_records.append(_to_jsonable(decision))

    # 5. Preserve validation failures, duplicate reports and conflicts.
    invalid_data = [
        _to_jsonable(record)
        for record in invalid_records
    ]

    duplicate_data = [
        _to_jsonable(duplicate)
        for duplicate in deduplication.duplicates
    ]

    conflict_data = [
        _to_jsonable(conflict)
        for conflict in deduplication.metadata_conflicts
    ]

    # 6. Export all results.
    _write_json(output_path / "eligible.json", eligible_records)
    _write_json(output_path / "excluded.json", excluded_records)
    _write_json(output_path / "invalid_records.json", invalid_data)
    _write_json(output_path / "duplicates.json", duplicate_data)
    _write_json(output_path / "metadata_conflicts.json", conflict_data)

    summary = {
        "input_records": len(records) + len(invalid_records),
        "valid_input_records": len(records),
        "invalid_records": len(invalid_records),
        "deduplicated_records": len(deduplication.records),
        "duplicate_records": len(deduplication.duplicates),
        "metadata_conflicts": len(deduplication.metadata_conflicts),
        "eligible_records": len(eligible_records),
        "excluded_records": len(excluded_records),
    }

    _write_json(output_path / "summary.json", summary)

    return summary