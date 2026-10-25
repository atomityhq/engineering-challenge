"""End-to-end automated tests for the workflow CLI commands."""

from typer.testing import CliRunner

from workflow.cli import app

runner = CliRunner(env={"COLUMNS": "200"})


def test_cli_normal_pass_and_approve(temp_db_path: str) -> None:
    """CLI: Run standard content to pause, inspect status, then approve."""
    # 1. Run
    res_run = runner.invoke(app, ["run", "content-cli-001", "--db", temp_db_path])
    assert res_run.exit_code == 0
    assert "Evaluation completed" in res_run.stdout
    assert "Decision: human_review" in res_run.stdout
    assert "Workflow paused." in res_run.stdout

    # 2. Status
    res_status = runner.invoke(app, ["status", "content-cli-001", "--db", temp_db_path])
    assert res_status.exit_code == 0
    assert "awaiting_human_review" in res_status.stdout
    assert "content-cli-001" in res_status.stdout

    # 3. Approve
    res_approve = runner.invoke(app, ["approve", "content-cli-001", "--reviewer", "senior_editor", "--db", temp_db_path])
    assert res_approve.exit_code == 0
    assert "Successfully approved and completed" in res_approve.stdout

    # 4. Duplicate Approve (idempotent)
    res_dup = runner.invoke(app, ["approve", "content-cli-001", "--db", temp_db_path])
    assert res_dup.exit_code == 0
    assert "is already completed" in res_dup.stdout
    assert "idempotent" in res_dup.stdout

    # 5. Events table
    res_events = runner.invoke(app, ["events", "content-cli-001", "--db", temp_db_path])
    assert res_events.exit_code == 0
    assert "workflow_completed" in res_events.stdout

    # 6. Events JSON
    res_json = runner.invoke(app, ["events", "content-cli-001", "--json", "--db", temp_db_path])
    assert res_json.exit_code == 0
    assert '"event_type": "workflow_completed"' in res_json.stdout


def test_cli_revision_scenario_and_resume(temp_db_path: str) -> None:
    """CLI: Run revise-once scenario, verify revision attempt output, and resume."""
    res_run = runner.invoke(app, ["run", "content-cli-rev", "--scenario", "revise-once", "--db", temp_db_path])
    assert res_run.exit_code == 0
    assert "Revision attempt: 1" in res_run.stdout
    assert "Human review required" in res_run.stdout
    assert "Workflow paused." in res_run.stdout

    # Resume command
    res_resume = runner.invoke(app, ["resume", "content-cli-rev", "--reviewer", "editor_jane", "--db", temp_db_path])
    assert res_resume.exit_code == 0
    assert "Loaded checkpoint" in res_resume.stdout
    assert "Workflow completed." in res_resume.stdout


def test_cli_retry_limit_scenario(temp_db_path: str) -> None:
    """CLI: Run revise-limit scenario and verify proper termination output."""
    res_run = runner.invoke(app, ["run", "content-cli-limit", "--scenario", "revise-limit", "--db", temp_db_path])
    assert res_run.exit_code == 0
    assert "Revision attempt: 1" in res_run.stdout
    assert "Revision attempt: 2" in res_run.stdout
    assert "Maximum revision attempts reached." in res_run.stdout
    assert "Workflow stopped." in res_run.stdout


def test_cli_malformed_input_rejection(temp_db_path: str) -> None:
    """CLI: Missing/empty content ID or body is rejected with error code."""
    res = runner.invoke(app, ["run", "   ", "--db", temp_db_path])
    assert res.exit_code != 0
    assert "Input validation error" in res.stdout


def test_cli_list_command(temp_db_path: str) -> None:
    """CLI: list command displays table of runs."""
    runner.invoke(app, ["run", "content-list-1", "--db", temp_db_path])
    runner.invoke(app, ["run", "content-list-2", "--db", temp_db_path])

    res = runner.invoke(app, ["list", "--db", temp_db_path])
    assert res.exit_code == 0
    assert "content-list-1" in res.stdout
    assert "content-list-2" in res.stdout
