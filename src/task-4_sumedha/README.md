# Task 4: Resumable Review Workflow

## Overview

This submission implements a resumable content review workflow using Python, LangGraph, Pydantic, and SQLite. It evaluates mock content, performs bounded revisions, pauses for human review, and resumes from a durable checkpoint without repeating completed work.

The implementation is local and deterministic. It requires no external services, credentials, or paid model access.

## Requirements

- Python 3.12
- `langgraph==1.2.16`
- `langgraph-checkpoint-sqlite==3.1.2`
- `pydantic==2.14.1`
- `pytest==9.1.1`

## Setup

From this directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Project Structure

```text
.
├── models.py                         # Validated content and typed workflow state
├── evaluator.py                      # Deterministic, index-based fake evaluator
├── workflow.py                       # LangGraph nodes, routing, interrupts, and completion
├── persistence.py                    # SQLite connection and SqliteSaver lifecycle
├── cli.py                            # Local run, resume, and status commands
├── requirements.txt                  # Pinned Python dependencies
├── fixtures/
│   └── workflow_scenarios.json       # Mock content and evaluator decision sequences
├── examples/
│   └── demo.py                       # Cross-process checkpoint and resume demonstration
└── tests/
    └── test_workflow.py              # Workflow, persistence, validation, and CLI tests
```

Local checkpoint databases and their SQLite sidecar files are excluded through `.gitignore`.

## Workflow Design

The workflow is built with LangGraph `StateGraph` and follows these stages:

1. **Evaluate**: The fake evaluator selects a deterministic decision for the current evaluation index.
2. **Revise**: A revision marker is added to the mock content and the revision count is incremented. Execution then returns to evaluation.
3. **Human review**: A preparation node records the review status, then LangGraph `interrupt()` pauses execution for an approval decision.
4. **Complete**: Approval routes to a separate idempotent completion node that records one completion event.

An evaluation decision of `human_review` routes to the review boundary. A `revise` decision routes to revision unless the configured limit has been reached. The default maximum is two completed revision attempts. A further revision request produces the terminal `retry_limit_reached` status.

Declining a review records the outcome and pauses again. Approving it routes to completion. Completed and retry-limited workflows are not silently restarted.

## Checkpointing and Recovery

`persistence.py` manages a standard SQLite connection and LangGraph `SqliteSaver` through a context manager. The connection remains open while the graph is inspected or invoked and is closed afterward.

Each run receives a UUID thread ID. LangGraph stores checkpoints under that ID, including the content, status, evaluation result, revision count, event history, and pending human-review interrupt. Resume operations reopen the same database and use the same thread ID as the lookup key.

Approval resumes the saved interrupt with `Command(resume=True)`. No replacement initial state is supplied. LangGraph continues from the saved review node, so completed evaluation and revision nodes are not run again. `Command(resume=False)` records a decline and returns to the review pause.

The checkpoint serializer explicitly allowlists the Pydantic `ContentInput` type and does not enable pickle fallback.

## Running the CLI

Commands should be run from this directory. The default database is `workflow_checkpoints.sqlite3`.

Start a workflow:

```bash
python cli.py run content-001 --scenario revise-once
```

The command prints the event history and a thread ID. Use that ID for later commands:

```bash
python cli.py status <thread-id>
python cli.py resume <thread-id> --approve
python cli.py resume <thread-id> --decline
```

The global `--database` option can select another checkpoint file and must appear before the command:

```bash
python cli.py --database local-demo.sqlite3 status <thread-id>
```

Available deterministic scenarios are:

- `pass`: immediately requests human review.
- `revise-once`: requests one revision, then human review.
- `retry-limit`: repeatedly requests revision until the two-attempt limit is reached.

Only one active workflow may exist for the fixture content at a time. A completed or retry-limited run remains available as history but does not prevent a new run.

## Running the Demonstration

```bash
python examples/demo.py
```

The demonstration uses a temporary SQLite database. It starts the `revise-once` scenario in one subprocess, resumes approval in another subprocess, reads the final status, and submits a duplicate approval. It verifies the exact event order, confirms that evaluation and revision are not repeated, and checks that completion is recorded once.

The script exits with a nonzero status if an important check fails.

## Testing

```bash
python -m pytest -v
```

The suite covers immediate review, one revision with exact event ordering, the two-revision limit, clean cross-process recovery, duplicate approval, malformed input, invalid evaluator decisions, unknown thread IDs, read-only status inspection, decline followed by approval, duplicate active starts, and fixture validation.

Latest manually verified result:

```text
16 passed, 0 failed
```

Tests use isolated temporary databases and do not depend on the default local checkpoint database.

## Design Decisions and Trade-offs

- **Deterministic evaluator**: Ordered fixture responses make routing and recovery behavior repeatable and testable. This exercises orchestration rather than model quality.
- **State-derived evaluation index**: The evaluator selects a response using the persisted revision count instead of an in-memory cursor. Recreating the evaluator in another process therefore does not lose its position.
- **SQLite checkpoints**: SQLite provides durable local state with little setup and integrates directly with LangGraph's official `SqliteSaver`.
- **Command-line review**: An `argparse` interface keeps the human-review boundary observable without adding a web application.
- **Simple revisions**: Revision updates are deliberately mock transformations. The focus is routing, retry bounds, persistence, and idempotency.

## Known Limitations

- This is a local, single-user demonstration rather than a deployed service.
- The evaluator and revision logic are deterministic fakes; no production LLM or content-generation system is included.
- The fixture contains one content item and three predefined evaluation scenarios.
- Human review is a Boolean approve-or-decline decision through the CLI. There is no authentication, authorization, or reviewer interface.
- Concurrent reviewers, multiple worker processes, database contention, and distributed execution have not been designed or load-tested.
- Recovery has been verified across clean process boundaries at the human-review checkpoint. Abrupt termination during a node or SQLite write has not been fault-injection tested.

## AI Assistance

AI coding assistance was used to support implementation, debugging and documentation. The changes were reviewed, and the workflow was verified through manual demonstrations and automated tests.
