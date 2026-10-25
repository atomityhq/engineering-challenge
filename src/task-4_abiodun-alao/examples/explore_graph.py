import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langgraph.types import Command

from workflow.components import FakeReviser, ScriptedEvaluator 
from workflow.graph import build_graph
from workflow.inputs import load_content, load_evaluator_script 
from workflow.models import WorkflowState 
from workflow.storage import open_storage

db_path = ROOT / "data" / "explore.db"
for f in db_path.parent.glob("explore.db*"):
    f.unlink()

storage = open_storage(db_path)
events = storage.events
app = build_graph(
    ScriptedEvaluator(load_evaluator_script(ROOT / "fixtures" / "evaluator" / "revise_once.json")),
    FakeReviser(),
    events,
    storage.checkpointer,
)
config = {"configurable": {"thread_id": "run-001"}} 

print("1) Start the run (stream shows each node as it finishes):")
initial = WorkflowState(run_id="run-001", content=load_content(ROOT / "fixtures" / "content" / "content-001.json"))
for step in app.stream(initial, config, stream_mode="updates"):
    for node, update in step.items():
        print(f"   ✓ {node:<16} -> {list(update) if isinstance(update, dict) else update}")

snapshot = app.get_state(config)
print(f"\n2) Paused. Next node: {snapshot.next}. Status: {snapshot.values['status'].value}. "
      f"Revisions: {snapshot.values['revision_count']}")

print("\n3) Event log so far:")
for e in events.for_run("run-001"):
    print("  ", json.dumps({k: v for k, v in e.items() if k != "at"}))

print("\n4) A human approves -> resume with Command(resume=...):")
for step in app.stream(Command(resume={"decision": "approve", "reviewer": "ada"}), config, stream_mode="updates"):
    for node in step:
        print(f"   ✓ {node}")

print(f"\n5) Final status: {app.get_state(config).values['status'].value}")
print("   Full event log:", events.names("run-001"))