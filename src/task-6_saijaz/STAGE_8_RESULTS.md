# Stage 8 — Additional cases and sensitivity comparison

## Delivered

- `fixtures/additional-cases.json`: three independent, eligible synthetic cases without expected labels.
- `fixtures/README.md`: explicit primary, official-indirect, and reputable-secondary authority relationships and trusted-metadata limitations.
- `g2/sensitivity.py`: immutable validated runs/comparisons, chosen/equal/authority-heavy weight-only evaluation, exact competition ranks, ties, routing changes, complete reports, deterministic JSON.
- `tests/test_sensitivity.py`: four tests covering independent Decimal arithmetic, routes, rank stability, exact ties, null blockers, fixed-policy constraints, construction validation, immutability, and serialization.

## Verified results

All cases have support and temporal validity 1. Policy floors, threshold, authority mapping, versions other than weight version, and fixture context stay fixed. Authority preferences are 0.5, 0.75, and 1 respectively.

| Case | Chosen score | Equal score | Authority-heavy score | Ranks | Decisions |
| --- | --- | --- | --- | --- | --- |
| secondary-transit-report | 0.85 | 0.8333333333333333 | 0.75 | 3 / 3 / 3 | pass / pass / human_review |
| indirect-institutional-rule | 0.925 | 0.9166666666666666 | 0.875 | 2 / 2 / 2 | pass / pass / pass |
| primary-future-rule | 1.0 | 1.0 | 1.0 | 1 / 1 / 1 | pass / pass / pass |

Exactly one routing change; two unchanged routes. No ranking reversal or ties in the additional fixture. The generic comparison API also supports blocked cases: null scores remain unranked. Exact ties share competition rank (1 + number of strictly greater scores); lexical case IDs only order tied display, not scores. Separate tests verify ranks 1, 1, 3, null and stable tied display.

## Executed evidence

- Python 3.11 interpreter `/usr/bin/python3.11`, bytecode disabled.
- Full unittest discovery: **82 tests passed**, including all earlier starter-case regression tests.
- AST parsing: **21 Python files** valid.
- Editor diagnostics: no errors in the new module or tests.
- Repeated comparison serialization is byte-identical; parsed JSON equals the explicit dictionary, with complete report objects and explicit nulls.
- Original root fixture SHA-256 matches HEAD: `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`.
- Git inspection before this results document: 33 untracked submission files, all inside `src/task-6_saijaz/`; no tracked modifications.
- No dependencies installed, network used, commits created, or original fixture modified.

## Limitations and stage boundary

This is synthetic weight-preference analysis, not calibration, source verification, or expert judgment. Fixed support/timing and ordered authority explain the unchanged rankings. Weights are never normalized or scores rounded for routing/ranking; previously documented aggregate range limitations remain unchanged.

Stage 8 is complete. Stage 9 CLI and saved generated JSON examples require separate authorization and have not been implemented.
