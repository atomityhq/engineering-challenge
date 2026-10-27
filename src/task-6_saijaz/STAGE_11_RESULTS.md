# Stage 11 — Documentation and acceptance mapping

## Completed scope

- `README.md`: setup/run/tests, declared versus verified Python version, architecture and contracts, checks/precedence, temporal/applicability rules, anchors, policy rationale, actual examples/sensitivity, trusted-metadata boundary and limitations.
- `ACCEPTANCE.md`: task definition-of-done and additional failure paths mapped to concrete implementation, artifacts and existing unittest methods.
- `PR_DESCRIPTION.md`: local prepared explanation covering the requested rationale, boundaries, sensitivity and uncalibrated status. No actual PR, commit or push.
- `MASTER_PLAN.md`: Stage 11 completion, Stage 12 pending, historical-versus-executed sensitivity distinction and secondary-versus-official-indirect routing correction.
- `CLI_USAGE.md`: completed security/documentation status, pending clean-checkout rehearsal.

No production code, dependencies or saved example files changed in this stage.

## Actual verification

Configured `/usr/bin/python3.11`, system Python **3.11.15**. Ran `/usr/bin/python3.11 -B -m unittest discover -s tests -q` in the submission: **95 tests passed**.

A separate read-only verification checked:

- README's 10 and ACCEPTANCE's 2 relative Markdown links exist; PR description has no Markdown links.
- All **57 distinct acceptance test-method references** exist in parsed test source, including shorthand references. This is a name-existence audit, not proof of every semantic coverage claim.
- Actual policy versions, weights (0.45,0.30,0.25), floors (1,0.5,1), threshold 0.80 match documentation. Config inspection confirmed uncalibrated status.
- All nine saved starter decisions match the documented ordered outcomes.
- Saved sensitivity scores match documented arithmetic within 1e-15; exactly `secondary-transit-report` changes route, with unchanged ranking.
- Both live command-specific help outputs expose `--fixture`, `--config`, `--output`.
- Original fixture bytes exactly match `git show HEAD:fixtures/g2-cases.json`; SHA-256 is `e43d7a2cdac137c4d0925ebb9b43137ecfee1e018acde5cf10fd7bc767bbede7`.
- Git detailed status at the documentation audit showed **46 untracked files**, all inside `src/task-6_saijaz/`, no tracked/out-of-scope changes. This result precedes this results file, which adds one submission file; it is not a claim that the final count remains 46.

The initial auxiliary verification completed tests and policy/Git inspection but did not complete all requested checks. A direct read-only audit completed links, AST references, examples, CLI help and original integrity; no unperformed audit is presented as successful.

Saved examples were not regenerated during Stage 11; Stage 9/10 evidence and the passing CLI/security regressions cover reproduction. No isolated copy/worktree rehearsal occurred. Python commands used `-B`; no installer, network operation or source edits through the terminal.

## Remaining boundary

Stage 12 clean-checkout rehearsal requires separate authorization. Documentation does not certify other interpreters/platforms, real-world evidence truth, calibrated predictions, publication approval, OS-level isolation, universal transport denial, large-input quotas or atomic file rollback. Prepared PR text is not a submitted pull request.
