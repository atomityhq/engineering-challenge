# Stage 2 — Fixture adapter and test-label firewall

Status: complete. Stage 3 and subsequent stages remain pending authorization.

## Implemented

- `g2/fixtures.py`: frozen `FixtureInputs`, pure `validate_fixture`, and UTF-8 `load_fixture(Path)` with safe structured read/encoding errors.
- `g2/testing.py`: test-only `ExpectedDecision`, frozen `ExpectedOutcome`, and separate `extract_expected_outcomes` API. Production fixture loading does not import this module or return labels.
- `tests/test_fixtures.py`: 12 additional unit tests; I/O is mocked, synthetic inputs are independent of the original fixture, and no unit tests write files or access networks.

Envelope validation requires exact keys, schema `1.0`, synthetic true, a non-null assessment date, non-empty cases, and unique non-blank case identifiers. Demo policy requires exact keys, a nonnegative integer event-age limit (booleans rejected), and the recognized `human_review` unknown-temporal convention.

The supplied original age limit is 30. Other nonnegative limits are accepted as explicit fixture-owned inputs, not silently substituted. `instructions`, `regulation_rule`, and `weights_and_threshold` must be non-blank strings but are inert informational prose; they are discarded rather than interpreted as policy.

Fixture cases may carry an optional `expected_decision` field. Production adaptation recognizes its key but never inspects its value; absent or replaced labels do not affect validated inputs. All other extra fields are rejected. The test-only extractor requires a recognized label for every case and returns immutable ID/label pairs separately. It is intentionally not re-exported from the package root.

`FixtureInputs` contains only schema version, synthetic flag, assessment date, event-age limit, and label-free cases. Direct construction validates those invariants. The original fixture is read in place, never copied or modified.

## Verification

Executed from the submission directory with `/usr/bin/python3.11 -B -m unittest discover -s tests -q`:

**30 tests passed, zero failures/errors** (18 Stage 1 tests plus 12 Stage 2 tests).

New coverage: missing/extra envelope and policy fields, schema/synthetic/date errors, empty cases, duplicate IDs, nested validation paths, strict demo-policy values, immutable direct construction, label mutation/removal invariance, separate label validation, inert instruction/policy prose, renamed ID/statement metadata preservation, and safe mocked file/encoding failures.

All nine Python files passed in-memory AST parsing; editor diagnostics reported no errors for source and tests.

A separate read-only integration probe loaded the original nine cases through `load_fixture` and extracted nine acceptance labels through the test-only API. Schema `1.0`, assessment date `2026-10-06`, and age limit 30 were confirmed. Replacing every original label in memory with an arbitrary JSON object left `validate_fixture` output identical. Production dataclass-field exclusion and AST import separation checks passed.

Original fixture SHA-256 remained `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`; tracked fixture diff was empty during the audit. No dependency installation, bytecode generation, or network access was needed.

An initial test run exposed a date-construction error: already-parsed date objects were incorrectly sent through the JSON date parser. The constructor now uses the date-instance invariant check; the full suite and integration probe were rerun successfully. A first narrow edit did not apply this correction, so the affected method was replaced and its actual contents verified before rerunning.

## Deferred verification

No evaluator exists yet. ID/statement changes are verified to preserve metadata and assessment context, not claimed to preserve executed routing. Actual routing invariance, all starter expected outcomes, and evaluator label-leakage tests remain assigned to later stages. No scoring policy, temporal rules, CLI, or generated evaluation reports were implemented here.
