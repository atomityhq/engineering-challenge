# Executable Demonstration Walkthrough
## Task 4: Resumable Review Workflow (Atomity Engineering Challenge)

This guide provides reproducible step-by-step commands to demonstrate every required capability:
evaluation, automated revision, human-review pause, SQLite checkpoint persistence, resume across process restarts, approval idempotency, retry limits, and persistent audit logging.

All commands below should be executed from the submission directory:
`src/task-4_ranjeetkumarguptabro-maker/`

---

## 0. Prerequisites & Environment Setup

```bash
# From repository root:
cd src/task-4_ranjeetkumarguptabro-maker

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 1. Run Automated Test Suite

Execute all 34 automated unit and integration tests covering Tests A through F:

```bash
pytest -v
```

Expected output:
```text
============================== 34 passed in 1.8s ==============================
```

---

## 2. Scenario A: Normal Pass to Human Review & Approval

### Step 2.1: Start the workflow
```bash
python -m workflow run content-001
```

Representative output:
```text
Starting workflow for content: content-001
Title: Report: Evidence Grounding and Content Validation

Evaluation completed
Decision: human_review

Human review required
Checkpoint saved

Workflow paused.
Use 'resume' or 'approve' to continue after review.
```

### Step 2.2: Inspect the paused state
```bash
python -m workflow status content-001
```

Representative output:
```text
             Workflow Status — content-001             
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Property              ┃ Value                       ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Run ID                │ run_content-001             │
│ Content ID            │ content-001                 │
│ Status                │ awaiting_human_review       │
│ Stage                 │ human_review                │
│ Revisions Completed   │ 0                           │
│ Max Revisions Allowed │ 2                           │
│ Evaluations Performed │ 1                           │
│ Checkpoint Version    │ v1                          │
│ Human Review Status   │ pending                     │
└───────────────────────┴─────────────────────────────┘
```

### Step 2.3: Approve the workflow
```bash
python -m workflow approve content-001 --reviewer "Jane Doe (Lead Editor)"
```

Representative output:
```text
Successfully approved and completed workflow for 'content-001'.
Final status: completed
```

### Step 2.4: Verify approval idempotency
Execute the approval command again on the completed workflow:
```bash
python -m workflow approve content-001
```

Representative output:
```text
Workflow 'content-001' is already completed.
Approval is idempotent. No duplicate completion event recorded.
```

---

## 3. Scenario B: One Revision, Process Restart, and Resumption

Demonstrates:
1. Draft triggers a revision loop.
2. Content is deterministically revised.
3. Second evaluation passes quality checks.
4. Process pauses and saves checkpoint to SQLite.
5. Python process terminates.
6. A fresh process restarts and resumes without repeating completed evaluation or revision work.

### Step 3.1: Start draft requiring revision
```bash
python -m workflow run content-002 --scenario revise-once
```

Representative output:
```text
Starting workflow for content: content-002
Title: Overview: LLM Reasoning Reliability in Production

Evaluation completed
Decision: revise

Revision attempt: 1

Evaluation completed
Decision: human_review

Human review required
Checkpoint saved

Workflow paused.
Use 'resume' or 'approve' to continue after review.
```

### Step 3.2: Simulate process termination
Exit your terminal or start a new shell session. The workflow state is safely stored in `workflow_data.db`.

### Step 3.3: Resume in a fresh Python process
```bash
python -m workflow resume content-002 --reviewer "Alex Chen (Staff Engineer)"
```

Representative output:
```text
Loaded checkpoint (v1)
Current stage: human_review

Approval required.
Approved by Alex Chen (Staff Engineer).

Workflow completed.
```

### Step 3.4: Inspect the complete event sequence
```bash
python -m workflow events content-002
```

Representative output:
```text
Event Log for Content: content-002
---------------------------------------------------------------------------------------------------------------
TIMESTAMP                | EVENT                    | STAGE            | REV  | EXPLANATION
---------------------------------------------------------------------------------------------------------------
2026-10-22 16:04:09      | workflow_started         | initial          | 0    | Workflow started for content 'content-002'.
2026-10-22 16:04:09      | evaluation_completed     | evaluate         | 0    | Evaluation completed with decision: revise.
2026-10-22 16:04:09      | revision_requested       | evaluate         | 1    | Revision attempt 1 requested: Initial draft requires citation.
2026-10-22 16:04:09      | revision_completed       | revise           | 1    | Revision 1 completed successfully.
2026-10-22 16:04:09      | evaluation_completed     | evaluate         | 1    | Evaluation completed with decision: human_review.
2026-10-22 16:04:09      | human_review_required    | human_review     | 1    | Content passed automated evaluation. Human review required.
2026-10-22 16:04:09      | checkpoint_saved         | human_review     | 1    | Workflow checkpoint v1 persisted at human-review boundary.
2026-10-22 16:04:34      | workflow_resumed         | approval         | 1    | Workflow execution resumed from persisted checkpoint.
2026-10-22 16:04:34      | human_approved           | approval         | 1    | Content approved by Alex Chen (Staff Engineer).
2026-10-22 16:04:34      | workflow_completed       | complete         | 1    | Workflow completed successfully.
---------------------------------------------------------------------------------------------------------------
Total events: 10
```

Notice that earlier nodes (`evaluate` and `revise`) were **not** re-run upon resumption. Resumption continued directly from the checkpoint boundary.

---

## 4. Scenario C: Revision Limit Enforcement (Retry Boundary)

Demonstrates bounded execution stopping an infinite loop after 2 revision attempts:

```bash
python -m workflow run content-003 --scenario revise-limit
```

Representative output:
```text
Starting workflow for content: content-003
Title: Analysis: Contested Industry Metrics

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

Check the terminal status:
```bash
python -m workflow status content-003
```
Status is `revision_limit_reached` and the workflow halted safely without entering an infinite loop.

---

## 5. Scenario D: Malformed Input Rejection

Demonstrates strict boundary validation:

```bash
# Empty ID
python -m workflow run "   "
```

Representative output:
```text
Input validation error: 1 validation error for ContentItem
id
  Value error, Content ID cannot be empty or whitespace only.
```
Execution halts immediately with an error exit code before any workflow node or database transaction begins.

---

## 6. List All Workflow Runs

```bash
python -m workflow list
```

Displays a consolidated table of all runs, stages, revision counts, and checkpoint versions.
