"""Default file locations. The supplied fixture is read in place, never copied."""

from __future__ import annotations

from pathlib import Path

SUBMISSION_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SUBMISSION_ROOT.parent.parent

STARTER_FIXTURE = REPO_ROOT / "fixtures" / "g2-cases.json"
WEIGHTING_FIXTURE = SUBMISSION_ROOT / "fixtures" / "g2-weighting-cases.json"
EDGE_FIXTURE = SUBMISSION_ROOT / "fixtures" / "g2-edge-cases.json"

POLICY_CONFIG = SUBMISSION_ROOT / "config" / "g2_policy.json"
WEIGHTS_CONFIG = SUBMISSION_ROOT / "config" / "weights.json"

EXAMPLES_DIR = SUBMISSION_ROOT / "examples"


def display_path(path: Path) -> str:
    """Repository-relative path when possible, so reports do not depend on the checkout location."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()
