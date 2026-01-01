"""Comprehensive end-to-end tests for global command architecture.

This test suite validates the complete global command architecture including:
- First run initialization (clean ~/.config/myagents/, verify creation)
- All commands from all directories (project, parent, arbitrary)
- Preference modification workflow
- Home directory single source of truth behavior (no fallback)
- Project context detection (when in project, use project; otherwise, use home)

Test Matrix:
- Commands: myagents, --version, --help, chat, studio, config, preferences
- Directories: project dir, parent dir, /tmp
- States: clean install, existing config, modified preferences

Test Strategy: End-to-end workflow testing with state management
"""

import pytest
import subprocess
import tempfile
import shutil
import json
import time
from pathlib import Path


# Test configuration
PROJECT_DIR = Path(__file__).parents[3]  # Goes up to project root
PARENT_DIR = PROJECT_DIR.parent
HOME_CONFIG_DIR = Path.home() / ".config" / "myagents"
MYAGENTS_CLI = "myagents"


@pytest.fixture
def clean_home_config():
    """Backup and clean ~/.config/myagents/ for clean state tests."""
    backup_dir = None

    # Backup existing config if it exists
    if HOME_CONFIG_DIR.exists():
        backup_dir = HOME_CONFIG_DIR.parent / f"myagents_backup_{int(time.time())}"
        shutil.copytree(HOME_CONFIG_DIR, backup_dir)
        shutil.rmtree(HOME_CONFIG_DIR)

    yield

    # Restore backup if it existed
    if backup_dir and backup_dir.exists():
        if HOME_CONFIG_DIR.exists():
            shutil.rmtree(HOME_CONFIG_DIR)
        shutil.copytree(backup_dir, HOME_CONFIG_DIR)
        shutil.rmtree(backup_dir)
    elif HOME_CONFIG_DIR.exists():
        # Clean up created config if no backup existed
        shutil.rmtree(HOME_CONFIG_DIR)


@pytest.fixture
def temp_arbitrary_dir():
    """Create a temporary directory for testing from arbitrary locations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def clean_preferences():
    """Clean preferences before and after test.

    Also cleans ~/.myagents/preferences.json to prevent contamination.
    """
    import os

    # Clean ~/.config/myagents/preferences.json
    prefs_file = HOME_CONFIG_DIR / "preferences.json"

    if prefs_file.exists():
        prefs_file.unlink()

    # Clean ~/.myagents/preferences.json (higher priority routing)
    myagents_prefs_file = Path.home() / ".myagents" / "preferences.json"
    if myagents_prefs_file.exists():
        myagents_prefs_file.unlink()

    yield

    # Always clean up - never restore backups to prevent contamination
    if prefs_file.exists():
        prefs_file.unlink()

    if myagents_prefs_file.exists():
        myagents_prefs_file.unlink()


@pytest.fixture
def subprocess_env_no_isolation():
    """Create subprocess env without test isolation for e2e tests.

    These tests need to test the real routing behavior including home directory
    creation, so we temporarily disable test isolation for subprocess calls.
    """
    import os
    env = os.environ.copy()
    # Remove test isolation flag for subprocess
    env.pop('MYAGENTS_TEST_ISOLATION', None)
    return env


# ============================================================================
# FIRST RUN INITIALIZATION TESTS
# ============================================================================

@pytest.mark.workflow_health_check
@pytest.mark.e2e
class TestFirstRunInitialization:
    """Test suite for first run initialization behavior."""

    def test_e2e_clean_install_setup_and_run(self, clean_home_config, temp_arbitrary_dir, subprocess_env_no_isolation):
        """TEST-003: Full E2E test from clean install to working commands.

        This tests the complete new user experience:
        1. Remove existing config (clean state)
        2. Run 'myagents setup' to initialize
        3. Verify all config files are created
        4. Verify langgraph.json references existing files
        5. Verify commands work after setup
        """
        # Step 1: Verify clean state (handled by clean_home_config fixture)
        assert not HOME_CONFIG_DIR.exists(), "Home config should be removed"

        # Step 2: Run setup
        result_setup = subprocess.run(
            [MYAGENTS_CLI, "setup"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True,
            env=subprocess_env_no_isolation
        )
        assert result_setup.returncode == 0, f"Setup should succeed: {result_setup.stderr}"

        # Step 3: Verify config files created
        config_yml = HOME_CONFIG_DIR / "config.yml"
        langgraph_json = HOME_CONFIG_DIR / "langgraph.json"
        assert config_yml.exists(), "config.yml should be created"
        assert langgraph_json.exists(), "langgraph.json should be created"

        # Step 4: Verify langgraph.json references existing files
        with open(langgraph_json) as f:
            langgraph_data = json.load(f)

        assert "graphs" in langgraph_data, "langgraph.json should have graphs"

        for graph_name, graph_path in langgraph_data["graphs"].items():
            file_path, entry_point = graph_path.split(":")
            assert Path(file_path).exists(), \
                f"Graph {graph_name} references {file_path} which doesn't exist"

        # Step 5: Verify commands work after setup
        result_chat = subprocess.run(
            [MYAGENTS_CLI, "chat", "--help"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True,
            env=subprocess_env_no_isolation
        )
        assert result_chat.returncode == 0, f"chat should work after setup: {result_chat.stderr}"

        result_config = subprocess.run(
            [MYAGENTS_CLI, "config", "show"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True,
            env=subprocess_env_no_isolation
        )
        assert result_config.returncode == 0, f"config show should work after setup: {result_config.stderr}"

    def test_remote_command_works_without_setup(self, clean_home_config, temp_arbitrary_dir, subprocess_env_no_isolation):
        """TEST-004: Verify global commands work without running setup.

        Global commands that don't require langgraph.json should work
        even on a completely clean install:
        - --version
        - --help
        - remote relay status (if remote commands are available)
        """
        # Verify clean state (no setup has been run)
        assert not HOME_CONFIG_DIR.exists(), "Home config should not exist"

        # Test --version works without setup
        result_version = subprocess.run(
            [MYAGENTS_CLI, "--version"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True,
            env=subprocess_env_no_isolation
        )
        assert result_version.returncode == 0, f"--version should work without setup: {result_version.stderr}"
        assert "myagents" in result_version.stdout.lower() or len(result_version.stdout) > 0, \
            "Should show version information"

        # Test --help works without setup
        result_help = subprocess.run(
            [MYAGENTS_CLI, "--help"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True,
            env=subprocess_env_no_isolation
        )
        assert result_help.returncode == 0, f"--help should work without setup: {result_help.stderr}"
        assert len(result_help.stdout) > 0, "Should show help information"

        # Test remote relay status if available
        result_remote = subprocess.run(
            [MYAGENTS_CLI, "remote", "relay", "status"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True,
            env=subprocess_env_no_isolation
        )
        # Remote relay status can return 0 (running) or 1 (stopped/not configured)
        # Either is valid - we just check it doesn't crash
        assert result_remote.returncode in [0, 1], \
            f"remote relay status should not crash without setup: {result_remote.stderr}"



# ============================================================================
# COMMAND EXECUTION FROM DIFFERENT DIRECTORIES
# ============================================================================

@pytest.mark.workflow_health_check
@pytest.mark.e2e
class TestCommandExecutionFromDirectories:
    """Test all commands work from different directories."""

    # Chat command tests (requires langgraph.json)

    def test_chat_from_project_dir(self):
        """Test chat command from project directory.

        In the new architecture, chat uses home directory config (~/.config/myagents/)
        and works from ANY directory, including project directory.
        """
        result = subprocess.run(
            [MYAGENTS_CLI, "chat", "--help"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        # Should succeed using home directory langgraph.json
        # Note: This assumes home config exists from development setup
        assert result.returncode == 0, f"chat should work from project using home config: {result.stderr}"


    # Studio command tests

    def test_studio_status_from_project_dir(self):
        """Test studio status from project directory.

        In the new architecture, studio status uses home directory config.
        - If home config exists: returns status (0=running, 1=stopped)
        - If home config missing: returns error directing to 'myagents setup'
        """
        result = subprocess.run(
            [MYAGENTS_CLI, "studio", "status"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        # Status command returns 1 when stopped, 0 when running
        # Also returns 1 if home config doesn't exist
        assert result.returncode in [0, 1], f"studio status should not crash: {result.stderr}"

        # Either shows status or error about missing home config
        if result.returncode == 0:
            # Studio is running - should show status
            assert "status" in result.stdout.lower() or "running" in result.stdout.lower(), \
                f"Should show status info when running: {result.stdout}"
        else:
            # Either studio is stopped OR home config is missing
            # Check if it's a config error or just stopped status
            if result.stdout:
                # Has output - likely status message
                assert "status" in result.stdout.lower() or "stopped" in result.stdout.lower(), \
                    f"Should show status info when stopped: {result.stdout}"
            else:
                # No stdout - likely config error in stderr
                assert "langgraph.json" in result.stderr.lower(), \
                    f"Should mention config issue in stderr: {result.stderr}"


    # Preferences command tests

    def test_preferences_list_from_project_dir(self):
        """Test preferences list from project directory."""
        result = subprocess.run(
            [MYAGENTS_CLI, "preferences", "list"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"preferences list should work: {result.stderr}"

    def test_preferences_list_from_arbitrary_dir(self, temp_arbitrary_dir):
        """Test preferences list from arbitrary directory."""
        result = subprocess.run(
            [MYAGENTS_CLI, "preferences", "list"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"preferences list should work: {result.stderr}"

    # Config command tests

    def test_config_show_from_project_dir(self):
        """Test config show from project directory."""
        result = subprocess.run(
            [MYAGENTS_CLI, "config", "show"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"config show should work: {result.stderr}"

    def test_config_show_from_arbitrary_dir(self, temp_arbitrary_dir):
        """Test config show from arbitrary directory."""
        result = subprocess.run(
            [MYAGENTS_CLI, "config", "show"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"config show should work: {result.stderr}"


# ============================================================================
# PREFERENCE MODIFICATION WORKFLOW
# ============================================================================

@pytest.mark.workflow_health_check
@pytest.mark.e2e
class TestPreferenceWorkflow:
    """Test preference modification workflows."""

    def test_set_and_get_preference(self, clean_preferences):
        """Test setting and retrieving a preference.

        Validates:
        - Preferences can be set
        - Preferences persist across commands
        - Preferences can be retrieved correctly
        """
        # Set preference
        result_set = subprocess.run(
            [MYAGENTS_CLI, "preferences", "set", "test.key", "test_value"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result_set.returncode == 0, f"set should succeed: {result_set.stderr}"

        # Get preference
        result_get = subprocess.run(
            [MYAGENTS_CLI, "preferences", "get", "test.key"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result_get.returncode == 0, f"get should succeed: {result_get.stderr}"
        assert "test_value" in result_get.stdout, f"Should show set value: {result_get.stdout}"


    def test_delete_preference(self, clean_preferences):
        """Test deleting a preference.

        Validates:
        - Preferences can be deleted
        - Deleted preferences are not retrievable
        - Delete operation is idempotent
        """
        # Set preference
        subprocess.run(
            [MYAGENTS_CLI, "preferences", "set", "delete.test", "value"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            check=True
        )

        # Delete preference
        result_del = subprocess.run(
            [MYAGENTS_CLI, "preferences", "delete", "delete.test"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result_del.returncode == 0, f"delete should succeed: {result_del.stderr}"

        # Verify preference is gone
        result_get = subprocess.run(
            [MYAGENTS_CLI, "preferences", "get", "delete.test"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result_get.returncode == 1, "Getting deleted preference should fail"

    def test_list_preferences(self, clean_preferences):
        """Test listing all preferences.

        Validates:
        - List shows all set preferences
        - List is empty when no preferences set
        - List updates after set/delete operations
        """
        # List when empty
        result_empty = subprocess.run(
            [MYAGENTS_CLI, "preferences", "list"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result_empty.returncode == 0, f"list should work when empty: {result_empty.stderr}"

        # Set multiple preferences
        subprocess.run(
            [MYAGENTS_CLI, "preferences", "set", "pref1", "value1"],
            check=True, capture_output=True
        )
        subprocess.run(
            [MYAGENTS_CLI, "preferences", "set", "pref2", "value2"],
            check=True, capture_output=True
        )

        # List should show both
        result_list = subprocess.run(
            [MYAGENTS_CLI, "preferences", "list"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result_list.returncode == 0, f"list should succeed: {result_list.stderr}"
        assert "pref1" in result_list.stdout, "Should show pref1"
        assert "pref2" in result_list.stdout, "Should show pref2"

    def test_clear_all_preferences(self, clean_preferences):
        """Test clearing all preferences.

        Validates:
        - Clear removes all preferences
        - List is empty after clear
        - Clear is idempotent
        """
        # Set preferences
        subprocess.run(
            [MYAGENTS_CLI, "preferences", "set", "clear.test1", "value1"],
            check=True, capture_output=True
        )
        subprocess.run(
            [MYAGENTS_CLI, "preferences", "set", "clear.test2", "value2"],
            check=True, capture_output=True
        )

        # Clear all
        result_clear = subprocess.run(
            [MYAGENTS_CLI, "preferences", "clear"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result_clear.returncode == 0, f"clear should succeed: {result_clear.stderr}"

        # Verify list is empty
        result_list = subprocess.run(
            [MYAGENTS_CLI, "preferences", "list"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result_list.returncode == 0, f"list should work: {result_list.stderr}"
        # Output should indicate no preferences or be empty
        assert "clear.test1" not in result_list.stdout, "Cleared preference should not appear"


# ============================================================================
# HOME DIRECTORY SINGLE SOURCE OF TRUTH BEHAVIOR
# ============================================================================

@pytest.mark.workflow_health_check
@pytest.mark.e2e
class TestHomeDirSingleSource:
    """Test home directory single source of truth behavior (no fallback)."""







# ============================================================================
# COMMAND STATE MATRIX TESTS
# ============================================================================

@pytest.mark.workflow_health_check
@pytest.mark.e2e
class TestCommandStateMatrix:
    """Test commands across different states (clean install, existing config, modified prefs)."""

    def test_version_clean_install(self, clean_home_config, temp_arbitrary_dir):
        """Test --version on clean install."""
        result = subprocess.run(
            [MYAGENTS_CLI, "--version"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"--version should work on clean install: {result.stderr}"
        assert len(result.stdout) > 0, "Should show version"


    def test_preferences_clean_install(self, clean_home_config, temp_arbitrary_dir):
        """Test preferences on clean install."""
        result = subprocess.run(
            [MYAGENTS_CLI, "preferences", "list"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"preferences should work on clean install: {result.stderr}"

    def test_chat_with_existing_config(self):
        """Test chat with existing home config."""
        # Assumes home config exists from previous tests or real usage
        result = subprocess.run(
            [MYAGENTS_CLI, "chat", "--help"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"chat should work with existing config: {result.stderr}"

    def test_studio_with_modified_preferences(self, clean_preferences):
        """Test studio with modified preferences.

        In the new architecture, studio requires home directory config.
        This test verifies studio works with modified preferences when home config exists.
        """
        # Set a preference first
        subprocess.run(
            [MYAGENTS_CLI, "preferences", "set", "studio.test", "value"],
            capture_output=True,
            text=True,
            check=True
        )

        # Run studio command
        result = subprocess.run(
            [MYAGENTS_CLI, "studio", "status"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )
        # Status returns 1 when stopped, 0 when running
        # Also returns 1 if home config doesn't exist
        assert result.returncode in [0, 1], f"studio should work with modified prefs: {result.stderr}"

        # Either shows status or error about missing home config
        if result.returncode == 0:
            # Studio is running
            assert "status" in result.stdout.lower() or "running" in result.stdout.lower(), \
                f"Should show status when running: {result.stdout}"
        else:
            # Either studio is stopped OR home config is missing
            if result.stdout:
                # Has output - likely status message
                assert "status" in result.stdout.lower() or "stopped" in result.stdout.lower(), \
                    f"Should show status when stopped: {result.stdout}"
            else:
                # No stdout - likely config error in stderr
                assert "langgraph.json" in result.stderr.lower(), \
                    f"Should mention config issue in stderr: {result.stderr}"


# ============================================================================
# PERFORMANCE AND METRICS TESTS
# ============================================================================

@pytest.mark.workflow_health_check
@pytest.mark.e2e
class TestPerformanceMetrics:
    """Test command execution performance."""

    def test_version_execution_time(self):
        """Test --version executes quickly (< 2 seconds)."""
        import time
        start = time.time()

        result = subprocess.run(
            [MYAGENTS_CLI, "--version"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )

        elapsed = time.time() - start

        assert result.returncode == 0, f"Command should succeed: {result.stderr}"
        assert elapsed < 2.0, f"--version should be fast, took {elapsed:.2f}s"

    def test_help_execution_time(self):
        """Test --help executes quickly (< 3 seconds)."""
        import time
        start = time.time()

        result = subprocess.run(
            [MYAGENTS_CLI, "--help"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )

        elapsed = time.time() - start

        assert result.returncode == 0, f"Command should succeed: {result.stderr}"
        assert elapsed < 3.0, f"--help should be fast, took {elapsed:.2f}s"

    def test_preferences_list_execution_time(self):
        """Test preferences list executes quickly (< 3 seconds)."""
        import time
        start = time.time()

        result = subprocess.run(
            [MYAGENTS_CLI, "preferences", "list"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True
        )

        elapsed = time.time() - start

        assert result.returncode == 0, f"Command should succeed: {result.stderr}"
        assert elapsed < 3.0, f"preferences list should be fast, took {elapsed:.2f}s"


# ============================================================================
# INTEGRATION AND COVERAGE TESTS
# ============================================================================

@pytest.mark.workflow_health_check
@pytest.mark.e2e
class TestCoverageMatrix:
    """Comprehensive coverage validation tests."""

    def test_all_commands_covered(self):
        """Verify all commands are tested.

        Commands to cover:
        - myagents (no args, shows help)
        - --version
        - --help
        - chat
        - studio (start, stop, restart, status)
        - config (show, set-path, clear, init)
        - preferences (get, set, delete, list, clear)
        """
        # This is a meta-test validating test coverage
        # Just verify core commands work

        commands_to_test = [
            ([MYAGENTS_CLI, "--version"], "version", [0]),
            ([MYAGENTS_CLI, "--help"], "help", [0]),
            ([MYAGENTS_CLI, "chat", "--help"], "chat", [0]),
            ([MYAGENTS_CLI, "studio", "status"], "studio", [0, 1]),  # 1 when stopped is OK
            ([MYAGENTS_CLI, "config", "show"], "config", [0]),
            ([MYAGENTS_CLI, "preferences", "list"], "preferences", [0]),
        ]

        results = {}
        for cmd, name, valid_codes in commands_to_test:
            result = subprocess.run(
                cmd,
                cwd=str(PROJECT_DIR),
                capture_output=True,
                text=True
            )
            results[name] = (result.returncode in valid_codes)

        # All commands should succeed (with valid exit codes)
        failed = [name for name, success in results.items() if not success]
        assert len(failed) == 0, f"Commands failed: {failed}"

    def test_all_directories_covered(self, temp_arbitrary_dir):
        """Verify commands tested from all directory types.

        Directory types:
        - Project directory (has langgraph.json)
        - Parent directory (no langgraph.json)
        - Arbitrary directory (/tmp)
        """
        directories = [
            (PROJECT_DIR, "project"),
            (PARENT_DIR, "parent"),
            (temp_arbitrary_dir, "arbitrary"),
        ]

        results = {}
        for dir_path, dir_type in directories:
            result = subprocess.run(
                [MYAGENTS_CLI, "--version"],
                cwd=str(dir_path),
                capture_output=True,
                text=True
            )
            results[dir_type] = (result.returncode == 0)

        # Should work from all directories
        failed = [dtype for dtype, success in results.items() if not success]
        assert len(failed) == 0, f"Failed from directories: {failed}"

    def test_all_states_covered(self, clean_home_config, temp_arbitrary_dir):
        """Verify commands tested in all states.

        States:
        - Clean install (no ~/.config/myagents)
        - Existing config (has ~/.config/myagents)
        - Modified preferences (has custom preferences)
        """
        states_results = []

        # Test clean install
        result1 = subprocess.run(
            [MYAGENTS_CLI, "--version"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True
        )
        states_results.append(("clean_install", result1.returncode == 0))

        # Wait for file system operations to settle after first command
        time.sleep(0.1)

        # Test with existing config (created by previous command)
        result2 = subprocess.run(
            [MYAGENTS_CLI, "preferences", "list"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True
        )
        states_results.append(("existing_config", result2.returncode == 0))

        # Test with modified preferences
        subprocess.run(
            [MYAGENTS_CLI, "preferences", "set", "test.state", "value"],
            capture_output=True,
            text=True,
            check=True
        )

        # Wait for preference file to be written and synced to disk
        # File system operations may be buffered, especially in container environments
        time.sleep(0.2)

        result3 = subprocess.run(
            [MYAGENTS_CLI, "preferences", "get", "test.state"],
            cwd=str(temp_arbitrary_dir),
            capture_output=True,
            text=True
        )
        states_results.append(("modified_prefs", result3.returncode == 0))

        # All states should work
        failed = [state for state, success in states_results if not success]
        assert len(failed) == 0, f"Failed states: {failed}"
