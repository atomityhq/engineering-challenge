# Stage 9 CLI usage

## Runtime and location

Python 3.11+ is required; only Python 3.11.15 has been tested here. No pip installation, downloaded packages, network, credentials, or build backend are required. `pyproject.toml` is project metadata, not a distribution-packaging claim.

From `src/task-6_saijaz/`, invoke `python -B -m g2 evaluate --output examples/my-starter-report.json` or `python -B -m g2 compare --output examples/my-sensitivity-report.json`. On the verified machine the interpreter is `/usr/bin/python3.11`. Use a new output filename: saved reference examples already exist and are protected from overwrite.

Use `python -B -m g2 --help` and the command-specific `--help` for arguments. Run tests from the same directory with `python -B -m unittest discover -s tests -q`.

## Arguments and outputs

Both commands accept `--fixture PATH`, `--config PATH`, and required `--output PATH`.

- `evaluate` defaults to the original repository `fixtures/g2-cases.json`, resolved from the module location. The task's `challenge-starter/g2-cases.json` reference is stale.
- `compare` defaults to submission `fixtures/additional-cases.json` and compares chosen, equal, and authority-heavy weights; other settings remain fixed.
- Configuration defaults to submission `config/policy.json`, resolved from the module location.
- Explicit relative paths resolve against the current working directory. Defaults do not.
- The output parent must already exist. Every existing output is refused; there is no force option. Fixture/config path aliases, symlinks, and hard links are protected. Files are created exclusively, not overwritten.
- Exit 0 means report generation completed, including cases routed to reject/revise/review. Exit 2 means arguments, validation, or file I/O failed.
- Reports go only to UTF-8 JSON files. Safe diagnostic codes/messages go through logging on stderr; file paths and raw input are not logged. Help uses argparse's normal console output.
- Serialization retains full-precision scores, explicit nulls, and fixed fixture dates, with sorted JSON keys and a trailing newline.

## Reference examples

`examples/starter-report.json` and `examples/sensitivity-report.json` are actual CLI-generated output, not hand-written examples. The evaluation envelope contains schema, gate, synthetic status, as_of, and complete case reports. Comparison JSON contains all three runs, ranks/ties, score/decision vectors, and routing changes.

The original nine cases retain their mandated outcomes. In the additional fixture only secondary reporting changes from pass to review under authority-heavy weights; ranks remain unchanged. Assertions are synthetic trusted metadata, weights uncalibrated, and pass is not publication approval.

## File-write limitation

Exclusive creation prevents accidental overwrite, including a concurrent creation of the target path. A failure during a write may leave a partial newly created file; no atomic publication/rollback guarantee is claimed. Error handling does not delete such files automatically. Avoid adversarial concurrent changes to input paths or parent directories. Security regression and final README/acceptance mapping are complete; see `STAGE_10_RESULTS.md` and `STAGE_11_RESULTS.md`. Stage 12 records the historical 95-test rehearsal and the corrected-snapshot **96-test isolated rehearsal**, including byte-for-byte reproduction of default/explicit starter and comparison outputs; see `STAGE_12_RESULTS.md`. A local commit is user-authorized; no push or PR creation is authorized by these CLI instructions.
