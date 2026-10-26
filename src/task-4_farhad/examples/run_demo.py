"""End-to-end demo using real, separate processes (so 'restart' is genuine).
Run from the task folder:   python examples/run_demo.py
Writes the transcript to examples/demo_output.txt
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "examples" / "demo.db"
OUT = ROOT / "examples" / "demo_output.txt"
RUN_ID = "run-content-001"

STEPS = [
    ["run", "content-001", "--scenario", "one_revision_then_pass"],
    ["resume", RUN_ID, "--approve"],      # a NEW process: loads the saved checkpoint
    ["approve", RUN_ID],                  # duplicate approval: must be a no-op
    ["log", RUN_ID],
]

DB.unlink(missing_ok=True)
transcript = []
for step in STEPS:
    cmd = [sys.executable, "-m", "workflow", *step, "--db", str(DB)]
    header = "$ python -m workflow " + " ".join(step)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    block = f"{header}\n{proc.stdout}{proc.stderr}(exit code {proc.returncode})\n"
    print(block)
    transcript.append(block)
OUT.write_text("\n".join(transcript), encoding="utf-8")
print(f"Transcript saved to {OUT}")
