# Design Document — Resumable Review Workflow (Task 4)
**Evidence-to-Insight Engineering Challenge**  
**Candidate Identifier:** `task-4_ranjeetkumarguptabro-maker`

---

## 1. Architectural Overview

The Resumable Review Workflow coordinates content quality evaluation, automated revisions, human review checkpoints, and final approval for Atomity's Evidence-to-Insight system.

Its core objective is **operational reliability across time and process boundaries**:
1. When content passes automated evaluation, the workflow must safely halt at the human-review boundary.
2. The entire execution snapshot must be persisted durably to local storage (SQLite).
3. The host process can terminate, crash, or be restarted.
4. When resumed, the workflow must load its checkpoint and resume downstream execution **without rerunning completed evaluation or revision work**.
5. Final approval must be strictly **idempotent**, preventing duplicate completion actions or events.
6. Revision loops must be strictly bounded (max 2 attempts) to prevent infinite cycles.

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

---

## 2. Core Design Decisions & Engineering Trade-Offs

### 2.1 Genuine LangGraph Orchestration vs Custom State Machine
- **Requirement:** LangGraph is mandatory and must control workflow nodes, state transitions, and conditional routing.
- **Implementation:** We utilize LangGraph's `StateGraph(WorkflowState)`. Node transitions are declared explicitly via `add_conditional_edges`.
- **Interrupt Mechanism:** Instead of synthetic polling or external state tracking, we use LangGraph's native compile-time interruption (`interrupt_before=["approve_and_complete"]`). When execution reaches this point, LangGraph pauses execution, snapshots the current state values, and returns control to the caller.
- **Resumption:** Resumption is initiated by invoking the compiled graph with `graph.invoke(None, config={"configurable": {"thread_id": run_id}})`. LangGraph inspects its stored Pregel tasks, notes that `evaluate_node` and `revise_node` have already committed their checkpoints, and resumes execution strictly with `approve_and_complete_node`.

### 2.2 Dual Persistence Strategy: LangGraph Checkpoints + Relational Metadata
We implemented a clean two-tier persistence model in SQLite (`workflow_data.db`):
1. **LangGraph Checkpoint Storage (`SqliteSaver`):**
   - Stores raw graph state snapshots, channel values, write logs, and thread checkpoints.
   - Configured with `JsonPlusSerializer` and explicit allowlist of models to ensure secure, warning-free serialization and deserialization.
2. **Relational Metadata & Audit Events (`workflow_runs` & `workflow_events`):**
   - `workflow_runs`: High-level indexed table (`run_id`, `content_id`, `status`, `stage`, `revision_count`, `checkpoint_version`) allowing rapid queryability for `status` and `list` commands without deserializing graph blobs.
   - `workflow_events`: Append-only, indexed audit log capturing every fine-grained transition (`workflow_started`, `evaluation_completed`, `revision_requested`, `revision_completed`, `human_review_required`, `checkpoint_saved`, `workflow_resumed`, `human_approved`, `workflow_completed`, `revision_limit_reached`).
   - Idempotency is enforced using `INSERT OR IGNORE` on `event_id` and semantic state checks.

### 2.3 Strict Separation Between Revision Attempts and Evaluation Attempts
- **Revision Count:** Number of content modifications completed (starts at 0, max 2).
- **Evaluation Count:** Number of evaluation passes executed.
- When an initial draft fails evaluation:
  - Evaluation 1 runs -> decision `revise` -> revision 1 is requested -> revision 1 completes (`revision_count = 1`).
  - Evaluation 2 runs -> decision `revise` -> revision 2 is requested -> revision 2 completes (`revision_count = 2`).
  - Evaluation 3 runs -> decision `revise` -> revision budget (2) is exhausted (`revision_count < max_revisions` evaluates to `False`).
  - The routing function directs the execution to `limit_reached_node`.
  - The workflow transitions to the documented terminal status `WorkflowStatus.REVISION_LIMIT_REACHED` and emits a `revision_limit_reached` event explaining the outcome.
  - Zero possibility of an infinite loop.

### 2.4 Multi-Layered Approval Idempotency
To prevent duplicate completion events or redundant downstream work if `approve` or `resume` is executed multiple times:
1. **Application Boundary Layer (`ReviewWorkflowEngine` & CLI):**
   Checks `current_state.status`. If already `COMPLETED`, returns the existing state immediately and prints a clean notice.
2. **Graph Node Layer (`approve_and_complete_node`):**
   If invoked with a state that is already `COMPLETED`, the node returns an empty dictionary `{}` without emitting duplicate events.
3. **Database Layer (`WorkflowDatabase.save_event`):**
   Uses `INSERT OR IGNORE` on `event_id` and unique indexes.

### 2.5 Replaceable Evaluator Interface & Offline Determinism
- The `Evaluator` abstract base class decouples workflow logic from LLM calls or model APIs.
- Three implementations are provided:
  - `ScriptedEvaluator`: Returns a predetermined sequence of decisions, enabling automated unit and regression tests.
  - `RuleBasedEvaluator`: Inspects deterministic markers in text (`[NEEDS_REVISION]`, `[FAIL_LIMIT]`, `[REJECT]`), enabling realistic CLI demonstrations.
  - `FunctionalEvaluator`: Allows arbitrary Python callables to act as evaluators.
- **Zero Paid APIs / Zero Network Calls:** The entire system runs 100% locally and deterministically.

---

## 3. Data Contracts and State Lifecycle

### 3.1 `WorkflowState`
```python
class WorkflowState(BaseModel):
    run_id: str                          # Stable thread ID: "run_{content_id}"
    content_id: str                      # Identifier of content item
    content: ContentItem                 # Validated content object
    status: WorkflowStatus               # PENDING, AWAITING_HUMAN_REVIEW, COMPLETED, etc.
    stage: WorkflowStage                 # INITIAL, EVALUATE, REVISE, HUMAN_REVIEW, COMPLETE
    revision_count: int = 0              # Revisions completed (0, 1, 2)
    evaluation_count: int = 0            # Total evaluations run (1, 2, 3)
    max_revisions: int = 2               # Configurable revision budget
    human_review_status: HumanReviewStatus  # NOT_REQUIRED, PENDING, APPROVED, REJECTED
    evaluation_result: Optional[EvaluationResult] = None
    revision_history: List[RevisionRecord] = []
    approval_metadata: Optional[ApprovalMetadata] = None
    checkpoint_version: int = 0          # Monotonically increasing checkpoint version
    next_action: Optional[str] = None    # Actionable prompt for next step
    created_at: datetime
    updated_at: datetime
    events: Annotated[List[WorkflowEvent], operator.add] = []  # LangGraph append reducer
```

### 3.2 State Transition Matrix

| Current Status | Event / Trigger | Next Status | Next Stage | Action Taken |
| :--- | :--- | :--- | :--- | :--- |
| `PENDING` | `run()` | `EVALUATING` | `EVALUATE` | Evaluates draft |
| `EVALUATING` | decision: `revise` & rev < 2 | `REVISING` | `REVISE` | Applies revision; increments rev count |
| `REVISING` | Revision done | `EVALUATING` | `EVALUATE` | Loops back to evaluate |
| `EVALUATING` | decision: `revise` & rev >= 2 | `REVISION_LIMIT_REACHED` | `REVISION_LIMIT_REACHED` | Terminal halt; records limit event |
| `EVALUATING` | decision: `human_review` | `AWAITING_HUMAN_REVIEW` | `HUMAN_REVIEW` | Checkpoint saved; pauses execution |
| `AWAITING_HUMAN_REVIEW` | `approve()` / `resume()` | `COMPLETED` | `COMPLETE` | Approves; records completion |
| `COMPLETED` | `approve()` (duplicate) | `COMPLETED` | `COMPLETE` | No-op; idempotent return |

---

## 4. Security & Robustness Considerations

1. **Content Treated as Data, Never Code:**
   - Content titles and bodies are plain strings. No `eval()`, `exec()`, or template injection functions are used.
   - Text revisions use safe string formatting and immutable Pydantic copy operations (`model_copy`).
2. **Boundary Input Validation:**
   - Empty IDs, invalid characters (`/`, `\`, control chars), whitespace-only strings, and negative revision budgets are rejected at the Pydantic model boundary before any workflow node or database transaction begins.
3. **No Credential Exposure:**
   - No API keys, credentials, or remote endpoints are required or referenced.
4. **Crash Recovery & Concurrency:**
   - SQLite WAL (Write-Ahead Logging) mode is enabled (`PRAGMA journal_mode = WAL;`) for concurrent read access and ACID resilience against sudden process termination.
