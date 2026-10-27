# Stage 12 — Isolated rehearsal and final scope audit

## Readiness

Stages 0–12 are complete. Task 6 is ready for user review and separately authorized submission on the verified Python 3.11.15/Linux runtime. No commit, push or pull request was created. Readiness is limited to the documented synthetic/offline component, not evidence truth, calibration or publication approval.

## Rehearsal method

Created a temporary directory inside the submission, extracted `git archive HEAD` into an isolated checkout and overlaid the current uncommitted submission snapshot. Baseline HEAD: `6272194723474802bc50ed4fd998f65d75b595555`. This is **HEAD baseline plus an uncommitted submission snapshot**, not certification of an already committed submission. No Git state was changed, and no user changes were discarded.

Excluded rehearsal directory, `.venv`, `__pycache__`, `.pyc` and `.git` from the overlay. Source/copied submission manifests matched **47 files** before execution; manifest SHA-256 `859bf1129df39dfddd951f99819e84fb3a301bdb3f6556a7701cf869f0ee2299`. This records the pre-final-documentation snapshot; later documentation edits change that manifest, not the verified implementation/examples.

All child commands ran from the copied `src/task-6_saijaz/`, with `PYTHONPATH`/`PYTHONHOME` unset, `PYTHONDONTWRITEBYTECODE=1`, and temporary-directory environment variables pointing inside the rehearsal. No original workspace package or virtual environment was needed. TemporaryDirectory cleanup succeeded.

## Executed commands and results

Interpreter: `/usr/bin/python3.11`, **3.11.15**.

- `/usr/bin/python3.11 -B -m unittest discover -s tests -q`: **95 tests pass**, exit 0 (0.592 seconds).
- `/usr/bin/python3.11 -B -m g2 evaluate --output examples/my-starter-report.json`: exit 0.
- `/usr/bin/python3.11 -B -m g2 compare --output examples/my-sensitivity-report.json`: exit 0.
- `/usr/bin/python3.11 -B -m g2 evaluate --fixture ../../fixtures/g2-cases.json --config config/policy.json --output examples/my-explicit-starter-report.json`: exit 0.

Each report command repeated unchanged exited **2** with `OUTPUT_EXISTS`, preserving existing destination bytes. Generated outputs matched both copied and original saved examples byte-for-byte:

| Output | Bytes | SHA-256 |
| --- | --- | --- |
| Default starter | 54,449 | `d86d05da0879579cbb41b05b97387b9afaf585a591215050f3f94997cba2e9a3` |
| Sensitivity | 58,007 | `0812a37a4b9f1dfcd9769d2f567f052b300575057eeda816137627436bf54d09` |
| Explicit starter | 54,449 | `d86d05da0879579cbb41b05b97387b9afaf585a591215050f3f94997cba2e9a3` |

All nine starter decisions retained the documented outcomes (3 pass, 3 revise, 2 human_review, 1 reject). Comparison contains three reports in each of `grounding-first-v1`, `grounding-first-v1:equal-v1`, and `grounding-first-v1:authority-heavy-v1`.

All **24 copied Python files** passed AST parsing. No copied environment/bytecode/Git contamination was present. Copied snapshot files remained unchanged; only the three expected temporary reports were added.

## Integrity and scope

Original fixture: **5,975 bytes**, SHA-256 `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`. Original, HEAD and copied fixture were byte-identical. The temporary checkout necessarily reproduces the baseline fixture for isolation; no duplicate fixture was added to the deliverable and the live original remained untouched.

Before/after original tracked/untracked file snapshots matched **65 files**, excluding the temporary rehearsal. Detailed Git status remained unchanged: empty tracked diff, **47 untracked submission files only**. Those figures precede creation of this results file/final status documentation updates; this results file adds one submission file. No production source/config/reference example was changed in Stage 12. No installer, dependency download, network operation, container, commit, stash, push or PR operation occurred.

## Verification limits

The isolated full suite includes fresh-process tests guarding selected socket/urllib and system date/time APIs before G2 import, for evaluate and compare. These are application-level assertions, not an OS sandbox, exhaustive transport/clock interception or universal security certification. No additional Python version/platform or hidden tests were certified. No real evidence verification, calibrated predictive quality, large-input quotas, atomic write rollback or hostile concurrent path-mutation guarantee is claimed.

Historical Stage 11 documents retain their then-pending status where appropriate. The original Stage 12 results above describe the earlier 95-test snapshot; they are not rewritten as results for a later implementation.

## Corrected-snapshot rehearsal — 2026-10-27

After the final-review stale-news/status-uncertainty correction, a second rehearsal exported `git archive HEAD` into a temporary isolated root and copied the current submission over it, excluding caches. This again verified a HEAD baseline plus an uncommitted submission snapshot, not an already committed checkout. The earlier manifest and timing figures above apply only to the historical rehearsal.

Verified on `/usr/bin/python3.11`, Python **3.11.15/Linux**:

- Workspace suite: **96 tests passed**.
- Isolated-copy suite: **96 tests passed**.
- Default starter evaluation, explicit `../../fixtures/g2-cases.json` plus `config/policy.json` evaluation, and weight comparison: all exited 0.
- All three generated outputs matched the saved reference reports **byte-for-byte**.
- All **24 production/test Python files** parsed successfully.
- Assessment date remained **2026-10-06**; all nine starter decisions and the three-case score/rank/routing comparison retained their documented results.
- Original fixture bytes matched HEAD and remained unchanged.
- Repository status before and after the rehearsal was identical; the temporary copy was deleted.

No dependencies were installed and no network, commit, push or PR operation was performed by this rehearsal. Documentation-only updates followed. The user subsequently authorized a local commit and confirmed that Azure Boards does not apply, waiving the plan's `AB#<id>` commit-reference requirement. Push and PR creation remain separately authorized actions. All verification limits stated above still apply.
