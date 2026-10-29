"""The command line interface, called in-process with a temporary database."""

import json
import re

import pytest

from workflow.__main__ import main


@pytest.fixture
def cli(tmp_path, capsys):
    db = str(tmp_path / "workflow.db")

    def run(*args):
        code = main([*args, "--db", db])
        out, err = capsys.readouterr()
        return code, out, err

    return run


def event_names(cli, run_id):
    code, out, _ = cli("events", run_id)
    assert code == 0
    return [e["event"] for e in json.loads(out)]


# --- run ------------------------------------------------------------------


def test_run_pauses_for_review(cli):
    code, out, _ = cli("run", "content-001", "--scenario", "one-revision", "--run-id", "run-1")
    assert code == 0
    assert "Decision: revise" in out
    assert "Revision attempt: 1" in out
    assert "Checkpoint saved" in out
    assert "python -m workflow approve run-1" in out


def test_run_creates_a_random_run_id(cli):
    code, out, _ = cli("run", "content-001", "--scenario", "normal-pass")
    assert code == 0
    assert re.search(r"Run: run-[0-9a-f]{6}\b", out)


def test_run_stops_at_revision_limit(cli):
    code, out, _ = cli("run", "content-001", "--scenario", "revision-limit", "--run-id", "run-1")
    assert code == 0
    assert out.count("Revision attempt:") == 2
    assert "Maximum revision attempts reached (2)." in out
    assert "Status: REVISION_LIMIT_REACHED" in out


def test_max_revisions_option(cli):
    code, out, _ = cli("run", "content-001", "--scenario", "revision-limit", "--run-id", "run-1", "--max-revisions", "1")
    assert code == 0
    assert out.count("Revision attempt:") == 1


def test_reused_run_id_is_refused(cli):
    cli("run", "content-001", "--scenario", "normal-pass", "--run-id", "run-1")
    code, _, err = cli("run", "content-001", "--scenario", "normal-pass", "--run-id", "run-1")
    assert code == 1
    assert "already exists" in err


# --- invalid input --------------------------------------------------------


def test_malformed_content_is_refused_before_anything_runs(cli):
    code, out, err = cli("run", "content-bad", "--scenario", "normal-pass", "--run-id", "run-1")
    assert code == 1
    assert "Invalid content item 'content-bad'" in err
    assert "body: Field required" in err
    assert out == ""

    code, _, err = cli("status", "run-1")
    assert code == 1
    assert "No run with id 'run-1'" in err


@pytest.mark.parametrize(
    "args, message",
    [
        (["content-999", "--scenario", "normal-pass"], "Unknown content id 'content-999'."),
        (["content-001", "--scenario", "nope"], "Unknown scenario 'nope'."),
        (["content-001", "--scenario", "normal-pass", "--max-revisions", "-1"], "Invalid run input: max_revisions must be 0 or more."),
    ],
)
def test_bad_run_arguments_are_refused(cli, args, message):
    code, _, err = cli("run", *args)
    assert code == 1
    assert message in err


# --- approve --------------------------------------------------------------


def test_approve_completes_the_run(cli):
    cli("run", "content-001", "--scenario", "one-revision", "--run-id", "run-1")

    code, out, _ = cli("approve", "run-1")
    assert code == 0
    assert "Workflow completed." in out
    assert event_names(cli, "run-1") == [
        "evaluation_completed",
        "revision_completed",
        "evaluation_completed",
        "human_review_required",
        "checkpoint_saved",
        "checkpoint_loaded",
        "human_approved",
        "workflow_completed",
    ]


def test_second_approve_changes_nothing(cli):
    cli("run", "content-001", "--scenario", "normal-pass", "--run-id", "run-1")
    cli("approve", "run-1")

    code, out, _ = cli("approve", "run-1")
    assert code == 0
    assert "already completed. Nothing changed." in out
    assert event_names(cli, "run-1").count("workflow_completed") == 1


def test_stopped_run_cannot_be_approved(cli):
    cli("run", "content-001", "--scenario", "revision-limit", "--run-id", "run-1")
    code, _, err = cli("approve", "run-1")
    assert code == 1
    assert "cannot be approved. Status: REVISION_LIMIT_REACHED" in err


def test_unknown_run_cannot_be_approved(cli):
    code, _, err = cli("approve", "run-404")
    assert code == 1
    assert "No run with id 'run-404'" in err


# --- status and events ----------------------------------------------------


def test_status_shows_a_paused_run(cli):
    cli("run", "content-001", "--scenario", "one-revision", "--run-id", "run-1")
    code, out, _ = cli("status", "run-1")
    assert code == 0
    assert "Status:         WAITING_FOR_REVIEW" in out
    assert "Revisions:      1 of 2" in out
    assert "Next step:      human_review" in out


def test_status_shows_a_finished_run(cli):
    cli("run", "content-001", "--scenario", "normal-pass", "--run-id", "run-1")
    cli("approve", "run-1")
    code, out, _ = cli("status", "run-1")
    assert code == 0
    assert "Status:         COMPLETED" in out
    assert "Next step:      none (finished)" in out


def test_events_are_json(cli):
    cli("run", "content-001", "--scenario", "normal-pass", "--run-id", "run-1")
    code, out, _ = cli("events", "run-1")
    assert code == 0
    events = json.loads(out)
    assert events[0]["event"] == "evaluation_completed"
    assert events[0]["decision"] == "human_review"


def test_events_for_unknown_run_are_refused(cli):
    code, _, err = cli("events", "run-404")
    assert code == 1
    assert "No run with id 'run-404'" in err
