
# Task 1 — Source Normalisation and Filtering

## Overview

This project implements a small, local Python component that validates saved source records, normalises URLs, identifies duplicates, preserves discovery provenance, applies configurable source policies, and exports eligible and excluded records with explicit reason codes.

The implementation is deterministic and does not require external APIs, model access, authentication, or a live web crawler.

## Requirements

- Python 3.11 or later
- Pydantic 1.x
- pytest for automated tests

## Installation

Create and activate a virtual environment.

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Run the Tests

From this directory, run:

```bash
python -m pytest -q
```

The test suite covers input validation, URL normalisation, duplicate detection, provenance preservation, metadata conflicts, competitor policies, invalid input, the complete pipeline, and CLI behaviour.

## Run the Example

From this directory, run:

```bash
python -m source_filter.cli \
  --input fixtures/source_records.json \
  --policy policy.json \
  --output-dir examples/output
```

The example uses synthetic local records. It does not contact the example domains or retrieve live content.

## Input Contract

The input is a JSON array of source records.

Required fields:

- `source_id`: non-empty record identifier
- `url`: HTTP or HTTPS URL

Optional fields include:

- `publisher`
- `source_type`
- `claim_kind`
- `publication_date`
- `event_date`
- `canonical_url`
- `discovery_lineage`

Unknown dates remain `null`. Invalid individual records are reported separately, while malformed JSON or an invalid top-level structure produces a clear error.

## Processing Architecture

The processing pipeline follows these stages:

1. Load and validate individual JSON records.
2. Load and validate the policy configuration.
3. Normalise URLs and identify exact or canonical-URL duplicates.
4. Preserve discovery lineage and report conflicting metadata.
5. Apply source and competitor policies.
6. Export eligible records, excluded records, validation failures, duplicate reports, metadata conflicts, and a summary.

### URL Normalisation

The implementation lowercases URL schemes and hostnames, removes fragments and default ports, removes common tracking parameters, and preserves meaningful query parameters.

An explicit canonical URL is preferred when supplied. Otherwise, the source URL is used.

### Deduplication and Provenance

Records are grouped by their normalised canonical URL. The first record provides the retained source ID, and discovery lineage is merged in input order without duplicates.

Conflicting known metadata is reported rather than silently ignored. Records with metadata conflicts are excluded from eligibility pending review.

### Source and Competitor Policies

Policies are defined in `policy.json`.

- Primary and authoritative sources are approved by the default configuration.
- Low-quality sources are excluded.
- Competitor promotional or product claims are excluded.
- Competitor generic industry claims are excluded and marked as requiring independent verification.
- Unapproved source types are excluded by default.

Changing the policy configuration changes which source types are eligible without requiring changes to the processing pipeline.

## Output Files

The example writes the following files into the requested output directory:

| File | Purpose |
|---|---|
| `eligible.json` | Records accepted by the configured policy |
| `excluded.json` | Records excluded with explicit reason codes |
| `invalid_records.json` | Individual input validation failures |
| `duplicates.json` | Duplicate detection results |
| `metadata_conflicts.json` | Conflicting metadata observations |
| `summary.json` | Counts for the processing run |

## Design Decisions

- Pydantic is used to validate typed input and output contracts.
- URL normalisation is deliberately conservative to avoid deleting meaningful query parameters.
- JSON configuration keeps source policy separate from processing logic.
- Invalid records are preserved in an error report rather than silently discarded.
- Duplicate provenance is merged while retaining deterministic record selection.
- Metadata conflicts prevent automatic eligibility.
- A local CLI provides a reproducible example without external services.

## Known Limitations

- URL normalisation uses a limited set of rules and does not establish that two different URLs always identify the same real-world document.
- The component does not fetch or independently verify source content.
- Competitor generic claims are flagged for independent verification, but that verification is not performed automatically.
- Source authority depends on the supplied source classification and configured policy; the implementation does not independently establish publisher credibility.
- Metadata conflicts are reported for review, and the first record supplies the representative value.
- The system is a local prototype, not a production crawling or publishing service.

## Synthetic Fixture

`fixtures/source_records.json` contains seven synthetic records covering canonical duplicates, unknown dates, an authoritative source, competitor claims, a low-quality source, and a malformed record.

All test data uses example domains and should not be interpreted as real-world evidence.
