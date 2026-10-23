#!/usr/bin/env python3

import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
CLI_PATH = PROJECT_DIR / "cli.py"
PAUSED_EVENTS = [
    "evaluation: revise",
    "revision: completed attempt 1",
    "evaluation: human_review",
    "human_review: awaiting approval",
]
COMPLETED_EVENTS = [
    *PAUSED_EVENTS,
    "human_review: approved",
    "workflow: completed",
]


def run_cli(database: Path, *arguments: str) -> str:
    command = [
        sys.executable,
        str(CLI_PATH),
        "--database",
        str(database),
        *arguments,
    ]
    print(f"\n$ python cli.py {' '.join(arguments)}")
    result = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode != 0:
        raise RuntimeError(f"CLI process exited with status {result.returncode}")
    return result.stdout


def event_history(output: str) -> list[str]:
    return [line.removeprefix("  - ") for line in output.splitlines() if line.startswith("  - ")]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="atomity-task4-demo-") as temp_dir:
        database = Path(temp_dir) / "checkpoints.sqlite3"

        started = run_cli(
            database,
            "run",
            "content-001",
            "--scenario",
            "revise-once",
        )
        require("Workflow paused for human review." in started, "workflow did not pause")
        require(event_history(started) == PAUSED_EVENTS, "unexpected pre-review events")

        thread_line = next(
            (line for line in started.splitlines() if line.startswith("Thread ID: ")),
            None,
        )
        require(thread_line is not None, "CLI did not print a thread ID")
        thread_id = thread_line.removeprefix("Thread ID: ")

        print("\n--- Starting a fresh process to resume the SQLite checkpoint ---")
        resumed = run_cli(database, "resume", thread_id, "--approve")
        require("Workflow status: completed" in resumed, "workflow did not complete")
        require(event_history(resumed) == COMPLETED_EVENTS, "work was repeated on resume")

        final_status = run_cli(database, "status", thread_id)
        require("Status: completed" in final_status, "persisted status is not completed")
        require(event_history(final_status) == COMPLETED_EVENTS, "persisted events changed")

        duplicate = run_cli(database, "resume", thread_id, "--approve")
        require(event_history(duplicate) == COMPLETED_EVENTS, "duplicate approval changed events")
        require(
            event_history(duplicate).count("workflow: completed") == 1,
            "workflow completed more than once",
        )

    print("\nDemo completed successfully: persisted work resumed without repetition.")


if __name__ == "__main__":
    main()
