import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from cli import CliError, FIXTURE_PATH, load_workflow_fixture
from evaluator import FakeEvaluator
from models import ContentInput
from persistence import open_sqlite_checkpointer
from workflow import build_workflow, create_initial_state, resume_after_review


PROJECT_DIR = Path(__file__).resolve().parents[1]
CLI_PATH = PROJECT_DIR / "cli.py"


def config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def content() -> ContentInput:
    return ContentInput(content_id="content-001", text="Draft content")


def run_cli(database: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI_PATH),
            "--database",
            str(database),
            *arguments,
        ],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )


def test_workflow_fixture_contains_expected_content_and_scenarios() -> None:
    fixture_content, scenarios = load_workflow_fixture(FIXTURE_PATH)

    assert fixture_content.content_id == "content-001"
    assert fixture_content.text.strip()
    assert scenarios == {
        "pass": ["human_review"],
        "revise-once": ["revise", "human_review"],
        "retry-limit": ["revise", "revise", "revise"],
    }


def test_missing_and_invalid_workflow_fixtures_have_clear_errors(
    tmp_path: Path,
) -> None:
    with pytest.raises(CliError, match="workflow fixture not found"):
        load_workflow_fixture(tmp_path / "missing.json")

    invalid_fixture = tmp_path / "invalid.json"
    invalid_fixture.write_text('{"content_item": {}, "scenarios": {}}')
    with pytest.raises(CliError, match="invalid workflow fixture"):
        load_workflow_fixture(invalid_fixture)


def test_immediate_review_checkpoint_and_approval(tmp_path: Path) -> None:
    database = tmp_path / "immediate.sqlite3"
    thread_id = "immediate-review"
    run_config = config(thread_id)

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(FakeEvaluator(["human_review"]), checkpointer)
        paused = graph.invoke(
            create_initial_state(thread_id, content()),
            run_config,
        )
        checkpoint = graph.get_state(run_config)

    assert database.exists()
    assert "__interrupt__" in paused
    assert checkpoint.values["status"] == "awaiting_human_review"
    assert checkpoint.values["event_log"] == [
        "evaluation: human_review",
        "human_review: awaiting approval",
    ]

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(FakeEvaluator([]), checkpointer)
        completed = graph.invoke(resume_after_review(True), run_config)

    assert completed["status"] == "completed"
    assert completed["human_approved"] is True
    assert completed["event_log"] == [
        "evaluation: human_review",
        "human_review: awaiting approval",
        "human_review: approved",
        "workflow: completed",
    ]


def test_one_revision_then_review_has_exact_event_order(tmp_path: Path) -> None:
    database = tmp_path / "one-revision.sqlite3"
    thread_id = "one-revision"
    run_config = config(thread_id)

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(
            FakeEvaluator(["revise", "human_review"]),
            checkpointer,
        )
        paused = graph.invoke(
            create_initial_state(thread_id, content()),
            run_config,
        )
        assert paused["revision_count"] == 1
        completed = graph.invoke(resume_after_review(True), run_config)

    assert completed["event_log"] == [
        "evaluation: revise",
        "revision: completed attempt 1",
        "evaluation: human_review",
        "human_review: awaiting approval",
        "human_review: approved",
        "workflow: completed",
    ]


def test_repeated_revisions_stop_after_two_attempts(tmp_path: Path) -> None:
    database = tmp_path / "retry-limit.sqlite3"
    thread_id = "retry-limit"
    run_config = config(thread_id)

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(FakeEvaluator(["revise"] * 3), checkpointer)
        result = graph.invoke(
            create_initial_state(thread_id, content()),
            run_config,
        )
        persisted = graph.get_state(run_config).values

    expected_events = [
        "evaluation: revise",
        "revision: completed attempt 1",
        "evaluation: revise",
        "revision: completed attempt 2",
        "evaluation: revise",
        "retry_limit_reached: maximum of 2 revisions",
    ]
    assert result["status"] == "retry_limit_reached"
    assert result["revision_count"] == 2
    assert result["event_log"] == expected_events
    assert persisted["event_log"] == expected_events
    assert "revision: completed attempt 3" not in result["event_log"]


def test_checkpoint_resumes_in_separate_process_without_repeating_work(
    tmp_path: Path,
) -> None:
    database = tmp_path / "cross-process.sqlite3"
    thread_id = "cross-process"
    run_config = config(thread_id)

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(
            FakeEvaluator(["revise", "human_review"]),
            checkpointer,
        )
        paused = graph.invoke(
            create_initial_state(thread_id, content()),
            run_config,
        )
        assert paused["status"] == "awaiting_human_review"

    resume_script = """
import sys
from evaluator import FakeEvaluator
from persistence import open_sqlite_checkpointer
from workflow import build_workflow, resume_after_review

database, thread_id = sys.argv[1:]
config = {"configurable": {"thread_id": thread_id}}
with open_sqlite_checkpointer(database) as checkpointer:
    graph = build_workflow(FakeEvaluator([]), checkpointer)
    result = graph.invoke(resume_after_review(True), config)
    assert result["status"] == "completed"
"""
    process = subprocess.run(
        [sys.executable, "-c", resume_script, str(database), thread_id],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(FakeEvaluator([]), checkpointer)
        restored = graph.get_state(run_config).values

    assert restored["status"] == "completed"
    assert restored["revision_count"] == 1
    assert restored["event_log"] == [
        "evaluation: revise",
        "revision: completed attempt 1",
        "evaluation: human_review",
        "human_review: awaiting approval",
        "human_review: approved",
        "workflow: completed",
    ]


def test_duplicate_approval_does_not_change_completed_workflow(
    tmp_path: Path,
) -> None:
    database = tmp_path / "duplicate-approval.sqlite3"
    thread_id = "duplicate-approval"
    run_config = config(thread_id)

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(FakeEvaluator(["human_review"]), checkpointer)
        graph.invoke(create_initial_state(thread_id, content()), run_config)
        completed = graph.invoke(resume_after_review(True), run_config)
        duplicate = graph.invoke(resume_after_review(True), run_config)

    assert duplicate["event_log"] == completed["event_log"]
    assert duplicate["event_log"].count("workflow: completed") == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"content_id": "", "text": "content"},
        {"content_id": "content-001", "text": "   "},
        {"text": "content"},
        {"content_id": "content-001"},
    ],
)
def test_malformed_content_is_rejected(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        ContentInput.model_validate(payload)


def test_invalid_evaluator_decision_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid evaluation decision"):
        FakeEvaluator(["publish"])  # type: ignore[list-item]


def test_unknown_thread_id_returns_clear_cli_error(tmp_path: Path) -> None:
    process = run_cli(tmp_path / "unknown.sqlite3", "status", "missing-thread")

    assert process.returncode == 2
    assert "unknown thread ID: missing-thread" in process.stderr


def test_status_is_read_only(tmp_path: Path) -> None:
    database = tmp_path / "status.sqlite3"
    thread_id = "status-read-only"
    run_config = config(thread_id)

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(FakeEvaluator(["human_review"]), checkpointer)
        graph.invoke(create_initial_state(thread_id, content()), run_config)
        before = graph.get_state(run_config)

    process = run_cli(database, "status", thread_id)
    assert process.returncode == 0, process.stderr
    assert "Status: awaiting_human_review" in process.stdout

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(FakeEvaluator([]), checkpointer)
        after = graph.get_state(run_config)

    assert after.values["event_log"] == before.values["event_log"]
    assert after.next == before.next
    assert (
        after.config["configurable"]["checkpoint_id"]
        == before.config["configurable"]["checkpoint_id"]
    )


def test_decline_then_later_approval(tmp_path: Path) -> None:
    database = tmp_path / "decline.sqlite3"
    thread_id = "decline-then-approve"
    run_config = config(thread_id)

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(FakeEvaluator(["human_review"]), checkpointer)
        graph.invoke(create_initial_state(thread_id, content()), run_config)
        declined = graph.invoke(resume_after_review(False), run_config)

    assert declined["status"] == "awaiting_human_review"
    assert declined["human_approved"] is False
    assert "__interrupt__" in declined

    with open_sqlite_checkpointer(database) as checkpointer:
        graph = build_workflow(FakeEvaluator([]), checkpointer)
        approved = graph.invoke(resume_after_review(True), run_config)

    assert approved["status"] == "completed"
    assert approved["event_log"][-3:] == [
        "human_review: not approved",
        "human_review: approved",
        "workflow: completed",
    ]


def test_duplicate_active_workflow_start_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "duplicate-start.sqlite3"

    first = run_cli(database, "run", "content-001", "--scenario", "pass")
    assert first.returncode == 0, first.stderr

    duplicate = run_cli(database, "run", "content-001", "--scenario", "pass")
    assert duplicate.returncode == 2
    assert "already has an active workflow" in duplicate.stderr
