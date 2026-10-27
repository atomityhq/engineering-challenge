# Stage 1 — Typed contracts and strict validation

Status: complete. Stage 2 and subsequent stages remain pending separate authorization.

## Implemented boundaries

- `g2/contracts.py`: frozen, slotted `Metadata` and label-free `EvaluationCase`; exact `SourceType`, `ContentType`, and `CurrentStatus` enums.
- `g2/_checks.py`: shared scalar construction checks. Direct dataclass construction cannot bypass declared enum, boolean, date, text, or metadata types through ordinary initialization.
- `g2/errors.py`: immutable `ValidationIssue` plus `ValidationError`, carrying stable code, field path, and safe explanation.
- `g2/validation.py`: pure JSON decoding, exact case/metadata object shapes, strict ASCII ISO calendar dates, enum conversion, and actual boolean checks.
- `g2/__init__.py`: public contract and validation imports.
- `tests/test_validation.py`: standard-library unit tests using independent in-memory synthetic data; no starter fixture loading or filesystem/network side effects.

Every date key is required but accepts explicit null. Recognized `unknown` categories remain valid. Cross-field temporal inconsistencies, future verification, and supersession disagreements are preserved for later assessment, not resolved by structural validation. Text is not trimmed or interpreted as instructions.

`expected_decision` is excluded from the evaluation contract and rejected as an extra input field. This establishes input exclusion only; fixture adaptation and evaluator leakage/routing tests belong to later stages.

## Validation behavior

Error codes currently include `INVALID_TYPE`, `EMPTY_STRING`, `MISSING_FIELD`, `UNKNOWN_FIELD`, `INVALID_DATE`, `INVALID_ENUM`, `INVALID_JSON`, `DUPLICATE_KEY`, and `NON_FINITE_NUMBER`.

Boundary errors have field paths, including caller-supplied nested case context. JSON decoder hooks report `$` because the standard-library hooks do not supply nested locations. Unknown keys, enum input values, raw documents, and decoder messages are not included in error messages. No logging of input content is performed.

JSON decoding rejects repeated keys at every nesting level, nonstandard NaN/infinity literals, and finite-token float overflow such as `1e999`. Decoder nesting/integer-limit failures become safe structured errors. No general maximum document size or adversarial resource-budget guarantee is claimed.

## Executed verification

Working directory: repository `src/task-6_saijaz/`.

Executed command: `/usr/bin/python3.11 -B -m unittest discover -s tests -v`.

Result: **18 tests passed, zero failures or errors**, under the Stage 0 Python 3.11.15 interpreter. Parameterized subtests exercise all metadata/date/boolean fields and supported category values.

Coverage includes:

- Valid JSON-to-contract conversion and unchanged caller input.
- Every required case/metadata key; null versus missing dates.
- Extra/non-string keys, including expected labels.
- Non-object input, blank text, and wrong scalar types.
- Boolean coercion rejection and exact enum vocabulary.
- Invalid calendar dates, timestamps, alternate ISO forms, whitespace, and non-ASCII date digits; valid leap-day and upper date boundary.
- Recognized unknowns and every content/status combination remaining structurally valid.
- Safe nested error paths, duplicate keys, non-finite numbers, malformed/deep JSON.
- Direct construction invariants, frozen case/metadata/error objects, and label-free dataclass fields.

Additional checks: all six Python files parsed successfully via in-memory `ast.parse`; editor diagnostics reported no errors for `g2/` and `tests/`. No separate static type checker or compatibility suite on other Python versions was run.

Repository audit at validation time: all eight untracked files were within the submission directory; tracked diff was empty. Original fixture bytes matched `HEAD` and retained SHA-256 `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`. Validation used `-B`; no dependencies were installed or network access required.

## Scope choices and deferred work

Two small support modules avoid circular imports: contracts and parsers share `_checks.py`, and both use `errors.py`. No external validation framework was added.

Stage 2 will implement the original fixture envelope adapter and separate expected-label extraction. Policy contracts, temporal assessments, report/output invariants, score calculation, sensitivity, CLI, and generated reports remain unimplemented. No starter routing outcomes are claimed yet.
