
# Task 2 — Claim-to-Evidence Validation

## Overview

This project implements a small, testable Python component that evaluates whether supplied evidence supports pre-extracted factual claims.

It preserves source references and exact excerpts, identifies missing sources, flags unsupported numerical claims, detects selected conflicting statements, and exposes uncertainty for human review.

The implementation uses Pydantic for typed input/output validation and pytest for automated tests. It runs locally without API keys or external services.

## Project structure

```text
task-2_guna/
├── README.md
├── requirements.txt
├── main.py
├── models.py
├── validator.py
├── fixtures/
│   └── claims.json
├── examples/
│   ├── input.json
│   └── expected_output.json
└── tests/
    └── test_validator.py
```

## Requirements

- Python 3.10 or newer
- Pydantic 2.x
- pytest

## Installation

From the repository root, activate your virtual environment and install dependencies:

```powershell
python -m pip install -r src/task-2_guna/requirements.txt
```

## Run automated tests

```powershell
python -m pytest src/task-2_guna/tests -v
```

## Run the demonstration

```powershell
python src/task-2_guna/main.py
```

The demonstration reads `fixtures/claims.json` and prints a validation result for each claim. Malformed claim records should be reported clearly instead of being accepted as valid claims.

## Input contract

The input JSON contains two arrays: `sources` and `claims`.

Each source contains:

- `source_id`: identifier referenced by claims.
- `locator`: location of the excerpt in its source.
- `excerpt`: exact evidence text.

Each claim contains:

- `claim_id`: unique claim identifier.
- `text`: claim to validate.
- `source_ids`: list of source identifiers.
- `classification`: `fact` or `inference`.

## Output contract

Each validation result includes:

- Claim identifier and text.
- Status: `supported`, `unsupported`, or `uncertain`.
- Submitted classification and assessed classification, where available.
- Referenced source IDs.
- Evidence source IDs, locators, and exact excerpts.
- Contradictions.
- Unresolved questions.
- A brief explanation of the decision.

## Status meanings

- **supported** — the implemented comparison rules found direct textual support.
- **unsupported** — a source is missing, no usable evidence is available, or a required numerical value is not supported by the relevant excerpts.
- **uncertain** — evidence is ambiguous or conflicting, or the claim may be an inference incorrectly labelled as a fact.

## Design decisions

1. **Typed contracts:** Pydantic models validate claim and source records.
2. **Traceability:** Results preserve the original source IDs, locators, and excerpts.
3. **Explicit uncertainty:** Conflicting evidence is retained for review rather than silently choosing a source.
4. **Offline execution:** The component requires no model API or undisclosed credentials.
5. **Independent testing:** Validation logic can be exercised with pytest without a web application or external service.

## Security considerations

Evidence excerpts are treated as untrusted data. The implementation does not execute source text or interpret it as application instructions. No API keys or passwords are required.

## Limitations

This is a deliberately limited rule-based baseline, not a general semantic fact-checker.

- Normalized text matching does not reliably understand paraphrases.
- Keyword overlap is only a rough approximation of shared context.
- Numeric presence checks do not prove mathematical correctness or unit equivalence.
- Direction and inference detection rely on a limited vocabulary.
- Locator validation cannot confirm that a location exists in the original document unless that document is available.
- Human review is still required for ambiguous or high-impact claims.

These limitations are documented to avoid presenting heuristic matching as general semantic verification.

## Test coverage

The test suite currently covers direct support, unsupported numerical claims, missing sources, conflicting evidence, inference-labelled-as-fact, malformed claims, and additional evidence-reference edge cases. Expand the tests when adding further validation rules.
