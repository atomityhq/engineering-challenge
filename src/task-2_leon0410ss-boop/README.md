# Task 2 — Claim-to-Evidence Validation

## Overview

This project implements a small, testable Python component for validating whether pre-extracted factual claims are adequately supported by supplied source evidence.

The validator is designed as a narrow and transparent rule-based baseline. It does not attempt general-purpose semantic fact verification. Instead, it focuses on explicit evidence resolution, numerical consistency, direct textual support, simple inference detection, conflict preservation, and uncertainty reporting.

## Features

The validator supports:

- resolving claim references to source excerpts
- detecting missing source IDs
- detecting missing evidence locators
- identifying directly supported claims
- detecting unsupported numerical values
- distinguishing facts from simple inference or causal claims
- detecting conflicting numerical evidence
- preserving unresolved questions
- returning explicit `supported`, `unsupported`, or `uncertain` decisions
- maintaining a provenance chain from claim to source, locator, excerpt, and validation decision
- rejecting malformed inputs through Pydantic validation

## Project Structure

```text
task-2_leon0410ss-boop/
├── examples/
│   └── run_validation.py
├── fixtures/
│   ├── validation_cases.json
│   └── malformed_claim.json
├── src/
│   ├── __init__.py
│   ├── models.py
│   ├── rules.py
│   └── validator.py
├── tests/
│   └── test_validator.py
├── requirements.txt
└── README.md
```

## Setup and execution

Requires Python 3.10 or later. The submission was verified with Python 3.14.
From the repository root:

```bash
cd src/task-2_leon0410ss-boop
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python examples/run_validation.py
```

Run the tests from the submission directory: fixture paths are relative to it.
The example prints JSON for all five claims, including the resolved evidence,
exact locators, status, classification, contradictions, and explanations.
Dependency installation requires package access; tests and the example run
locally without credentials, model calls, or external services.

The malformed-input example can be run separately from the same directory:

```bash
python - <<'PY'
from pathlib import Path
from pydantic import ValidationError
from src.models import Claim

try:
    Claim.model_validate_json(Path("fixtures/malformed_claim.json").read_text())
except ValidationError as error:
    print(error)
else:
    raise SystemExit("Expected a validation error")
PY
```

## Contracts and design note

`src/models.py` defines the Pydantic input and output contracts. A `Source`
contains a source ID, title, and excerpts with exact string locators. A `Claim`
contains its ID, text, and a list of `(source_id, locator)` references.
`ValidationResult` contains the original claim, support status, fact/inference
classification, supporting source IDs, evidence records, contradictions,
unresolved questions, and a reason.

`src/rules.py` contains independent, deterministic text and numerical rules.
`src/validator.py` resolves each reference by exact source ID and locator,
preserves resolved excerpts, and returns `uncertain` for unresolved references
or absent evidence. Conflicting sets of numerical tokens across referenced
excerpts are preserved as contradictions and produce `uncertain`.

For other claims, support and classification are evaluated against the first
resolved excerpt. Text equality after lowercasing and whitespace normalization
establishes direct support. A claim number absent from that excerpt produces
`unsupported`; other unmatched text produces `uncertain`. A fixed list of
English inference markers identifies unmatched causal or speculative language.
Source text is processed only as data and is never executed as instructions.

## Fixtures and checks

All fixtures are synthetic and local to this submission. No supplied repository
fixtures are copied or changed.

| Case | Fixture | Expected result | Automated check |
| --- | --- | --- | --- |
| Direct support | `claim-001` | `supported`, `fact`, source-001 / paragraph-2 | `test_directly_supported_claim` |
| Unsupported numerical value | `claim-002` | `unsupported`, no supporting IDs | `test_unsupported_numerical_claim` |
| Missing source | `claim-003` | `uncertain`, explicit missing-source question | `test_missing_source` |
| Conflicting excerpts | `claim-004` | `uncertain`, both excerpts and contradiction retained | `test_conflicting_evidence` |
| Inference presented as fact | `claim-005` | `uncertain`, `inference` | `test_inference_presented_as_fact` |
| Malformed input | `malformed_claim.json` | Pydantic `ValidationError` for missing text | `test_malformed_claim` |

Unknown source IDs and unknown locators are reported during reference
resolution. Missing required fields or invalid field types are rejected by
Pydantic. The six tests above do not exhaustively exercise malformed references
or locator failure cases.

## Known limitations and trade-offs

- This is a narrow rule-based baseline, not general semantic verification.
  It does not establish the truth of a source or understand paraphrases,
  negation, units, numerical roles, or contextual entailment.
- Support evaluation uses only the first resolved excerpt. For a supported
  result, all resolved source IDs are currently listed; this does not establish
  that each additional excerpt independently supports the claim.
- Numerical conflict detection compares token sets without checking whether
  the excerpts discuss the same metric, entity, or period. It can flag unrelated
  numbers and miss non-numerical contradictions.
- Inference detection uses a small English substring list. Exact text matches
  and early uncertain results are classified as `fact`, which does not prove
  they are objective facts.
- An unresolved reference returns before conflict detection, so contradictions
  among the remaining resolved excerpts are not reported in that case.
- Empty strings and duplicate source IDs or locators are not explicitly
  rejected. Duplicate identifiers resolve to the first match.
- Dependencies are not pinned. The implementation requires Pydantic 2 APIs.

These constraints keep the decision process inspectable, while leaving broader
semantic validation and more complete edge-case coverage for future work.
