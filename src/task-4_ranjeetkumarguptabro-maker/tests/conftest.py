"""Pytest fixtures and test harnesses for the Resumable Review Workflow."""

import os
from pathlib import Path
import tempfile
from typing import Generator

import pytest

from workflow.models import ContentItem
from workflow.persistence import WorkflowDatabase


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Yield a path to a temporary SQLite database file and remove it after test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    if os.path.exists(path):
        os.remove(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def workflow_db(temp_db_path: str) -> WorkflowDatabase:
    """Provide an isolated, fully initialized WorkflowDatabase instance."""
    return WorkflowDatabase(temp_db_path)


@pytest.fixture
def sample_content() -> ContentItem:
    """Provide a standard, valid mock content item."""
    return ContentItem(
        id="content-unit-test-1",
        title="Automated Test Content Title",
        body="Body of content verifying review workflow orchestration under unit tests.",
    )
