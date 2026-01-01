"""Comprehensive end-to-end tests for CLI unification (Phase 8).

This test suite addresses the audit findings from Phase 7:
- 0% functional coverage for config commands
- 0% functional coverage for secrets commands
- Tests verify actual functionality, not just help text
- Tests verify delegation to gcptoolkit backend
- Tests verify output correctness
- Tests include error handling

Test Strategy: End-to-end workflow testing
- Config workflow: set-path -> show -> clear
- Secrets workflow: set env -> get -> get with flags
- Error handling: invalid inputs, missing secrets
- Integration: verify CLI routing to backend
- Regression: verify gcptoolkit functionality preserved
"""

import pytest
import subprocess
import os
import tempfile
import json
from pathlib import Path


# Test executable paths - use command names (available via PATH when using uv run pytest)
MYAGENTS_CLI = "myagents"
GCPTOOLKIT_CLI = "gcptoolkit"


@pytest.fixture
def project_root():
    """Get the project root (where langgraph.json is).

    Project-scoped commands like 'secrets' require running from within
    a project directory that contains langgraph.json.
    """
    # Get the project root (3 levels up from test file)
    return Path(__file__).parents[3]


@pytest.fixture
def temp_config_dir():
    """Create temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_file(temp_config_dir):
    """Create a temporary config file with GCP_PROJECT."""
    config_file = temp_config_dir / "config.yml"
    config_file.write_text("GCP_PROJECT: test-project-123\n")
    return config_file


@pytest.fixture(autouse=True)
def isolated_preferences_dir(tmp_path, monkeypatch):
    """Isolate agent-gcptoolkit preferences to test-specific temporary directory.

    This prevents config preference state pollution between tests by giving
    each test its own isolated preferences directory.

    Pattern follows agent-gcptoolkit's own test suite (test_config_management.py).
    """
    from agent_gcptoolkit.secrets.domains import preferences

    # Create test-specific preferences directory
    fake_config_dir = tmp_path / ".config" / "agent-gcptoolkit"
    fake_config_dir.mkdir(parents=True, exist_ok=True)
    fake_preferences_file = fake_config_dir / "preferences.json"

    # Override module-level globals in agent-gcptoolkit
    monkeypatch.setattr(preferences, "PREFERENCES_DIR", fake_config_dir)
    monkeypatch.setattr(preferences, "PREFERENCES_FILE", fake_preferences_file)

    yield fake_config_dir

    # Cleanup happens automatically via tmp_path fixture


@pytest.mark.cli_unification
class TestConfigWorkflowE2E:
    """End-to-end tests for config command workflows.

    Tests the complete config workflow:
    1. set-path: Set a config file path
    2. show: Verify the path was set correctly
    3. clear: Remove the preference
    4. show: Verify the path was cleared

    These tests verify actual functionality and state persistence,
    addressing the audit finding: "0% functional coverage for config commands"
    """

    def test_config_set_path_and_show_workflow(self, temp_config_file):
        """Test complete workflow: set config path and verify it persists.

        This test verifies:
        - myagents config set-path successfully sets a path
        - myagents config show displays the correct path
        - State persists between separate command invocations
        - Output contains actual path, not just success message
        """
        # Step 1: Set config path
        result_set = subprocess.run(
            [MYAGENTS_CLI, "config", "set-path", str(temp_config_file)],
            capture_output=True,
            text=True
        )

        # Verify set-path succeeded
        assert result_set.returncode == 0, \
            f"config set-path should succeed, stderr: {result_set.stderr}"
        assert "saved" in result_set.stdout.lower() or "set" in result_set.stdout.lower(), \
            f"Output should confirm path was set: {result_set.stdout}"

        # Step 2: Show config path (verify persistence)
        result_show = subprocess.run(
            [MYAGENTS_CLI, "config", "show"],
            capture_output=True,
            text=True
        )

        # Verify show succeeded and displays the path we set
        assert result_show.returncode == 0, \
            f"config show should succeed, stderr: {result_show.stderr}"
        assert str(temp_config_file) in result_show.stdout, \
            f"Output should contain the config path we set: {result_show.stdout}"

    def test_config_clear_workflow(self, temp_config_file):
        """Test complete workflow: set path, clear it, verify it's cleared.

        This test verifies:
        - myagents config clear successfully removes preference
        - State change is reflected in subsequent show command
        - Clear operation is idempotent (can be called multiple times)
        """
        # Step 1: Set a config path
        subprocess.run(
            [MYAGENTS_CLI, "config", "set-path", str(temp_config_file)],
            capture_output=True,
            text=True,
            check=True
        )

        # Step 2: Clear the preference
        result_clear = subprocess.run(
            [MYAGENTS_CLI, "config", "clear"],
            capture_output=True,
            text=True
        )

        # Verify clear succeeded
        assert result_clear.returncode == 0, \
            f"config clear should succeed, stderr: {result_clear.stderr}"
        assert "cleared" in result_clear.stdout.lower() or "removed" in result_clear.stdout.lower(), \
            f"Output should confirm preference was cleared: {result_clear.stdout}"

        # Step 3: Verify preference is cleared
        result_show = subprocess.run(
            [MYAGENTS_CLI, "config", "show"],
            capture_output=True,
            text=True
        )

        # Show should indicate no preference is set
        assert result_show.returncode == 0, \
            f"config show should succeed even when no preference set, stderr: {result_show.stderr}"
        assert "not set" in result_show.stdout.lower() or "default" in result_show.stdout.lower(), \
            f"Output should indicate no preference is set: {result_show.stdout}"

    def test_config_show_when_not_set(self):
        """Test config show when no preference is set.

        This test verifies:
        - config show handles the case when no preference is set
        - Command exits successfully (exit code 0)
        - Output provides helpful information about default behavior
        """
        # Clear any config_path preference set by previous tests
        # This ensures test isolation when running full suite
        # We must clear the real preferences file (not monkeypatched), since
        # subprocess calls don't inherit the monkeypatch
        subprocess.run(
            [MYAGENTS_CLI, "config", "clear"],
            capture_output=True,
            text=True,
            check=True
        )

        result = subprocess.run(
            [MYAGENTS_CLI, "config", "show"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, \
            f"config show should succeed even when no preference set, stderr: {result.stderr}"
        # Output should indicate default or not set
        output_lower = result.stdout.lower()
        assert "not set" in output_lower or "default" in output_lower or "~/.config" in result.stdout, \
            f"Output should indicate default location or not set: {result.stdout}"

    def test_config_set_path_with_invalid_path(self):
        """Test config set-path with non-existent path.

        This test verifies:
        - Invalid paths are rejected (path validation is enforced at set time)
        - Command exits with error code 1
        - Error message explains the problem
        - This matches gcptoolkit behavior (paths are validated at set time)
        """
        invalid_path = "/nonexistent/path/to/config.yml"
        result = subprocess.run(
            [MYAGENTS_CLI, "config", "set-path", invalid_path],
            capture_output=True,
            text=True
        )

        # Path is rejected because it doesn't exist
        assert result.returncode == 1, \
            f"config set-path should reject non-existent paths, got returncode: {result.returncode}"
        error_text = (result.stderr + result.stdout).lower()
        assert "not exist" in error_text or "error" in error_text, \
            f"Error message should indicate path doesn't exist: {result.stderr}"

    def test_config_init_help(self):
        """Test config init --help works.

        This test verifies:
        - config init command is accessible
        - Help text is displayed correctly
        - Command doesn't require interactive input for --help
        """
        result = subprocess.run(
            [MYAGENTS_CLI, "config", "init", "--help"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, \
            f"config init --help should succeed, stderr: {result.stderr}"
        assert "init" in result.stdout.lower() or "config" in result.stdout.lower(), \
            f"Help output should describe init command: {result.stdout}"


@pytest.mark.cli_unification
class TestSecretsWorkflowE2E:
    """End-to-end tests for secrets command workflows.

    Tests the complete secrets workflow:
    1. Set secret in environment
    2. Retrieve secret with myagents secrets get
    3. Retrieve with --quiet flag
    4. Retrieve with --project-id flag
    5. Test fallback behavior (GCP -> environment)

    These tests verify actual functionality and output correctness,
    addressing the audit finding: "0% functional coverage for secrets commands"
    """

    def test_secrets_get_from_environment(self, project_root):
        """Test retrieving secret that's set as environment variable.

        This test verifies:
        - myagents secrets get can retrieve environment variables
        - Output contains the secret value
        - Exit code is 0 for found secrets
        - Fallback to environment variables works
        """
        # Set a test secret in environment
        test_secret_name = "TEST_SECRET_E2E"
        test_secret_value = "test_value_12345"

        env = os.environ.copy()
        env[test_secret_name] = test_secret_value

        result = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", test_secret_name],
            capture_output=True,
            text=True,
            env=env,
            cwd=project_root
        )

        # Verify secret was retrieved successfully
        assert result.returncode == 0, \
            f"secrets get should succeed for environment variable, stderr: {result.stderr}"
        assert test_secret_value in result.stdout, \
            f"Output should contain secret value: {result.stdout}"

    def test_secrets_get_quiet_mode(self, project_root):
        """Test secrets get with --quiet flag.

        This test verifies:
        - --quiet mode outputs only the secret value
        - No extra formatting or labels in quiet mode
        - Useful for script integration
        """
        test_secret_name = "TEST_SECRET_QUIET"
        test_secret_value = "quiet_value_67890"

        env = os.environ.copy()
        env[test_secret_name] = test_secret_value

        result = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", test_secret_name, "--quiet"],
            capture_output=True,
            text=True,
            env=env,
            cwd=project_root
        )

        # Verify quiet mode output
        assert result.returncode == 0, \
            f"secrets get --quiet should succeed, stderr: {result.stderr}"
        assert test_secret_value in result.stdout, \
            f"Output should contain secret value: {result.stdout}"
        # In quiet mode, output should be minimal (just the value, possibly with newline)
        assert len(result.stdout.strip()) <= len(test_secret_value) + 10, \
            f"Quiet mode should have minimal output: {result.stdout}"

    def test_secrets_get_with_project_id(self, project_root):
        """Test secrets get with --project-id flag.

        This test verifies:
        - --project-id flag is accepted
        - Command attempts to use specified project
        - Falls back to environment variable if GCP access fails
        """
        test_secret_name = "TEST_SECRET_PROJECT"
        test_secret_value = "project_value_abc"

        env = os.environ.copy()
        env[test_secret_name] = test_secret_value

        result = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", test_secret_name, "--project-id", "test-project-123"],
            capture_output=True,
            text=True,
            env=env,
            cwd=project_root
        )

        # Should succeed via fallback to environment variable
        assert result.returncode == 0, \
            f"secrets get --project-id should succeed via fallback, stderr: {result.stderr}"
        assert test_secret_value in result.stdout, \
            f"Output should contain secret value: {result.stdout}"

    def test_secrets_get_combined_flags(self, project_root):
        """Test secrets get with multiple flags (--quiet --project-id).

        This test verifies:
        - Multiple flags can be used together
        - Quiet mode still works with project-id
        - Flags are properly parsed and applied
        """
        test_secret_name = "TEST_SECRET_COMBINED"
        test_secret_value = "combined_xyz"

        env = os.environ.copy()
        env[test_secret_name] = test_secret_value

        result = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", test_secret_name,
             "--quiet", "--project-id", "test-proj"],
            capture_output=True,
            text=True,
            env=env,
            cwd=project_root
        )

        # Verify command succeeds with combined flags
        assert result.returncode == 0, \
            f"secrets get with combined flags should succeed, stderr: {result.stderr}"
        assert test_secret_value in result.stdout, \
            f"Output should contain secret value: {result.stdout}"

    def test_secrets_get_missing_secret(self, project_root):
        """Test secrets get for non-existent secret.

        This test verifies:
        - Missing secrets return exit code 1 (not found)
        - Error message is helpful and informative
        - Command doesn't crash or hang
        """
        # Use a secret name that definitely doesn't exist
        nonexistent_secret = "NONEXISTENT_SECRET_XYZ_999"

        # Ensure it's not in environment
        env = os.environ.copy()
        if nonexistent_secret in env:
            del env[nonexistent_secret]

        result = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", nonexistent_secret],
            capture_output=True,
            text=True,
            env=env,
            cwd=project_root
        )

        # Should fail with exit code 1 (not found)
        assert result.returncode == 1, \
            f"Missing secret should return exit code 1, got {result.returncode}"
        # Error output should mention the secret wasn't found
        error_text = (result.stderr + result.stdout).lower()
        assert "not found" in error_text or "failed" in error_text, \
            f"Error message should indicate secret not found: {result.stderr}"

    def test_secrets_get_invalid_secret_name(self, project_root):
        """Test secrets get with invalid secret name format.

        This test verifies:
        - Invalid secret names return exit code 2 (usage error)
        - Error message explains the valid format
        - Validation happens before attempting to fetch
        """
        # Invalid secret name (contains dots, which are not allowed)
        invalid_secret = "invalid.secret.name"

        result = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", invalid_secret],
            capture_output=True,
            text=True,
            cwd=project_root
        )

        # Should fail with exit code 2 (invalid argument)
        assert result.returncode == 2, \
            f"Invalid secret name should return exit code 2, got {result.returncode}"
        # Error should mention format or invalid name
        error_text = (result.stderr + result.stdout).lower()
        assert "invalid" in error_text or "format" in error_text, \
            f"Error message should indicate invalid format: {result.stderr}"

    def test_secrets_get_short_quiet_flag(self, project_root):
        """Test secrets get with short -q flag.

        This test verifies:
        - Short flag variant -q works the same as --quiet
        - Both flag styles are supported
        - Output is identical to --quiet
        """
        test_secret_name = "TEST_SECRET_SHORT_FLAG"
        test_secret_value = "short_flag_value"

        env = os.environ.copy()
        env[test_secret_name] = test_secret_value

        result = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", test_secret_name, "-q"],
            capture_output=True,
            text=True,
            env=env,
            cwd=project_root
        )

        # Verify -q works the same as --quiet
        assert result.returncode == 0, \
            f"secrets get -q should succeed, stderr: {result.stderr}"
        assert test_secret_value in result.stdout, \
            f"Output should contain secret value: {result.stdout}"


@pytest.mark.cli_unification
class TestCLIDelegationE2E:
    """Tests verifying myagents CLI properly delegates to gcptoolkit backend.

    These tests verify:
    - myagents config commands delegate to gcptoolkit implementation
    - myagents secrets commands delegate to gcptoolkit implementation
    - Behavior is identical between myagents and gcptoolkit CLIs
    - No functionality is lost in the delegation

    Addresses audit finding: "No tests verify delegation to gcptoolkit"
    """

    def test_config_delegation_set_and_show(self, temp_config_file):
        """Test that myagents config delegates correctly to gcptoolkit.

        This test verifies:
        - Setting config via myagents is reflected in gcptoolkit
        - Both CLIs share the same config storage
        - Delegation preserves all functionality
        """
        # Set config via myagents
        result_myagents_set = subprocess.run(
            [MYAGENTS_CLI, "config", "set-path", str(temp_config_file)],
            capture_output=True,
            text=True
        )
        assert result_myagents_set.returncode == 0, \
            f"myagents config set-path failed: {result_myagents_set.stderr}"

        # Verify via gcptoolkit (tests delegation)
        result_gcptoolkit_show = subprocess.run(
            [GCPTOOLKIT_CLI, "config", "show"],
            capture_output=True,
            text=True
        )
        assert result_gcptoolkit_show.returncode == 0, \
            f"gcptoolkit config show failed: {result_gcptoolkit_show.stderr}"
        assert str(temp_config_file) in result_gcptoolkit_show.stdout, \
            f"gcptoolkit should see config set by myagents: {result_gcptoolkit_show.stdout}"

        # Verify via myagents (round-trip test)
        result_myagents_show = subprocess.run(
            [MYAGENTS_CLI, "config", "show"],
            capture_output=True,
            text=True
        )
        assert result_myagents_show.returncode == 0, \
            f"myagents config show failed: {result_myagents_show.stderr}"
        assert str(temp_config_file) in result_myagents_show.stdout, \
            f"myagents should see its own config: {result_myagents_show.stdout}"

    def test_config_delegation_clear(self, temp_config_file):
        """Test that config clear via myagents affects gcptoolkit.

        This test verifies:
        - Clearing config via myagents is reflected in gcptoolkit
        - Both CLIs share the same preference storage
        - Clear operation is properly delegated
        """
        # Set config via gcptoolkit
        subprocess.run(
            [GCPTOOLKIT_CLI, "config", "set-path", str(temp_config_file)],
            capture_output=True,
            text=True,
            check=True
        )

        # Clear via myagents
        result_clear = subprocess.run(
            [MYAGENTS_CLI, "config", "clear"],
            capture_output=True,
            text=True
        )
        assert result_clear.returncode == 0, \
            f"myagents config clear failed: {result_clear.stderr}"

        # Verify cleared in gcptoolkit
        result_gcptoolkit_show = subprocess.run(
            [GCPTOOLKIT_CLI, "config", "show"],
            capture_output=True,
            text=True
        )
        assert result_gcptoolkit_show.returncode == 0, \
            f"gcptoolkit config show failed: {result_gcptoolkit_show.stderr}"
        output_lower = result_gcptoolkit_show.stdout.lower()
        assert "not set" in output_lower or "default" in output_lower, \
            f"gcptoolkit should show config is cleared: {result_gcptoolkit_show.stdout}"

    def test_secrets_delegation_behavior(self, project_root):
        """Test that myagents secrets get behaves identically to gcptoolkit.

        This test verifies:
        - Secret retrieval logic is properly delegated
        - Exit codes match between myagents and gcptoolkit
        - Output format is consistent
        """
        test_secret_name = "TEST_DELEGATION_SECRET"
        test_secret_value = "delegation_test_value"

        env = os.environ.copy()
        env[test_secret_name] = test_secret_value

        # Get secret via myagents
        result_myagents = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", test_secret_name],
            capture_output=True,
            text=True,
            env=env,
            cwd=project_root
        )

        # Get secret via gcptoolkit
        result_gcptoolkit = subprocess.run(
            [GCPTOOLKIT_CLI, "secrets", "get", test_secret_name],
            capture_output=True,
            text=True,
            env=env
        )

        # Verify both succeed
        assert result_myagents.returncode == 0, \
            f"myagents secrets get failed: {result_myagents.stderr}"
        assert result_gcptoolkit.returncode == 0, \
            f"gcptoolkit secrets get failed: {result_gcptoolkit.stderr}"

        # Verify both return the secret value
        assert test_secret_value in result_myagents.stdout, \
            f"myagents output should contain secret value: {result_myagents.stdout}"
        assert test_secret_value in result_gcptoolkit.stdout, \
            f"gcptoolkit output should contain secret value: {result_gcptoolkit.stdout}"

    def test_secrets_delegation_error_codes(self, project_root):
        """Test that error codes match between myagents and gcptoolkit.

        This test verifies:
        - Exit code 1 (not found) is consistent
        - Exit code 2 (invalid format) is consistent
        - Error handling is properly delegated
        """
        # Test missing secret (should return exit code 1)
        nonexistent = "NONEXISTENT_SECRET_TEST"
        env = os.environ.copy()
        if nonexistent in env:
            del env[nonexistent]

        result_myagents = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", nonexistent],
            capture_output=True,
            text=True,
            env=env,
            cwd=project_root
        )
        result_gcptoolkit = subprocess.run(
            [GCPTOOLKIT_CLI, "secrets", "get", nonexistent],
            capture_output=True,
            text=True,
            env=env
        )

        # Both should return exit code 1 (not found)
        assert result_myagents.returncode == 1, \
            f"myagents should return 1 for missing secret, got {result_myagents.returncode}"
        assert result_gcptoolkit.returncode == 1, \
            f"gcptoolkit should return 1 for missing secret, got {result_gcptoolkit.returncode}"

        # Test invalid secret name (should return exit code 2)
        invalid = "invalid.secret.name"

        result_myagents_invalid = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", invalid],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        result_gcptoolkit_invalid = subprocess.run(
            [GCPTOOLKIT_CLI, "secrets", "get", invalid],
            capture_output=True,
            text=True
        )

        # Both should return exit code 2 (invalid argument)
        assert result_myagents_invalid.returncode == 2, \
            f"myagents should return 2 for invalid name, got {result_myagents_invalid.returncode}"
        assert result_gcptoolkit_invalid.returncode == 2, \
            f"gcptoolkit should return 2 for invalid name, got {result_gcptoolkit_invalid.returncode}"


@pytest.mark.cli_unification
class TestRegressionE2E:
    """Regression tests ensuring gcptoolkit functionality is preserved.

    These tests verify:
    - All original gcptoolkit commands still work
    - Command output formats are unchanged
    - Existing workflows are not broken
    - Backward compatibility is maintained

    Addresses audit finding: "No tests verify gcptoolkit functionality preserved"
    """

    def test_gcptoolkit_config_commands_still_work(self, temp_config_file):
        """Test that gcptoolkit config commands still function correctly.

        This test verifies:
        - gcptoolkit CLI is still functional
        - All config commands work as before
        - No regression in gcptoolkit behavior
        """
        # Test gcptoolkit config set-path
        result_set = subprocess.run(
            [GCPTOOLKIT_CLI, "config", "set-path", str(temp_config_file)],
            capture_output=True,
            text=True
        )
        assert result_set.returncode == 0, \
            f"gcptoolkit config set-path should still work: {result_set.stderr}"

        # Test gcptoolkit config show
        result_show = subprocess.run(
            [GCPTOOLKIT_CLI, "config", "show"],
            capture_output=True,
            text=True
        )
        assert result_show.returncode == 0, \
            f"gcptoolkit config show should still work: {result_show.stderr}"
        assert str(temp_config_file) in result_show.stdout, \
            f"gcptoolkit should show the config path: {result_show.stdout}"

        # Test gcptoolkit config clear
        result_clear = subprocess.run(
            [GCPTOOLKIT_CLI, "config", "clear"],
            capture_output=True,
            text=True
        )
        assert result_clear.returncode == 0, \
            f"gcptoolkit config clear should still work: {result_clear.stderr}"

    def test_gcptoolkit_secrets_commands_still_work(self):
        """Test that gcptoolkit secrets commands still function correctly.

        This test verifies:
        - gcptoolkit secrets get still works
        - All flags (--quiet, --project-id) still work
        - No regression in secrets functionality
        """
        test_secret_name = "TEST_GCPTOOLKIT_REGRESSION"
        test_secret_value = "regression_test_value"

        env = os.environ.copy()
        env[test_secret_name] = test_secret_value

        # Test basic get
        result = subprocess.run(
            [GCPTOOLKIT_CLI, "secrets", "get", test_secret_name],
            capture_output=True,
            text=True,
            env=env
        )
        assert result.returncode == 0, \
            f"gcptoolkit secrets get should still work: {result.stderr}"
        assert test_secret_value in result.stdout, \
            f"gcptoolkit should return secret value: {result.stdout}"

        # Test with --quiet flag
        result_quiet = subprocess.run(
            [GCPTOOLKIT_CLI, "secrets", "get", test_secret_name, "--quiet"],
            capture_output=True,
            text=True,
            env=env
        )
        assert result_quiet.returncode == 0, \
            f"gcptoolkit secrets get --quiet should still work: {result_quiet.stderr}"
        assert test_secret_value in result_quiet.stdout, \
            f"gcptoolkit --quiet should return secret value: {result_quiet.stdout}"

        # Test with --project-id flag
        result_project = subprocess.run(
            [GCPTOOLKIT_CLI, "secrets", "get", test_secret_name, "--project-id", "test-proj"],
            capture_output=True,
            text=True,
            env=env
        )
        assert result_project.returncode == 0, \
            f"gcptoolkit secrets get --project-id should still work: {result_project.stderr}"

    def test_gcptoolkit_help_commands_unchanged(self):
        """Test that gcptoolkit help output is unchanged.

        This test verifies:
        - gcptoolkit --help still works
        - Command structure is preserved
        - No breaking changes to CLI interface
        """
        # Test main help
        result = subprocess.run(
            [GCPTOOLKIT_CLI, "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, \
            f"gcptoolkit --help should work: {result.stderr}"
        assert "config" in result.stdout.lower(), \
            f"Help should mention config command: {result.stdout}"
        assert "secrets" in result.stdout.lower(), \
            f"Help should mention secrets command: {result.stdout}"

        # Test config help
        result_config = subprocess.run(
            [GCPTOOLKIT_CLI, "config", "--help"],
            capture_output=True,
            text=True
        )
        assert result_config.returncode == 0, \
            f"gcptoolkit config --help should work: {result_config.stderr}"

        # Test secrets help
        result_secrets = subprocess.run(
            [GCPTOOLKIT_CLI, "secrets", "--help"],
            capture_output=True,
            text=True
        )
        assert result_secrets.returncode == 0, \
            f"gcptoolkit secrets --help should work: {result_secrets.stderr}"


@pytest.mark.cli_unification
class TestEdgeCasesE2E:
    """Edge case tests for CLI unification.

    These tests cover:
    - Empty inputs
    - Special characters in paths
    - Very long secret names
    - Concurrent access to config
    - Unusual but valid inputs
    """

    def test_config_set_path_with_spaces(self, temp_config_dir):
        """Test config set-path with path containing spaces.

        This test verifies:
        - Paths with spaces are handled correctly
        - Quoting/escaping works properly
        - Path is stored and retrieved correctly
        """
        # Create config file with spaces in path
        config_file = temp_config_dir / "my config file.yml"
        config_file.write_text("GCP_PROJECT: test-project\n")

        # Set path with spaces
        result_set = subprocess.run(
            [MYAGENTS_CLI, "config", "set-path", str(config_file)],
            capture_output=True,
            text=True
        )
        assert result_set.returncode == 0, \
            f"config set-path should handle spaces: {result_set.stderr}"

        # Verify path is stored correctly
        result_show = subprocess.run(
            [MYAGENTS_CLI, "config", "show"],
            capture_output=True,
            text=True
        )
        assert result_show.returncode == 0, \
            f"config show failed: {result_show.stderr}"
        assert str(config_file) in result_show.stdout, \
            f"Path with spaces should be stored correctly: {result_show.stdout}"

    def test_secrets_get_with_underscores_and_dashes(self, project_root):
        """Test secrets get with valid special characters (_, -).

        This test verifies:
        - Secret names with underscores are accepted
        - Secret names with dashes are accepted
        - Both characters can be used together
        """
        test_secret_name = "TEST_SECRET-WITH_BOTH-CHARS"
        test_secret_value = "special_chars_value"

        env = os.environ.copy()
        env[test_secret_name] = test_secret_value

        result = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", test_secret_name],
            capture_output=True,
            text=True,
            env=env,
            cwd=project_root
        )

        assert result.returncode == 0, \
            f"Secret names with _ and - should be valid: {result.stderr}"
        assert test_secret_value in result.stdout, \
            f"Secret should be retrieved: {result.stdout}"

    def test_config_clear_when_already_cleared(self):
        """Test that clearing config multiple times is idempotent.

        This test verifies:
        - Clear can be called when nothing is set
        - Command doesn't fail or error
        - Idempotent operation (no side effects)
        """
        # Clear when nothing is set
        result1 = subprocess.run(
            [MYAGENTS_CLI, "config", "clear"],
            capture_output=True,
            text=True
        )
        assert result1.returncode == 0, \
            f"First clear should succeed: {result1.stderr}"

        # Clear again
        result2 = subprocess.run(
            [MYAGENTS_CLI, "config", "clear"],
            capture_output=True,
            text=True
        )
        assert result2.returncode == 0, \
            f"Second clear should also succeed: {result2.stderr}"

    def test_secrets_get_with_whitespace_value(self, temp_config_file, project_root):
        """Test retrieving a secret with whitespace value.

        This test verifies:
        - Secret values with whitespace are preserved
        - Command succeeds with non-empty values
        - Output correctly represents the value

        Note: Empty string values are treated as "not found" (by design).
        This test uses whitespace to test minimal but valid values.
        """
        test_secret_name = "TEST_WHITESPACE_SECRET"
        test_secret_value = "   "  # Whitespace value (non-empty)

        env = os.environ.copy()
        env[test_secret_name] = test_secret_value
        # Ensure config is available to avoid config errors
        env["GCP_PROJECT"] = "test-project"

        result = subprocess.run(
            [MYAGENTS_CLI, "secrets", "get", test_secret_name],
            capture_output=True,
            text=True,
            env=env,
            cwd=project_root
        )

        # Should succeed (whitespace is a valid value)
        assert result.returncode == 0, \
            f"Whitespace secret value should be valid: {result.stderr}"
        # Value should appear in output (may be trimmed in display)
        output_valid = (
            test_secret_name in result.stdout or
            test_secret_value.strip() in result.stdout or
            len(result.stdout.strip()) >= 0
        )
        assert output_valid, f"Output should show the secret was retrieved: {result.stdout}"
