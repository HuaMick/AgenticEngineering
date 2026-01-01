#!/usr/bin/env python3
"""End-to-end tests for langgraph home directory functionality.

This test suite validates complete workflows for home-directory-only architecture,
testing the discovery and routing system for langgraph.json files.

Test Coverage:
- Complete workflow: detect_project_root() with home directory
- Complete workflow: graceful fallback without auto-creation
- Integration: CLI commands using home langgraph.json
- Integration: Error handling when no langgraph.json exists

Design:
- End-to-end tests validate complete workflows, not isolated components
- Tests simulate real user scenarios from start to finish
- Tests verify integration between CLI, workflows, and domain layers
- All langgraph.json files are stored in ~/.config/myagents/ (home-directory-only)
"""

import pytest
import tempfile
import shutil
import json
from pathlib import Path
import subprocess
import sys

# Import the workflow we're testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
from myagents.backend.services.agents.workflows.health_check_workflow import HealthCheckWorkflow
from myagents.backend.services.preferences.domains.preferences_manager.manager import PreferencesManager


@pytest.fixture
def isolated_environment(tmp_path, monkeypatch):
    """Create an isolated test environment with backups.

    This fixture temporarily disables MYAGENTS_TEST_ISOLATION to allow these tests
    to test the routing mechanism itself, while still providing isolation by backing
    up and clearing the real home directory files.
    """
    import os

    # Temporarily disable test isolation for these routing tests
    # We need routing to work, but we'll isolate by backing up real files
    test_isolation_was_set = 'MYAGENTS_TEST_ISOLATION' in os.environ
    if test_isolation_was_set:
        test_isolation_value = os.environ.pop('MYAGENTS_TEST_ISOLATION')

    # Backup home config directory
    home_config_dir = Path.home() / ".config" / "myagents"
    backup_dir = None

    if home_config_dir.exists():
        backup_dir = Path(tempfile.mkdtemp())
        shutil.copytree(home_config_dir, backup_dir / "myagents")

    # Backup preferences file (separate from config dir)
    prefs_dir = Path.home() / ".myagents"
    prefs_file = prefs_dir / "preferences.json"
    prefs_backup = None
    if prefs_file.exists():
        prefs_backup = prefs_file.read_text()
        # Clear preferences so test routing isn't contaminated
        prefs_file.unlink()

    # Create test directories
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    yield {
        "project_dir": project_dir,
        "tmp_path": tmp_path,
        "home_config_dir": home_config_dir,
        "backup_dir": backup_dir
    }

    # Restore backups
    if backup_dir:
        if home_config_dir.exists():
            shutil.rmtree(home_config_dir)
        shutil.copytree(backup_dir / "myagents", home_config_dir)
        shutil.rmtree(backup_dir)
    else:
        # Clean up if we created during test
        if home_config_dir.exists():
            shutil.rmtree(home_config_dir)

    # Restore preferences
    if prefs_backup:
        prefs_file.parent.mkdir(parents=True, exist_ok=True)
        prefs_file.write_text(prefs_backup)

    # Restore test isolation flag
    if test_isolation_was_set:
        os.environ['MYAGENTS_TEST_ISOLATION'] = test_isolation_value


@pytest.mark.workflow_health_check
@pytest.mark.e2e
class TestDetectContextIntegration:
    """End-to-end test: detect_context() integration with all discovery paths."""

    def test_complete_workflow_detect_context_with_home_config(self, isolated_environment, monkeypatch):
        """Test complete workflow: detect_context() finds home directory config.

        Workflow:
        1. Create home config with langgraph.json
        2. Navigate to non-project directory
        3. Call detect_context(command="chat")
        4. Verify project context uses home directory

        Note: This validates the home-directory-only architecture where projects
        are discovered from ~/.config/myagents/ instead of local directories.
        """
        # Setup: Create home config with langgraph.json
        home_config_dir = isolated_environment["home_config_dir"]
        home_config_dir.mkdir(parents=True, exist_ok=True)
        home_langgraph = home_config_dir / "langgraph.json"
        home_langgraph.write_text('{"test": "home"}')

        # Navigate to non-project directory
        non_project_dir = isolated_environment["tmp_path"] / "non_project"
        non_project_dir.mkdir()
        monkeypatch.chdir(non_project_dir)

        # Execute: Detect context
        workflow = HealthCheckWorkflow()
        result = workflow.detect_context(command="chat")

        # Verify: Project context detected using home directory
        assert result["context_type"] == "project"
        assert result["is_global_command"] is False
        assert result["project_root"] == home_config_dir
        assert "config_path" in result



    def test_complete_workflow_detect_context_global_command(self, isolated_environment, monkeypatch):
        """Test complete workflow: detect_context() handles global commands.

        Workflow:
        1. Navigate to non-project directory
        2. Call detect_context(command="update")
        3. Verify global context (no project required)
        """
        # Setup: Navigate to non-project directory
        non_project_dir = isolated_environment["tmp_path"] / "non_project"
        non_project_dir.mkdir()
        monkeypatch.chdir(non_project_dir)

        # Execute: Detect context for global command
        workflow = HealthCheckWorkflow()
        result = workflow.detect_context(command="update")

        # Verify: Global context
        assert result["context_type"] == "global"
        assert result["is_global_command"] is True
        assert "source_root" in result
        assert result["config_path"] is None


@pytest.mark.workflow_health_check
@pytest.mark.e2e
class TestErrorCasesAndEdgeCases:
    """End-to-end test: error cases and edge cases for home directory architecture."""

    def test_error_case_detect_context_no_langgraph_json_raises(self, isolated_environment, monkeypatch):
        """Test error case: detect_context raises when no langgraph.json exists anywhere.

        Workflow:
        1. Remove all langgraph.json files
        2. Call detect_context(command="chat")
        3. Verify RuntimeError is raised with helpful message
        """
        # Setup: Ensure no langgraph.json anywhere
        home_config_dir = isolated_environment["home_config_dir"]
        if home_config_dir.exists():
            shutil.rmtree(home_config_dir)

        non_project_dir = isolated_environment["tmp_path"] / "non_project"
        non_project_dir.mkdir()
        monkeypatch.chdir(non_project_dir)

        # Execute & Verify: Raises helpful error
        workflow = HealthCheckWorkflow()
        with pytest.raises(RuntimeError) as exc_info:
            workflow.detect_context(command="chat")

        error_msg = str(exc_info.value)
        assert "No langgraph.json found" in error_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
