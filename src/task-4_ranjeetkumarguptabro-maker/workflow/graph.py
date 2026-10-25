"""LangGraph graph topology, conditional routing, and execution engine for Task 4.

Wires nodes, conditional edges, checkpointers, and interruption boundaries into
a compiled, resumable StateGraph.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from workflow.evaluator import Evaluator, RuleBasedEvaluator
from workflow.events import create_event
from workflow.models import (
    ApprovalMetadata,
    ContentItem,
    EvaluatorDecision,
    EventType,
    WorkflowEvent,
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
)
from workflow.nodes import (
    approve_and_complete_node,
    evaluate_node,
    human_review_node,
    limit_reached_node,
    revise_node,
)
from workflow.persistence import WorkflowDatabase


def route_after_evaluation(state: WorkflowState) -> str:
    """Conditional routing function determining the branch after evaluation.
    
    Routing rules:
    - If decision is REVISE and revision budget remains (revision_count < max_revisions):
        route to 'revise'
    - If decision is REVISE and revision budget is exhausted (revision_count >= max_revisions):
        route to 'limit_reached' (terminal bounded state)
    - If decision is HUMAN_REVIEW:
        route to 'human_review' (pause boundary)
    """
    decision = state.evaluation_result.decision if state.evaluation_result else EvaluatorDecision.HUMAN_REVIEW

    if decision == EvaluatorDecision.REVISE:
        if state.revision_count < state.max_revisions:
            return "revise"
        return "limit_reached"

    return "human_review"


def build_workflow_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> CompiledStateGraph:
    """Construct and compile the LangGraph StateGraph.
    
    Configures nodes, conditional branches, and interrupts before the approval node
    so that state is persisted and execution pauses at the human-review boundary.
    """
    builder = StateGraph(WorkflowState)

    # Register nodes
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("revise", revise_node)
    builder.add_node("limit_reached", limit_reached_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("approve_and_complete", approve_and_complete_node)

    # Wire edges
    builder.add_edge(START, "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        route_after_evaluation,
        {
            "revise": "revise",
            "limit_reached": "limit_reached",
            "human_review": "human_review",
        },
    )
    builder.add_edge("revise", "evaluate")
    builder.add_edge("limit_reached", END)
    builder.add_edge("human_review", "approve_and_complete")
    builder.add_edge("approve_and_complete", END)

    # Compile with human review interrupt boundary and checkpointer
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["approve_and_complete"],
    )


class ReviewWorkflowEngine:
    """High-level orchestration manager for running, checkpointing, and resuming workflows."""

    def __init__(
        self,
        db: Optional[WorkflowDatabase] = None,
        evaluator: Optional[Evaluator] = None,
    ) -> None:
        self.db = db or WorkflowDatabase()
        self.checkpointer = self.db.get_checkpointer()
        self.evaluator = evaluator or RuleBasedEvaluator()
        self.graph = build_workflow_graph(checkpointer=self.checkpointer)

    def run(
        self,
        content: ContentItem,
        max_revisions: int = 2,
        evaluator: Optional[Evaluator] = None,
    ) -> WorkflowState:
        """Start or execute a workflow from the beginning until paused or completed."""
        active_evaluator = evaluator or self.evaluator
        run_id = f"run_{content.id}"
        config = {
            "configurable": {
                "thread_id": run_id,
                "evaluator": active_evaluator,
                "db": self.db,
            }
        }

        # Check if already completed to ensure idempotency
        existing_run = self.db.get_run_by_content_id(content.id)
        if existing_run and existing_run["status"] == WorkflowStatus.COMPLETED.value:
            latest = self.get_state(content.id)
            if latest:
                return latest

        # Create initial state and record workflow_started event
        start_evt = create_event(
            workflow_id=run_id,
            content_id=content.id,
            event_type=EventType.WORKFLOW_STARTED,
            stage=WorkflowStage.INITIAL,
            revision_count=0,
            explanation=f"Workflow started for content '{content.id}'.",
            metadata={"title": content.title, "max_revisions": max_revisions},
            db=self.db,
        )

        initial_state = WorkflowState(
            run_id=run_id,
            content_id=content.id,
            content=content,
            status=WorkflowStatus.PENDING,
            stage=WorkflowStage.INITIAL,
            max_revisions=max_revisions,
            events=[start_evt],
        )

        # Execute graph (runs through evaluate / revise until interrupt or end)
        self.graph.invoke(initial_state.model_dump(), config=config)

        # Retrieve current snapshot from checkpointer
        current = self.get_state(content.id)
        if current is None:
            raise RuntimeError(f"Failed to retrieve checkpoint state for run '{run_id}'.")

        self.db.save_run(current)
        return current

    def resume_and_approve(
        self,
        content_id: str,
        approval_metadata: Optional[ApprovalMetadata] = None,
        evaluator: Optional[Evaluator] = None,
    ) -> WorkflowState:
        """Resume a paused workflow from the human-review checkpoint and approve it.
        
        Safely idempotent: if already completed, returns existing state without
        emitting duplicate completion events or repeating downstream steps.
        """
        run_id = f"run_{content_id}"
        active_evaluator = evaluator or self.evaluator
        approval = approval_metadata or ApprovalMetadata(approved_by="human_reviewer")

        config = {
            "configurable": {
                "thread_id": run_id,
                "evaluator": active_evaluator,
                "db": self.db,
                "approval_metadata": approval,
            }
        }

        current = self.get_state(content_id)
        if current is None:
            raise ValueError(f"No checkpoint found for content ID '{content_id}'. Cannot resume.")

        # Idempotency check: if already completed, return immediately
        if current.status == WorkflowStatus.COMPLETED:
            return current

        # Check eligibility
        if current.status != WorkflowStatus.AWAITING_HUMAN_REVIEW and current.stage != WorkflowStage.HUMAN_REVIEW:
            if current.status == WorkflowStatus.REVISION_LIMIT_REACHED:
                raise ValueError(
                    f"Workflow for content '{content_id}' reached revision limit and cannot be approved."
                )
            raise ValueError(
                f"Workflow for content '{content_id}' is not in review (current status: {current.status.value})."
            )

        # Resume execution through approve_and_complete to END
        self.graph.invoke(None, config=config)

        # Retrieve final state
        updated = self.get_state(content_id)
        if updated is None:
            raise RuntimeError(f"Failed to load state after resuming run '{run_id}'.")

        self.db.save_run(updated)
        return updated

    def get_state(self, content_id: str) -> Optional[WorkflowState]:
        """Load the current workflow snapshot from the LangGraph checkpointer."""
        run_id = f"run_{content_id}"
        config = {"configurable": {"thread_id": run_id}}
        snapshot = self.graph.get_state(config)
        if not snapshot or not snapshot.values:
            return None

        # Reconstruct WorkflowState from values dict
        try:
            return WorkflowState.model_validate(snapshot.values)
        except Exception:
            return None

    def get_events(self, content_id: str) -> list[WorkflowEvent]:
        """Fetch chronological audit events from SQLite storage."""
        return self.db.get_events_for_content(content_id)
