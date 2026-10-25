# Task 4 — Resumable Review Workflow
**Atomity Evidence-to-Insight Engineering Challenge**  
**Candidate Submission:** `task-4_ranjeetkumarguptabro-maker`  
**Candidate:** Ranjeet Kumar Gupta

---

## 1. Task Selection and Objective

This submission implements **Task 4: Resumable Review Workflow** of Atomity's official Evidence-to-Insight challenge.

The objective is to build a reliable, fully testable, and inspectable workflow using **LangGraph** that:
1. Coordinates content quality evaluation and automated revisions.
2. Binds revision attempts to a configurable maximum of **two attempts** to eliminate infinite loops.
3. Pauses execution when content is ready for human review.
4. Persists the workflow state and checkpoints durably to local SQLite storage.
5. Safely **resumes across complete process restarts** without re-executing previously completed evaluation or revision work.
6. Provides an explicit CLI to inspect, resume, and approve workflows.
7. Guarantees **idempotent approval**, preventing duplicate completion actions or events.
8. Emits a structured, persistent, and inspectable audit event log.
9. Runs completely offline without external APIs, paid models, or cloud infrastructure.

---

## 2. Architecture Overview & LangGraph Topology

The orchestration graph is implemented using LangGraph's `StateGraph` compiled with an SQLite checkpointer and native interruption at the review boundary.

```text
                             ┌───────────────────────┐
                             │         START         │
                             └───────────┬───────────┘
                                         │
                                         ▼
                        ┌─────────────────────────────────┐
          ┌────────────►│          evaluate_node          │
          │             └────────────────┬────────────────┘
          │                              │
          │                     [route_after_eval]
          │                      /       |        \
          │      decision==revise        |         \ decision==human_review
          │    (revision_count < 2)      |          \
          │            /                 |           ▼
   ┌──────┴──────┐    /                  |    ┌─────────────────────────┐
   │ revise_node │◄──┘                   |    │    human_review_node    │
   └─────────────┘                       |    └────────────┬────────────┘
                                         |                 │
                       decision==revise  |        [LangGraph Interrupt]
                     (revision_count>=2) |                 │
                                         ▼                 ▼
                               ┌──────────────────┐  [CLI approve / resume]
                               │limit_reached_node│        │
                               └─────────┬────────┘        ▼
                                         │    ┌─────────────────────────┐
                                         │    │approve_and_complete_node│
                                         │    └────────────┬────────────┘
                                         │                 │
                                         ▼                 ▼
                                    ┌───────────────────────────┐
                                    │            END            │
                                    └───────────────────────────┘
```

### Graph Nodes and Responsibilities
- `evaluate`: Invokes the replaceable `Evaluator` interface against the current draft and revision count. Records `evaluation_completed` and (if revision needed) `revision_requested`.
- `revise`: Predictably modifies content body, increments `revision_count`, logs a `RevisionRecord`, and records `revision_completed`. Loops back to `evaluate`.
- `limit_reached`: Terminal node entered when evaluator requests revision but `revision_count >= max_revisions`. Sets status to `REVISION_LIMIT_REACHED` and emits `revision_limit_reached`.
- `human_review`: Prepares state for human review, increments `checkpoint_version`, records `human_review_required` and `checkpoint_saved`. Pauses execution via LangGraph compile-time interruption `interrupt_before=["approve_and_complete"]`.
- `approve_and_complete`: Resumes from checkpoint, verifies approval idempotency, records `workflow_resumed`, `human_approved`, and `workflow_completed`, then transitions to `COMPLETED`.

---

## 3. Typed State and Data Contracts

All models are built with **Pydantic V2** with strict boundary validation:

```python
class WorkflowState(BaseModel):
    run_id: str                              # Unique run identifier: "run_{content_id}"
    content_id: str                          # Identifier of content item
    content: ContentItem                     # Validated content item (id, title, body, version)
    status: WorkflowStatus                   # PENDING, EVALUATING, AWAITING_HUMAN_REVIEW, COMPLETED, etc.
    stage: WorkflowStage                     # INITIAL, EVALUATE, REVISE, HUMAN_REVIEW, COMPLETE
    revision_count: int = 0                  # Number of revisions completed (0, 1, 2)
    evaluation_count: int = 0                # Total evaluations performed (1, 2, 3)
    max_revisions: int = 2                   # Configurable revision limit
    human_review_status: HumanReviewStatus      # NOT_REQUIRED, PENDING, APPROVED, REJECTED
    evaluation_result: Optional[EvaluationResult] = None
    revision_history: List[RevisionRecord] = []
    approval_metadata: Optional[ApprovalMetadata] = None
    checkpoint_version: int = 0              # Monotonically increasing checkpoint version
    next_action: Optional[str] = None        # Actionable next step indicator
    created_at: datetime
    updated_at: datetime
    events: Annotated[List[WorkflowEvent], operator.add] = []  # LangGraph append reducer
```

### Input Validation Boundaries
- `ContentItem.id`: Rejects empty strings, whitespace, or invalid characters (`/`, `\`, control chars).
- `ContentItem.title` & `ContentItem.body`: Rejects empty or whitespace-only inputs.
- `WorkflowState`: Enforces consistency between `content_id` and `content.id`, and rejects negative revision bounds.

---

## 4. Persistence and Restart Resumption Design

- **Checkpointer:** `SqliteSaver` from `langgraph-checkpoint-sqlite` attached to `workflow_data.db`.
- **Deserialization Security:** Configured with `JsonPlusSerializer` and an explicit allowlist of domain models, eliminating deprecation warnings and ensuring deterministic serialization.
- **Process Restart Immunity:** When the workflow pauses at `human_review`:
  1. The checkpoint is committed to SQLite with thread ID `run_{content_id}`.
  2. The Python process exits.
  3. A new process invokes `engine.resume_and_approve(content_id)`.
  4. LangGraph queries the checkpointer, restores the exact channel state, and continues directly into `approve_and_complete_node`.
  5. Earlier `evaluate` and `revise` nodes are **never re-run**.

---

## 5. Approval Idempotency

Repeated invocations of `approve` or `resume` on a completed workflow are guarded at three independent layers:
1. **CLI / Engine Layer:** Checks `state.status == WorkflowStatus.COMPLETED`. If already completed, returns existing state immediately without invoking graph transitions.
2. **Graph Node Layer (`approve_and_complete_node`):** Checks if state is already completed and returns an empty dictionary `{}`.
3. **Event Database Layer (`WorkflowDatabase.save_event`):** Uses `INSERT OR IGNORE` on `event_id`.

**Result:** Exactly **one** `workflow_completed` event is ever recorded.

---

## 6. Revision Limit Enforcement

- The maximum number of revision attempts defaults to `2` (configurable).
- The workflow maintains an explicit distinction between:
  - `evaluation_count`: Number of evaluations executed.
  - `revision_count`: Number of revisions executed.
- When an evaluator repeatedly returns `revise`:
  - 1st Evaluation: returns `revise` -> Revision 1 executes (`revision_count = 1`).
  - 2nd Evaluation: returns `revise` -> Revision 2 executes (`revision_count = 2`).
  - 3rd Evaluation: returns `revise` -> Condition `revision_count < max_revisions` (2 < 2) is `False`.
  - Conditional router branches to `limit_reached` node.
  - Workflow terminates with status `REVISION_LIMIT_REACHED`.
  - Emits `revision_limit_reached` event explaining that the budget was exhausted.
  - No infinite loops.

---

## 7. Persistent Event Log

Every state transition produces a structured `WorkflowEvent` persisted both in the LangGraph state snapshot and in the SQLite `workflow_events` table:

```json
[
  {
    "event_id": "evt_9f06d7397065",
    "workflow_id": "run_demo-content-001",
    "content_id": "demo-content-001",
    "event_type": "workflow_started",
    "stage": "initial",
    "revision_count": 0,
    "decision": null,
    "explanation": "Workflow started for content 'demo-content-001'.",
    "metadata": { "title": "Overview: LLM Reasoning Reliability in Production", "max_revisions": 2 },
    "timestamp": "2026-10-22T16:04:09.456966Z"
  },
  {
    "event_id": "evt_420b50e0a358",
    "workflow_id": "run_demo-content-001",
    "content_id": "demo-content-001",
    "event_type": "evaluation_completed",
    "stage": "evaluate",
    "revision_count": 0,
    "decision": "revise",
    "explanation": "Evaluation completed with decision: revise.",
    "metadata": { "scores": { "clarity": 0.6, "evidence_grounding": 0.5 } },
    "timestamp": "2026-10-22T16:04:09.465472Z"
  },
  {
    "event_id": "evt_11597862aa7b",
    "workflow_id": "run_demo-content-001",
    "content_id": "demo-content-001",
    "event_type": "revision_completed",
    "stage": "revise",
    "revision_count": 1,
    "decision": null,
    "explanation": "Revision 1 completed successfully.",
    "metadata": { "revision_number": 1 },
    "timestamp": "2026-10-22T16:04:09.467800Z"
  },
  {
    "event_id": "evt_7f09a8bc43d1",
    "workflow_id": "run_demo-content-001",
    "content_id": "demo-content-001",
    "event_type": "human_review_required",
    "stage": "human_review",
    "revision_count": 1,
    "decision": "human_review",
    "explanation": "Content passed automated evaluation. Human review required for publication.",
    "metadata": { "revisions_performed": 1 },
    "timestamp": "2026-10-22T16:04:09.472100Z"
  },
  {
    "event_id": "evt_cp001bfa92e1",
    "workflow_id": "run_demo-content-001",
    "content_id": "demo-content-001",
    "event_type": "checkpoint_saved",
    "stage": "human_review",
    "revision_count": 1,
    "explanation": "Workflow checkpoint v1 persisted at human-review boundary.",
    "metadata": { "checkpoint_version": 1 },
    "timestamp": "2026-10-22T16:04:09.473500Z"
  },
  {
    "event_id": "evt_res002bc91d4",
    "workflow_id": "run_demo-content-001",
    "content_id": "demo-content-001",
    "event_type": "workflow_resumed",
    "stage": "approval",
    "revision_count": 1,
    "explanation": "Workflow execution resumed from persisted checkpoint.",
    "metadata": { "resumed_from_version": 1 },
    "timestamp": "2026-10-22T16:04:34.120000Z"
  },
  {
    "event_id": "evt_app003de88a9",
    "workflow_id": "run_demo-content-001",
    "content_id": "demo-content-001",
    "event_type": "human_approved",
    "stage": "approval",
    "revision_count": 1,
    "explanation": "Content approved by Jane Doe (Lead Editor).",
    "metadata": { "approved_by": "Jane Doe (Lead Editor)" },
    "timestamp": "2026-10-22T16:04:34.125000Z"
  },
  {
    "event_id": "evt_com004ef77b1",
    "workflow_id": "run_demo-content-001",
    "content_id": "demo-content-001",
    "event_type": "workflow_completed",
    "stage": "complete",
    "revision_count": 1,
    "explanation": "Workflow completed successfully.",
    "metadata": { "final_revision_count": 1 },
    "timestamp": "2026-10-22T16:04:34.130000Z"
  }
]
```

---

## 8. Installation & Setup

### Environment Requirements
- Python 3.11 or 3.12 (tested on Python 3.12.8)
- SQLite 3 (standard library)

```bash
# Navigate to submission directory
cd src/task-4_ranjeetkumarguptabro-maker

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 9. Running the Automated Tests

Execute the complete test suite:

```bash
pytest -v
```

### Actual Test Execution Results
```text
============================= test session starts ==============================
platform darwin -- Python 3.12.8, pytest-9.1.1, pluggy-1.7.0
rootdir: src/task-4_ranjeetkumarguptabro-maker
configfile: pyproject.toml
testpaths: tests
plugins: langsmith-0.14.12, anyio-4.15.1
collected 34 items

tests/test_cli.py::test_cli_normal_pass_and_approve PASSED               [  2%]
tests/test_cli.py::test_cli_revision_scenario_and_resume PASSED          [  5%]
tests/test_cli.py::test_cli_retry_limit_scenario PASSED                  [  8%]
tests/test_cli.py::test_cli_malformed_input_rejection PASSED             [ 11%]
tests/test_cli.py::test_cli_list_command PASSED                          [ 14%]
tests/test_evaluator.py::test_scripted_evaluator_sequence PASSED         [ 17%]
tests/test_evaluator.py::test_rule_based_evaluator_markers PASSED        [ 20%]
tests/test_evaluator.py::test_functional_evaluator_adapter PASSED        [ 23%]
tests/test_events.py::test_event_formatting_and_json_serialization PASSED [ 26%]
tests/test_events.py::test_format_events_table_empty PASSED              [ 29%]
tests/test_idempotency.py::test_duplicate_approval_idempotency PASSED    [ 32%]
tests/test_idempotency.py::test_duplicate_run_on_completed_workflow PASSED [ 35%]
tests/test_idempotency.py::test_approval_rejected_when_revision_limit_reached PASSED [ 38%]
tests/test_idempotency.py::test_resume_non_existent_workflow_raises_error PASSED [ 41%]
tests/test_persistence.py::test_sqlite_tables_created PASSED             [ 44%]
tests/test_persistence.py::test_save_and_retrieve_run_metadata PASSED    [ 47%]
tests/test_persistence.py::test_event_persistence_and_ordering PASSED    [ 50%]
tests/test_resume.py::test_resume_does_not_rerun_completed_nodes PASSED  [ 52%]
tests/test_resume.py::test_real_process_restart_via_cli_subprocess PASSED [ 55%]
tests/test_validation.py::test_malformed_content_item_rejections[case0] PASSED [ 58%]
tests/test_validation.py::test_malformed_content_item_rejections[case1] PASSED [ 61%]
tests/test_validation.py::test_malformed_content_item_rejections[case2] PASSED [ 64%]
tests/test_validation.py::test_malformed_content_item_rejections[case3] PASSED [ 67%]
tests/test_validation.py::test_malformed_content_item_rejections[case4] PASSED [ 70%]
tests/test_validation.py::test_malformed_content_item_rejections[case5] PASSED [ 73%]
tests/test_validation.py::test_malformed_content_item_rejections[case6] PASSED [ 76%]
tests/test_validation.py::test_workflow_engine_rejects_empty_id PASSED   [ 79%]
tests/test_validation.py::test_state_validation_rejects_id_mismatch PASSED [ 82%]
tests/test_validation.py::test_state_validation_rejects_negative_revisions PASSED [ 85%]
tests/test_validation.py::test_state_validation_rejects_negative_max_revisions PASSED [ 88%]
tests/test_workflow.py::test_normal_pass_to_human_review PASSED          [ 91%]
tests/test_workflow.py::test_one_revision_then_pass PASSED               [ 94%]
tests/test_workflow.py::test_two_revisions_then_pass PASSED              [ 97%]
tests/test_workflow.py::test_revision_limit_stops_execution PASSED       [100%]

============================== 34 passed in 1.76s ==============================
```

---

## 10. CLI Usage and Representative Scenarios

All commands can be invoked using either `python -m workflow` or `python -m workflow.cli`.

### Scenario 1: Normal Pass and Approval
```bash
# 1. Start workflow
python -m workflow run content-001

# 2. Check status
python -m workflow status content-001

# 3. Approve
python -m workflow approve content-001 --reviewer "Jane Doe"

# 4. Duplicate approval (idempotency check)
python -m workflow approve content-001
```

### Scenario 2: One Revision, Process Restart, and Resumption
```bash
# 1. Run draft requiring revision
python -m workflow run content-002 --scenario revise-once

# 2. Process exits and terminates.

# 3. Resume in a fresh process
python -m workflow resume content-002 --reviewer "Alex Chen"

# 4. Inspect audit events
python -m workflow events content-002
```

### Scenario 3: Revision Limit Enforcement
```bash
# Run content triggering persistent revision requests
python -m workflow run content-003 --scenario revise-limit

# Inspect terminal state
python -m workflow status content-003
```

---

## 11. Acceptance Criteria Checklist

| Acceptance Criterion | Status | Satisfying Code / Tests |
| :--- | :---: | :--- |
| **AC-1: LangGraph Orchestration** | **Met** | `workflow/graph.py`, `workflow/nodes.py`. Uses `StateGraph` and conditional edges. |
| **AC-2: Mock Content Processing** | **Met** | `workflow/models.py`, `fixtures/content_fixtures.py`. Passes cleanly. |
| **AC-3: Deterministic Evaluators** | **Met** | `workflow/evaluator.py`, `fixtures/evaluator_fixtures.py`. `ScriptedEvaluator` and `RuleBasedEvaluator`. |
| **AC-4: Conditional Routing** | **Met** | `route_after_evaluation` in `workflow/graph.py`. `tests/test_workflow.py`. |
| **AC-5: Revision Limit (Max 2)** | **Met** | `limit_reached_node` in `workflow/nodes.py`. `test_revision_limit_stops_execution`. |
| **AC-6: Persist at Review Boundary** | **Met** | `SqliteSaver` checkpointer in `workflow/persistence.py`. `test_sqlite_tables_created`. |
| **AC-7: Process Restart & Resume** | **Met** | `ReviewWorkflowEngine.resume_and_approve`. `test_real_process_restart_via_cli_subprocess`. |
| **AC-8: No Unnecessary Rerun** | **Met** | Checkpointed Pregel tasks. `test_resume_does_not_rerun_completed_nodes`. |
| **AC-9: CLI Human Approval** | **Met** | `workflow/cli.py` (`approve` & `resume`). `tests/test_cli.py`. |
| **AC-10: Completion Recorded** | **Met** | Exactly 1 `workflow_completed` event recorded. `test_normal_pass_to_human_review`. |
| **AC-11: Idempotent Approval** | **Met** | Multi-layer guards. `test_duplicate_approval_idempotency`. |
| **AC-12: Inspectable Event Log** | **Met** | Structured JSON & table outputs in `workflow/events.py`. `test_event_formatting_and_json_serialization`. |
| **AC-13: Input Validation** | **Met** | Strict Pydantic boundary validation. `test_malformed_content_item_rejections`. |
| **AC-14: Zero Paid APIs / Offline** | **Met** | Completely offline, local SQLite storage, zero external network dependencies. |

---

## 12. Known Limitations & Trade-Offs

1. **Local SQLite Concurrency:** SQLite is ideal for single-node CLI and embedded automation. For distributed horizontal scale across multiple worker containers, a distributed checkpointer (e.g. Postgres / Redis) would be used.
2. **Single Human Decision Type:** The challenge scope focuses on approval. An optional `reject` or `cancel` decision is supported in data models, but the default CLI path implements approval.
3. **Synthetic Evaluator:** Evaluators inspect deterministic fixture strings rather than calling live foundation models, fulfilling the prompt requirement to test orchestration reliability rather than model quality.

---

## 13. Use of AI Tools

AI assistance was used during the development of this challenge as an agentic pair programmer to:
- Draft modular boilerplate across files.
- Scaffold test matrices for edge cases.

**What was checked and verified manually:**
- **LangGraph Version Compatibility:** Verified that modern LangGraph (`>=1.2.0`) correctly uses `SqliteSaver` and `JsonPlusSerializer` without deserialization warnings.
- **Process Restart Boundary:** Verified real OS-level subprocess termination and resumption using independent process runs.
- **Node Re-execution Assertions:** Verified with `FailingEvaluator` that `evaluate` and `revise` are never invoked on resume.
- **Git Tree Isolation:** Ensured all submission files remain strictly inside `src/task-4_ranjeetkumarguptabro-maker/`.
