# Task 8 — Audit Records and Replay

## Objective

Build a small audit and replay component that records the execution of a fixture-driven workflow and allows the saved result to be reconstructed later without external services.

The focus is on:

* Traceability.
* Artifact integrity.
* Secret redaction.
* Deterministic replay.
* Clear audit records.

Do not build a production observability platform.

---

## Input

A small fixture-driven workflow containing **three fake operations**.

The operations may represent simple workflow steps such as:

```text
Operation 1 → Operation 2 → Operation 3
```

They should be deterministic and require no external services.

The workflow should generate inputs and outputs that can be persisted and referenced by the audit system.

---

## Output

Produce:

1. A structured audit log.
2. Saved input/output artifacts.
3. A replay command.

The replay command must reconstruct the saved result without making network or model calls.

A simple local-file implementation is sufficient.

---

# Required Build Steps

## 1. Record

Every workflow run must receive a unique run identifier.

Every operation within the run must also receive an operation identifier.

At minimum, record:

* Run ID.
* Operation ID.
* Operation status.
* Input reference.
* Output reference.
* Operation name/type.
* Execution information required to understand the result.

A conceptual audit record could look like:

```json
{
  "run_id": "run-001",
  "operation_id": "op-002",
  "operation": "transform",
  "status": "success",
  "input_ref": "artifacts/input.json",
  "output_ref": "artifacts/op-002-output.json"
}
```

The exact schema is up to the candidate.

---

# 2. Preserve

The audit record must preserve enough information to reconstruct and verify the workflow result.

Save:

* The fixture used for the run.
* The configuration version.
* Output artifacts.
* Hashes of output artifacts.

The saved record should allow a reviewer to determine:

```text
Which run?
      ↓
Which operation?
      ↓
Which input?
      ↓
Which configuration?
      ↓
Which output?
      ↓
Is the output unchanged?
```

Use content hashes to detect changes to saved artifacts.

---

# 3. Redact

Include a deliberately planted fake secret in one of the workflow inputs or operation outputs.

For example:

```text
FAKE_API_KEY=synthetic-secret-123
```

The secret must **not appear in the audit logs**.

The implementation should redact the value before it reaches the log/audit representation.

The test should demonstrate that:

* The original fixture may contain the planted secret.
* The audit log does not expose the secret.
* Redaction happens deterministically.

Do not use a real credential.

---

# 4. Replay

Provide a command that replays a previously saved run.

For example:

```bash
python -m src.replay examples/run-001
```

The exact command is up to the candidate.

Replay must:

1. Load the saved fixture.
2. Load the relevant configuration.
3. Reconstruct the workflow result.
4. Compare the reconstructed result with the saved result.
5. Report whether the replay matches.

Replay must work **without network or model calls**.

The replay path must therefore use the saved fixtures and local deterministic operations.

---

# Required Checks

## 1. Successful Run

Demonstrate a complete workflow run where all three fake operations succeed.

The submission should contain:

* Audit records.
* Saved inputs.
* Saved outputs.
* Output hashes.
* A successful replay.

---

## 2. Failed Operation Recorded

Create a fixture where one of the fake operations fails.

The audit record must capture the failure rather than silently dropping it.

At minimum, the failed operation should have:

```text
status = failed
```

and enough information to identify the operation and its failure state.

The complete run should remain inspectable.

---

## 3. Fake Secret Redacted

Use a deliberately planted synthetic secret.

Verify that:

```text
secret exists in fixture
```

but:

```text
secret does not exist in audit log
```

The test must fail if the secret leaks into the recorded audit data.

---

## 4. Replay Makes No External Calls

Replay must operate entirely from local saved data.

The test should demonstrate that replay does not require:

* Network access.
* Model APIs.
* External services.
* Credentials.

A useful approach is to make external access fail during the replay test and verify that replay still succeeds.

---

## 5. Altered Artifact Detected

After a successful run, deliberately modify one of the saved output artifacts.

The implementation must detect that the artifact no longer matches its recorded hash.

For example:

```text
Original artifact
      ↓
SHA-256
      ↓
Recorded hash
```

Then:

```text
Modified artifact
      ↓
SHA-256
      ↓
Different hash
      ↓
Integrity failure
```

Do not silently accept the altered artifact.

---

## 6. Malformed Input

Provide a malformed workflow fixture.

The implementation must reject it with a clear and predictable error.

Do not allow malformed input to create a misleading successful audit record.

---

# Audit Log

The audit log should be structured rather than being only human-readable console output.

JSON is sufficient.

For example:

```json
{
  "run_id": "run-001",
  "config_version": "demo-v1",
  "operations": [
    {
      "operation_id": "op-001",
      "name": "prepare",
      "status": "success",
      "input_ref": "artifacts/op-001-input.json",
      "output_ref": "artifacts/op-001-output.json",
      "output_hash": "..."
    },
    {
      "operation_id": "op-002",
      "name": "transform",
      "status": "failed",
      "input_ref": "artifacts/op-002-input.json",
      "output_ref": null,
      "output_hash": null
    }
  ]
}
```

This is an example only. The candidate may choose a different schema if it preserves the required information.

---

# Artifact Integrity

Use a deterministic content hash for saved artifacts.

The hash should be calculated from the actual artifact content.

For example:

```text
artifact → SHA-256 → recorded hash
```

During replay or audit verification:

```text
saved artifact → SHA-256
                         ↓
                 compare with
                 recorded hash
```

A mismatch must be reported clearly.

---

# Replay Result

The replay command should produce an understandable result.

For example:

```text
Run: run-001
Replay: successful

Operations replayed: 3
External calls: 0
Artifact integrity: verified
Output comparison: match
```

For an altered artifact:

```text
Run: run-001
Replay: failed

Artifact integrity: failed
Reason: output hash mismatch
Artifact: artifacts/op-003-output.json
```

The exact output format is up to the candidate.

---

# Separation of Logs and Audit Records

Keep ordinary application logs separate from the auditable decision/execution record.

For example:

```text
Application logs
    └── debugging / operational information

Audit records
    └── run identity
    └── operation identity
    └── inputs
    └── outputs
    └── configuration
    └── hashes
    └── status
```

The audit record should contain the information necessary to reconstruct and inspect the run without becoming an uncontrolled dump of application logs.

---

# Security

The implementation must consider the risk of sensitive information appearing in logs.

At minimum:

* Redact the deliberately planted fake secret.
* Do not commit real credentials.
* Do not require real credentials for the example.
* Keep replay offline.
* Treat workflow inputs as potentially untrusted data.
* Do not expose unnecessary sensitive content in audit records.

The fake secret should be synthetic.

---

# Storage

The minimum implementation can use:

* JSON audit logs.
* Local files for fixtures.
* Local files for artifacts.
* Content hashes for integrity.

SQLite is also acceptable, but it is not required.

Do not introduce a hosted tracing or observability platform merely to satisfy this task.

---

# Acceptable Simplification

The minimum implementation is:

* JSON logs.
* Local files.
* Three fake operations.
* Deterministic workflow.
* Artifact hashes.
* Secret redaction.
* Offline replay.

You do **not** need:

* A hosted tracing platform.
* A production observability backend.
* Distributed tracing infrastructure.
* OpenTelemetry integration.
* Cloud storage.
* A web interface.

The architecture should remain small and understandable.

---

# Optional Extension

You may optionally export the same audit events to OpenTelemetry.

This is not required for the minimum submission.

If implemented, it should remain an extension of the local audit system rather than replacing the required offline audit/replay path.

---

# Typed Contracts

Use typed inputs and outputs.

Pydantic, JSON Schema or an equivalent validation mechanism is acceptable.

Define clear contracts for:

* Workflow input.
* Operation result.
* Audit event.
* Audit manifest/log.
* Replay result.

Malformed input should produce a defined failure state rather than an unstructured crash.

---

# Suggested Fixture Set

At minimum, include fixtures covering:

```text
successful-run
failed-operation
fake-secret
altered-artifact
malformed-input
```

These may be combined where appropriate.

All demonstration data should be synthetic.

---

# Example Workflow

A simple implementation could use:

```text
Fixture
  ↓
Operation 1
  ↓
Operation 2
  ↓
Operation 3
  ↓
Artifacts + Audit Log
  ↓
Replay
  ↓
Integrity + Output Comparison
```

The operations themselves can be deliberately simple.

The challenge is the **auditability and replay behaviour**, not the complexity of the business logic.

---

# Submission Requirements

Submit a pull request containing:

1. The Task 8 implementation.
2. Typed input/output contracts.
3. Three fake workflow operations.
4. Audit log implementation.
5. Saved fixture and artifact handling.
6. Secret-redaction implementation.
7. Artifact hashing/integrity validation.
8. Replay command.
9. Automated tests.
10. A successful run example.
11. A failed-operation example.
12. A replay demonstration.
13. Setup and test instructions.
14. A short decision note describing:

* The audit-record structure.
* The replay approach.
* One alternative considered.
* Known limitations.
* Integration boundary.

---

# Definition of Done

The task is complete when a reviewer can:

1. Install the documented dependencies.
2. Run the fixture-driven workflow.
3. Inspect the generated audit log.
4. Identify the run and each operation.
5. Inspect saved input/output references.
6. Verify the configuration version.
7. Verify output hashes.
8. Confirm the fake secret is redacted.
9. Run the replay command.
10. Confirm replay performs no external calls.
11. Confirm replay reconstructs the expected result.
12. Modify an artifact and confirm the integrity check detects it.
13. Run the failed-operation fixture and inspect the recorded failure.
14. Run the malformed-input test.
15. Run the complete automated test suite.

The final implementation should demonstrate that a workflow execution can be **audited, its artifacts verified, sensitive values protected, and its result replayed deterministically from saved local data**.
