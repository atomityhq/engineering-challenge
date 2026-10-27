# Stage 9 — CLI and executable examples

## Delivered

- `g2/__main__.py`: evaluate/compare commands, required file output, module-relative defaults, safe logging, explicit nonzero failures, exclusive output creation and input alias protection.
- `CLI_USAGE.md`: invocation, arguments, exit codes, default paths, report schema, overwrite behavior and limitations.
- `pyproject.toml`: dependency-free Python >=3.11 metadata; no build backend or pip workflow claimed.
- `tests/test_cli.py`: six tests covering actual module commands, deterministic files, all four decision routes as successful execution, current-directory-independent defaults, malformed/missing fixture/config, safe errors, direct/symlink/hardlink overwrite protection, existing files, missing parents, mocked permission denial, help and argument errors.
- `examples/starter-report.json` and `examples/sensitivity-report.json`: generated JSON verified against actual fresh CLI runs and API serialization.

## Executed verification

Configured interpreter: `/usr/bin/python3.11`, Python 3.11.15. Bytecode disabled; no package installation required.

- **88 tests passed** across all completed stages.
- **23 Python files** parsed successfully through AST checks.
- No editor errors in the new CLI/test files.
- Fresh evaluate and compare subprocesses both exit 0, produce empty stdout/stderr, and reproduce reference examples byte-for-byte.
- Starter example: 54,449 bytes, nine reports; three pass, three revise, two human_review, one reject; null fields preserved.
- Sensitivity example: 58,007 bytes, three cases across three runs; one changed and two unchanged routes; no ranking reversal.
- Repeated API serialization and both saved examples match byte-for-byte.
- A repeated invocation against existing saved files correctly returns `OUTPUT_EXISTS`; it does not overwrite them. Fresh verification used temporary paths, automatically cleaned inside the submission.
- Original root fixture SHA-256 matches HEAD: `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`.
- Detailed Git inspection before this document: 40 untracked files, every entry within `src/task-6_saijaz/`; no tracked modifications.
- No network, credentials, new dependencies, commits, pushes, or PRs used.

## Boundary and limitations

All existing destinations are refused, a stricter rule than merely refusing input overwrites. Output parents must exist. Direct paths, symlinks, and hardlink aliases of selected and default inputs are protected. Exclusive creation prevents accidental concurrent target overwrite, but atomic publication/rollback and adversarial concurrent parent/input path mutation are not guaranteed. A mid-write error may leave a newly created partial file; this is documented rather than silently deleted.

Help is normal argparse console output; report data is file-only and diagnostics use logging. Malformed arguments are not echoed. Reject/revise/review decisions are report content, not process errors.

Stage 9 is complete. Stage 10 full security/determinism regression requires separate authorization. Final README/acceptance mapping and clean-checkout rehearsal remain Stages 11–12.
