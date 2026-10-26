import pytest

from workflow.config import WorkflowConfig


@pytest.fixture
def config(tmp_path):
    return WorkflowConfig(db_path=tmp_path / "test.db")
