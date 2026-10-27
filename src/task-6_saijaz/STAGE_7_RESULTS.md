# Stage 7 — Ordered routing and complete reports

Status: complete. Stage 8 and later stages require separate authorization.

## Implemented

`g2/reports.py` provides pure `evaluate_case`, frozen `EvaluationReport` and `ReportFinding` contracts, typed `Decision`/`FindingOrigin` enums, and `report_to_dict`/`report_to_json`. Routing/report composition is separate from the existing score evaluator to keep responsibilities focused.

Every hard-check and temporal finding is collected before routing. Duplicate supersession codes merge into one finding while retaining both assessment origins and their explanations. The report's immutable assessment preserves hard-check metadata basis, temporal metadata/dates, criteria, and policy. Review findings are also added for unknown criteria, known floor failures, original-evidence requirements, and below-threshold scores. All remain visible even when a prohibition or known repair determines routing.

Decision precedence is reject (prohibited), revise (repairable), human_review (review), then pass. The primary reason is the first finding code in deterministic assessment order within the winning severity; a clean pass uses `PASS_REQUIREMENTS_MET`. Construction recomputes all findings and routing, rejects omissions/reclassification/incorrect decisions, and requires pass to agree with every Stage 6 prerequisite.

Evaluation consumes only a validated label-free case. Identity is copied to the output but neither ID nor statement affects evaluation. Production reporting imports no testing/expected-label module.

## Serialized report schema

Reports expose case ID, G2 gate/report schema, assessment date, policy/schema/weights versions, calibration status/rationale, checks, criteria, freshness metadata/dates/age limit, date basis, separate applicability, weights, floors, authority mapping, threshold, aggregate/null, eligibility/blockers/explanation, floor/threshold results, original-evidence requirement, pass prerequisites, final decision, primary reason, all findings, and the trusted-evidence limitation.

JSON uses sorted keys, two-space indentation, explicit nulls, ISO dates, enum values, full float precision, and a trailing newline. Non-finite numbers are disallowed. No system timestamps, expected labels, or raw statements are serialized. Returned dictionaries are independent representations; mutating one does not mutate the typed report. No JSON report reader is implemented: validated construction is the output contract, not arbitrary JSON-to-report reconstruction.

## Executed verification

`/usr/bin/python3.11 -B -m unittest discover -s tests -q` from the submission directory: **78 tests passed, zero failures/errors**. Seven new tests cover:

- All nine original expected outcomes, with expected labels extracted only by test code; replacing labels with arbitrary objects leaves evaluation unchanged.
- 16 boolean combinations × four statuses (64 subtests) for routing precedence, retained lower-priority findings, and unique merged codes.
- Supersession deduplication preserving both origins/explanations and separate temporal/evidence uncertainty.
- Floor, threshold, and generic competitor review with calculated diagnostic scores; permissive policy does not bypass original-evidence review.
- Required serialized fields, explicit nulls, semantic JSON roundtrips, exact score preservation, repeat-evaluation determinism, and absence of labels/statements.
- ID/prose mutation independence, malformed construction, omitted/reclassified findings, fabricated decisions/reasons, frozen reports, and origin validation.

All 19 Python source/test files passed in-memory AST parsing. Editor diagnostics were clean. Independent evaluation using the checked-in selected policy matched all nine labels; repeated serialization and semantic JSON roundtrips passed 9/9. A probe initially compared indented output to compact formatting; its inspection assertion was corrected without changing project serialization.

| Original case | Actual decision | Primary reason |
| --- | --- | --- |
| current-news | pass | PASS_REQUIREMENTS_MET |
| old-law-current | pass | PASS_REQUIREMENTS_MET |
| recent-article-old-event | revise | STALE_EVENT |
| unknown-date | human_review | UNKNOWN_EVENT_DATE |
| unsupported-claim | revise | UNSUPPORTED_CLAIM |
| superseded-source | revise | SUPERSEDED_EVIDENCE |
| competitor-promotion | reject | COMPETITOR_PROMOTION |
| conflicting-evidence | human_review | UNRESOLVED_SUPPORT |
| future-rule | pass | PASS_REQUIREMENTS_MET |

The original fixture remains unchanged and SHA-256 matches HEAD: `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`. Git inspection found no tracked changes and task artifacts remained inside the submission directory. No dependencies, network access, bytecode writes, commits, or publishing actions were introduced.

## Deferred

Stage 8 owns additional eligible synthetic cases and three-configuration sensitivity comparisons. Stage 9 owns CLI and saved generated example reports; this stage tests serialization in memory and does not claim saved example artifacts. Later stages retain security/full-regression, documentation, acceptance mapping, and clean-checkout rehearsal. Passing is internal demonstration-policy eligibility, never publication approval or independently established truth.
