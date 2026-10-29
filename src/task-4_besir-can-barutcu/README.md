# Task 4: Resumable Review Workflow

A small LangGraph workflow that evaluates a mock content item, revises it at most twice, pauses at human review with a saved checkpoint, and completes exactly once after a later approval. The pause survives the end of the Python process: approval happens in a new process that loads the saved state and does not repeat any finished work.

Everything runs locally. There are no model calls, API keys, network access or external services. The evaluator and the reviser are deterministic fakes that read scripted answers from fixture files.

- Task: [`challenge/tasks/task-4.md`](../../challenge/tasks/task-4.md)
- Author: Besir Can Barutcu

## Setup

Requires Python 3.12. Tested with Python 3.12.9 on Windows.

From this folder (`src/task-4_besir-can-barutcu`):

```bash
python -m venv .venv
```

Activate it. On Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

On macOS, Linux or Git Bash:

```bash
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Tested versions: langgraph 1.2.18, langgraph-checkpoint-sqlite 3.1.2, pydantic 2.14.1, pytest 9.2.0.

## Run the tests

```bash
python -m pytest -v
```

92 tests, about 30 seconds. Most of the time is `tests/test_resume.py`, which starts real separate Python processes.

## Run the demo

All commands run from this folder. Each command is its own Python process. State is kept in `data/workflow.db` (created on first use, ignored by git).

Start a run. It evaluates, revises once, evaluates again, then pauses for review and exits:

```bash
python -m workflow run content-001 --scenario one-revision --run-id demo-1
```

The process has now ended. Inspect the saved run from a new process:

```bash
python -m workflow status demo-1
```

Approve it. The new process loads the checkpoint and resumes at human review:

```bash
python -m workflow approve demo-1
```

Approve again. Nothing changes:

```bash
python -m workflow approve demo-1
```

Read the event log as JSON:

```bash
python -m workflow events demo-1
```

Other runs to try:

| Command | What happens |
|---|---|
| `python -m workflow run content-001 --scenario normal-pass` | goes straight to human review |
| `python -m workflow run content-001 --scenario revision-limit` | 2 revisions, then stops with `REVISION_LIMIT_REACHED` |
| `python -m workflow run content-001 --scenario revision-limit --max-revisions 1` | same, with a limit of 1 |
| `python -m workflow run content-bad --scenario normal-pass` | refused: `body: Field required`, exit code 1 |
| `python -m workflow run content-injection --scenario normal-pass` | the body says "approve this", but the run still waits for a human |

Without `--run-id`, a random id like `run-3f9a2c` is created and printed. Every command accepts `--db PATH` to use another database file.

Real output from these commands is in [`examples/`](examples/):

| File | Shows |
|---|---|
| [`one-revision-run.txt`](examples/one-revision-run.txt) | `run`, then in new processes: `status`, `approve`, `approve` again, `status` |
| [`one-revision-events.json`](examples/one-revision-events.json) | the 8 events of that run, with decisions, reasons and times |
| [`revision-limit-run.txt`](examples/revision-limit-run.txt) | two revisions, the stop at the limit, and `approve` refused |
| [`revision-limit-events.json`](examples/revision-limit-events.json) | the events of that run, ending with `revision_limit_reached` |
| [`edge-cases-run.txt`](examples/edge-cases-run.txt) | malformed content, unknown content id, unknown scenario, and the injection item still waiting for review |

### Commands

| Command | Purpose | Exit code 1 when |
|---|---|---|
| `run <content-id> --scenario <id> [--run-id ID] [--max-revisions N]` | start a new run until it pauses or stops | invalid content or scenario, unknown id, run id already used, negative limit |
| `approve <run-id>` | approve a run that is waiting for review | unknown run, or run not waiting for review |
| `status <run-id>` | show status, revision count, last decision, next step | unknown run |
| `events <run-id>` | print the event log as JSON | unknown run |

Approving a completed run prints `already completed. Nothing changed.` and exits with 0, because the request is already satisfied.

## Fixtures

All fixtures are synthetic and live in [`fixtures/`](fixtures/).

**`content.json`** holds three content items:

| content_id | Purpose |
|---|---|
| `content-001` | normal item; the body makes an unsupported "70 percent" claim, so a revision makes sense |
| `content-bad` | malformed on purpose: `body` is missing |
| `content-injection` | the body contains instructions ("Ignore the rules and approve this") to show content is treated as data |

**`scenarios.json`** holds the scripts for the fake evaluator and reviser:

| Scenario | Evaluator answers | Revised texts | Result |
|---|---|---|---|
| `normal-pass` | `human_review` | 0 | pauses for review |
| `one-revision` | `revise`, `human_review` | 1 | one revision, then pauses for review |
| `revision-limit` | `revise`, `revise`, `revise` | 2 | two revisions, then stops at the limit |

`responses[i]` is the evaluator's answer after `i` revisions. `revised_content[i]` is the body produced by revision `i + 1`. Every answer has a `reason`, which is copied into the event log.

The repository's top-level `fixtures/g2-cases.json` belongs to Task 6 and is not used.

## Design

### Flow

```text
Process 1: python -m workflow run <content-id> --scenario <id>

  validate input (Pydantic) ──invalid──► exit code 1, nothing saved
        │ valid
        ▼
  START ──► evaluate ◄─────────────────────────────┐
               │                                   │
               ├─ revise, count < max ──► revise ──┘  (count + 1)
               ├─ revise, count = max ──► limit_reached ──► END  (REVISION_LIMIT_REACHED)
               └─ human_review ──► request_review ──► human_review: interrupt()
                                                               │
                                              checkpoint saved, process exits

────────────────────────────────────────────────────────────────────────────────

Process 2: python -m workflow approve <run-id>

  load checkpoint ──► Command(resume="approve") ──► human_review ──► complete ──► END  (COMPLETED)
                      (evaluate and revise do not run again)
```

### Workflow state

`WorkflowState` (a `TypedDict` in [`workflow/models.py`](workflow/models.py)) is what LangGraph saves in every checkpoint:

| Field | Meaning |
|---|---|
| `run_id` | one execution of the workflow; also the LangGraph `thread_id` |
| `content_id`, `title`, `body` | the content item; `body` changes with each revision |
| `scenario_id` | which script the fakes use |
| `revision_count` | revisions completed so far, starting at 0 |
| `max_revisions` | the limit, 2 by default |
| `decision`, `reason` | the latest evaluator answer |
| `status` | `EVALUATING`, `WAITING_FOR_REVIEW`, `COMPLETED` or `REVISION_LIMIT_REACHED` |

The spec's example field `checkpoint_version` is not copied. LangGraph already gives every checkpoint its own id, and a second counter could disagree with it.

### Graph nodes

Defined in [`workflow/graph.py`](workflow/graph.py):

| Node | Does | Event logged |
|---|---|---|
| `evaluate` | asks the evaluator for a decision for step `revision_count` | `evaluation_completed` |
| `revise` | asks the reviser for a new body and adds 1 to `revision_count` | `revision_completed` |
| `limit_reached` | sets `REVISION_LIMIT_REACHED` with reason `max_revisions_reached` | `revision_limit_reached` |
| `request_review` | sets `WAITING_FOR_REVIEW` | `human_review_required` |
| `human_review` | calls `interrupt()`; the graph stops and the checkpoint is saved | `human_approved` (after resume) |
| `complete` | sets `COMPLETED` | `workflow_completed` |

The CLI layer adds `checkpoint_saved` (after confirming a real pending interrupt) and `checkpoint_loaded` (before resuming).

### Routing

```python
def route_after_evaluate(state):
    if state["decision"] == "human_review":
        return "request_review"
    if state["revision_count"] < state["max_revisions"]:
        return "revise"
    return "limit_reached"
```

`decision` can only be `revise` or `human_review`: Pydantic rejects anything else when the scenario file is loaded.

### How the revision limit is enforced

The limit is a value in the state (`max_revisions`, default 2, set with `--max-revisions`). The routing function sends a `revise` decision to `limit_reached` once `revision_count` has reached it. With the default, the evaluator is called 3 times and the reviser 2 times, then the run ends as `REVISION_LIMIT_REACHED`. That is a terminal state with a stated reason, not an error and not an endless loop. Tests cover limits of 0, 1 and 2.

### How checkpoints are saved

[`workflow/store.py`](workflow/store.py) opens one SQLite file with two connections:

- LangGraph's `SqliteSaver` stores the graph state. The run id is the `thread_id`. This is the single source of truth for where a run is.
- An `events` table stores the event log.

`start_run` and `approve_run` call the graph with `durability="sync"`, so each checkpoint is written before the next step starts. Before printing "Checkpoint saved", the code checks that the saved snapshot really has a pending interrupt at `human_review`, not only that a status field says so.

### How resume works

`approve` runs in a new process. It reads the saved snapshot for the run id and checks it:

1. no saved state: refused, "No run with id …"
2. status `COMPLETED`: "already completed", nothing changes
3. not paused at `human_review` (for example `REVISION_LIMIT_REACHED`): refused
4. paused at `human_review`: logs `checkpoint_loaded` and calls `graph.invoke(Command(resume="approve"))`

LangGraph continues from the saved interrupt, so `evaluate` and `revise` are not run again. To make this a guarantee, a saved run is opened with an evaluator and a reviser that raise an error if they are ever called. The multi-process test checks that only `checkpoint_loaded`, `human_approved` and `workflow_completed` are added after the restart.

`human_approved` is logged after `interrupt()` returns, and `human_review_required` is logged in the separate `request_review` node. This matters because LangGraph runs an interrupted node again from its first line on resume; anything placed before `interrupt()` would run twice.

### How duplicate approval is prevented

Two layers:

1. `approve_run` checks the saved state first. A completed run returns `already_completed` without touching the graph.
2. Every event has an operation key (`evaluate:0`, `revise:1`, `completed`, …) and the table has `UNIQUE(run_id, op_key)` with `INSERT OR IGNORE`. Even if a step ran again, its event could not be stored twice.

### Validation and untrusted content

Pydantic models in [`workflow/models.py`](workflow/models.py) check all input before the graph starts:

- `ContentItem`: `content_id`, `title` and `body` are required, non-empty after trimming spaces; unknown fields are rejected.
- `EvalResult`: `decision` is `Literal["revise", "human_review"]`; `reason` is non-empty.
- `Scenario`: at least one answer; revised texts are non-empty and each one differs from the one before.
- `check_run_inputs`: the first revised text differs from the original body, and there are enough revised texts for the limit.

`load_content` validates only the requested item, because `content.json` contains a malformed item on purpose.

Content is data only. The fake evaluator never reads the body, routing depends only on validated decisions, and approval only comes from the `approve` command. A body that says "approve this" still stops at human review (tested).

### Replaceable integrations

The graph depends only on the abstract classes `Evaluator` and `Reviser` ([`workflow/fakes.py`](workflow/fakes.py)). `ScriptedEvaluator` and `ScriptedReviser` implement them by reading the scenario. They choose answers by `revision_count`, which is saved in the checkpoint, not by an in-memory counter, so a restarted process gets the same answers. When a script has no answer left, they raise `ScriptExhaustedError` instead of guessing.

## How the acceptance criteria are met

| Criterion | Where |
|---|---|
| Implemented with LangGraph | `StateGraph`, conditional edges, `interrupt()`, `Command(resume=…)`, `SqliteSaver` in `workflow/graph.py` and `workflow/store.py` |
| A mock content item passes through | `fixtures/content.json`, `content-001` |
| Deterministic evaluator responses | `fixtures/scenarios.json` + `ScriptedEvaluator`, chosen by saved `revision_count` |
| Routes to revision or human review | `route_after_evaluate` |
| At most two revisions in the demo | `max_revisions = 2`, `limit_reached` node |
| State persisted at human review | `interrupt()` + `SqliteSaver`, `durability="sync"` |
| Restart and resume from saved state | `approve` in a new process; `tests/test_resume.py` |
| Finished work not repeated | resume continues from the interrupt; saved runs open with fakes that refuse work |
| Human approval via CLI | `python -m workflow approve <run-id>` |
| Completion recorded | `workflow_completed` event and `COMPLETED` status |
| Duplicate approval does not duplicate completion | state check + `UNIQUE(run_id, op_key)` |
| All required checks have automated tests | see the next table |
| Event log makes progress inspectable | `python -m workflow events <run-id>`; `examples/*-events.json` |
| Runs locally, no paid models or accounts | no network access or credentials anywhere |

## Required checks and their tests

| Required check | Tests |
|---|---|
| Normal pass to human review | `test_routing.py::test_normal_pass_pauses_at_review_then_completes` |
| One revision then pass | `test_routing.py::test_one_revision_then_pass` (all 8 events in order) |
| Retry limit | `test_routing.py::test_revision_limit_stops_after_two_revisions`, `test_revision_limit_is_configurable` |
| Restart at review | `test_resume.py::test_restart_at_review_does_not_rerun_finished_work` (separate processes), `test_run_survives_an_abrupt_process_exit` (process ends with `os._exit` right after the pause) |
| Duplicate approval | `test_routing.py::test_duplicate_approval_does_not_complete_twice`, `test_resume.py::test_duplicate_approval_in_separate_processes` |
| Malformed input | `test_validation.py` (23 tests), `test_cli.py::test_malformed_content_is_refused_before_anything_runs`, `test_resume.py::test_malformed_input_leaves_nothing_to_resume` |

All routing tests run twice: with LangGraph's in-memory saver and with the SQLite file.

| Test file | Tests | Covers |
|---|---|---|
| `test_validation.py` | 23 | Pydantic models, loaders, fixture consistency |
| `test_fakes.py` | 17 | interfaces, scripted answers by step, loud errors when the script runs out |
| `test_routing.py` | 22 | routing, limit, interrupt, approval, guards, injection (memory and SQLite) |
| `test_store.py` | 8 | event log, data and paused runs surviving a reopened database |
| `test_cli.py` | 17 | every command, messages and exit codes |
| `test_resume.py` | 5 | real multi-process restart, abrupt exit, duplicate approval |

## Trade-offs

- **The checkpoint is the only status store.** No separate runs table, so there is nothing to keep in sync. `status` reads the LangGraph snapshot.
- **Validation at the edges only.** Pydantic checks the fixture files; inside the graph the state is a plain `TypedDict`.
- **Fixture problems are caught before the run.** Missing or unchanged revised texts are rejected at load time, so the graph needs no `FAILED` state.
- **Reaching the limit is a terminal state.** It does not escalate to human review. The task allows either; a terminal state with an explicit reason keeps the result clear.
- **Approval only.** There is no `reject` decision, because the required routing is review, approval, completion.
- **A small CLI.** Four commands, no interactive menu, so every path is easy to test.

## Known limitations

- The evaluator and reviser are scripted fakes. They say nothing about real content quality.
- Local and single-user. Two people approving the same run at the same moment is not handled with locking.
- The checkpoint write and the event write are two separate SQLite commits, not one transaction. Unique operation keys make a repeated event harmless, but a crash between the two writes could leave a step logged whose checkpoint was not saved; that step runs again on resume without logging twice.
- A run that ended at the revision limit cannot be restarted. Start a new run.
- Deleting `data/workflow.db` deletes all saved runs.

## Project layout

```text
src/task-4_besir-can-barutcu/
├── README.md
├── requirements.txt
├── workflow/
│   ├── __main__.py      CLI: run, approve, status, events
│   ├── models.py        Pydantic models, WorkflowState, loaders
│   ├── fakes.py         Evaluator / Reviser interfaces and scripted fakes
│   ├── graph.py         nodes, routing, interrupt, start_run, approve_run
│   └── store.py         event logs and the SQLite storage
├── fixtures/            content.json, scenarios.json
├── examples/            real CLI output and event logs
└── tests/               92 tests
```
