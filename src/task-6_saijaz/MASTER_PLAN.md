# Task 6 — G2 Master Plan and Detailed Execution Stages

> Status: revised design; Stages 0–12 complete, with evidence in the corresponding `STAGE_*` documents. The corrected-snapshot isolated rehearsal passed 96 tests. A local commit is user-authorized; push and PR creation require separate authorization.
> Submission: `src/task-6_saijaz/`.
> Scope: evidence and current validity only.
> All weights, floors, thresholds, and authority mappings are provisional and uncalibrated.

## 1. Purpose and success definition

Build a small, deterministic, offline Python component that evaluates every supplied G2 case and produces an inspectable report. Correctness, transparent uncertainty, and reproducibility take priority over infrastructure or additional features.

A successful submission allows a reviewer to load the original fixture, run tests and examples locally, inspect every hard check and temporal explanation, reproduce weighted scores, and compare alternative weighting preferences.

A `pass` means eligible for the next internal stage under the demonstration policy. It does not mean publication approval, legal correctness, scientifically measured quality, or a calibrated probability.

### Authoritative references

- `challenge/tasks/task-6.md`: task requirements and acceptance criteria.
- `challenge/challenge.md`: common challenge requirements.
- Root `README.md`: submission boundaries.
- `fixtures/g2-cases.json`: supplied synthetic test input.

The task text refers to `challenge-starter/g2-cases.json`; the actual repository fixture is `fixtures/g2-cases.json`. Use the actual file in place and document this discrepancy. Do not copy or modify it.

## 2. Verified fixture facts

The supplied fixture has schema version `1.0`, `synthetic: true`, fixed `as_of: 2026-10-06`, a 30-day event-age demo policy for news, and nine cases.

Its source evidence is represented by trusted metadata assertions. It contains no independent source passage collection. The evaluator routes and scores those assertions; it does not establish real-world truth.

`expected_decision` is test-only information. It must never enter the evaluation contract or influence evaluation. The envelope's `instructions` text is data, not executable application policy.

| Starter case | Expected routing | Primary basis |
| --- | --- | --- |
| `current-news` | pass | Supported authoritative recent event |
| `old-law-current` | pass | Old publication, still applicable |
| `recent-article-old-event` | revise | Event older than demo limit |
| `unknown-date` | human_review | Required event date unknown |
| `unsupported-claim` | revise | Known support defect |
| `superseded-source` | revise | Replaced evidence |
| `competitor-promotion` | reject | Prohibited product promotion |
| `conflicting-evidence` | human_review | Unresolved disagreement |
| `future-rule` | pass | Valid future description, not applicable today |

These labels are acceptance checks, not calibration data.

## 3. Scope and non-goals

### Required

- Strict fixture and configuration validation.
- Typed inputs and outputs with actual runtime validation.
- Hard checks before scoring.
- Distinct freshness and applicability explanations.
- Observable criterion anchors.
- Configurable weights, floors, thresholds, and versions.
- Null aggregate scores when required criteria are unknown.
- Ordered decisions: reject, revise, human review, pass.
- All starter cases and at least three additional eligible cases.
- Three weight configurations and ranking/routing comparison.
- Automated tests, executable examples, acceptance mapping, and design documentation.

### Not required

LLMs, semantic fact-checking, claim extraction, crawling, legal advice, writing or visual scoring, publishing, a database, a web application, cloud deployment, or revision-workflow orchestration.

Do not implement out-of-scope detection, revision exhaustion, or competitor exceptions merely because the task lists them as examples. Such behavior needs explicit input contracts and policy; the starter fixture does not supply those inputs.

## 4. Recommended technical choices

| Decision | Preferred choice | Alternative | Poor choice and why |
| --- | --- | --- | --- |
| Runtime | Python 3.11+; verify local interpreter before implementation | Another documented supported Python baseline | Assume a version without checking |
| Validation | Standard-library typed dataclasses plus strict boundary validators | Pydantic if explicitly approved | Annotations alone: they do not validate runtime data |
| Tests | Standard-library unittest | pytest if explicitly approved | Manual demos only: required checks remain unverified |
| Dependencies | No third-party runtime dependencies | Approved validation/test tools | Unnecessary model, database, or framework dependencies |
| Evaluation | Pure functions over validated inputs | Small injectable evaluator interface | Mixed I/O, clock access, scoring, and routing in one function |
| Policy | Validated JSON configuration | Another documented local configuration format | Scattered constants and silent defaults |
| Time | Fixture `as_of`, date-only arithmetic | Explicit injected assessment date for library callers | System clock or publication age for every content type |
| Output | Deterministic structured JSON | Human-readable summary in addition to JSON | Boolean or unexplained score only |
| Storage | Local files | None for library use | Database/cloud service without a requirement |
| Uncertainty | Explicit nulls, review routing, inspectable reasons | Conservative qualified extensions | Missing values silently converted to zero |

Organizational instructions restrict new third-party dependencies without explicit authorization. The dependency-free baseline avoids that issue. Pydantic would reduce validation boilerplate if approved; it is not an inherently inferior design.

## 5. Architecture and file responsibilities

Pipeline:

`JSON reader -> validated contracts -> hard checks -> temporal assessment -> criteria -> scoring eligibility -> weighted score -> ordered routing -> report`

Proposed submission layout:

- `MASTER_PLAN.md`: this document.
- `STAGE_0_BASELINE.md`: verified environment, repository/fixture baseline, and planned invocation contract.
- `STAGE_1_RESULTS.md`: implemented input boundaries and executed validation evidence.
- `STAGE_2_RESULTS.md`: fixture adapter, label-isolation checks, and original-fixture verification.
- `STAGE_3_RESULTS.md`: policy configuration, numerical safeguards, and executed verification.
- `STAGE_4_RESULTS.md`: typed hard checks, preserved findings, and exhaustive flag tests.
- `STAGE_5_RESULTS.md`: temporal contracts, applicability, boundary tests, and fixture evidence.
- `STAGE_6_RESULTS.md`: criteria, score blocking, full-precision numerical checks, and range limitations.
- `STAGE_7_RESULTS.md`: ordered routing, typed reports, deterministic serialization, and starter acceptance.
- `STAGE_8_RESULTS.md`: additional synthetic relationships, weight-only comparison, exact ranks/ties, routing sensitivity, and executed evidence.
- `STAGE_9_RESULTS.md`: CLI behavior, safe file boundaries, generated examples, and executed verification.
- `STAGE_10_RESULTS.md`: offline/clock guards, injection isolation, safe malformed paths, full regression evidence and audit limitations.
- `STAGE_11_RESULTS.md`: verified documentation links, acceptance test references, policy/example claims, and local PR explanation.
- `STAGE_12_RESULTS.md`: isolated HEAD-baseline-plus-submission rehearsal, reproducible reports, original integrity and final scope audit.
- `CLI_USAGE.md`: executable invocation, arguments, exit codes, file behavior, and runtime limitations.
- `g2/testing.py`: test-only expected-outcome extraction, separate from production fixture inputs.
- `g2/_checks.py`: shared scalar invariants used by contracts and parsers.
- `g2/errors.py`: safe structured validation issue and exception.
- `README.md`: setup, run, tests, decisions, limitations.
- `pyproject.toml`: Python requirement and tool/project metadata only; primary execution needs no installation or build backend. Distribution packaging is outside the minimum scope.
- `g2/__init__.py`: public package boundary.
- `g2/contracts.py`: immutable typed input/output structures and enums.
- `g2/validation.py`: strict JSON-to-contract validation and structured errors.
- `g2/fixtures.py`: fixture loading and isolated test-label extraction.
- `g2/policy.py`: policy contract and numerical validation.
- `g2/hard_checks.py`: evidence and competitor checks.
- `g2/freshness.py`: news/regulation temporal rules.
- `g2/evaluator.py`: criteria and score eligibility composition.
- `g2/reports.py`: ordered routing, merged findings, complete reports, and deterministic JSON serialization.
- `g2/sensitivity.py`: alternative configurations and comparison results.
- `g2/__main__.py`: CLI boundary.
- `config/policy.json`: provisional selected policy.
- `fixtures/additional-cases.json`: varied local sensitivity cases.
- `fixtures/README.md`: explicit asserted source relationships and synthetic sensitivity limitations.
- `tests/`: unit, integration, and CLI tests.
- `examples/starter-report.json`: actual generated evaluation output.
- `examples/sensitivity-report.json`: actual generated comparison output.
- `ACCEPTANCE.md`: requirements linked to tests and artifacts.
- `PR_DESCRIPTION.md`: prepared PR explanation, not an automatically submitted PR.

Keep modules small; merge a module if separation creates empty wrappers rather than useful boundaries. This layout is a proposal, not a target file count.

## 6. Contracts and validation rules

### Fixture envelope

Validate supported schema version, synthetic flag, fixed assessment date, recognized demo policy, non-empty cases, and unique non-empty identifiers. Recognize the supplied informational instructions field but never execute it.

### Evaluation case

Identifier, non-empty statement, and validated metadata only. No expected label field is permitted in the public evaluation input.

### Metadata

Require source type, content type, published date, event date, effective date, verification date, current status, support flag, supersession flag, contradiction flag, and competitor product claim flag.

Nullable date keys must still exist. A missing required key is malformed input; an explicit null is legitimate unknown information.

- Dates: exact documented ISO calendar-date format; reject timestamps and impossible dates.
- Booleans: accept actual booleans only, not strings or integers.
- Enums: reject unknown categories rather than silently inventing authority.
- Unknown keys: reject at strict evaluation/configuration boundaries. Fixture adapters explicitly recognize test-only fields.
- JSON: reject non-finite numbers and duplicate object keys rather than accepting ambiguous input.
- Cross-field temporal inconsistency: valid structural input that becomes an inspectable review finding, not fabricated resolution.

Errors contain a stable code, field path, and safe explanation. Do not log full statements, raw records, or credentials. Use the established Python logging facility for operational diagnostics; structured output files are artifacts, not logs.

### Output

Reports contain case ID, gate, `as_of`, schema/policy/weights versions, calibration status, checks and reasons, criteria and explanations, freshness details, date basis, applicability, weights, floors, threshold, aggregate score or null, scoring eligibility, final decision, primary reason, and all findings.

Use typed structures and construction-time invariant checks for outputs as well as inputs. Aggregate score must be finite and within range; pass reports must satisfy all pass invariants. Serialization must preserve explicit nulls.

Do not add system-clock timestamps by default. Equivalent validated input and policy must produce equivalent serialized reports.

## 7. Evaluation semantics

### Hard checks

Positive check names avoid inverted interpretations:

- `material_claim_supported`
- `evidence_not_superseded`
- `competitor_promotion_absent`
- `evidence_conflict_absent`

Each exposes status (`pass`, `fail`, or `unknown`), reason, and metadata basis. Findings separately distinguish prohibited, repairable, and review conditions. Conflict is a review blocker, not proof that the claim is false. Record every finding even when a higher-priority decision determines routing.

Supersession is conservative: if `superseded` is true **or** `current_status` is `superseded`, `evidence_not_superseded` fails and adds a repairable finding. If those two assertions disagree, also add `SUPERSESSION_METADATA_CONFLICT`; do not discard the explicit replacement assertion. Supersession produces revise unless a prohibition requires reject.

If support is false, the support check fails. If support is true but evidence has an unresolved contradiction, the support check is unknown and the conflict check fails with review classification. Otherwise, the support check passes. Support false plus contradiction preserves both findings and routes to revise by precedence.

A failed mandatory check or unresolved support cannot produce a passing weighted result. No later configuration may turn prohibited promotion into a pass.

### Temporal status decision table

Apply known supersession first. For structurally valid metadata, use this exhaustive content/status table:

| Content type | Current status | Temporal treatment |
| --- | --- | --- |
| Either | `superseded`, or superseded flag true | Temporal value 0; revise; preserve other uncertainties. |
| News | `current` | Apply event-age rules below. |
| News | `unknown` | Temporal value null; unknown applicability; review. |
| News | `adopted_not_applicable` | Recognized but incompatible content/status combination; temporal null; review. |
| Regulation | `current` | Require known effective date on/before `as_of`; otherwise temporal null and review. |
| Regulation | `adopted_not_applicable` | Require known effective date strictly after `as_of`; otherwise temporal null and review. |
| Regulation | `unknown` | Temporal null; applicability unknown; review. |

A mismatched recognized status is evaluated as an inconsistency, not rejected as malformed JSON. Unrecognized strings fail validation.

### News freshness

Use `(as_of - event_date).days`, not publication age.

- Ages 0 through 30 inclusive: current under fixture demo convention.
- Age above 30: known stale coverage, revise.
- Null event date: temporal criterion null, review unless an earlier decision applies.
- Future event in the current ordinary news contract: review for future/inconsistent event metadata; scheduled-event semantics are outside the minimum contract.
- Non-current assertions use the temporal status table; recognized unknown applicability routes to review, while invalid enum strings fail validation.

For news, `currently_applicable` is null with an explicit `not_applicable` applicability assessment: legal effective-date applicability is not the relevant concept for an event. The temporal score concerns valid event coverage.

Record publication and verification dates as context, without substituting either for unknown event dates. A null legal-applicability field for news is not an unknown required criterion and does not itself block scoring.

### Regulation applicability

No universal publication-age penalty.

- Current rule: effective date known and on/before `as_of`, no supersession or unresolved temporal inconsistency; temporally appropriate and currently applicable under trusted assertions. An unrelated claim-support conflict blocks scoring separately without automatically changing otherwise established dates.
- Adopted-not-applicable rule: effective date after `as_of`; temporally appropriate for its supported future-facing statement, but currently applicable is false.
- Superseded: revise regardless of otherwise recent dates.
- Unknown required effective/applicability metadata: review and unknown temporal criterion.
- Current status with future effective date: review inconsistency.
- Not-applicable status with effective date on or before `as_of`: review inconsistency, including exact equality; do not assume legal activation.

The gate cannot independently confirm that prose accurately describes future applicability. It relies on `supported` metadata and records that boundary.

### Verification and consistency

Expose `last_verified_at`; do not invent a verification expiry interval. A verification date after `as_of` adds `FUTURE_VERIFICATION_DATE`, makes temporal validity null, and blocks scoring unless a known temporal defect already determines temporal validity 0 and revise. Missing verification date alone does not create a new undocumented expiry requirement when other required temporal facts are known.

Temporal value precedence is explicit: known invalidity (0) takes priority over uncertainty (null), which takes priority over established temporal appropriateness (1). Preserve all findings. Inconsistent current/effective status, future verification, or unknown required timing cannot leave a temporal value of 1. An evidence contradiction alone affects support, not necessarily event timing: only contradictory temporal assertions make temporal validity unknown.

Do not enforce simplistic global date ordering: legitimate publication can announce a later event. Contradictory supersession/status assertions retain the known supersession defect and also expose the inconsistency.

### Criterion anchors

| Criterion | 0 | 0.5 | 1 | Unknown |
| --- | --- | --- | --- | --- |
| Evidence support | Supplied assertion explicitly says unsupported | Evidence explicitly supports only a qualified portion of a material claim | Supplied assertion says supported, with no unresolved contradiction | Null when supported metadata coexists with unresolved evidence contradiction |
| Source authority | Source has no independent authority for this claim | Asserted reputable independent secondary reporting | Asserted appropriate primary issuing/announcing authority | Null when the source's authority relationship is explicitly unknown |
| Temporal validity | Known invalid timing, supersession, or stale coverage | Known limited applicability for an explicitly qualified period or scope | Appropriate for the supplied statement and `as_of`, including a correctly described future rule | Null for missing or inconsistent required temporal information |

The 0.5 anchors describe observable conceptual conditions, not missing information. The minimum boolean-support and date/status schema cannot represent partial support or qualified temporal scope, so the evaluator does not emit 0.5 for those two criteria. No extension to represent them is required. Missing dates never become 0.5.

Evidence-support mapping is exact: `supported == false` yields 0 even if contradiction is true; supported plus contradiction yields null; supported without contradiction yields 1. Preserve the contradiction independently in all cases. This avoids reporting full evidential support in a materially disputed case.

Source authority uses the concrete category table above, including 0.75 for official indirect reporting. Scores are synthetic policy preferences, not measurements. Generic competitor information requires independent original evidence and review; product promotion is always reject.

### Provisional scoring policy

Weights: evidence support 0.45, source authority 0.30, temporal validity 0.25.

Rationale: grounding is central; authority distinguishes acceptable provenance; temporal problems remain protected by explicit rules rather than compensated by averaging.

Threshold: 0.80. Floors: support 1.0, authority 0.5, temporal 1.0.

These floors are deliberately conservative. Support and temporal criteria mostly become eligibility gates, so authority drives much eligible-case variation. Document this limitation instead of claiming independent three-axis calibration.

Validate exact criterion keys, finite non-boolean values, nonnegative weights, sum within absolute tolerance `1e-9` of 1, and floors/threshold within [0, 1]. Never silently normalize invalid input. Use accurate summation and full precision for decisions; formatting rounds only displayed values.

Threshold rationale: 0.80 is a declared conservative prototype preference, not an optimized cutoff. With support and temporal validity at 1, the chosen score is `0.70 + 0.30 × authority`; the threshold requires authority of at least one third, while the stricter 0.5 authority floor remains decisive. Reputable secondary authority therefore passes at 0.85 under the chosen policy, reflecting acceptance of supported, temporally valid secondary evidence. With authority-heavy weights it scores 0.75 and requires review. A 0.75 threshold would admit that alternative result, while 0.85 would put the chosen secondary case exactly on the boundary. These consequences explain the preference without claiming calibration or selecting the threshold from expected starter labels.

The score threshold is partly redundant with floors under the chosen minimum schema. That redundancy is deliberate defense in depth and must be disclosed. The authority-heavy sensitivity configuration demonstrates a nonredundant threshold effect. Weight comparison does not independently validate the cutoff.

### Scoring eligibility

All three criteria are required even if a configuration gives one a zero weight. An unknown required value still blocks aggregate scoring. Keep score eligibility distinct from pass eligibility:

| Condition | Aggregate score | Decision |
| --- | --- | --- |
| Prohibition, failed mandatory support/supersession check, or known temporal defect | null | Reject/revise by precedence |
| Unknown required criterion, unresolved conflict, or unresolved required temporal inconsistency | null | Review unless an earlier reject/revise rule applies |
| All criteria known, no blocker, authority floor not met | Calculated | Review |
| All criteria known, floors met, score below threshold | Calculated | Review |
| All criteria known, checks/floors/threshold pass, no other finding | Calculated | Pass |

A competitor generic source can have known authority 0 and a calculated diagnostic score, but the authority floor and original-evidence review finding prevent passing. Its calculated score cannot resolve that evidence policy requirement. Promotion still blocks scoring and rejects.

Blocked cases retain individual assessments and all findings, with an explanation for null aggregate score. Use unrounded scores for threshold comparison and inclusive `score >= threshold` and `criterion >= floor` comparisons. Floating-point sum tolerance applies to weight validation only, not as an undocumented relaxation of pass thresholds. Independently test boundary arithmetic.

A tolerated near-one weight sum is not normalized. If its raw weighted aggregate exceeds [0, 1], evaluation raises `AGGREGATE_OUT_OF_RANGE` rather than clipping or returning an invalid score. A sum slightly below one is not rounded up for threshold comparison. Default weights avoid this numerical edge case; see `STAGE_6_RESULTS.md`.

### Decision precedence

1. Reject: explicit prohibition.
2. Revise: known repairable defect.
3. Human review: unknown information, conflict, inconsistency, floor failure, or below-threshold score without a known repair.
4. Pass: no earlier finding, checks pass, criteria known, floors met, threshold met.

Examples: promotion plus unknown date -> reject; unsupported plus unknown date -> revise; supersession plus conflict -> revise with both findings preserved; conflict alone -> review.

No score is a probability. No score proves truth. No numerical average overrides a prohibition or unresolved required fact.

## 8. Required sensitivity design

Add three eligible synthetic cases: reputable secondary reporting (authority 0.5), official indirect institutional reporting (0.75), and primary issuing/announcing authority (1). Each uses the exact source enum above and a distinct synthetic event or rule, with support and temporal validity 1. Describe the authority relationship in fixture documentation; do not classify it by parsing the statement. Eligibility here means scoring-eligible; all three also pass under the chosen configuration, while alternatives may route to review.

Compare chosen weights (0.45, 0.30, 0.25), equal weights, and authority-heavy weights (0.25, 0.50, 0.25). Keep threshold, floors, date, and cases fixed.

| Authority | Chosen score/routing | Equal score/routing | Authority-heavy score/routing |
| --- | --- | --- | --- |
| 0.5 | 0.85 / pass | 0.8333 / pass | 0.75 / review |
| 0.75 | 0.925 / pass | 0.9167 / pass | 0.875 / pass |
| 1 | 1 / pass | 1 / pass | 1 / pass |

These are proposed hand-calculated expectations; Stage 8 independently verified the executed values and routes. The full-precision actual artifact is `examples/sensitivity-report.json`, with evidence in `STAGE_8_RESULTS.md`.

Report scores, ranks, ties, routing changes, unchanged cases, and limitations. Ranking remains unchanged in this one-axis fixture design; routing changes only for the reputable-secondary case, not the official-indirect case. Do not invent ranking reversals. If richer valid criteria are introduced later, document the schema and reasoning before adding them.

## 9. Detailed execution stages

Each stage begins only after its prerequisites are complete. Tests accompany implementation; they are not deferred until the end. No implementation stage is authorized merely by creating this plan.

### Stage 0 — Confirm scope and environment

**Status:** complete. See `STAGE_0_BASELINE.md` for recorded evidence. Existing system Python `/usr/bin/python3.11` was configured and verified as 3.11.15; all ten probed standard-library imports succeeded. The original fixture is unchanged against Git and its SHA-256 baseline is recorded. At Stage 0, no component tests or CLI commands had yet been run.

**Goal:** establish reproducible constraints before code creation.

**Actions:** inspect submission directory and applicable instructions; configure the chosen Python environment before any Python execution; verify interpreter version; confirm standard-library baseline; inspect repository status without changing existing work; identify clean-checkout invocation approach.

**Deliverables:** recorded Python baseline, dependency choice, exact submission boundaries, planned test/run commands.

**Tests/checks:** ensure supplied fixture path exists and remains untouched; identify any pre-existing user changes.

**Completion:** environment and scope are documented; no dependency or packaging claims rely on assumptions.

**Risk:** tooling may be unavailable. Report actual limitations, never claim tests were run when they were not.

### Stage 1 — Define typed contracts and strict validation

**Status:** complete. Frozen input contracts, strict pure parsers, construction invariants, and safe structured errors are implemented. All 18 validation tests passed under Python 3.11.15; all six Python files passed in-memory syntax parsing and no editor diagnostics were reported. See `STAGE_1_RESULTS.md` for coverage and limitations. Output contracts remain assigned to their later stages.

**Prerequisite:** Stage 0.

**Actions:** define immutable input case/metadata structures and supported enums; implement strict object/key/type/date/enum validators and reusable construction checks; define structured validation errors; reject duplicate JSON keys/non-finite numbers. Define policy contracts in Stage 3, temporal structures in Stage 5, final report structures in Stage 7, and comparison structures in Stage 8 rather than guessing every output now.

**Deliverables:** contracts, validators, validation tests.

**Tests:** missing versus null dates, invalid boolean coercions, invalid ISO dates, empty strings, unknown enums/keys, recognized unknown categories, malformed JSON, and input construction invariants. Output invariant tests accompany the stages defining those outputs.

**Completion:** invalid structure fails predictably; explicit unknown dates remain valid input; every public parameter and return has a type hint and public APIs have English docstrings.

**Best choice:** explicit small validators with field paths. **Poor choice:** unchecked dictionaries or silent coercion.

### Stage 2 — Fixture adapter and test-label firewall

**Status:** complete. Strict fixture validation and read-only UTF-8 loading return immutable, label-free assessment inputs. A separate test-only API extracts expected labels. All 30 tests passed; nine Python files passed syntax parsing, and the original nine-case fixture loaded successfully without modification. Label replacement leaves adapter outputs identical; actual routing invariance remains deferred until an evaluator exists. See `STAGE_2_RESULTS.md`.

**Prerequisite:** Stage 1.

**Actions:** load the original envelope; validate version, synthetic flag, demo policy, case uniqueness, and `as_of`; create evaluation cases without labels; collect expected decisions only through a separate testing adapter/result.

**Deliverables:** fixture loader and adapter tests.

**Tests:** label replacement has no effect; evaluation contract rejects expected labels; renamed IDs and changed statement text do not change metadata-derived routing; missing envelope fields fail.

**Completion:** evaluator API has no path to `expected_decision`; informational instruction strings cannot control policy.

**Risk:** stripping labels inside the evaluator is weaker than excluding them before evaluation; use the latter.

### Stage 3 — Policy configuration and numerical safeguards

**Status:** complete. Immutable policy contracts and `config/policy.json` implement the provisional weights/floors/threshold/map and explicit uncalibrated status. All 41 tests passed, including tolerance-edge and overflow checks; 11 Python files passed syntax parsing. Actual configuration loading succeeded and the original fixture remains unchanged. See `STAGE_3_RESULTS.md`; scoring and routing remain deferred.

**Prerequisite:** Stage 1; fixture conventions from Stage 2.

**Actions:** define typed policy contracts, selected weights, floors, threshold and its consequences, exact authority-category map, versions, calibration status, rationale, and tolerance; load local JSON policy; retain fixture-owned freshness convention separately.

**Deliverables:** validated policy file, policy implementation, configuration tests.

**Tests:** negative weights, wrong sum, missing/extra criteria, booleans, NaN/infinity, invalid floors/threshold, tolerance boundary; policy cannot silently override fixture freshness.

**Completion:** all configuration is inspectable and explicitly uncalibrated; invalid configuration fails rather than being normalized.

**Question:** why not learned weights? No independent judgments or held-out calibration evidence exist.

### Stage 4 — Hard checks and findings

**Status:** complete. Pure metadata-derived checks and immutable assessments preserve prohibited, repairable, and review findings with construction invariants. All 49 tests passed, including 64 flag/status combinations; 13 Python files passed syntax parsing and the original fixture remains unchanged. See `STAGE_4_RESULTS.md`. Pipeline ordering, score blocking, and final routing remain assigned to later composition stages.

**Prerequisites:** Stages 1–3.

**Actions:** implement support, supersession, promotion, and conflict assessments; distinguish prohibited, repairable, and review findings; preserve all issues and metadata basis.

**Deliverables:** pure hard-check function and focused tests.

**Tests:** each flag individually; combined flags; either supersession assertion alone blocks passing; disagreement preserves a conflict finding; supported-plus-contradiction yields unknown support; unsupported-plus-contradiction retains a known repairable defect; promotion remains prohibited regardless of source type or high criterion values.

**Completion:** checks run before scoring, use understandable positive names, and cannot be bypassed by weights.

### Stage 5 — Freshness and current applicability

**Status:** complete. `g2/freshness.py` implements pure temporal assessments with distinct legal applicability, retained uncertainties, and output construction invariants. All 61 tests passed, all 15 Python files passed syntax parsing, and editor diagnostics were clean. Original fixture remained identical to HEAD. See `STAGE_5_RESULTS.md`; criteria, scoring, and final routing remain deferred.

**Prerequisites:** Stages 1–4.

**Actions:** define typed freshness/applicability structures; implement the exhaustive content/status table; compute news event age from supplied date; implement current/future/superseded regulation handling; expose dates and applicability; apply known-invalid/unknown/valid temporal precedence and preserve inconsistencies.

**Deliverables:** freshness module, explanation structures, temporal test matrix.

**Tests:** exactly 30/31 days, event equals `as_of`, null event date with recent publication, old current law, current effective date equals `as_of`, adopted-not-applicable effective date equals `as_of`, future law, missing effective date, every content/status pairing, recognized unknown status, current/future inconsistencies, future verification setting temporal null, known temporal defect plus future verification retaining 0, and supersession precedence.

**Completion:** no clock access or universal publication-age penalty; valid future rule reports false current applicability; unknown timing remains null.

**Risk:** prose truth cannot be assessed from metadata. State the trusted-support boundary explicitly.

### Stage 6 — Criteria, score eligibility, and aggregate calculation

**Status:** complete. Pure `assess_score` supplies anchored criteria, retained blocker explanations, diagnostic scores separate from floors, and immutable computed-output invariants. All 71 tests passed; 17 Python files passed syntax parsing and new-file diagnostics were clean. Original fixture remained unchanged. See `STAGE_6_RESULTS.md`; final routing and reports remain Stage 7 work.

**Prerequisites:** Stages 3–5.

**Actions:** map support/authority/temporal findings to anchored values; withhold aggregate score on blocking conditions; calculate weighted sum for eligible cases; retain floors and score explanations.

**Deliverables:** criterion evaluator and independent numerical tests.

**Tests:** unknown criterion propagates null; known hard failure never gets a passing aggregate; score range; full-precision threshold boundaries; zero-weight unknown required criterion still blocks scoring; low authority cannot bypass floor.

**Completion:** formula is reproducible, criteria are not duplicated under extra names, and score is never called a probability.

### Stage 7 — Ordered routing and complete reports

**Status:** complete. `g2/reports.py` enforces routing precedence and pass invariants, preserves merged finding origins/basis, and serializes complete reports with explicit nulls. All 78 tests passed, all 19 Python files passed syntax parsing, and all nine original outcomes matched without label leakage. See `STAGE_7_RESULTS.md`. Additional cases/comparisons and saved CLI examples remain later-stage work.

**Prerequisites:** Stages 4–6.

**Actions:** define typed final report structures and their construction invariants; apply reject/revise/review/pass precedence after collecting findings; expose primary reason and all findings; enforce pass invariants and preserve explicit nulls.

**Deliverables:** evaluator composition, complete report serialization, starter and precedence tests.

**Tests:** all nine starter outcomes; prohibition plus review; repairable defect plus review; conflict alone; below threshold; scores/floors unable to override checks; output nulls and explanations.

**Completion:** every starter outcome matches without ID/text branching; all reports disclose versions, `as_of`, calibration, and applicability.

### Stage 8 — Additional cases and sensitivity comparison

**Status:** complete. Three additional eligible cases and three weight-only configurations have verified arithmetic, deterministic ranks/ties, and one secondary-source routing change without ranking reversal. See `STAGE_8_RESULTS.md`.

**Prerequisite:** Stage 7.

**Actions:** define typed comparison result structures; create three varied eligible local cases with the exact source categories and documented authority relationships; compare three weight sets while fixing all other policy; generate scores, deterministic ranks/ties, routing changes, and unchanged cases.

**Deliverables:** additional fixture, comparison implementation, comparison tests.

**Tests:** independent expected arithmetic from Section 8; at least three cases scoreable; chosen/equal/alternative all evaluated; expected routing change; unchanged ranking disclosed; tie handling stable.

**Completion:** comparison is meaningful but honestly limited; no result is represented as calibration or expert judgment.

### Stage 9 — CLI and executable examples

**Status:** complete. Both CLI commands, safe file boundaries, and saved actual reports are verified; 88 tests passed at this stage. See `STAGE_9_RESULTS.md` and `CLI_USAGE.md`.

**Prerequisites:** Stages 7–8.

**Actions:** expose evaluate and compare commands through `python -m g2` from the submission directory; require no pip installation, build backend, or downloaded packages for the primary path; document fixture/config/output arguments; default supplied fixture resolved relative to module/submission location rather than arbitrary current directory; save deterministic JSON inside submission examples. Keep `pyproject.toml` for project/tool metadata; do not imply distribution packaging is implemented.

**Deliverables:** CLI, integration tests, actual generated starter and comparison reports.

**Tests:** valid invocation; malformed input/config exit nonzero; evaluation decisions themselves do not cause execution failure; missing file and unwritable output handled; refuse accidental overwrite of input paths; JSON output parses.

**Completion:** examples run without network, credentials, or paid services; generated artifacts are actual output, not hand-written claims of execution.

**Best choice:** structured file output plus safe logging. **Poor choice:** console-only unstructured reports.

### Stage 10 — Security, determinism, and regression verification

**Status:** complete. All 95 tests passed, 24 Python files parsed, guarded fresh-process CLI execution and hash-seed/timezone equivalence succeeded, and examples/original fixture remained unchanged. Null-byte paths now fail safely at CLI and loader boundaries. See `STAGE_10_RESULTS.md` for evidence and verification limits.

**Prerequisites:** Stages 1–9; checks also run throughout.

**Actions:** run the full test suite; check diagnostics; add offline/network-denial tests, source-injection tests, repeated-run equivalence, label leakage guards, and original-fixture integrity checks; inspect public APIs and logging.

**Deliverables:** verified test result summary and any corrected failures.

**Tests:** network functions fail if invoked; system date changes cannot alter fixed-input output; input contains instruction-like text but rules remain unchanged; original input bytes remain unchanged; no unsupported stdout/log dumps.

**Completion:** tests actually pass in the configured interpreter and no relevant new diagnostics remain; limitations of any unavailable verification are documented.

### Stage 11 — Documentation and acceptance mapping

**Status:** complete. README, acceptance mapping and local PR description are written. All 95 tests pass; 12 Markdown links and 57 distinct acceptance test-method references are verified, along with documented policy values, example scores/routes and CLI flags. Original fixture remains byte-identical to HEAD; no PR is submitted. See `STAGE_11_RESULTS.md`.

**Prerequisites:** implementation verified through Stage 10.

**Actions:** write setup/run/test instructions, anchors, rationale, threshold/floor policy, temporal rules, label isolation, sensitivity results, known limitations, and fixture discrepancy; map each task requirement to concrete tests/artifacts; prepare PR description.

**Deliverables:** README, ACCEPTANCE, PR_DESCRIPTION, generated examples.

**Completion:** a reviewer can inspect every requirement without inferring hidden assumptions; exact tested Python version is distinguished from declared minimum support.

**Risk:** claiming all Python versions above the minimum are certified. Document only versions actually tested.

### Stage 12 — Clean-checkout rehearsal and scope audit

**Status:** complete. The historical isolated HEAD baseline plus uncommitted submission snapshot passed 95 tests; the corrected-snapshot rehearsal on 2026-10-27 passed **96 tests** and 24 Python AST checks. Default/explicit starter and comparison commands reproduced saved artifacts byte-for-byte. The original fixture matched HEAD, repository status remained unchanged by the rehearsal, and temporary cleanup succeeded. These rehearse snapshots, not an already committed checkout. See `STAGE_12_RESULTS.md`.

**Prerequisites:** Stage 11.

**Actions:** rehearse documented commands from a clean isolated copy/worktree when available without discarding user changes; verify fixture resolution and no external-system runtime access; inspect repository diff and example reproducibility.

**Deliverables:** final verification summary and submission readiness assessment.

**Completion:** no modifications outside `src/task-6_saijaz/`; tests and both examples run; reports are reproducible; no credentials or unapproved dependencies; no automatic commit, push, or PR submission.

**Commit rule:** the original plan required an actual `AB#<id>` and prohibited inventing an ID. On 2026-10-27 the user explicitly confirmed that Azure Boards does not apply to this challenge and waived that requirement. The authorized local commit therefore omits an AB reference and uses the confirmed Farrukh Aijaz identity. This waiver does not authorize a push or PR creation.

## 10. Acceptance and test coverage matrix

| Requirement | Planned verification |
| --- | --- |
| Every starter case | Starter outcome and report-detail tests |
| Fixed `as_of` | Injected-date and system-clock independence tests |
| Envelope/metadata validation | Structural and malformed-input tests |
| Hard checks before scoring | Ordering/blocked-score tests |
| Current news | Event-age and pass invariants |
| Old event in new article | Publication/event distinction test |
| Old applicable law | No publication-age penalty test |
| Future rule | Temporal validity true, applicability false |
| Unknown criteria | Explicit null criterion and aggregate score |
| Conflicting evidence | Review, null support/aggregate for supported disputed claims, and preserved conflict finding |
| Conflicting supersession assertions | Either assertion blocks passing; inconsistency retained |
| Supported category semantics | Exact enums, unknown-category behavior, and full content/status table |
| Future verification date | Temporal null unless known temporal defect already establishes 0 |
| Offline setup | Direct module execution with no installer/build backend |

## 11. Common questions and answers

### Is this the best possible scoring model?

No universal best model is established. This is a conservative, inspectable prototype satisfying the task. Its strongest qualities are hard constraints, explicit uncertainty, and reproducibility, not optimized predictive performance.

### Why does source authority dominate eligible-case variation?

Support and temporal floors intentionally exclude defective cases before passing. The eligible fixture family therefore has limited variation. The sensitivity report must explain this instead of inventing partial evidence or temporal certainty. The chosen threshold is also partly redundant with those floors; alternative weights demonstrate its effect without establishing calibration.

### Why use 0.75 authority?

The exact `official_indirect` category asserts an official institutional account of another issuer's event/rule. Its provisional score lies above reputable secondary reporting (0.5) and below the originating authority (1). This is a transparent ordinal preference, not a measured credibility percentage. Relationships are supplied metadata, never inferred from company names or text.

### Can a future rule score temporal validity 1?

Yes, for a supported statement accurately describing future applicability. That does not mean the rule applies today. Report those concepts separately and disclose reliance on support metadata.

### What if multiple problems exist?

Preserve all findings, select one final decision by precedence, and identify the primary routing reason. Do not hide lower-priority issues.

### What if configuration says calibration is required?

The minimum configuration does not require genuine calibration for demo-stage passing; it records uncalibrated status. A future policy requiring calibration would route uncalibrated results to review and needs explicit contract/tests.

### Are ordinary rejected cases runtime failures?

No. Successful evaluation can produce reject, revise, or review. Nonzero CLI exit codes mean malformed input, invalid configuration, I/O failure, or execution failure, not editorial routing.

### Should source passages or real URLs be invented?

No. Preserve supplied metadata and explain the evidence boundary. Additional fixtures stay synthetic. Real verification would be a separate upstream component.

### Should supplied expected outcomes tune the threshold?

No. They verify mandated routing. Threshold and weight preference remain provisional; nine labeled synthetic cases do not constitute scientific calibration.

### Is a database or UI useful here?

Not for the required behavior. It increases setup and failure modes without improving acceptance coverage.

### What remains before submission?

Stages 0–12 are complete. Evidence is recorded in corresponding stage documents, including the corrected 96-test isolated rehearsal. Candidate folder remains `src/task-6_saijaz/`; dependencies remain standard-library only. The user authorized a local commit as Farrukh Aijaz and waived the inapplicable Azure Boards reference rule. The commit must contain only this submission folder. Pushing the branch and opening the required PR still need separate authorization. Rehearsal results describe the tested snapshot; a committed-checkout verification must be reported separately when performed.

## 12. Final readiness checklist

- [x] Plan reviewed; authorized Stages 0–12 completed.
- [x] Python environment configured and version verified.
- [x] Strict input/output contracts and policy validation complete.
- [x] All nine starter outcomes verified without label leakage.
- [x] Hard failures cannot be overridden by scoring.
- [x] Unknown criteria remain null.
- [x] Freshness distinguishes publication, event, effective date, and applicability.
- [x] Criterion anchors, floors, weights, and threshold documented as provisional.
- [x] Three additional eligible cases and three-config comparison complete.
- [x] Routing changes and unchanged rankings explained.
- [x] All required, boundary, security, and determinism tests pass within documented verification limits.
- [x] Real generated example reports saved.
- [x] README, concrete acceptance mapping and local PR description complete and verified.
- [x] Clean-checkout instructions rehearsed using an isolated HEAD baseline plus submission snapshot.
- [x] Source fixture unchanged and all work inside submission folder.
- [x] Known limitations and trusted-metadata boundary documented.
- [x] No automatic publishing, commit, push, or PR creation.

### Supported categories and authority policy

The minimum contract recognizes exactly:

- `content_type`: `news`, `regulation`.
- `current_status`: `current`, `superseded`, `adopted_not_applicable`, `unknown`.
- `source_type`: `primary_authority`, `official_indirect`, `reputable_secondary`, `competitor`, `unknown`.

Starter schema 1.0 fields and supplied category values remain unchanged. Additional local category values are a documented submission vocabulary extension; the original file is not modified. Reject all other strings as malformed input. Recognized `unknown` represents valid structure with unresolved knowledge.

| Source type | Authority score | Asserted relationship to the claim |
| --- | --- | --- |
| `primary_authority` | 1 | Issuer of the rule or originating announcer of the event. |
| `official_indirect` | 0.75 | Official institution reporting another issuer's rule or event, not the originating authority. |
| `reputable_secondary` | 0.5 | Reputable independent secondary publisher reporting the rule or event. |
| `competitor` | 0 | Competitor-origin information is not independent publication evidence; generic information requires original evidence and review. |
| `unknown` | null | Authority relationship unavailable; review unless an earlier decision applies. |

These relationships are trusted synthetic metadata, not inferred from source names or prose. The 0.75 value expresses an uncalibrated preference for an official indirect institutional account over secondary reporting while reserving full authority for the issuer. Promotion rejects for every source category when its flag is true.
