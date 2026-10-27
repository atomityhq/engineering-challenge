# Stage 3 — Policy configuration and numerical safeguards

Status: complete. Stage 4 and later stages remain pending authorization.

## Implemented

- `g2/policy.py`: frozen `CriterionValues`, `AuthorityMapping`, and `Policy`; pure `validate_policy` and safe UTF-8 JSON `load_policy`.
- `config/policy.json`: explicit provisional grounding-first policy, exact authority map, versions, uncalibrated status, and rationale.
- `tests/test_policy.py`: 11 additional unit tests with in-memory data and mocked file I/O.

Chosen policy:

| Criterion | Weight | Floor |
| --- | --- | --- |
| Evidence support | 0.45 | 1.0 |
| Source authority | 0.30 | 0.5 |
| Temporal validity | 0.25 | 1.0 |

Threshold: 0.80. Authority map: primary 1, official indirect 0.75, reputable secondary 0.5, competitor 0, unknown null. Versions: policy schema `1.0`, policy `g2-demo-v1`, weights `grounding-first-v1`.

The configuration records the provisional rationale rather than implying measurement or label-based calibration. With support and time at 1, the chosen score formula is 0.70 + 0.30 × authority; its threshold is partly redundant with the authority floor. Actual scores/routing have not yet been implemented or evaluated.

## Validation contract

Exact criterion, authority, and top-level keys are mandatory. Values must be finite non-boolean numbers. Weights are nonnegative; accurate `math.fsum` must be within absolute `1e-9` of one, with relative tolerance zero. Invalid sums are never normalized. Floats immediately inside/outside both tolerance edges are tested using `math.nextafter`; accepted input is preserved without normalization.

Floors, thresholds, and known authority values must be in [0, 1]. Unknown authority must stay null. A standalone `CriterionValues` validates nonnegative finite entries; its role-specific sum or upper-bound checks occur when assembled into `Policy`. Sum and numeric-conversion overflow produce safe structured errors. Weight sum tolerance is fixed implementation policy, not an externally configurable relaxation of future pass thresholds.

Schema 1.0 accepts only `uncalibrated` status; unsupported calibration claims are rejected. Policy and weights versions and rationale must be non-blank strings. Direct construction enforces typed nested contracts and invariants. Alternate known authority values within [0, 1] are structurally accepted as explicit provisional preferences; the selected file contains the master-plan mapping. Every materially changed configuration should receive a new version and documented rationale; no automated historical version registry is claimed.

There are no policy fields for assessment date, event-age limit, or fixture temporal conventions. Such extra keys are rejected, keeping fixture-owned context separate. Operational errors do not reveal file paths or raw data. Strict JSON decoding reuses duplicate-key/non-finite rejection from Stage 1.

## Executed verification

Command from submission directory: `/usr/bin/python3.11 -B -m unittest discover -s tests -q`.

**41 tests passed, zero failures/errors**: 18 Stage 1, 12 Stage 2, and 11 Stage 3 tests.

New coverage: missing/extra criterion and policy keys, attempted freshness/tolerance overrides, booleans/string/non-finite/negative/oversized numeric inputs, wrong sums and accurate-sum overflow, upper/lower tolerance edges, no normalization, floor/threshold/authority bounds, unknown-authority null preservation, schema/version/calibration validation, immutable direct construction, safe mocked I/O, and strict JSON errors.

All 11 Python files passed in-memory AST parsing; no editor diagnostics were reported for the new source, tests, or JSON configuration. Actual `load_policy` and `load_fixture` calls succeeded. The original fixture retained its 30-day limit and matched Git HEAD byte-for-byte, SHA-256 `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`. Staged and unstaged tracked diffs were empty; all untracked submission artifacts were within the designated folder.

No dependencies installed, network operations, or bytecode writes. Only the established Python 3.11.15 environment was tested; no separate type-checker run is claimed.

## Deferred

Stage 4 hard checks/findings, Stage 5 temporal assessment, and Stage 6 score calculation remain unimplemented. Configuration validation does not establish empirical calibration or demonstrate passing outcomes. Required unknown-criterion blocking and threshold comparison without pass-tolerance relaxation will be tested when scoring/routing exists.
