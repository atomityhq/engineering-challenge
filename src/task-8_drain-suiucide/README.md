# Task 8 — Audit Records and Replay

A small, deterministic, offline Python implementation of Atomity's **Audit Records and Replay** challenge. It runs three fake workflow operations, records a structured audit manifest, stores input/output artifacts, redacts credential-like values from audit-boundary data, verifies SHA-256 hashes, and replays the workflow from saved local inputs and configuration.

The workflow is intentionally synthetic. It demonstrates audit and replay mechanics; it does not connect to an LLM, browser, CRM, database, or external API.

## Requirements

- Python 3.10 or newer
- No third-party runtime dependencies
- `pytest` is optional; the test suite also runs with the Python standard library's `unittest`

Run all commands from this directory (`src/task-8_drain-suiucide/`).

## Run the example

Successful run:

```bash
python -m workflow_audit run \
  --fixture fixtures/successful-run.json \
  --run-dir .runs/successful-run \
  --run-id demo-success-001
```

Expected summary: `status: success`, three operation records. Inspect these files:

- `.runs/successful-run/audit.json` — machine-readable audit manifest
- `.runs/successful-run/events.jsonl` — separate execution event log
- `.runs/successful-run/artifacts/` — sanitised operation inputs and outputs
- `.runs/successful-run/source_fixture.json` — redacted fixture copy used for offline replay
- `.runs/successful-run/config.json` — versioned deterministic configuration

Replay the run offline:

```bash
python -m workflow_audit replay --run-dir .runs/successful-run
```

Expected replay result: `status: match`, `operations_replayed: 3`, `external_calls: 0`.

Verify artifact integrity without executing operations:

```bash
python -m workflow_audit verify --run-dir .runs/successful-run
```

Failure demonstration (the second operation deliberately fails):

```bash
python -m workflow_audit run \
  --fixture fixtures/failed-operation.json \
  --run-dir .runs/failed-run \
  --run-id demo-failed-001
```

The command exits with code 2 because the demonstration operation failed, but it still writes an audit record with `status: failed` and a stable error code. The failure is deterministic and can be replayed:

```bash
python -m workflow_audit replay --run-dir .runs/failed-run
```

Malformed input demonstration:

```bash
python -m workflow_audit run \
  --fixture fixtures/malformed-input.json \
  --run-dir .runs/invalid-run \
  --run-id demo-invalid-001
```

The fixture is rejected before the run directory or a successful-looking audit record is created.

> Run directories are never overwritten. Remove the specific `.runs/...` directory before rerunning the same example, or use a new path and run ID.

## Run tests

No external service or model is used by the tests.

```bash
python -m unittest discover -s tests -v
```

Or, if pytest is installed:

```bash
pytest -q
```

The test suite checks:

1. Three successful operations and matching offline replay.
2. A failed operation being preserved in the audit record and reproduced by replay.
3. A planted fake API key being redacted from audit/event records and saved operation-input snapshots.
4. Detection of a modified artifact through its SHA-256 hash.
5. Predictable rejection of malformed input before creating a run.
6. Refusal to overwrite an existing run directory.
7. Rejection of an artifact path that attempts to escape the run directory.

## Architecture

```text
Validated local fixture + versioned config
                 |
                 v
        prepare (normalise lead)
                 |
                 v
        enrich (deterministic route)
                 |
                 v
        summarize (final result)
                 |
                 v
       Sanitised inputs / outputs
                 |
       +---------+----------+
       |                    |
       v                    v
 audit.json             events.jsonl
 run and op IDs         operational events
 references + hashes    timestamps + statuses
       |
       v
 replay: verify hashes -> re-run locally -> compare outputs
```

### Audit record

`audit.json` contains the run ID, case ID, run status, configuration version and hashes, source-fixture reference and hash, each operation's ID/name/status, input/output references and hashes, and a stable error code/message on failure. The manifest references content rather than embedding full operation payloads.

`events.jsonl` is a separate operational event stream. Both the audit manifest and event records omit raw input payloads. Operation input/output snapshots are redacted before persistence.

### Replay and integrity

Replay first verifies the SHA-256 hashes of the saved configuration, source fixture, and referenced operation input/output artifacts. It rejects artifact paths that escape the run directory, loads the saved fixture and configuration, re-runs the deterministic operations locally, and compares the sanitised replay outputs with the saved outputs. The replay path does not use network or model clients; the tests block common socket and HTTP entry points to detect accidental external calls.

The saved `source_fixture.json` is a redacted copy of the validated fixture, preventing planted credential-like values from being persisted in the run directory. The synthetic `metadata.debug_note` field is not used by workflow operations, so redacting it does not change their results or deterministic replay. The original synthetic marker remains in the source fixtures under `fixtures/` to exercise redaction. Hashes are calculated from the actual bytes of persisted files. Redaction is heuristic and cannot guarantee detection of every possible secret format.

### Redaction boundary

The demo redacts common credential assignments (for example `FAKE_API_KEY=value`, `password=value`, `access_token=value`) and bearer-token strings in nested strings before writing operation snapshots and events. This is a deliberately small demonstration policy, not a complete secret-detection system. Production use would require a defined data-classification policy, provider-specific secret patterns, access controls, retention rules, and tests against representative secret formats.

### Decision note and trade-offs

- **Chosen:** JSON manifest plus local files. This makes every artifact inspectable and keeps the demo offline and dependency-free.
- **Alternative considered:** SQLite. It would make indexed queries easier but adds schema/migration complexity that is unnecessary for three local operations.
- **Determinism:** All operations are pure functions of the fixture, config, and prior operation output. A fixed config version and a supplied fixture make replay reproducible.
- **Idempotent safety:** Run directories are not overwritten, and run IDs are validated before execution. A duplicate approval action does not exist in this task's scope.
- **Failure behavior:** A failed operation is explicitly recorded with a stable public error code; later operations do not run after the failure.
- **Integrity model:** SHA-256 detects accidental or unauthorised artifact modification relative to the manifest. It does not authenticate who created the manifest; an attacker who can alter both manifest and artifacts could recalculate hashes. Signing or trusted append-only storage would be needed for stronger authenticity guarantees.
- **Known limitation:** The redaction policy is heuristic and may miss secrets in unknown formats. The workflow is intentionally synthetic and is not a production queue, scheduler, or distributed workflow engine.

## Fixture notes

- `successful-run.json`: all three operations succeed and the final qualification routes a larger fictional company to `high_value`.
- `failed-operation.json`: the second operation fails deterministically to demonstrate durable failure records.
- `malformed-input.json`: required lead fields are missing and the employee count has the wrong type.

The `FAKE_API_KEY` marker is intentionally synthetic and is not a real credential.
