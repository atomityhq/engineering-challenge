# Task 4 — Resumable Review Workflow

## Objective

Build a small, testable workflow that coordinates content evaluation, revision and human review.

The workflow must be **resumable**: when execution reaches a human-review boundary, its state must be persisted so that the process can later continue without repeating work that has already completed.

This task is specifically about workflow routing, persistence and reliable execution. It does **not** require a production content-generation or publishing system.

---

## Input

Provide:

* A mock content item.
* Deterministic fake evaluator responses.

The evaluator and content-generation components may be simple fakes. Their purpose is to exercise the workflow rather than demonstrate model quality.

---

## Output

The workflow must produce:

1. A saved workflow state.
2. An event log showing the workflow progression.

The event log should make the following stages inspectable where applicable:

```text
evaluation
    ↓
revision
    ↓
human-review pause
    ↓
completion
```

The exact sequence depends on the evaluator result.

---

## Required Framework

**LangGraph is required for this task.**

Use LangGraph to implement the workflow state, nodes and routing.

Do not replace LangGraph with a custom state-machine implementation.

---

## Required Behaviour

### 1. Evaluate

The workflow begins by evaluating the mock content item.

The evaluator should return a deterministic result that allows the workflow to decide what happens next.

At minimum, the workflow must support outcomes that result in:

* Revision.
* Human review.

---

### 2. Route

Implement the following core routing behaviour:

```text
evaluate
   ├── revise
   │      ↓
   │   evaluate
   │
   └── human review
          ↓
       approval
          ↓
       complete
```

The implementation may use a different internal node structure, but the routing behaviour must be equivalent.

---

### 3. Bound Execution

The demonstration must stop after a configurable maximum of **two revision attempts**.

The retry/revision limit must be explicit and testable.

The workflow must not continue indefinitely when the evaluator repeatedly requests revision.

For example:

```text
evaluation
    ↓
revision 1
    ↓
evaluation
    ↓
revision 2
    ↓
evaluation
    ↓
retry limit reached
```

When the limit is reached, the workflow must enter an appropriate terminal or human-review state rather than continuing indefinitely.

---

### 4. Persist at the Human-Review Boundary

When the workflow reaches human review, save the current workflow state.

The persisted state must contain enough information to continue execution later.

At minimum, the state should preserve information such as:

* Content item.
* Current workflow stage.
* Evaluation result.
* Revision count.
* Relevant workflow identifiers.
* Any information required for the next step.

Local persistence is sufficient.

You may use a local file, SQLite or another simple local persistence mechanism.

---

### 5. Pause for Human Review

The workflow must be able to stop at the human-review boundary.

The CLI should provide a simple way for a reviewer to approve or otherwise continue the workflow.

No web interface is required.

---

### 6. Resume

After the human-review pause, restart the process and resume from the saved state.

The workflow must **not rerun completed work unnecessarily**.

For example, if evaluation and revision were already completed before the checkpoint, resuming should not execute those nodes again merely because the process restarted.

The event log should make this behaviour observable.

---

### 7. Complete

After the human review is approved, the workflow should reach a clear completion state.

Completion should be recorded in the event log.

Repeated approval of an already-completed workflow must not create duplicate completion events or otherwise repeat the completion action.

---

## Required Checks

Automated tests must cover all of the following.

### Normal pass to human review

A content item should successfully proceed through evaluation and reach the human-review boundary.

The workflow state should be persisted.

After approval, the workflow should complete successfully.

---

### One revision then pass

The evaluator should initially request a revision.

The workflow should:

1. Evaluate.
2. Route to revision.
3. Perform the revision.
4. Evaluate again.
5. Route to human review.
6. Persist.
7. Resume after approval.
8. Complete.

The event log should demonstrate the complete sequence.

---

### Retry limit

Test a deterministic evaluator that repeatedly requests revision.

The workflow must stop after the configured maximum of two revision attempts.

It must not enter an infinite loop.

The resulting state or event log must clearly indicate why the workflow stopped.

---

### Restart at review

Run the workflow until it reaches human review.

Persist the state.

Terminate the process.

Start the workflow again using the saved state.

The workflow must resume from human review rather than rerunning previously completed evaluation or revision work.

---

### Duplicate approval

Approve a workflow that has already been completed.

The system must not:

* Complete it again.
* Duplicate the completion event.
* Repeat completed downstream work.

The operation should be safely idempotent.

---

### Malformed input

Invalid or incomplete workflow input must result in a predictable validation failure.

The workflow should not start processing an invalid content item as though it were valid.

---

## Acceptance Criteria

A submission is acceptable when:

* The workflow is implemented using LangGraph.
* A mock content item can pass through the workflow.
* Evaluator responses are deterministic.
* Evaluation can route to revision or human review.
* Revision attempts are explicitly limited to a maximum of two in the demo.
* Workflow state is persisted at the human-review boundary.
* The process can be restarted and resumed from the saved state.
* Completed work is not unnecessarily repeated after resume.
* Human approval can be performed through a CLI.
* Completion is recorded.
* Duplicate approval does not duplicate completion.
* All required checks have automated tests.
* An event log makes workflow progression inspectable.
* The workflow can run locally without paid model access or external accounts.

---

## Acceptable Simplification

Keep the implementation deliberately small.

You do **not** need:

* A production database.
* A web application.
* Real model calls.
* Real content publishing.
* External APIs.
* Authentication.
* Production cloud infrastructure.
* A complex human-review interface.

Local persistence and a CLI approval command are sufficient.

Evaluators and content-generation steps can be deterministic fakes.

The objective is to demonstrate reliable workflow orchestration, checkpointing and resumption.

---

## Optional Extension

You may additionally implement:

* Cancellation handling.
* Recovery from a transient tool failure.

If implemented, clearly distinguish a transient failure that can be retried from a permanent failure that should terminate the workflow.

This is optional and should not replace the required acceptance checks.

---

## Implementation Expectations

Use Python for the implementation.

Use typed workflow inputs and outputs with Pydantic, JSON Schema or an equivalent validation mechanism.

Keep the evaluator and content-generation logic behind simple interfaces so that deterministic fakes can be replaced later.

The workflow should have explicit:

* State.
* Nodes.
* Routing conditions.
* Persistence/checkpoint behaviour.
* Terminal states.

A CLI demonstration is sufficient.

---

## Event Log

The event log should allow a reviewer to understand what happened during a run.

For example:

```json
[
  {
    "event": "evaluation_completed",
    "revision_count": 0
  },
  {
    "event": "revision_requested",
    "revision_count": 1
  },
  {
    "event": "evaluation_completed",
    "revision_count": 1
  },
  {
    "event": "human_review_required"
  },
  {
    "event": "checkpoint_saved"
  },
  {
    "event": "human_approved"
  },
  {
    "event": "workflow_completed"
  }
]
```

This is an illustrative structure, not a required schema.

The important requirement is that the event history makes routing, revision attempts, persistence, human review and completion inspectable.

---

## Example Workflow

A successful example may look like:

```text
$ python -m workflow run content-001

Evaluation completed
Decision: revise

Revision attempt: 1

Evaluation completed
Decision: human_review

Human review required
Checkpoint saved

Workflow paused.
```

After restarting:

```text
$ python -m workflow resume content-001

Loaded checkpoint
Current stage: human_review

Approval required.
Approved.

Workflow completed.
```

The resumed execution should not repeat the earlier evaluation or revision.

---

## Example: Retry Limit

A deterministic evaluator repeatedly returning `revise` should produce behaviour similar to:

```text
Evaluation completed
Decision: revise

Revision attempt: 1

Evaluation completed
Decision: revise

Revision attempt: 2

Evaluation completed
Decision: revise

Maximum revision attempts reached.
Workflow stopped.
```

The exact terminal state may differ, provided the limit and reason are explicit.

---

## State Requirements

The workflow state should be sufficient to reconstruct where execution stopped.

A minimal conceptual state could contain:

```json
{
  "run_id": "run-001",
  "content_id": "content-001",
  "status": "human_review",
  "revision_count": 1,
  "evaluation_result": "human_review",
  "checkpoint_version": 1
}
```

You may extend this structure as required by your implementation.

Do not persist unnecessary secrets or credentials.

---

## Security and Reliability

Treat content and evaluator responses as data rather than executable instructions.

The workflow must not execute instructions embedded inside content merely because they appear in the content item.

The implementation must not require secrets for the local demonstration.

State transitions should be deterministic for the supplied fake evaluator responses.

Operations that may be retried must be designed so that repeated execution does not create duplicate completion or other unintended side effects.

---

## Submission Requirements

Your pull request should contain:

1. The Task 4 implementation.
2. LangGraph workflow definition.
3. Typed workflow state and input/output contracts.
4. Local persistence/checkpoint implementation.
5. Automated tests.
6. Fixtures for deterministic evaluator responses.
7. Event-log output.
8. An executable CLI example.
9. Setup and run instructions.
10. A short architecture/design note.
11. Known limitations.

The pull request description should explain:

* The workflow state.
* The graph nodes.
* Routing conditions.
* How revision limits are enforced.
* How checkpoints are persisted.
* How resume works.
* How duplicate approval is prevented from duplicating completion.
* How the required test cases were evaluated.

---

## Definition of Done

The task is complete when a reviewer can:

1. Install the dependencies locally.
2. Run the automated tests.
3. Start a workflow using the supplied mock content.
4. Observe evaluation and routing.
5. Trigger a revision.
6. Reach human review.
7. Verify that a checkpoint was saved.
8. Stop and restart the process.
9. Resume from the saved state.
10. Approve the workflow.
11. Verify completion in the event log.
12. Verify that completed work was not unnecessarily repeated.
13. Verify that duplicate approval does not duplicate completion.
14. Verify that the two-revision limit prevents an infinite loop.
15. Run the malformed-input test.

The implementation should demonstrate a **small, reliable and inspectable LangGraph workflow**, rather than attempting to build the complete content-production system.
