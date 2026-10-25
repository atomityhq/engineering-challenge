"""Command-line interface for running, inspecting, resuming, and approving workflows.

Supports all required operations from the Task 4 specification:
- run: starts a workflow with mock or fixture content
- status: inspects current state, stage, revisions, and checkpoint
- resume: resumes a paused workflow from checkpoint to completion
- approve: approves a paused workflow (safely idempotent)
- events: displays the full audit event log in table or JSON format
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from workflow.evaluator import Evaluator, RuleBasedEvaluator, ScriptedEvaluator
from workflow.events import format_events_json, format_events_table
from workflow.graph import ReviewWorkflowEngine
from workflow.models import (
    ApprovalMetadata,
    ContentItem,
    EvaluatorDecision,
    WorkflowStage,
    WorkflowStatus,
)
from workflow.persistence import WorkflowDatabase

app = typer.Typer(
    name="workflow",
    help="Atomity Task 4 — Resumable Review Workflow CLI",
    add_completion=False,
)
console = Console()


def _get_engine(db_path: Optional[str], evaluator: Optional[Evaluator] = None) -> ReviewWorkflowEngine:
    path = db_path or os.environ.get("WORKFLOW_DB_PATH", "workflow_data.db")
    db = WorkflowDatabase(path)
    return ReviewWorkflowEngine(db=db, evaluator=evaluator)


def _load_mock_content(content_id: str, scenario: Optional[str] = None, title: Optional[str] = None, body: Optional[str] = None) -> ContentItem:
    """Construct mock content based on scenario or input parameters."""
    if title and body:
        return ContentItem(id=content_id, title=title, body=body)

    # Scenarios for deterministic demonstration
    if scenario == "revise-limit" or "limit" in content_id.lower():
        return ContentItem(
            id=content_id,
            title="Analysis: Emerging Enterprise Multi-Agent Standards",
            body="Initial draft analyzing multi-agent frameworks. [FAIL_LIMIT] Missing rigorous benchmark citations and vendor comparisons.",
        )
    elif scenario == "revise-once" or "rev" in content_id.lower():
        return ContentItem(
            id=content_id,
            title="Overview: LLM Reasoning Reliability in Production",
            body="Survey of agent reliability. [NEEDS_REVISION] Requires empirical grounding on latency and error budgets.",
        )
    else:
        # Default normal pass scenario
        return ContentItem(
            id=content_id,
            title="Report: Evidence Grounding and Content Validation",
            body="High-confidence evidence synthesis conforming to Atomity G2 publication standards.",
        )


@app.command("run")
def run_command(
    content_id: str = typer.Argument(..., help="Content identifier to process (e.g. 'content-001')."),
    scenario: Optional[str] = typer.Option(
        None,
        "--scenario",
        "-s",
        help="Deterministic test scenario: 'pass', 'revise-once', or 'revise-limit'.",
    ),
    max_revisions: int = typer.Option(2, "--max-revisions", "-m", help="Maximum permitted revision attempts."),
    title: Optional[str] = typer.Option(None, "--title", help="Custom content title."),
    body: Optional[str] = typer.Option(None, "--body", help="Custom content body."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to SQLite database."),
) -> None:
    """Start or run a workflow for a content item until pause or completion."""
    try:
        content = _load_mock_content(content_id=content_id, scenario=scenario, title=title, body=body)
    except Exception as e:
        console.print(f"[bold red]Input validation error:[/bold red] {e}")
        raise typer.Exit(code=1)

    evaluator = RuleBasedEvaluator()
    engine = _get_engine(db, evaluator=evaluator)

    console.print(f"\n[bold]Starting workflow for content:[/bold] {content.id}")
    console.print(f"[dim]Title: {content.title}[/dim]\n")

    state = engine.run(content, max_revisions=max_revisions)

    # Print sequential progression matching task specification expectations
    events = engine.get_events(content.id)
    printed_revisions = set()
    for evt in events:
        if evt.event_type.value == "evaluation_completed":
            console.print("Evaluation completed")
            if evt.decision:
                console.print(f"Decision: [bold cyan]{evt.decision}[/bold cyan]\n")
        elif evt.event_type.value == "revision_requested":
            rev_num = evt.revision_count
            if rev_num not in printed_revisions:
                console.print(f"Revision attempt: [bold yellow]{rev_num}[/bold yellow]\n")
                printed_revisions.add(rev_num)
        elif evt.event_type.value == "human_review_required":
            console.print("[bold yellow]Human review required[/bold yellow]")
        elif evt.event_type.value == "checkpoint_saved":
            console.print("[bold green]Checkpoint saved[/bold green]\n")
        elif evt.event_type.value == "revision_limit_reached":
            console.print("[bold red]Maximum revision attempts reached.[/bold red]")
            console.print("[bold red]Workflow stopped.[/bold red]\n")

    if state.status == WorkflowStatus.AWAITING_HUMAN_REVIEW:
        console.print("[bold blue]Workflow paused.[/bold blue]")
        console.print("[dim]Use 'resume' or 'approve' to continue after review.[/dim]\n")
    elif state.status == WorkflowStatus.COMPLETED:
        console.print("[bold green]Workflow completed.[/bold green]\n")
    elif state.status == WorkflowStatus.REVISION_LIMIT_REACHED:
        console.print(f"[dim]Terminal state: {state.status.value}[/dim]\n")


@app.command("status")
def status_command(
    content_id: str = typer.Argument(..., help="Content identifier to inspect."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to SQLite database."),
) -> None:
    """Inspect current workflow status, stage, revision count, and checkpoint version."""
    engine = _get_engine(db)
    state = engine.get_state(content_id)

    if not state:
        console.print(f"[bold red]Error:[/bold red] No workflow state found for content ID '{content_id}'.")
        raise typer.Exit(code=1)

    table = Table(title=f"Workflow Status — {content_id}", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="bold")
    table.add_column("Value")

    table.add_row("Run ID", state.run_id)
    table.add_row("Content ID", state.content_id)
    table.add_row("Status", f"[bold]{state.status.value}[/bold]")
    table.add_row("Stage", state.stage.value)
    table.add_row("Revisions Completed", str(state.revision_count))
    table.add_row("Max Revisions Allowed", str(state.max_revisions))
    table.add_row("Evaluations Performed", str(state.evaluation_count))
    table.add_row("Checkpoint Version", f"v{state.checkpoint_version}")
    table.add_row("Human Review Status", state.human_review_status.value)
    if state.approval_metadata:
        table.add_row("Approved By", state.approval_metadata.approved_by)
    table.add_row("Last Updated", state.updated_at.isoformat())

    console.print(table)


@app.command("resume")
def resume_command(
    content_id: str = typer.Argument(..., help="Content identifier of paused workflow."),
    reviewer: str = typer.Option("human_reviewer", "--reviewer", "-r", help="Name of the human reviewer."),
    comment: Optional[str] = typer.Option(None, "--comment", "-c", help="Optional review comment."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to SQLite database."),
) -> None:
    """Resume a paused workflow from its checkpoint and perform approval."""
    engine = _get_engine(db)
    current = engine.get_state(content_id)

    if not current:
        console.print(f"[bold red]Error:[/bold red] No saved checkpoint found for content '{content_id}'.")
        raise typer.Exit(code=1)

    console.print(f"\nLoaded checkpoint (v{current.checkpoint_version})")
    console.print(f"Current stage: [bold yellow]{current.stage.value}[/bold yellow]\n")

    if current.status == WorkflowStatus.COMPLETED:
        console.print("[dim]Workflow was already approved and completed. Idempotent call — no action taken.[/dim]\n")
        console.print("[bold green]Workflow completed.[/bold green]\n")
        return

    if current.status != WorkflowStatus.AWAITING_HUMAN_REVIEW:
        console.print(f"[bold red]Error:[/bold red] Cannot resume workflow with status '{current.status.value}'.")
        raise typer.Exit(code=1)

    console.print("Approval required.")
    approval = ApprovalMetadata(approved_by=reviewer, comment=comment)
    console.print(f"Approved by [bold cyan]{reviewer}[/bold cyan].\n")

    final_state = engine.resume_and_approve(content_id, approval_metadata=approval)

    if final_state.status == WorkflowStatus.COMPLETED:
        console.print("[bold green]Workflow completed.[/bold green]\n")
    else:
        console.print(f"[bold yellow]Workflow reached stage: {final_state.stage.value}[/bold yellow]\n")


@app.command("approve")
def approve_command(
    content_id: str = typer.Argument(..., help="Content identifier of workflow to approve."),
    reviewer: str = typer.Option("human_reviewer", "--reviewer", "-r", help="Name of the human reviewer."),
    comment: Optional[str] = typer.Option(None, "--comment", "-c", help="Optional reviewer comment."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to SQLite database."),
) -> None:
    """Approve a workflow awaiting human review. Safely idempotent if already completed."""
    engine = _get_engine(db)
    current = engine.get_state(content_id)

    if not current:
        console.print(f"[bold red]Error:[/bold red] No workflow found for content ID '{content_id}'.")
        raise typer.Exit(code=1)

    if current.status == WorkflowStatus.COMPLETED:
        console.print(f"[dim]Workflow '{content_id}' is already completed.[/dim]")
        console.print("[dim]Approval is idempotent. No duplicate completion event recorded.[/dim]\n")
        return

    approval = ApprovalMetadata(approved_by=reviewer, comment=comment)
    final_state = engine.resume_and_approve(content_id, approval_metadata=approval)

    console.print(f"[bold green]Successfully approved and completed workflow for '{content_id}'.[/bold green]")
    console.print(f"[dim]Final status: {final_state.status.value}[/dim]\n")


@app.command("events")
def events_command(
    content_id: str = typer.Argument(..., help="Content identifier whose event log to view."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of table."),
    db: Optional[str] = typer.Option(None, "--db", help="Path to SQLite database."),
) -> None:
    """Display the persistent event log showing the complete workflow progression."""
    engine = _get_engine(db)
    events = engine.get_events(content_id)

    if not events:
        console.print(f"[dim]No events found for content '{content_id}'.[/dim]")
        return

    if json_output:
        console.print(format_events_json(events))
    else:
        console.print(f"\n[bold]Event Log for Content: {content_id}[/bold]")
        console.print(format_events_table(events))
        console.print(f"\n[dim]Total events: {len(events)}[/dim]\n")


@app.command("list")
def list_command(
    db: Optional[str] = typer.Option(None, "--db", help="Path to SQLite database."),
) -> None:
    """List all workflow runs recorded in the database."""
    engine = _get_engine(db)
    runs = engine.db.list_runs()

    if not runs:
        console.print("[dim]No workflow runs found in database.[/dim]")
        return

    table = Table(title="Workflow Runs", show_header=True, header_style="bold cyan")
    table.add_column("Content ID", style="bold")
    table.add_column("Status")
    table.add_column("Stage")
    table.add_column("Revisions")
    table.add_column("Checkpoint")
    table.add_column("Last Updated")

    for r in runs:
        table.add_row(
            r["content_id"],
            r["status"],
            r["stage"],
            str(r["revision_count"]),
            f"v{r['checkpoint_version']}",
            r["updated_at"],
        )

    console.print(table)


if __name__ == "__main__":
    app()
