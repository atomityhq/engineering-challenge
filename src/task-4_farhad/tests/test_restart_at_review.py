"""Required check: terminate at human review, restart, resume without repeating work.
Uses real, separate OS processes through the CLI."""
from tests.helpers import cli, cli_log

RUN = "run-content-001"   # the CLI's default run id for content-001


def test_resume_in_new_process_does_not_repeat_work(tmp_path):
    db = tmp_path / "restart.db"

    first = cli("run", "content-001", "--scenario", "one_revision_then_pass", "--db", str(db))
    assert first.returncode == 0, first.stderr
    assert "paused at human review" in first.stdout
    before_names = [e["event"] for e in cli_log(db, RUN)]
    assert before_names.count("evaluation_completed") == 2
    assert before_names.count("revision_requested") == 1
    assert before_names[-1] == "checkpoint_saved"

    # The first process has exited. A second, brand-new process resumes from the file.
    second = cli("resume", RUN, "--approve", "--db", str(db))
    assert second.returncode == 0, second.stderr
    assert "Loaded checkpoint" in second.stdout
    assert "Current stage: human_review" in second.stdout
    assert "Workflow completed." in second.stdout
    assert "Traceback" not in second.stderr

    after_names = [e["event"] for e in cli_log(db, RUN)]
    assert after_names[:len(before_names)] == before_names          # history untouched
    new_events = after_names[len(before_names):]
    assert new_events == ["checkpoint_loaded", "human_approved", "workflow_completed"]
    assert after_names.count("evaluation_completed") == 2           # no re-evaluation
    assert after_names.count("revision_requested") == 1             # no re-revision
