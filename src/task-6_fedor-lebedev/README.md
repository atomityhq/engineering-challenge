# Task 6: G2 evidence and current-validity gate

This folder implements **Task 6, one content-quality gate (G2)**. The gate decides whether a content case may proceed based on evidence support, source authority, temporal validity and current applicability. It runs hard checks first, keeps freshness as a separate, explained assessment, and computes a transparent weighted score only for cases that are eligible for scoring. Decisions are `reject`, `revise`, `human_review` or `pass`.

G2 judges evidence and current validity only. Design, visual quality, writing style and audience engagement are not inputs, criteria or weights.

Everything is deterministic, offline and rule-based: no LLM, no network, no credentials, no learned weights.

## Quick start

Requires Python 3.10 or newer. Tested with Python 3.12.10 and 3.14.2, pydantic 2.14.1 and pytest 9.1.1.

```bash
cd src/task-6_fedor-lebedev
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the tests (192 tests, about a second):

```bash
python -m pytest
```

Evaluate the supplied starter fixture (`fixtures/g2-cases.json` at the repository root, read in place) and compare each decision with the fixture's test-only `expected_decision` after evaluation:

```bash
python -m g2_gate evaluate --check-expected
```

```text
case                                   decision       score    ES   SA   TV  freshness           expected      ok  routing reasons
current-news                           pass          1.0000     1    1    1  current             pass          yes -
old-law-current                        pass          1.0000     1    1    1  current             pass          yes -
recent-article-old-event               revise           -       1    1    0  stale               revise        yes STALE_EVENT
unknown-date                           human_review     -       1    1 null  unknown             human_review  yes UNKNOWN_EVENT_DATE, UNKNOWN_CRITERION
unsupported-claim                      revise           -       0    1    1  current             revise        yes UNSUPPORTED_MATERIAL_CLAIM
superseded-source                      revise           -       1    1    0  superseded          revise        yes SUPERSEDED_EVIDENCE
competitor-promotion                   reject           -       1    0    1  current             reject        yes COMPETITOR_PRODUCT_PROMOTION, COMPETITOR_SOURCE_NEEDS_JUDGMENT
conflicting-evidence                   human_review     -     0.5    1    1  current             human_review  yes CONFLICTING_EVIDENCE
future-rule                            pass          1.0000     1    1    1  not_yet_applicable  pass          yes -

9/9 decisions match expected_decision (compared after evaluation; the evaluator never sees it).
```

Other commands:

```bash
python -m g2_gate evaluate --format json                                   # full reports
python -m g2_gate evaluate --fixture fixtures/g2-edge-cases.json --check-expected
python -m g2_gate evaluate --fixture fixtures/g2-weighting-cases.json --weights equal-v1
python -m g2_gate sensitivity                                              # weight comparison (markdown)
python -m g2_gate describe                                                 # policy, weights, criterion anchors
python -m g2_gate demo                                                     # regenerate examples/
```

Exit codes: `0` success; `1` a decision differs from `expected_decision` (only with `--check-expected`, in either output format; with `--format json` each fixture also gets an `expectation_check` block); `2` invalid fixture or configuration: unreadable or non-UTF-8 file, invalid or too deeply nested JSON, a repeated JSON key, schema violations (listed by field path), or a case id repeated across the fixtures given to `sensitivity`. A traceback is never the intended outcome for bad input.

## Layout

```text
src/task-6_fedor-lebedev/
├── README.md                    this file: setup, design note, limitations
├── requirements.txt / pyproject.toml
├── config/
│   ├── g2_policy.json           policy version, calibration status, threshold, floors, source authority table
│   └── weights.json             chosen weights + two comparison configurations, each with a rationale per weight
├── fixtures/
│   ├── g2-weighting-cases.json  6 additional eligible cases for the weight comparison
│   └── g2-edge-cases.json       17 additional edge and failure cases
├── g2_gate/
│   ├── models.py                typed input contracts (Pydantic)
│   ├── config.py                policy and weight contracts, weight validation
│   ├── loading.py               file reading and validation errors (InputValidationError)
│   ├── paths.py                 default file locations
│   ├── codes.py                 reason codes
│   ├── hard_checks.py           mandatory checks, run before scoring
│   ├── freshness.py             freshness and current-applicability assessment
│   ├── criteria.py              criterion definitions, anchors and scoring
│   ├── scoring.py               weighted sum, floors, threshold
│   ├── decision.py              decision precedence
│   ├── evaluator.py             pipeline and per-case report
│   ├── report.py                typed output contracts
│   ├── sensitivity.py           weight sensitivity comparison
│   └── cli.py                   command-line demo
├── examples/                    generated outputs (reports, summaries, sensitivity); a test keeps them current
└── tests/                       192 tests
```

## How it works

```text
fixture JSON
   │  schema validation (strict; malformed input fails with field paths)
   ▼
G2Case (id, statement, metadata)   + as_of and demo_policy from the fixture
   │                                 (expected_decision is stripped; the evaluator refuses a FixtureCase)
   ├─► hard checks ───────────────► routing reasons
   ├─► freshness / applicability ─► routing reasons + explained assessment
   └─► criteria (0 / 0.5 / 1 / null) ► "unknown criterion" reasons
   │
   ▼
eligible for scoring?  all hard checks pass AND freshness passes AND every criterion known
   │ yes                                      │ no
   ▼                                          ▼
weighted score, floors, threshold          score = null, with the reasons it was withheld
   │                                          │
   └──────────────► decision precedence ◄─────┘
                    reject > revise > human_review > pass
                         │
                         ▼
                    G2 report (JSON)
```

Every report contains: hard-check results (status, route, inputs, detail), criterion scores with the matched anchor and the inputs used, the freshness assessment and its explanation, the weights, the score and its per-criterion contributions when eligible (or why it was withheld), the decision with its meaning, every reason (not only the winning one), the policy version, weights version, calibration status, and digests of the configuration and the case input. See [`examples/starter-reports.json`](examples/starter-reports.json).

## Fixture metadata boundary

The gate **trusts the fixture's metadata assertions** (`supported`, `superseded`, `contradiction`, `competitor_product_claim`, `current_status`, `source_type`, and the dates) as inputs from earlier stages. It is responsible for routing and scoring those assertions and for checking that they are consistent with each other and with `as_of`. Examples: status against effective date, the superseded flag against the status, dates later than `as_of`.

It is **not** responsible for verifying the real-world truth of the fictional data, and it does not read `statement` text. Statements, the fixture's `instructions` and the demo-policy prose are carried as untrusted data and never interpreted.

Input notes:

* The task text names `challenge-starter/g2-cases.json`. In this repository the file is `fixtures/g2-cases.json`, and it is read from there without being copied or modified.
* Every metadata key is required. A missing key is malformed input and fails validation. An explicit `null` is allowed only where "unknown" is meaningful (the four dates and `supported`) and is handled as unknown, never as a default.
* Booleans must be JSON booleans, dates must be `YYYY-MM-DD`, enums are closed, and unknown keys are rejected, so a typo such as `superseeded` cannot pass silently. A key repeated within one JSON object is rejected too, because a plain JSON parser would silently keep the last value.
* `qualified_support` (optional, default `false`) is an extension used only by this submission's fixtures. It records that the evidence supports the claim only with a stated qualification. It is the only way to reach the evidence-support `0.5` anchor other than a contradiction.
* `expected_decision` is test-only. `FixtureCase.to_gate_input()` drops it, `G2Case` forbids it, and `evaluate_case` raises if handed a `FixtureCase`.

## Hard checks

Evaluated before scoring. A check that does not pass contributes its route, and no score can override it: an ineligible case is never scored at all.

| Check | Fails when | Route |
| --- | --- | --- |
| `no_competitor_promotion` | `competitor_product_claim` is true | `reject` (policy prohibition, not repairable) |
| `material_claim_supported` | `supported` is false / null | `revise` / `human_review` (unknown) |
| `evidence_not_superseded` | `superseded` is true **or** `current_status` is `superseded` | `revise`. If the two signals disagree, an informational `SUPERSESSION_METADATA_INCONSISTENT` reason is added |
| `no_material_contradiction` | `contradiction` is true | `human_review`: someone must decide which evidence governs |
| `source_not_competitor` | `source_type` is `competitor` | `human_review`: competitor material is used only through an explicit, human-approved exception. When the content also promotes the competitor's product, `reject` takes precedence and this reason is still listed |

## Freshness and current applicability

Freshness is never a universal publication-age rule. The report names the date used, its type, its age against `as_of`, the rule applied, the applicability state, the verification state, and a plain-language explanation. Each freshness issue records the metadata field that caused it (for example `DATE_AFTER_AS_OF` on `published_at`), and the matching reason uses that field as its subject.

**News**: the reference date is the **event date**. The event must be at most `news_max_event_age_days` (30, read from the fixture's `demo_policy`) before `as_of`. **This 30-day window is the fixture's demo test convention, not a validated freshness threshold**, and the report says so. A recent article about an old event is stale. The publication date is never substituted for a missing event date.

**Regulation**: there is **no age limit**. Applicability comes from `current_status` and `effective_from`, and the publication date is recorded but not used. A 2021 rule that is `current` and has applied since 2021-06-01 is current.

**Current applicability**, for both content types:

| `current_status` | `effective_from` vs `as_of` | Applicability | Freshness status |
| --- | --- | --- | --- |
| `current` | on or before, or absent for news | applicable | `current` (news must also be inside its window) |
| `current` | after | unknown (status and date conflict) | `conflicting`, routed to `human_review` |
| `current` (regulation) | missing | unknown | `unknown`, routed to `human_review` |
| `adopted_not_applicable` | after | not yet applicable | `not_yet_applicable`: passes freshness, `currently_applicable: false`, plus a `presentation_constraint` ("present as adopted but not applicable until …") |
| `adopted_not_applicable` | on or before / missing | unknown | `conflicting` / `unknown`, routed to `human_review` |
| `superseded` (or `superseded: true`) | any | no longer applicable | `superseded`, routed to `revise` by the hard check |
| `unknown` | any | unknown | `unknown`, routed to `human_review` |

Other date checks: `published_at` or `last_verified_at` later than `as_of` is `conflicting`. An `event_date` later than `as_of` is `future_event`, because the event cannot be confirmed as having happened. Unknown, conflicting or future-dated temporal metadata routes to `human_review`, following the fixture's `unknown_required_temporal_metadata`.

**Verification recency**: if `current_status` was last verified more than 30 days before `as_of` (a demo convention mirroring the news window, configured in `g2_policy.json`), or never, the case is still temporally valid. Its temporal-validity score drops to the `0.5` anchor instead of `1`. This is a graded signal, not a gate.

All date arithmetic uses the fixture's `as_of`. No module reads the system clock, and a test enforces this.

## Criteria and anchors

Each criterion reads a different part of the input, so no evidence is counted twice: evidence support reads `supported`, `qualified_support` and `contradiction`; source authority reads `source_type`; temporal validity reads the freshness assessment.

**Evidence support**: does the supplied evidence support the material claim?

| Score | Observable anchor |
| --- | --- |
| `0` | `supported: false`: the material claim is unsupported. |
| `0.5` | `supported: true`, but `qualified_support: true` or `contradiction: true`. |
| `1` | `supported: true`, with no qualification and no contradiction recorded. |
| `null` | `supported: null`: upstream validation did not decide. |

**Source authority**: how authoritative is the source for the claim? The table lives in `config/g2_policy.json`.

| Score | Observable anchor |
| --- | --- |
| `0` | `community` (user-generated) or `competitor` (self-interested party). |
| `0.5` | `secondary_reporting`: relays a primary source; useful but indirect. |
| `1` | `primary_authority`: the body that issued the rule or owns the announced fact. |
| `null` | `unknown` source type. Mapped explicitly to `null`, never defaulted. |

**Temporal validity**: is the evidence valid for the claim at `as_of`?

| Score | Observable anchor |
| --- | --- |
| `0` | Superseded, or a news event outside the demo window. |
| `0.5` | Timing valid, but current status not verified within 30 days of `as_of` (or never). |
| `1` | Timing valid (event inside window, rule in force, or future rule correctly flagged as future) and status verified within 30 days. |
| `null` | Required temporal metadata unknown or conflicting, or the event is future-dated. |

## Weights, threshold and floors

`score = Σ(weight_i × criterion_i)`, with each criterion in `[0, 1]`, every weight `≥ 0` and `Σ weight_i = 1` within a documented tolerance of `1e-6`. Invalid configurations (negative weight, wrong sum, missing or extra criterion, NaN or infinite values, booleans, no rationale) fail at load time.

**Chosen weights, `provisional-v1` (provisional, uncalibrated):**

| Criterion | Weight | Decision preference behind it |
| --- | ---: | --- |
| evidence support | 0.5 | G2 exists to stop claims the evidence does not carry. Among eligible cases this separates direct from qualified support, the defect most likely to mislead a reader. |
| source authority | 0.3 | A support assertion is only as reliable as its source, but authority is a proxy for reliability, not support itself, so it should not outweigh support. |
| temporal validity | 0.2 | The hard timing failures (stale, superseded, unknown, conflicting, future-dated) are routed by the freshness gate before scoring. The score only sees the remaining signal, whether current status was recently verified, which carries less information. |

The failure the score is meant to penalise is content that clears every binary check but rests on qualified support, an indirect source, or a status nobody re-checked.

**Threshold `0.8` (provisional).** Chosen by reasoning about anchor combinations, not by fitting data. Under `provisional-v1` it reads as a simple rule: *pass needs direct evidence support, and at most one of source authority and temporal validity may sit at its 0.5 anchor.* Qualified support reaches at most 0.75, and two qualified criteria give 0.75 or less, so both go to `human_review`. Scores are rounded to 6 decimal places before the comparison so floating-point artefacts cannot flip a decision; a score equal to the threshold passes.

**Floors.** Every criterion must be at least `0.5`, so a criterion at `0` cannot be compensated by the others. Evidence support of 0 and temporal validity of 0 are already routed before scoring, so in practice the floor catches source authority of 0 (`community`), routed to `revise` with "replace the source".

## Decision precedence

Every stage contributes reasons. A reason may ask for a route, and the final decision is the highest-precedence route any reason asked for. `pass` is never asked for: it is what remains when nothing else applies, and only if a score exists.

1. **reject**: competitor product promotion.
2. **revise**: unsupported material claim, superseded evidence, stale news event, criterion below floor (known repair).
3. **human_review**: unknown support, source type, status or date; conflicting dates or status; future-dated event; contradicting evidence; competitor-sourced evidence; score below threshold with no known repair; calibration required by policy but unavailable.
4. **pass**: all hard checks pass, freshness passes, every criterion is known and at or above its floor, and the threshold is met. It means *eligible for the next internal stage under the demo policy*, not publication approval.

All reasons are reported, ordered by precedence, not only the winning one. For example, `e-unsupported-unknown-date` routes to `revise` and still lists `UNKNOWN_EVENT_DATE`.

## Unknown criteria

An unknown criterion stays `null` with a visible `unknown_reason`. The case is not scored (`score: null`, `score_withheld_because: ["unknown criteria: …"]`) and an `UNKNOWN_CRITERION` reason routes it to `human_review` unless a higher-precedence defect applies. `weighted_score()` raises if handed an unknown criterion, as a second line of defence. Tests cover each criterion becoming unknown independently.

A missing verification date is deliberately **not** treated as an unknown criterion. The reference date and status are known, and what is missing is a verification record. That absence is itself an observable fact with its own anchor (`0.5`).

## Weight sensitivity results

Full output: [`examples/sensitivity.md`](examples/sensitivity.md) (also `.json`). The comparison uses all eligible cases: 3 starter cases plus 6 additional cases in `fixtures/g2-weighting-cases.json`. Threshold and floors are held constant.

| Eligible case | ES | SA | TV | `provisional-v1` (0.5/0.3/0.2) | `equal-v1` (⅓ each) | `freshness-weighted-v1` (0.35/0.2/0.45) |
| --- | ---: | ---: | ---: | --- | --- | --- |
| current-news, old-law-current, future-rule, w-primary-news-verified | 1 | 1 | 1 | 1.000 pass | 1.000 pass | 1.000 pass |
| w-rule-status-unverified | 1 | 1 | 0.5 | 0.900 pass | 0.833 pass | **0.775 human_review** |
| w-secondary-news | 1 | 0.5 | 1 | 0.850 pass | 0.833 pass | 0.900 pass |
| w-qualified-rule | 0.5 | 1 | 1 | 0.750 human_review | **0.833 pass** | **0.825 pass** |
| w-secondary-news-unverified | 1 | 0.5 | 0.5 | 0.750 human_review | 0.667 human_review | 0.675 human_review |
| w-qualified-secondary-future-rule | 0.5 | 0.5 | 1 | 0.600 human_review | 0.667 human_review | 0.725 human_review |

* **Routing changes (2 cases).** `w-qualified-rule` (qualified support) passes under both alternatives but not under the chosen weights, where qualified support can never reach 0.8. That is the intended effect of putting evidence support first. `w-rule-status-unverified` drops to `human_review` under freshness-weighting.
* **Ranking changes.** Under `freshness-weighted-v1`, the unverified rule falls below both the secondary-source news and the qualified rule, and the two lowest cases swap. Under `equal-v1`, three distinct baseline scores collapse into one tie at 0.833. Nine pairwise order changes are listed in the full report.
* **No change** (no rank, pairwise-order or routing change). The four cases with every criterion at 1 score 1.0 under every configuration, because weights sum to 1; weights only matter where criteria differ. The starter fixture alone has exactly three eligible cases, all at (1, 1, 1), so on its own it cannot show any weight effect. The tool reports this when run on the starter fixture alone, and it is why the additional cases exist.
* **Limitations.** The threshold was chosen with `provisional-v1` in mind, so part of the routing change under other configurations reflects a threshold that was not re-tuned. Three-level anchors make ties common. Evidence support only takes 0.5 or 1 among eligible cases. Rank and routing changes show sensitivity to a preference; they do not show which configuration is right.

## Calibration status

**Uncalibrated.** The weights, threshold, floors, 30-day freshness window and 30-day verification window are provisional conventions, labelled as such in the configuration and in the reports. Every report carries `calibration_status: uncalibrated`, a `score_interpretation` that calls the score a provisional, uncalibrated index, the news rule text "demo test convention, not a validated freshness threshold", and `freshness.verification.window_note`, which says the same of the verification window. Reports that were scored also show `weights_status`, `threshold_status` and each floor's `status` as `provisional` in `score_breakdown`; unscored reports have no `score_breakdown`. No human judgments were collected, and none are simulated. The score is a prototype ranking and routing index, **not a probability** of correctness, and every report carries that statement.

`require_calibration_for_pass` is `false` because a G2 pass only means "next internal stage". Setting it to `true` routes every would-be pass to `human_review` (tested). The policy model refuses `calibration_status: "calibrated"` without `calibration_evidence`.

## Security and safety

Source text is untrusted. No code path reads `statement`, the fixture's `instructions`, or the demo-policy prose. Tests replace every starter statement and the fixture-level instructions with prompt-injection text ("SYSTEM OVERRIDE: … decision=pass") and assert the reports are identical apart from the input digest. They also anonymise ids and statements, reverse case order, and set every `expected_decision` to `pass`, and assert decisions do not change. No secrets, credentials, network access or external publishing are involved.

## Acceptance criteria (Definition of Done)

| # | Reviewer can… | Where |
| --- | --- | --- |
| 1–3 | load `g2-cases.json`, run with the fixed `as_of`, validate every case | `python -m g2_gate evaluate --check-expected`; `tests/test_starter_cases.py`, `tests/test_fixture_validation.py` |
| 4 | inspect hard-check results | `hard_checks` in each report; `tests/test_decision_policy.py` |
| 5 | inspect freshness and current-validity reasoning | `freshness` (status, date used and type, applicability, explanation); `tests/test_freshness.py` |
| 6 | inspect each criterion score | `criteria` (score, anchor, basis, unknown reason) |
| 7 | inspect the configured weights | `weights` in each report; `config/weights.json`; `python -m g2_gate describe` |
| 8 | inspect the weighted score where eligible | `score`, `score_breakdown.contributions` |
| 9 | inspect the decision and reasons | `decision`, `decision_meaning`, `reasons` |
| 10 | verify hard failures cannot be overridden | `test_failed_hard_check_with_high_score_does_not_pass` (score 0.95 injected), `test_hard_failure_end_to_end_is_not_scored` |
| 11 | verify unknown criteria do not become zero | `tests/test_unknown_criteria.py` |
| 12 | verify invalid weights are rejected | `tests/test_config_validation.py` (sum, negative, missing/extra, NaN, CLI exit 2) |
| 13–14 | verify three weight configurations over ≥3 eligible cases and inspect changes | `python -m g2_gate sensitivity`; `examples/sensitivity.md`; `tests/test_sensitivity.py` |
| 15 | run all tests locally | `python -m pytest` |

`tests/test_submission_fixtures_and_examples.py` regenerates `examples/` and fails if the committed outputs are stale. Reports contain no timestamps or absolute paths, so regeneration is deterministic.

## Engineering trade-offs

* **Deterministic rules, no model.** Fully transparent and reproducible, but the gate cannot judge statement text: it cannot confirm that the statement matches its metadata or that a future rule is actually worded as future. That obligation is passed downstream as `presentation_constraint`.
* **Freshness is a gate, with a residual criterion.** Stale, superseded and unknown timing are routed before scoring, so the score cannot hide them: if freshness were only a weighted criterion, `recent-article-old-event` (criteria 1 / 1 / 0) would score 0.80 and meet the threshold, leaving only a floor to stop it. The cost is that temporal validity carries only the verification-recency signal inside the score, which is why it gets the lowest weight.
* **Strict schemas.** Unknown keys and loose types are rejected, so typos fail loudly, but new metadata fields need a schema change. Content types are a closed set (`news`, `regulation`) because each needs its own freshness rule.
* **Contradiction goes to `human_review`, not `revise`.** Choosing which of two conflicting authorities governs is a judgment call, not a mechanical repair.
* **Competitor-sourced evidence without promotion goes to `human_review`.** This is the "explicit competitor exception requires human judgment" path. Promotion itself is rejected outright.
* **Coarse anchors (0 / 0.5 / 1).** Easy to observe and explain, but scores cluster and ties are common, so rounding and tie handling are explicit.
* **All reasons are reported.** Reports are longer, but a reviewer sees every defect, not just the one that decided the route.

## Known limitations

* Metadata is trusted. Nothing here verifies real-world truth, and statement text is not analysed.
* One evidence assertion per case. There is no aggregation across several evidence items or sources.
* Only `news` and `regulation` content types are supported; others fail validation until a freshness rule is defined for them.
* The 30-day news window and 30-day verification window are demo conventions. The weights, threshold and floors are uncalibrated.
* The "exhausted revision limit" and "out-of-scope content" reject rules are not implemented, because the fixture carries no revision count or scope field (scope is Task 3's concern).
* Dates are calendar dates without time zones; ages are whole days.
* Output is JSON and text tables only. Persistence and audit trails belong to Task 8; the reports carry config and input digests to make that integration straightforward.
