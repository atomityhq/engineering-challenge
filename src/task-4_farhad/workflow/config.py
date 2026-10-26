"""Explicit, testable configuration. No secrets required."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkflowConfig:
    # Spec: the demo must stop after a configurable maximum of two revisions.
    max_revisions: int = 2
    db_path: Path = Path("workflow.db")  # checkpoints + event log (local SQLite)

    def __post_init__(self) -> None:
        if self.max_revisions < 0:
            raise ValueError("max_revisions must be >= 0")
