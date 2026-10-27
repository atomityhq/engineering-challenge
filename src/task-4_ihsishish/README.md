# Task 4: Resumable Review Workflow

This LangGraph demo evaluates a draft, revises it when needed, and waits for a person to approve or reject it. Progress is saved locally, so you can close the program and resume without repeating the earlier work. No API key or paid service is needed.

## Setup

Use Python 3.11 or newer. In Windows PowerShell, from the repository root:

```powershell
cd src\task-4_ihsishish
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the remaining commands in PowerShell from `src\task-4_ihsishish`.

## Run, restart, and approve

Use the fixture filenames exactly as shown. A reviewer starts with no `review.sqlite`; the first `start` command creates it.

**1. Start a run.**

```powershell
.\.venv\Scripts\python.exe app.py start fixtures\one_revision.json
```

The event log should show an evaluation, one revision, and another evaluation. The result says `HUMAN_REVIEW` and **Checkpoint saved**. A *checkpoint* is a saved copy of the draft, revision count, status, and event log in `review.sqlite`.

**2. Close PowerShell.** Open a new PowerShell window in the same folder. This checks that the saved run survives after the original process exits.

**3. Inspect and resume the saved run.**

```powershell
.\.venv\Scripts\python.exe app.py show one-001
.\.venv\Scripts\python.exe app.py review one-001
```

The fixture file is named `one_revision.json`. Its `content_id`, `one-001`, identifies the saved run for `show`, `review`, and `approve`. `show` should still display `HUMAN_REVIEW` and one revision. `review` displays the saved draft and asks `Approve this content? [y/n]`. Enter `y`: the result becomes `COMPLETED`. The earlier evaluation and revision appear only once in the event log.

**4. Approve again.**

```powershell
.\.venv\Scripts\python.exe app.py approve one-001
```

The result says **Already completed. Nothing was repeated.** There is still only one `Workflow completed` event. The `approve` command approves without showing the draft when a run is waiting for review; use `review` when a person needs to read it.

**5. Check the revision limit.**

```powershell
.\.venv\Scripts\python.exe app.py start fixtures\three_revisions.json
```

This fixture uses `three-001` and requests revision three times. The run performs only two revisions, then stops with `RETRY_LIMIT` and logs **Maximum revision attempts reached (2)**. The two-revision fixture uses `two-001` and reaches human review instead.

The local `review.sqlite` file retains previous runs and is excluded from Git. On your own computer, starting the same fixture a second time will report that its ID is already saved; this does not affect a reviewer with a fresh checkout.

## How the workflow decides

The default allows **up to two revisions**. The number below counts revisions already finished:

- If the evaluator says **ready for human review**, the workflow saves the draft and waits for a person. This can happen before any revision or after the first or second revision.
- If the evaluator says **revise** and the draft has had **0 revisions**, the workflow makes revision **1**, then evaluates it again.
- If the evaluator says **revise** and the draft has had **1 revision**, the workflow makes revision **2**, then evaluates it again.
- If the evaluator still says **revise** after **2 revisions**, the workflow stops at `RETRY_LIMIT`. It does not make a third revision.

At human review, enter `y` to approve and complete the run, or `n` to reject it. You can choose a lower revision limit with `--max-revisions 0` or `--max-revisions 1`.

## Design notes

**What is saved?** `data.py` defines validated input and evaluator responses, plus a typed workflow state. The state contains the content ID, current and prepared drafts, last evaluation and reason, revision count and limit, status, and event log.

**What are the graph nodes?** `workflow.py` defines five nodes:

| Node | Job |
| --- | --- |
| `evaluate` | Get a decision: revise or human review. |
| `revise` | Replace the draft with prepared revision text. |
| `review` | Record that a person must review the draft. |
| `limit` | Stop after the allowed revisions. |
| `approve` | Wait for the human decision, then complete or reject. |

`steps.py` supplies fake evaluators and a reviser. `app.py` supplies the commands.

**Where is progress saved?** LangGraph writes checkpoints to the local `review.sqlite` file. The content ID keeps each run's saved state separate.

**How does resume work?** At human review, the graph reaches an *interrupt*: a pause waiting for a person's answer. `review <id>` loads that checkpoint and continues from the pause. It does not rerun evaluation or revision.

**How is the limit enforced?** When evaluation says `revise`, the graph checks the count before revising again. If two revisions have already happened at the default limit, it records the limit event and stops.

**Why is approval safe to repeat?** Approval saves the status `COMPLETED` and records one completion event. A later `approve <id>` sees that status and makes no changes.

## Tests

Run all 16 tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q test_workflow.py
```

| Required check | Test |
| --- | --- |
| Normal pass | `test_normal_pass_persists_then_approves` |
| One revision | `test_one_revision_then_approval` |
| Retry limit | `test_retry_limit_stops_after_two_revisions` |
| Restart and resume | `test_restart_resumes_without_reevaluating` and `test_restart_in_separate_python_process` |
| Duplicate approval | `test_duplicate_cli_approval_does_not_repeat_completion` |
| Malformed input | `test_malformed_input_creates_no_checkpoint` |

Other tests cover manual and scripted evaluator responses, the second revision's text, and instruction-like content. Tests use temporary SQLite files; they do not change your `review.sqlite`.

## Other fixtures

- `two_revisions.json` reaches human review after two revisions. `security_test.json` contains instruction-like content; the workflow treats that content as data.
- `manual_revision.json` asks `Ready for human review?` after each draft. Enter `n` to request revision or `y` to pause for final review. The later `Approve this content?` prompt is the separate human decision.

## Limitations

| Area | Limitation |
| --- | --- |
| Evaluation | The fake evaluators follow preset or simple rules. They do not check whether claims are true. |
| Revision | The reviser uses text supplied in the fixture. If `second_revised_text` is absent, the second revision reuses `revised_text`. |
| Review and storage | SQLite is for a local, single-machine demo. There is no reviewer login or coordination for two people reviewing at the same time. |
