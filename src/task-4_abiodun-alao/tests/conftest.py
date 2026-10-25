import os

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES