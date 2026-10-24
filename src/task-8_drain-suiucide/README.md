# Task 8 — Audit Records and Replay

A small, deterministic, offline Python implementation of Atomity's
**Audit Records and Replay** challenge.

The workflow runs three synthetic operations, records a structured audit
manifest, persists operation inputs and outputs, redacts credential-like
values at the audit boundary, verifies SHA-256 hashes, and replays a saved run
from local artifacts and configuration.

The implementation is intentionally synthetic. It demonstrates auditability,
integrity verification, safe failure recording, and deterministic replay. It
does not connect to an LLM, browser, CRM, database, or external API.

## Requirements

- Python 3.10 or newer.
- No third-party runtime dependencies.
- The test suite uses Python's standard-library `unittest`.
- `pytest` is optional.

Run the commands in this README from the
`src/task-8_drain-suiucide/` directory.

## Quick start

### Run a successful workflow

```bash
python -m workflow_audit run \
  --fixture fixtures/successful-run.json \
  --run-dir .runs/successful-run \
  --run-id demo-success-001


Expected result: status: success with three operation records.

The run creates the following files:
- .runs/successful-run/audit.json — structured audit manifest.
- .runs/successful-run/events.jsonl — separate operational event log.
- .runs/successful-run/artifacts/ — sanitised operation inputs and outputs.
- .runs/successful-run/source_fixture.json — redacted fixture copy used for replay.
- .runs/successful-run/config.json — versioned workflow configuration.
Verify integrity
python -m workflow_audit verify \
  --run-dir .runs/successful-run


Expected result: status: pass and an empty failures list.

Integrity verification checks the saved manifest and hashes for its referenced
configuration, source fixture, and operation input/output artifacts.
Replay the saved workflow
python -m workflow_audit replay \
  --run-dir .runs/successful-run


Expected result:
- status: match
- operations_replayed: 3
- external_calls: 0
- differences: []
Replay loads the local fixture and saved configuration, executes the
deterministic operations, and compares the redacted outputs with the persisted
artifacts.
Run the failure demonstration
The second operation in this fixture deliberately fails.
python -m workflow_audit run \
  --fixture fixtures/failed-operation.json \
  --run-dir .runs/failed-run \
  --run-id demo-failed-001


The CLI returns a failure exit code for this demonstration, but preserves the
failed operation in the audit manifest with a stable error code and safe
message. Later operations do not execute after the failure.

Replay the failed run:
python -m workflow_audit replay \
  --run-dir .runs/failed-run


Expected result: status: match, operations_replayed: 2, and
external_calls: 0. A matching replay means the saved failure was reproduced;
it does not mean the original workflow succeeded.
Malformed input demonstration
python -m workflow_audit run \
  --fixture fixtures/malformed-input.json \
  --run-dir .runs/invalid-run \
  --run-id demo-invalid-001


The fixture should be rejected before a run directory or a successful-looking
audit record is created.
Run directories are never overwritten. Use a new run directory for a new run,
or deliberately remove the specific disposable demo directory before rerunning
that example.

Tests
Run the complete test suite:
python -m unittest discover -s tests -v


Alternatively, if pytest is installed:
pytest -q


The suite currently contains 27 tests: 11 workflow integration tests and
16 typed-contract tests.
Workflow and replay tests
The integration suite checks:
1. A successful three-operation workflow and matching offline replay.
2. A deliberate operation failure recorded in the manifest and reproduced
   by replay.
3. Redaction of the planted synthetic secret from saved run artifacts.
4. Redaction of a secret injected into an operation output.
5. Sanitisation of an unexpected operation exception, including a synthetic
   secret embedded in the exception message.
6. Detection of a modified artifact through its SHA-256 hash and blocking
   replay when integrity fails.
7. Rejection of a malformed audit manifest.
8. Rejection of an audit manifest containing an extra operation record.
9. Rejection of malformed input before the run directory is created.
10. Refusal to overwrite an existing run directory.
11. Rejection of artifact paths that attempt to escape the run directory.
The successful replay test also blocks common socket and HTTP entry points
to check that replay does not attempt external network access.
Typed OperationResult contract tests
The contract suite checks:
1. Round-trip serialisation of a successful result.
2. Round-trip serialisation of a failed result.
3. Rejection of non-object output by the success factory.
4. Rejection of non-object output in a deserialised success result.
5. Rejection of a failed result that also contains output.
6. Rejection of an explicitly present null output field on failure.
7. Requirement for a non-empty error code on failure.
8. Requirement for a non-empty error message on failure.
9. Rejection of explicitly present null failure fields on a successful result.
10. Rejection of unknown contract fields.
11. Rejection of non-JSON values.
12. Rejection of non-string object keys.
13. Rejection of non-finite numbers.
14. Rejection of circular data.
15. Rejection of invalid success state through direct dataclass construction.
16. Rejection of invalid failure state through direct dataclass construction.
The test suite uses synthetic fixtures and local files. It does not require
credentials, network services, or a model API.
Architecture
Validated local fixture + versioned configuration
                  |
                  v
         prepare (normalise lead)
                  |
                  v
         enrich (deterministic qualification)
                  |
                  v
         summarize (final result)
                  |
                  v
      Sanitised inputs and outputs
                  |
          +-------+-------+
          |               |
          v               v
      audit.json      events.jsonl
      Run and op IDs  Operational events
      References      Timestamps
      SHA-256 hashes  Statuses
      Error records
          |
          v
  Replay: verify hashes -> re-run locally -> compare outputs


Typed contracts
The implementation separates workflow data from audit/replay data using
validated typed contracts.
- WorkflowFixture validates the fixture consumed by the workflow.
- WorkflowConfig validates deterministic workflow configuration.
- OperationResult represents an operation success or failure.
- OperationRecord describes the persisted status and artifact references
  for a single operation.
- AuditEvent validates structured operational events.
- AuditManifest validates the saved run manifest and its operation records.
- ReplayResult represents the outcome of replay and integrity validation.
A successful OperationResult carries a JSON-object output. A failed result
carries a stable error code and safe public message instead of an output
payload. Unexpected exceptions are normalised to a stable error code, and raw
exception messages or tracebacks are not persisted by the workflow.
Audit records
audit.json contains the run ID, case ID, run status, configuration version
and hash, source-fixture reference and hash, operation IDs and names, operation
statuses, artifact references and hashes, and safe failure details where
applicable.

The manifest references artifacts instead of embedding full operation
payloads.

events.jsonl is a separate operational event stream. Audit events contain
metadata such as operation identity, event type, status, references, timestamps,
and safe error information. Raw operation input payloads are not written into
event records.

Operation input and output snapshots are redacted before persistence.
SHA-256 hashes are calculated from the actual bytes written to disk.
Replay and integrity
Replay verifies the saved manifest and hashes of the referenced configuration,
source fixture, and operation input/output artifacts before executing the
workflow.

It then loads the saved local fixture and configuration, validates them using
the typed contracts, runs the deterministic operations, and compares the
redacted replay outputs with saved outputs.

Replay does not use network or model clients. Tests block common socket and HTTP
entry points to detect accidental external calls, and replay reports
external_calls: 0.

The replay implementation also rejects operation records that exceed the
configured operation sequence and checks that recorded operations follow the
configured order.

Artifact references are resolved within the run directory. Paths that attempt
to escape that directory are rejected.
Redaction boundary
The source fixture used for replay is persisted as a redacted copy. The
synthetic metadata.debug_note field is not used by the workflow operations,
so redacting it does not change the operation results or deterministic replay.
The original synthetic marker remains in the source fixtures under fixtures/
to exercise redaction behaviour.

The demo redacts common credential-like assignments, such as FAKE_API_KEY,
password, and access_token, and bearer-token strings in nested strings
before audit-boundary persistence.

Redaction is heuristic. It cannot guarantee detection of every possible secret
format and is not a substitute for a production secret-management policy.

A production implementation would also need an explicit data-classification
policy, access controls, retention rules, and tests for the secret formats
relevant to its integrations.
Decision note and trade-offs
Chosen approach: JSON manifest plus local artifacts
A JSON manifest and ordinary files make the run inspectable, keep the
implementation dependency-free, and support a deterministic local demonstration.
Alternative considered: SQLite
SQLite would make indexed queries easier, but it would introduce schema and
migration concerns that are unnecessary for three local operations in this
challenge.
Determinism
Operations are deterministic functions of the fixture, configuration, and
previous operation output. A saved configuration version and source fixture
allow the workflow to be replayed offline.
Failure behaviour
A failed operation is recorded with a stable error code and safe message.
The workflow stops executing subsequent operations after a failure, and replay
checks that the failure is reproduced.
Integrity model
SHA-256 detects changes to referenced artifacts relative to the saved manifest.
It does not authenticate the person or process that created the manifest. An
attacker who can change both the manifest and its artifacts could recalculate
the hashes. Signing or trusted append-only storage would be required for
stronger authenticity guarantees.
Known limitations
- Redaction is heuristic and can miss unknown secret formats.
- Hashes provide integrity checking against the saved manifest but do not
  authenticate the manifest itself.
- The workflow is synthetic and is not a production queue, scheduler, or
  distributed workflow engine.
- The persisted JSON and JSONL files are local files; access control and
  retention are outside this demonstration's scope.
Fixture notes
- successful-run.json: all three operations succeed, and the final
  qualification routes a larger fictional company to high_value.
- failed-operation.json: the second operation fails deterministically to
  demonstrate a persisted and replayable failure.
- malformed-input.json: required lead fields are missing and the employee
  count has the wrong type.
The FAKE_API_KEY marker is synthetic test data and is not a real credential.