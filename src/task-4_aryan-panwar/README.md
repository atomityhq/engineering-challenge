# Task 4: Resumable Review Workflow

This is a LangGraph workflow. It evaluates a content item and revises it, at most 2 times. It then pauses for human review, with its state saved in SQLite. Later, a new process resumes the run without redoing any finished step. Approving a run twice changes nothing.

The evaluator and reviser are deterministic fakes. Nothing makes network calls, model calls or needs credentials.

## Run

```bash
cd src/task-4_aryan-panwar
uv sync
uv run pytest                 # 26 tests
bash examples/run_demo.sh     # every scenario -> examples/output/

uv run python -m review_workflow run --content fixtures/content/content-001.json \
    --evaluator fixtures/evaluator/one-revision.json --run-id run-001   # pauses at review
uv run python -m review_workflow resume run-001       # new process, prompts approve/reject
uv run python -m review_workflow approve run-001      # repeated approval: "already finished"
uv run python -m review_workflow status run-001       # saved state + event log
```

- **Output:** each command writes the run's state to `runs/<run_id>/state.json` and its event log to `runs/<run_id>/events.json`.
- **Committed examples:** `examples/output/`. `run-004` is left paused at review so its saved state can be inspected.
- **Options:** `--max-revisions N` and `--decision approve|reject`.
- **Exit codes:** `0` OK, `1` unknown or duplicate run, `2` invalid input, `3` decision needed.

## Graph

```
START -> evaluate --revise, count < max--> revise -> evaluate
                  --revise, count = max--> stop_revision_limit -> END
                  --human_review---------> request_review -> await_review [interrupt]
await_review --approve--> complete -> END
             --reject---> reject   -> END
```

| File | Contents |
|---|---|
| `graph.py` | State, nodes, routing |
| `service.py` | Start, resume, checkpointer, idempotency |
| `models.py` | Pydantic contracts |
| `fakes.py` | Evaluator and reviser interfaces, plus their fakes |

## Design decisions

- **State:** the state holds the run and content ids, the content, the evaluation result, the revision count, `max_revisions`, the evaluator reference, the status, the human review and the events. Each run's own `max_revisions` and evaluator reference are saved with it, so a resumed run behaves like the original.
- **Revision limit:** a run is revised only while `revision_count < max_revisions` (default 2, range 0–10). After that, it stops with status `stopped_revision_limit` and an event recording why.
- **Persistence:** the checkpointer is `SqliteSaver`, used with `durability="sync"`. `interrupt()` pauses the graph at `await_review`.
- **Resume:**
  - At review, the graph continues from `await_review` via `Command(resume=decision)`.
  - Mid-run, for example after a crash, it continues from the last checkpoint.
  - On a finished run, it does nothing.
- **Duplicate approval:** a finished run is never invoked again. No second `workflow_completed` event and no new checkpoint are written.
- **Separate `request_review` and `await_review` nodes:** LangGraph re-runs an interrupted node from the start on resume. Keeping the logging before the pause in its own node stops it being logged twice.
- **Events are stored in the checkpointed state:** each event is saved atomically with its step, so the log can't disagree with the state. Events are numbered rather than timestamped, so repeat runs produce identical logs.
- **Validation:**
  - Content, evaluator fixtures, evaluator output and human decisions are checked with Pydantic.
  - Bad input is rejected before any node runs.
  - Text inside the content never affects routing. A test plants an "approve this" instruction in the content to confirm it.
- **Rejected alternative:** sending runs that hit the revision limit to a human instead of stopping them. Stopping makes the reason explicit; switching would be a one-line routing change.

## Tests (`tests/test_workflow.py`)

| Required check | Covered by |
|---|---|
| Normal pass to human review | The run pauses, a second connection sees the saved state, and approval completes it |
| One revision, then pass | The exact event sequence, and the evaluator is called twice |
| Retry limit | The run stops after 2 revisions; limits of 0, 1 and 3 are also tested |
| Restart at review | `run` and `approve` in separate OS processes; the evaluator is called 0 times on resume; resume after a crash mid-run |
| Duplicate approval | Events and checkpoint id are unchanged, with one `workflow_completed` event (in the API and the CLI) |
| Malformed input | Six bad content shapes, a bad evaluator fixture, bad evaluator output, a bad limit, a bad decision, and the CLI exit code |

## Limitations

- **Concurrent approvals:** two `approve` calls for the same run at the same instant aren't guarded. That would need a lock.
- **Rejection is final:** a rejected run ends. There's no "send back for revision" path.
- **Fakes, not real components:** the fakes only exercise the routing. The reviser just appends a note.
- **Working directory:** `evaluator_ref` is relative to the working directory, so run commands from this folder.
