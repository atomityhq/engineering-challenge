# Stage 10 — Security, determinism, and regression verification

## Delivered and corrected

`tests/test_security.py` adds seven regressions:

1. Fresh interpreter imports and both CLI commands under network and system-clock guards.
2. Instruction-like statements, fixture instructions, informational policy prose, and arbitrary expected-label objects cannot change serialized evaluation or comparison results.
3. Original fixture baseline hash and bytes preserved through repeated evaluation/comparison.
4. Both example reports reproduced under two hash seeds and two timezones.
5. Production AST import/dynamic-execution firewall: no network/subprocess/pickle imports, test-label API imports, eval/exec/compile/dynamic imports, or print calls.
6. Malformed duplicate-key content does not leak marker, values, paths, or report dumps into logs/stdout.
7. Null-byte fixture/config/output paths fail safely.

The initial suite reproduced an uncaught `ValueError: embedded null byte` during CLI path resolution. Explicit `INVALID_PATH` checks now reject malformed paths before filesystem access in the CLI and both public file loaders. A subsequent loader regression reproduced the same defect directly before those boundaries were corrected. Existing valid output bytes did not change.

## Actual verification

- Configured `/usr/bin/python3.11`, Python 3.11.15; all execution used `-B`.
- **95 tests passed**, including all starter routing, eligibility, constructor, temporal, arithmetic, comparison and CLI regressions.
- **24 Python files** passed AST parsing: 14 production/test-support modules and 10 test modules.
- Public API audit: 14 modules, 25 functions, 35 classes and five explicit methods/properties; no missing parameter/return annotations or public docstrings. This verifies presence, not type correctness or prose quality; self/cls and generated methods excluded.
- Both actual CLI commands regenerated reports into automatically cleaned submission-local temporary paths, exited 0 without diagnostics, and matched reference JSON structurally and byte-for-byte.
- Starter SHA-256: `d86d05da0879579cbb41b05b97387b9afaf585a591215050f3f94997cba2e9a3`.
- Sensitivity SHA-256: `0812a37a4b9f1dfcd9769d2f567f052b300575057eeda816137627436bf54d09`.
- Original fixture matched HEAD byte-for-byte and SHA-256 `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`.
- Before this document, Git reported 42 untracked entries, all inside `src/task-6_saijaz/`; no tracked modifications or bytecode artifacts.
- No network, installations, credentials, commits, pushes, or PRs used.

## Audit findings and limits

The production source audit found no clock/network execution path and no evaluator import of the test-only label extractor. Metadata alone drives criteria/routing; case IDs are output identity, and statements are not serialized or parsed for policy. CLI diagnostics use constant safe messages/codes; successful reports are file artifacts rather than logs.

The fresh-process test replaces date/datetime classes before G2 imports and raises on current date/time access. It also raises on socket construction/connection/DNS and urllib request entry points. This is application-level regression coverage, **not an OS-level network sandbox or proof against every possible transport**. The import firewall supplements it but does not establish general static type correctness or malicious runtime monkeypatch resistance. Timezone/hash-seed variation and repeated byte equality verify tested configurations, not every platform/version.

Inputs remain synthetic trusted assertions. No independent source verification, calibration, or publication guarantee is claimed. Resource quotas for arbitrarily large valid JSON are not implemented; decoder limits are handled, but memory exhaustion is outside this local-demo verification. Previously documented concurrent-path and partial-output-file limitations remain. No atomic rollback is claimed.

An auxiliary read-only agent was unavailable due to service/credit limits; direct source inspection and executed regressions completed the audit instead.

Stage 10 is complete. Stage 11 final documentation/acceptance mapping and Stage 12 clean-checkout rehearsal remain separately authorized work.
