# Task 6 — G2 evidence and current-validity gate

A deterministic, offline Python gate over synthetic evidence assertions. It assesses support, source authority and temporal validity, then routes to `reject`, `revise`, `human_review` or `pass`. It does **not** assess writing, visuals or engagement. Pass means eligibility for the next internal stage, not publication approval.

## Setup, run and tests

Python **3.11+** is declared; **3.11.15 on Linux** is the verified runtime. All dependencies are standard-library modules. No installation, pip, build backend, external service, model, network access or credentials are needed. `pyproject.toml` is metadata only.

From the repository root, change to `src/task-6_saijaz/`. Use a Python 3.11+ interpreter (`/usr/bin/python3.11` on the verified machine):

- Tests: `python3.11 -B -m unittest discover -s tests -q` — **96 tests**, including the final-review stale-news regression.
- Starter evaluation: `python3.11 -B -m g2 evaluate --output examples/my-starter-report.json`.
- Weight comparison: `python3.11 -B -m g2 compare --output examples/my-sensitivity-report.json`.
- Help: `python3.11 -B -m g2 --help`, or command-specific `--help`.

Both commands accept `--fixture PATH`, `--config PATH`, and required `--output PATH`. For explicit starter input, use `--fixture ../../fixtures/g2-cases.json --config config/policy.json`. Output parents must exist; use new filenames. Every existing destination is refused, including the saved reference examples. There is no force option. Exit 0 means execution completed even when a case is rejected; exit 2 denotes argument, validation or I/O failure. Reports are UTF-8 JSON files, safe diagnostics use logging on stderr. See [CLI usage](CLI_USAGE.md).

Defaults resolve relative to the module: evaluate reads the original root fixture, compare reads the additional local fixture, and both load local policy. Explicit relative arguments resolve against the current directory. Keep the repository layout intact. The task's `challenge-starter/g2-cases.json` reference is stale; the actual supplied file is `../../fixtures/g2-cases.json`. It is read in place, never copied or modified.

## Architecture and contracts

`strict JSON -> validated inputs -> hard checks -> temporal assessment -> criteria/score eligibility -> weighted sum -> ordered routing -> complete report`

- `g2/contracts.py`, `validation.py`, `fixtures.py`: frozen/slotted input contracts and exact boundary validation.
- `g2/policy.py`, [policy configuration](config/policy.json): immutable scoring preferences and numerical safeguards.
- `g2/hard_checks.py`, `freshness.py`: pure metadata checks and explicit-date temporal reasoning.
- `g2/evaluator.py`, `reports.py`: criteria, score blocking, validated findings/routing and deterministic serialization.
- `g2/sensitivity.py`: fixed-context weight-only comparisons, ranks, ties and routing changes.
- `g2/__main__.py`: I/O and CLI boundary; pure evaluators do not access files, clocks or services.
- `g2/testing.py`: separate test-only expected-label extraction, never imported by the evaluator.

All required keys must exist, including nullable dates. Missing fields are malformed; explicit null represents unknown. Dates are exact ASCII YYYY-MM-DD; booleans are actual bools; enum strings must be recognized. Duplicate JSON keys, non-finite numbers, unknown keys and invalid types fail safely. Temporal inconsistencies remain structurally valid and produce findings. Output constructors recompute their invariants; annotations alone are not treated as validation.

Fixture instruction prose and statements are untrusted inert data. Source categories/support flags are trusted synthetic assertions. Expected labels are removed at adaptation, not interpreted by the evaluator. IDs identify output only; prose is neither parsed for rules nor included in reports.

## Hard checks and ordered routing

Four positive check names expose pass/fail/unknown, reasons and metadata basis:

1. `material_claim_supported`: false support fails; true support plus contradiction is unknown.
2. `evidence_not_superseded`: either supersession assertion fails; disagreement additionally remains visible.
3. `competitor_promotion_absent`: product promotion is prohibited for every source category.
4. `evidence_conflict_absent`: disagreement requires review, not a conclusion of falsehood.

Collect every finding before routing: **prohibited -> reject; repairable -> revise; unresolved/floor/threshold issue -> human_review; otherwise -> pass**. Promotion plus uncertainty rejects; unsupported plus conflict revises and retains both. No average overrides a mandatory check. Generic competitor information may have a diagnostic score, but always requires independent original evidence and review, even under permissive floors/thresholds.

## Freshness and applicability

Use fixture `as_of=2026-10-06`, not today's date. Publication and verification dates remain context; they never replace required event/effective dates.

- Current news uses event age: 0–30 days inclusive can be valid when required status is resolved; >30 needs revision regardless of asserted current status. This fixture-owned limit is a demo convention, not scientifically calibrated. Unknown/future event dates require review. Unknown news status or adopted-not-applicable news status is unresolved/incompatible; those findings remain visible even when known staleness takes revision precedence. News legal applicability is `not_applicable` with null `currently_applicable`, not a scoring unknown.
- Current regulations need effective date on/before as_of and no supersession/temporal inconsistency. Old publication alone is not stale.
- Adopted future regulations need effective date strictly after as_of. They may have temporal validity 1 while `currently_applicable=false`. Equality or inconsistent status requires review; prose accuracy relies on support metadata.
- Supersession gives temporal 0/inactive; unknown required dates/status give null. Future verification adds a review finding and temporal null unless known invalidity already establishes 0. No verification expiry or universal date ordering is invented.

Known invalidity takes precedence over uncertainty, then valid timing; all findings remain visible. Unrelated support conflict does not invent contradictory dates.

## Criterion anchors and policy

| Criterion | 0 | 0.5 | 1 | Unknown |
| --- | --- | --- | --- | --- |
| Evidence support | Explicit unsupported assertion | Explicit partial/qualified support | Supported without unresolved contradiction | Supported plus conflict -> null |
| Source authority | No independent claim authority | Reputable independent secondary reporting | Primary issuer/originating announcer | Unknown relationship -> null |
| Temporal validity | Superseded, stale or known-invalid timing | Explicit qualified period/scope | Appropriate event or current/future rule description | Missing/inconsistent required timing -> null |

The minimum boolean/date schema cannot represent partial support or qualified temporal scope: those two 0.5 anchors describe hypothetical explicit assertions and are **not implemented or emitted**. Supported inputs emit support and temporal values of 0, 1 or null; source authority does emit 0.5 for reputable secondary reporting. A partial-support or qualified-scope extension would require new typed metadata and tests, not an inference from missing information. Missing information never becomes 0.5 or 0. Source mapping: primary 1, official indirect 0.75, reputable secondary 0.5, competitor 0, unknown null. Relationships are assertions, not inferred from names. See [additional fixture relationships](fixtures/README.md).

Policy `g2-demo-v1`, weights version `grounding-first-v1`, calibration status **uncalibrated**:

| Criterion | Weight | Floor | Preference rationale |
| --- | --- | --- | --- |
| Evidence support | 0.45 | 1 | Grounding is central; unsupported claims are separately blocked |
| Source authority | 0.30 | 0.5 | Distinguishes acceptable provenance without replacing support |
| Temporal validity | 0.25 | 1 | Rewards appropriate timing while explicit temporal defects remain gates |

Threshold **0.80**, inclusive. All criteria are required even at zero weight. Any mandatory blocker/unknown withholds aggregate (null), but keeps criteria and reasons. Known low authority can be scored diagnostically and still fail floors. Eligible score is the full-precision `math.fsum(weight × criterion)`; floors and threshold are independent pass conditions.

Weights are finite/non-boolean/nonnegative and sum to 1 within absolute tolerance **1e-9**, never normalized. Floors/threshold are in [0,1]. Tolerance is for weight validation only, never threshold relaxation. If a tolerated sum >1 creates aggregate >1, evaluation fails `AGGREGATE_OUT_OF_RANGE`, not clipping; a sum below 1 is not rounded up.

The threshold is a conservative preference, not fitted to labels. With support/timing 1, selected score is 0.70 + 0.30 × authority. Threshold alone requires authority >=1/3, but the stricter 0.5 floor dominates. This redundancy is disclosed: support/timing floors constrain eligible variation, while authority-heavy weights make the threshold meaningful for secondary reporting. A 0.75 threshold would admit that alternative; 0.85 puts chosen secondary reporting at the boundary. Neither validates a cutoff. Scores are **not probabilities**.

## Executed examples and sensitivity

[Starter JSON](examples/starter-report.json) contains complete reports: checks/basis, criteria/floors, freshness/date context/applicability, versions/calibration, weights/threshold, aggregate or null, blockers, final decision and all finding origins/reasons.

| Starter case | Decision |
| --- | --- |
| current-news | pass |
| old-law-current | pass |
| recent-article-old-event | revise |
| unknown-date | human_review |
| unsupported-claim | revise |
| superseded-source | revise |
| competitor-promotion | reject |
| conflicting-evidence | human_review |
| future-rule | pass |

[Additional fixture](fixtures/additional-cases.json) has three distinct fictional source/event/rule scenarios; each is scoring-eligible with support/timing 1. [Comparison JSON](examples/sensitivity-report.json) keeps inputs, threshold, floors and mapping fixed:

| Case | Chosen score | Equal score | Authority-heavy score | Routes (chosen/equal/heavy) | Ranks |
| --- | --- | --- | --- | --- | --- |
| secondary-transit-report | 0.85 | 0.8333333333333333 | 0.75 | pass / pass / human_review | 3 / 3 / 3 |
| indirect-institutional-rule | 0.925 | 0.9166666666666666 | 0.875 | pass / pass / pass | 2 / 2 / 2 |
| primary-future-rule | 1 | 1 | 1 | pass / pass / pass | 1 / 1 / 1 |

Equal weights are 1/3 each; authority-heavy is (0.25,0.50,0.25). Exactly secondary reporting changes route; other routes and all ranks remain unchanged. This one-axis comparison tests policy sensitivity, not expert judgment/calibration. Exact ties share competition rank (1 + number strictly above); lexical IDs only order tied display, and null scores are unranked. Separate tests cover ties/blocked cases.

## Verification and limitations

[Acceptance mapping](ACCEPTANCE.md) links requirements to executable tests and artifacts. [Stage 10 evidence](STAGE_10_RESULTS.md) records 95 passing tests, 24 parsed Python files, guarded fresh-process network/clock tests, hash-seed/timezone invariance, safe logging and original fixture integrity. Both saved examples were reproduced byte-for-byte. Other Python versions/platforms and hidden tests are not certified.

- Fictional metadata is trusted, not independently verified. No live source passages, LLM, learned weights, expert panel, publication approval or real-world legal judgment.
- No schema for partial support/qualified timing, expiry, scheduled news, out-of-scope classification, revision exhaustion or competitor exceptions; these need separately specified inputs/policy.
- Application-level network guards and import checks are not an OS sandbox or universal security proof. No large-input resource quotas; memory exhaustion is outside the demo scope.
- Existing outputs and input aliases are protected; parent directories must exist. Mid-write failure can leave a new partial file. No atomic rollback or adversarial concurrent path-mutation guarantee.
- Strict vocabulary is intentional: unsupported categories fail rather than acquire guessed authority. Pure modules offer replaceable boundaries, but no unused integration framework is added.
- Clean-checkout rehearsal is complete; see the Stage 12 evidence below. No automatic commit/push/PR/publication.

[Stage 12 rehearsal](STAGE_12_RESULTS.md) records the historical 95-test snapshot and the **2026-10-27 corrected-snapshot rehearsal: 96 tests passed** in an isolated HEAD baseline plus submission copy. Default and explicit starter evaluation and weight comparison reproduced the saved reports byte-for-byte; all 24 Python files parsed and the original fixture matched HEAD. No dependency installation was required. This is snapshot verification, not a claim about an already committed checkout.

[Master plan](MASTER_PLAN.md) explains alternatives and stage history. [Local PR description](PR_DESCRIPTION.md) is prepared text only. A local commit is user-authorized; pushing and opening a PR require separate authorization.
