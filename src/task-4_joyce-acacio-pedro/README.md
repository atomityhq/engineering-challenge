
# Task 4 — Resumable Review Workflow

**Author:** Joyce Acácio Pedro

## Overview

This project implements a resumable content review workflow using Python and LangGraph.

The workflow evaluates content and determines whether it should be approved, revised, or submitted for human review.

It supports persistent checkpoints, workflow resumption, revision limits, and event logging.

## Features

- Deterministic content evaluation without external AI APIs.
- Automatic content revision.
- Maximum of two revision attempts.
- Human approval through a command-line interface.
- Persistent workflow checkpoints using SQLite.
- Workflow resumption after interruption or application restart.
- Event logging for important workflow transitions.
- Protection against duplicate approval and completion.
- Input validation using Pydantic.
- Automated tests using Pytest.

## Project Structure

```text
task-4_joyce-acacio-pedro/
├── examples/
│   └── human_review.json
├── fixtures/
├── tests/
│   ├── test_models.py
│   ├── test_graph.py
│   └── test_event_logger.py
├── workflow/
│   ├── __init__.py
│   ├── models.py
│   ├── graph.py
│   ├── nodes.py
│   └── event_logger.py
├── main.py
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.12 or later
- pip

## Installation

From the repository root, activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the project dependencies:

```powershell
pip install -r src/task-4_joyce-acacio-pedro/requirements.txt
```

Set the Python module path:

```powershell
$env:PYTHONPATH = "src/task-4_joyce-acacio-pedro"
```

## Running the Workflow

Start a workflow using a JSON input file:

```powershell
python src/task-4_joyce-acacio-pedro/main.py start --input src/task-4_joyce-acacio-pedro/examples/human_review.json
```

The workflow evaluates the content and determines the next action.


## Deterministic Evaluation Markers

The evaluator uses predefined markers to simulate different review decisions:

- `[REVISE]`: requests a content revision.
- `[ALWAYS_REVISE]`: continuously requests revisions to test the revision limit.
- `[HUMAN_REVIEW]`: pauses the workflow and requests human approval.

These markers make workflow behavior predictable and reproducible during testing.


## Human Approval

When content requires human review, the workflow pauses and saves its checkpoint.

Approve the workflow using:

```powershell
python src/task-4_joyce-acacio-pedro/main.py approve --workflow-id workflow-demo-002
```

The workflow resumes from its saved checkpoint instead of repeating completed steps.

## Checking Workflow Status

To inspect a workflow:

```powershell
python src/task-4_joyce-acacio-pedro/main.py status --workflow-id workflow-demo-002
```

## Running Tests

From the repository root:

```powershell
python -m pytest src/task-4_joyce-acacio-pedro/tests/ -v
```

## Persistence

The application uses two SQLite databases:

- `workflow_checkpoints.sqlite`: stores LangGraph workflow checkpoints.
- `workflow_events.sqlite`: stores workflow event history.

These databases are created locally during execution.

## Event Logging

The workflow records important events, including:

- `evaluation_completed`
- `revision_requested`
- `human_review_required`
- `checkpoint_saved`
- `human_approved`
- `workflow_completed`

Event keys help prevent duplicate event records.

## Design Notes

LangGraph manages the workflow states, transitions, and checkpoint-based resumption.

Pydantic validates workflow input and evaluation data.

The evaluator and revision logic are deterministic and use predefined content markers, making the workflow reproducible and suitable for local testing.

SQLite provides local persistence without requiring external services.

## Known Limitations

- The evaluator is rule-based and intended for demonstration and testing.
- The revision function performs a deterministic text transformation rather than using a language model.
- Human approval is performed through the command-line interface.
- The application is designed for local execution and does not include a web interface.

