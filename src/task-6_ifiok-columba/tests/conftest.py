import copy
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from g2_gate.config import load_policy  # noqa: E402
from g2_gate.loader import load_fixture, parse_fixture  # noqa: E402

SUPPLIED = REPO_ROOT / "fixtures" / "g2-cases.json"
EXTRA = PACKAGE_ROOT / "fixtures" / "extra-eligible-cases.json"


@pytest.fixture(scope="session")
def policy():
    return load_policy()


@pytest.fixture(scope="session")
def supplied():
    return load_fixture(SUPPLIED)  # (fixture, expectations)


@pytest.fixture(scope="session")
def extra():
    return load_fixture(EXTRA)


@pytest.fixture
def make_fixture():
    """Build a one-case fixture from the supplied envelope, with metadata overrides."""
    import json

    raw = json.loads(SUPPLIED.read_text(encoding="utf-8"))

    def _make(case_id="t", base="current-news", statement=None, **overrides):
        template = next(c for c in raw["cases"] if c["id"] == base)
        case = copy.deepcopy(template)
        case["id"] = case_id
        if statement is not None:
            case["statement"] = statement
        case["metadata"].update(overrides)
        case.pop("expected_decision", None)
        envelope = {**copy.deepcopy(raw), "cases": [case]}
        fixture, _ = parse_fixture(envelope)
        return fixture

    return _make
