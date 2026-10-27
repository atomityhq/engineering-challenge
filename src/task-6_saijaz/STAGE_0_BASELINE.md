# Stage 0 — Scope and environment baseline

Status: complete. Only Stage 0 was authorized and performed. No component source, tests, policy configuration, or generated evaluation reports exist yet.

## Verified runtime

- Configured environment: existing system Python at `/usr/bin/python3.11`.
- Verified runtime: Python `3.11.15` (GCC `11.4.0`); the Python 3.11 minimum is satisfied.
- The initially selected `/bin/python` is Python `3.10.12`, below the planned minimum. Do not rely on bare `python` resolving to the supported interpreter.
- Successful imports under the selected interpreter: `dataclasses`, `enum`, `datetime`, `json`, `math`, `argparse`, `pathlib`, `unittest`, `logging`, and `tomllib`.
- Dependency choice: standard library only for runtime and tests. No packages were installed. No third-party dependencies are approved or needed.
- Interpreter configuration returned the selected path; runtime execution independently verified it. No Pylance-specific analysis or component execution was performed.
- A `.venv` directory exists at the workspace root; it was not selected, modified, or inspected for dependencies. Neither the workspace root nor the repository contains `.vscode/settings.json` after configuration.

This verifies environment prerequisites, not component compatibility or correctness. Only Python 3.11.15 has been checked; other versions are not certified.

## Scope and repository baseline

- Workspace: `/home/saijaz/Desktop/Project`.
- Repository: `/home/saijaz/Desktop/Project/engineering-challenge`.
- All submission artifacts and future implementation edits belong exclusively in `src/task-6_saijaz/`.
- Before these Stage 0 documentation changes, `git status --short --untracked-files=all` reported only `?? src/task-6_saijaz/MASTER_PLAN.md`.
- `git diff --name-only HEAD` was empty: no pre-existing tracked changes were found.
- No `AGENTS.md` or `.github/copilot-instructions.md` was found within the repository. The supplied organization-wide instructions apply.
- Preserve existing user work. Do not commit, push, open a PR, install dependencies, or modify files outside the submission directory without further authorization.

## Original fixture integrity

Read the original fixture in place at `fixtures/g2-cases.json`; do not copy or modify it. The task's `challenge-starter/g2-cases.json` reference differs from the actual repository path.

Verified properties:

- Git-tracked; `git diff HEAD -- fixtures/g2-cases.json` was empty.
- SHA-256: `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`.
- Schema version: `1.0`; synthetic: `true`; fixed assessment date: `2026-10-06`.
- Nine cases. Expected decisions in fixture order: pass, pass, revise, human_review, revise, revise, reject, human_review, pass.

The hash records the current integrity baseline. Future verification must compare against it. Expected decisions remain test-only and must not enter evaluation inputs or tune the policy.

## Planned local invocation contract

Working directory for the primary execution path: `src/task-6_saijaz/` inside the repository. No pip installation or build backend is needed for this planned path.

The following commands are design targets, **not runnable or tested yet**; Stage 9 will finalize and verify CLI argument spelling:

| Purpose | Planned command from the submission directory |
| --- | --- |
| Test discovery | `/usr/bin/python3.11 -B -m unittest discover -s tests -v` |
| Starter evaluation | `/usr/bin/python3.11 -B -m g2 evaluate --fixture ../../fixtures/g2-cases.json --policy config/policy.json --output examples/starter-report.json` |
| Sensitivity comparison | `/usr/bin/python3.11 -B -m g2 compare --fixture fixtures/additional-cases.json --policy config/policy.json --output examples/sensitivity-report.json` |

On another machine, substitute a verified Python 3.11+ executable. The exact local system path is evidence for this machine, not a portable installation prerequisite. Default fixture resolution will be relative to the submission/module location; explicit paths above are relative to the stated working directory. Any project metadata added later will not imply distribution packaging support.

## Checks performed and deferred

Performed: interpreter configuration and version check, standard-library import probe, repository status/diff inspection, fixture parsing/hash verification, and instruction-file/settings existence checks. Read-only runtime probes used `-B` to avoid bytecode artifacts. No network access or dependency installation was required.

Deferred: component tests, strict validation, scoring/routing, CLI execution, report generation, network-denial tests, and clean-checkout rehearsal. No tests are claimed to have passed because no implementation tests exist.

Next stage: Stage 1, typed input contracts and strict validation, only after separate authorization.
