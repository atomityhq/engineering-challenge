# Stage 4 — Hard checks and findings

Status: complete. Stage 5 and later stages remain pending authorization.

## Implemented

`g2/hard_checks.py` supplies pure `assess_hard_checks(Metadata)` and frozen output contracts: `MetadataBasis`, `HardCheck`, `Finding`, and `HardCheckAssessment`. Typed enums identify check names/statuses and finding codes/classifications. Each check and finding has an explanation and metadata basis; no raw statements, expected labels, weights, dates, I/O, or clock are used.

Four checks are always returned in deterministic order:

1. `material_claim_supported`: fail for support false; unknown for support true with contradiction; otherwise pass.
2. `evidence_not_superseded`: fail when the supersession flag or superseded status asserts replacement.
3. `competitor_promotion_absent`: fail when the promotion flag is true, independently of source category.
4. `evidence_conflict_absent`: fail for contradiction; disagreement is not proof of falsehood.

Findings distinguish prohibited promotion, repairable missing support/replaced evidence, and review issues. Disagreeing supersession assertions also retain `SUPERSESSION_METADATA_CONFLICT`. Unresolved asserted support retains both `UNRESOLVED_SUPPORT` and `CONFLICTING_EVIDENCE`. Unsupported plus contradiction preserves the repairable support defect and separate conflict. There is no early return that hides lower-priority issues.

Construction invariants verify statuses against the basis, finding applicability/classification, complete ordered checks, consistent shared basis, and complete ordered findings. Normal construction cannot drop or reclassify a prohibition. Reasons are validated non-blank text, not claimed to be independently semantically verified.

## Executed verification

`/usr/bin/python3.11 -B -m unittest discover -s tests -q` from the submission directory: **49 tests passed, zero failures/errors**. Eight new tests include exhaustive 16 boolean combinations × four statuses (64 subtests), all source categories for promotion, deterministic all-finding retention, unrelated metadata independence, immutable output/type validation, and rejection of missing/inconsistent/reclassified assessments.

All 13 Python files passed in-memory AST parsing; no editor diagnostics were reported for the new source/tests. A read-only probe assessed all nine original cases successfully:

| Case | Non-passing hard checks | Findings |
| --- | --- | --- |
| current-news | none | none |
| old-law-current | none | none |
| recent-article-old-event | none | none |
| unknown-date | none | none |
| unsupported-claim | support fail | UNSUPPORTED_CLAIM |
| superseded-source | supersession fail | SUPERSEDED_EVIDENCE |
| competitor-promotion | promotion fail | COMPETITOR_PROMOTION |
| conflicting-evidence | support unknown; conflict fail | UNRESOLVED_SUPPORT; CONFLICTING_EVIDENCE |
| future-rule | none | none |

Stale and unknown dates intentionally do not fail evidence-only checks; Stage 5 supplies temporal assessment. No final decision is inferred from these checks alone.

Original fixture matched HEAD byte-for-byte and retained SHA-256 `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`. No tracked modifications were reported; submission artifacts remained inside the designated directory. No installs, network access, or bytecode writes occurred.

## Deferred composition

These hard checks accept no weight configuration, so weights cannot alter their statuses or classifications. Pipeline ordering, score blocking, and reject/revise/review precedence will be enforced and tested when the Stage 6–7 evaluator exists. Stage 4 does not claim actual passing scores or final starter routing. Generic competitor original-evidence review and authority-floor behavior remain part of later criterion/routing composition, not an extra fifth hard check.
