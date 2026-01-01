"""Shared fixtures for integration tests.

This conftest.py provides common fixtures used across multiple integration test modules.
"""

import pytest
import tempfile
import shutil
import subprocess
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    temp_path = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init"], cwd=temp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=temp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_path, capture_output=True)

    # Create initial file and commit
    (temp_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=temp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_path, capture_output=True)

    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def setup_test_env(temp_dir, monkeypatch):
    """Setup test environment with temporary directory for file operations tools."""
    # Temporarily override the allowed directory for testing
    from myagents.backend.services.agents.domains.file_operations import FileOperations
    test_ops = FileOperations(allowed_dir=temp_dir)

    # Monkey-patch the module-level _file_ops instance
    monkeypatch.setattr('myagents.backend.services.agents.tools.file_tools._file_ops', test_ops)

    return temp_dir


@pytest.fixture
def setup_git_test_env(temp_git_repo, monkeypatch):
    """Setup test environment with temporary git repository for git operations tools."""
    # Temporarily override the allowed directory for testing
    from myagents.backend.services.agents.domains.git_operations import GitOperations
    test_ops = GitOperations(allowed_dir=temp_git_repo)

    # Monkey-patch the module-level _git_ops instance
    monkeypatch.setattr('myagents.backend.services.agents.tools.git_tools._git_ops', test_ops)

    return temp_git_repo
