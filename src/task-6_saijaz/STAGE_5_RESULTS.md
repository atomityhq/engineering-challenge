# Stage 5 — Freshness and current applicability

Status: complete. Stage 6 and later stages require separate authorization.

## Implemented contracts and behavior

`g2/freshness.py` exposes pure `assess_freshness(metadata, as_of, news_max_event_age_days)`. Frozen `TemporalAssessment` and `TemporalFinding` contracts use typed `Applicability` and `TemporalCode` enums. Construction validates input types and recomputes output invariants from the immutable metadata/date/age-limit basis; findings cannot be removed, reclassified, or contradicted by a fabricated temporal value.

The assessment exposes temporal value (1.0, 0.0, or null), event age, relevant date basis, separate applicability and nullable current-applicability flag, all findings, and an explanation. Its metadata basis retains publication, event, effective, and verification dates. No system clock, I/O, policy weights, expected labels, network, or final decision is used.

- News uses event age, inclusively bounded by the supplied fixture limit. Publication/verification cannot substitute for an unknown event. Future ordinary-news events are review uncertainty. Unknown/incompatible statuses remain null rather than pretending established current coverage; stale-event invalidity is asserted for current news. Legal applicability is `not_applicable` with a null boolean for all news, not an additional unknown required criterion.
- Current regulations require an effective date on/before assessment. Adopted-not-applicable regulations require an effective date strictly after assessment; valid future descriptions have temporal value 1.0 and current applicability false. Status/effective inconsistencies remain unresolved rather than assuming activation.
- Either supersession assertion establishes temporal invalidity and inactive regulation applicability. Flag/status disagreement is retained. Missing required dates and other inconsistencies remain visible even with this higher-priority defect.
- Future verification adds uncertainty; no verification expiry is invented. For non-superseded regulations it also withholds asserted applicability. Known temporal invalidity 0 takes priority over uncertainty null, which takes priority over valid timing 1. All findings remain present.
- Evidence support/contradiction alone does not change established timing. No global date-order constraint or universal publication-age penalty is imposed.

The plan's shorthand “unknown applicability” for unknown news status refers to unresolved coverage status; legal applicability for news remains explicitly not applicable as specified in the news subsection.

## Verification

From the submission directory, `/usr/bin/python3.11 -B -m unittest discover -s tests -q` passed **61 tests with zero failures/errors**. Twelve new tests cover:

- News ages 0, 30, 31, and -1; injected dates and age limits including zero.
- Missing event dates with current publication/verification context.
- Regulation effective dates before, equal to, and after assessment for current and future statuses; old publication does not penalize a current rule.
- All two-content × four-status × two-supersession-flag combinations (16 subtests).
- Missing effective dates for all statuses; unknown/incompatible news status.
- Absent, old, equal, and future verification; invalidity plus retained uncertainty.
- Unrelated evidence fields, publication/event ordering, strict input types, deterministic repeated results, frozen output, and construction invariants.

All 15 Python source/test files passed in-memory AST parsing. Editor diagnostics for the new source and tests were clean.

The first test run exposed a guard that suppressed effective/status inconsistency under supersession. The regulation branch was corrected, then the complete suite rerun successfully. Independent probes confirmed supersession, flag/status disagreement, effective/status inconsistency, and future verification are all retained together while temporal value stays 0 and regulation applicability stays false.

## Original fixture probe

Assessment date: 2026-10-06. News limit: 30 days. No final routing verification is claimed here.

| Case | Temporal value | Event age | Applicability | Temporal findings |
| --- | --- | --- | --- | --- |
| current-news | 1.0 | 3 | not_applicable | none |
| old-law-current | 1.0 | null | currently_applicable | none |
| recent-article-old-event | 0.0 | 643 | not_applicable | STALE_EVENT |
| unknown-date | null | null | not_applicable | UNKNOWN_EVENT_DATE |
| unsupported-claim | 1.0 | 3 | not_applicable | none |
| superseded-source | 0.0 | null | not_currently_applicable | SUPERSEDED_EVIDENCE; UNKNOWN_EFFECTIVE_DATE |
| competitor-promotion | 1.0 | 3 | not_applicable | none |
| conflicting-evidence | 1.0 | 3 | not_applicable | none |
| future-rule | 1.0 | null | not_yet_applicable | none |

Hard-check defects in unsupported/promotional/conflicting cases remain separate; valid dates do not permit passing those cases. Missing effective date in the superseded case is retained without overriding known invalidity.

Original fixture remained byte-identical to Git HEAD (Git blob `a0b630e98e9a67651fd12fb01e87de789798d95d`; previously verified SHA-256 `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`). No tracked/staged changes were reported; untracked submission files remained within the designated directory. No dependencies, network, commits, or bytecode writes were introduced.

## Deferred

Stage 6 will compose anchored criteria, scoring eligibility, floors, and weighted aggregates. Stage 7 will merge hard-check and temporal findings into complete reports and enforce ordered routing. Shared supersession codes will need deliberate deduplication without losing metadata basis or distinct uncertainties. This stage verifies metadata assertions, not independent evidence or whether prose actually describes future applicability.
