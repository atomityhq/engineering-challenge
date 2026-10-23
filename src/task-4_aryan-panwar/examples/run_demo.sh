#!/usr/bin/env bash
# Runs every scenario from a clean state and records the console transcript.
# Usage (from the task folder): bash examples/run_demo.sh
set -u
cd "$(dirname "$0")/.."
OUT=examples/output
rm -rf "$OUT" && mkdir -p "$OUT"
wf() { uv run -q python -m review_workflow --db "$OUT/checkpoints.sqlite" --out "$OUT/runs" "$@"; }
step() { echo; echo "\$ python -m review_workflow $*"; wf "$@"; echo "[exit $?]"; }

{
echo "### 1. One revision, pause at human review, restart, approve"
step run --content fixtures/content/content-001.json --evaluator fixtures/evaluator/one-revision.json --run-id run-001
echo "# (process exited; the next command is a new process)"
step resume run-001 --decision approve

echo; echo "### 2. Duplicate approval of a completed run"
step approve run-001

echo; echo "### 3. Normal pass straight to review, then reject"
step run --content fixtures/content/content-001.json --evaluator fixtures/evaluator/pass.json --run-id run-002
step resume run-002 --decision reject --note "Angle does not fit this week"

echo; echo "### 4. Evaluator always asks for revision: stops at 2"
step run --content fixtures/content/content-001.json --evaluator fixtures/evaluator/always-revise.json --run-id run-003

echo; echo "### 5. Malformed input"
step run --content fixtures/content/malformed-missing-body.json --evaluator fixtures/evaluator/pass.json
step run --content fixtures/content/malformed-bad-id.json --evaluator fixtures/evaluator/pass.json
step run --content fixtures/content/content-001.json --evaluator fixtures/evaluator/malformed.json --run-id run-bad

echo; echo "### 6. Left paused at human review (inspect runs/run-004/state.json)"
step run --content fixtures/content/content-001.json --evaluator fixtures/evaluator/one-revision.json --run-id run-004
} 2>&1 | tee "$OUT/transcript.txt"
rm -f "$OUT/checkpoints.sqlite"
