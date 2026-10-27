"""End-to-end tests for the source processing pipeline."""

import json
from pathlib import Path

from source_filter.pipeline import run_pipeline


SUBMISSION_DIR = Path(__file__).resolve().parents[1]

FIXTURE_PATH = (
    SUBMISSION_DIR / "fixtures" / "source_records.json"
)

POLICY_PATH = SUBMISSION_DIR / "policy.json"


def test_pipeline_exports_all_expected_files(tmp_path):
    summary = run_pipeline(
        FIXTURE_PATH,
        POLICY_PATH,
        tmp_path,
    )

    expected_files = {
        "eligible.json",
        "excluded.json",
        "invalid_records.json",
        "duplicates.json",
        "metadata_conflicts.json",
        "summary.json",
    }

    assert expected_files == {
        path.name for path in tmp_path.iterdir()
    }

    assert summary["input_records"] == 7
    assert summary["invalid_records"] == 1
    assert summary["deduplicated_records"] == 5
    assert summary["duplicate_records"] == 1
    assert summary["eligible_records"] == 2
    assert summary["excluded_records"] == 3


def test_pipeline_preserves_unknown_dates(tmp_path):
    run_pipeline(
        FIXTURE_PATH,
        POLICY_PATH,
        tmp_path,
    )

    eligible = json.loads(
        (tmp_path / "eligible.json").read_text(
            encoding="utf-8"
        )
    )

    authoritative = next(
        item
        for item in eligible
        if item["source_id"] == "source-003"
    )

    assert authoritative["publication_date"] is None
    assert authoritative["event_date"] is None


def test_metadata_conflicts_block_eligibility(tmp_path):
    fixture = tmp_path / "conflicting-input.json"

    fixture.write_text(
        json.dumps(
            [
                {
                    "source_id": "primary-001",
                    "url": "https://example.org/story",
                    "source_type": "primary",
                    "claim_kind": "other",
                    "discovery_lineage": ["feed-a"],
                },
                {
                    "source_id": "competitor-001",
                    "url": (
                        "https://example.org/story"
                        "?utm_source=feed"
                    ),
                    "source_type": "competitor",
                    "claim_kind": "product_promotional",
                    "discovery_lineage": ["feed-b"],
                },
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"

    summary = run_pipeline(
        fixture,
        POLICY_PATH,
        output_dir,
    )

    excluded = json.loads(
        (output_dir / "excluded.json").read_text(
            encoding="utf-8"
        )
    )

    assert summary["metadata_conflicts"] >= 1
    assert summary["eligible_records"] == 0
    assert len(excluded) == 1

    assert "DUPLICATE_METADATA_CONFLICT" in (
        excluded[0]["reason_codes"]
    )