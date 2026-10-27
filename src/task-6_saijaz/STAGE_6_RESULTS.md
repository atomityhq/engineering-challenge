# Stage 6 — Criteria, score eligibility, and aggregate calculation

Status: complete. Stage 7 and later stages require separate authorization.

## Implemented

`g2/evaluator.py` exposes pure `assess_score(metadata, as_of, news_max_event_age_days, policy)`. Hard checks run first, temporal assessment second, then criteria and scoring eligibility. Frozen `CriterionAssessment` and `ScoreAssessment` contracts validate computed outputs against their evidence/timing/policy basis. No final decision, complete report, CLI, I/O, clock, or expected label is added.

Exactly three required criteria are returned in stable policy order:

- Evidence support: false support is 0.0 even with contradiction; asserted support plus conflict is null; clean asserted support is 1.0.
- Source authority: configured category relationship value; unknown stays null. Values are uncalibrated preferences, not measured quality.
- Temporal validity: Stage 5 value (0.0, null, or 1.0), retaining its separate applicability and findings.

Partial-support and qualified-temporal 0.5 anchors remain conceptual and are not emitted by this schema. Each criterion includes a floor, nullable floor result, and explanation. Floors use inclusive comparisons without tolerance.

Every non-passing mandatory check, every temporal finding, and every unknown required criterion contributes an inspectable blocking reason. Any blocker withholds the aggregate; unknown criteria block even at zero weight. Individual criteria and all upstream findings remain available.

For eligible cases, the raw aggregate is `math.fsum(weight × value)` across all three criteria. Full precision is retained. `threshold_met` uses inclusive comparison with no weight-sum tolerance applied to threshold decisions. Floor failure does not prevent a diagnostic score.

Generic competitor sources retain `original_evidence_required=True`, independent of configured authority/floors; they cannot meet pass requirements even under permissive configuration. This is a typed review requirement, not yet a merged report finding. Stage 7 must convert it to an inspectable review finding and enforce final routing. Promotion always blocks scoring.

`pass_requirements_met` expresses numerical/evidence prerequisites only, not a final decision. Immutable construction verifies same-basis hard checks, complete criteria, eligibility/blockers, score, floors, threshold, and original-evidence requirement.

## Numerical range edge case

Policy validation accepts weight sums within absolute tolerance 1e-9, without normalization. A valid near-one sum slightly above one can yield a raw aggregate above one for perfect criteria. Such an aggregate raises `AGGREGATE_OUT_OF_RANGE`; it is never clipped, normalized, or serialized as an out-of-range score. This is an explicit evaluation failure, not editorial routing. A slightly below-one sum remains below one and does not satisfy a threshold of one through tolerance. Tests cover both cases. Default configuration does not trigger this limitation.

## Executed verification

`/usr/bin/python3.11 -B -m unittest discover -s tests -q` from the submission directory: **71 tests passed, zero failures/errors**. Ten new tests cover:

- Independent Decimal expectations for primary, official indirect, reputable secondary, and generic competitor scores.
- Support/conflict mapping, all 64 boolean/status combinations under authority-only weights and permissive floors/threshold.
- Unknown authority, support, and timing blocking despite zero weights.
- Stale/missing/future timing and future verification blocking.
- Adjacent representable floats below/equal/above score thresholds and authority floors.
- Generic competitor original-evidence requirement surviving permissive authority/floors, and promotion still blocking.
- Weight-sum drift range handling, valid future regulation eligibility, deterministic repetition, immutable construction, mismatched basis and fabricated output rejection.

All 17 Python source/test files passed in-memory AST parsing. Editor diagnostics for new files were clean.

## Original fixture score probe

The original fixture and selected policy were loaded in place. These are scoring assessments, not final expected-decision checks.

| Case | Support | Authority | Temporal | Aggregate | Scoring eligible | Pass requirements met |
| --- | --- | --- | --- | --- | --- | --- |
| current-news | 1.0 | 1.0 | 1.0 | 1.0 | true | true |
| old-law-current | 1.0 | 1.0 | 1.0 | 1.0 | true | true |
| recent-article-old-event | 1.0 | 1.0 | 0.0 | null | false | false |
| unknown-date | 1.0 | 1.0 | null | null | false | false |
| unsupported-claim | 0.0 | 1.0 | 1.0 | null | false | false |
| superseded-source | 1.0 | 1.0 | 0.0 | null | false | false |
| competitor-promotion | 1.0 | 0.0 | 1.0 | null | false | false |
| conflicting-evidence | null | 1.0 | 1.0 | null | false | false |
| future-rule | 1.0 | 1.0 | 1.0 | 1.0 | true | true |

Original fixture SHA-256 remained identical to HEAD: `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`. No tracked changes were reported; all untracked submission artifacts were within `src/task-6_saijaz/`. No dependencies, installs, network, bytecode writes, or commits were introduced.

## Deferred

Stage 7 owns reject/revise/human_review/pass precedence, unified findings (including original-evidence/floor/threshold review reasons), primary routing reason, complete reports, serialization, and verification of all nine expected outcomes without label leakage. Stage 8 owns actual sensitivity artifacts. Scores are not probabilities and do not independently verify supplied evidence or prose.
