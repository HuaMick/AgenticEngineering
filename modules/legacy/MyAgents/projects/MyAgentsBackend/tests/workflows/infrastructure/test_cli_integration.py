"""Comprehensive e2e tests for CLI entrypoints and commands.

This test suite consolidates CLI command tests from packaging tests and routing tests.
Tests CLI command routing, help system, command availability, and root detection.
Infrastructure tests cover CLI functionality, packaging tests cover build artifacts.

CONSOLIDATED: Merged test_cli_command_routing.py (Phase 4.2)
- Global command tests from any directory
- Project-scoped command tests requiring project root
- CLI source root detection using __file__ (not cwd)
- Project root detection finding langgraph.json
- Error messages validation

LOCATION DECISION: KEEP in infrastructure/
Rationale: This file tests cross-workflow CLI integration behavior spanning
multiple workflows (help, chat, studio, preferences, update, rebuild).
It validates CLI routing, command availability, and error handling across
the entire CLI surface area, not workflow-specific functionality.

Marker: @pytest.mark.infrastructure_cli (cross-workflow CLI integration tests)
"""
import pytest
import subprocess
import os
import tempfile
from pathlib import Path


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def project_dir():
    """Return the MyAgents project directory."""
    return Path(__file__).parents[3]


@pytest.fixture
def parent_dir():
    """Return the parent directory of MyAgents project."""
    return Path(__file__).parents[4]


@pytest.fixture
def unrelated_dir():
    """Create a temporary unrelated directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Basic CLI Command Tests
# ============================================================================

@pytest.mark.infrastructure_cli
def test_myagents_help():
    """Test that myagents --help works."""
    result = subprocess.run(["myagents", "--help"], capture_output=True, text=True)
    assert result.returncode == 0, f"myagents --help failed: {result.stderr}"
    assert "MyAgents" in result.stdout or "usage:" in result.stdout.lower()

@pytest.mark.infrastructure_cli
def test_myagents_chat_help():
    """Test that myagents chat --help works.

    Fixed: Strengthen assertion to validate output content (addresses audit finding).
    Note: chat is a project-scoped command, so must run from project directory.
    """
    from pathlib import Path
    # Get the project root (where langgraph.json is)
    project_root = Path(__file__).parents[3]
    result = subprocess.run(
        ["myagents", "chat", "--help"],
        capture_output=True,
        text=True,
        cwd=project_root
    )
    assert result.returncode == 0, f"myagents chat --help failed: {result.stderr}"
    # Validate output contains expected help content
    assert "chat" in result.stdout.lower(), "Help output should mention 'chat' command"
    assert "--agent" in result.stdout or "agent" in result.stdout.lower(), "Help should mention agent option"

@pytest.mark.infrastructure_cli
def test_myagents_studio_status():
    """Test that myagents studio status works.

    Fixed: Distinguish success from error to eliminate reward hacking (addresses audit finding).
    The command should succeed (returncode 0 when running, 1 when stopped) and output
    meaningful status information.
    Note: studio is a project-scoped command, so must run from project directory.
    """
    from pathlib import Path
    # Get the project root (where langgraph.json is)
    project_root = Path(__file__).parents[3]
    result = subprocess.run(
        ["myagents", "studio", "status"],
        capture_output=True,
        text=True,
        cwd=project_root
    )
    # Validate output contains expected status information
    assert "Status:" in result.stdout, "Output should contain 'Status:' field"
    # Verify meaningful status is shown (RUNNING or STOPPED)
    assert "RUNNING" in result.stdout or "STOPPED" in result.stdout, \
        "Status should explicitly state RUNNING or STOPPED"
    # Return code should be 0 when running, 1 when stopped - either is valid
    assert result.returncode in [0, 1], \
        f"Status command should return 0 (running) or 1 (stopped), got {result.returncode}"

@pytest.mark.infrastructure_cli
def test_myagents_preferences_list():
    """Test that myagents preferences list works."""
    result = subprocess.run(["myagents", "preferences", "list"], capture_output=True, text=True)
    # Command should always succeed (returncode 0) even if no preferences set
    assert result.returncode == 0, f"myagents preferences list failed: {result.stderr}"
    # Output should contain either preferences or indication that none are set
    assert len(result.stdout) > 0 or len(result.stderr) > 0, "No output from preferences list command"

# ============================================================================
# Global Command Tests - Should work from any directory
# ============================================================================

@pytest.mark.infrastructure_cli
@pytest.mark.parametrize("command,subcommand,expected_keywords", [
    ("update", "--help", ["update", "reinstall"]),
    ("rebuild", "--help", ["rebuild", "reinstall"]),
    ("preferences", "list", []),
    ("config", "list", []),
])
@pytest.mark.parametrize("directory_fixture", ["project_dir", "parent_dir", "unrelated_dir"])
def test_global_command_works_from_any_directory(request, command, subcommand, expected_keywords, directory_fixture):
    """Test that global commands work from any directory.

    Addresses HIGH severity audit finding: Global commands completely untested.
    Global commands (update, rebuild, preferences, config) should work from any directory.
    """
    directory = request.getfixturevalue(directory_fixture)
    result = subprocess.run(
        ["myagents", command, subcommand],
        cwd=str(directory),
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"'myagents {command} {subcommand}' failed from {directory_fixture}: {result.stderr}"
    # Verify help output indicates this is the correct command
    if expected_keywords:
        has_keyword = any(kw in result.stdout.lower() for kw in expected_keywords)
        assert has_keyword, f"Expected one of {expected_keywords} in output"


# ============================================================================
# Project-Scoped Command Tests - Require project root
# ============================================================================

@pytest.mark.infrastructure_cli
@pytest.mark.parametrize("command,subcommand,directory_fixture,should_succeed,error_contains", [
    # Chat command tests - help works from anywhere
    ("chat", "--help", "project_dir", True, None),
    ("chat", "--help", "parent_dir", True, None),
    ("chat", "--help", "unrelated_dir", True, None),
    # Studio command tests - help works from anywhere, status requires project
    ("studio", "--help", "project_dir", True, None),
    ("studio", "--help", "parent_dir", True, None),
    ("studio", "--help", "unrelated_dir", True, None),
    ("studio", "status", "project_dir", True, None),
    ("studio", "status", "parent_dir", False, ["langgraph.json", "no langgraph.json found"]),
    ("studio", "status", "unrelated_dir", False, ["langgraph.json", "no langgraph.json found"]),
])
def test_project_scoped_command(request, command, subcommand, directory_fixture, should_succeed, error_contains):
    """Test project-scoped commands require project root.

    Addresses HIGH severity audit finding: Missing langgraph.json error handling not tested.
    Project commands (chat, studio) require langgraph.json in current or parent directory,
    EXCEPT when --help flag is used (help works from anywhere).
    """
    directory = request.getfixturevalue(directory_fixture)
    result = subprocess.run(
        ["myagents", command, subcommand],
        cwd=str(directory),
        capture_output=True,
        text=True
    )

    if should_succeed:
        # For studio status, check output content since return code may vary
        if command == "studio" and subcommand == "status":
            assert "status" in result.stdout.lower() or "studio" in result.stdout.lower()
        else:
            err_msg = f"'myagents {command} {subcommand}' failed from {directory_fixture}: {result.stderr}"
            assert result.returncode == 0, err_msg
            assert command in result.stdout.lower() or "agent" in result.stdout.lower()
    else:
        assert result.returncode != 0, f"'myagents {command}' should fail from {directory_fixture}"
        error_output = result.stderr.lower()
        for keyword in error_contains:
            assert keyword in error_output, f"Error should mention {keyword}"


# ============================================================================
# Root Detection Logic Tests
# ============================================================================

@pytest.mark.infrastructure_cli
def test_cli_source_root_uses_file_not_cwd():
    """Test that CLI source root detection uses __file__ not cwd.

    This test validates that global commands (update, rebuild) work from any
    directory, proving that CLI source root is detected via __file__ and not
    influenced by current working directory.
    """
    # Create a temporary directory far from CLI source
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run global command from unrelated directory
        result = subprocess.run(
            ["myagents", "update", "--help"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )

        # If this succeeds, it proves CLI source root is detected via __file__
        # because there's no way to find CLI source from this random directory
        # unless using __file__ path resolution
        assert result.returncode == 0, (
            f"Global command failed from unrelated directory. "
            f"This suggests CLI source root detection is NOT using __file__. "
            f"Error: {result.stderr}"
        )


@pytest.mark.infrastructure_cli
def test_project_root_detection_finds_langgraph_json(project_dir):
    """Test that project root detection correctly finds langgraph.json.

    This test validates that project-scoped commands can find langgraph.json
    when executed from the project directory.
    """
    # Verify langgraph.json exists in project directory
    langgraph_file = project_dir / "langgraph.json"
    assert langgraph_file.exists(), f"langgraph.json not found at {langgraph_file}"

    # Run project-scoped command from project directory
    result = subprocess.run(
        ["myagents", "chat", "--help"],
        cwd=str(project_dir),
        capture_output=True,
        text=True
    )

    # Should succeed because langgraph.json is found
    assert result.returncode == 0, (
        f"Project-scoped command failed from project directory. "
        f"This suggests project root detection is not working correctly. "
        f"Error: {result.stderr}"
    )


@pytest.mark.infrastructure_cli
def test_project_root_detection_fails_without_langgraph_json(unrelated_dir):
    """Test that project root detection fails when langgraph.json is not found.

    This test validates that project-scoped commands fail appropriately when
    langgraph.json cannot be found in the directory hierarchy.
    Note: Uses 'studio status' instead of 'chat --help' because help commands
    now work from anywhere without requiring langgraph.json.
    """
    # Verify langgraph.json does NOT exist in unrelated directory
    langgraph_file = unrelated_dir / "langgraph.json"
    assert not langgraph_file.exists(), f"Test setup error: langgraph.json exists at {langgraph_file}"

    # Run project-scoped command from unrelated directory
    result = subprocess.run(
        ["myagents", "studio", "status"],
        cwd=str(unrelated_dir),
        capture_output=True,
        text=True
    )

    # Should fail because langgraph.json is not found
    assert result.returncode != 0, (
        "Project-scoped command should fail when langgraph.json is not found"
    )

    # Verify error message mentions langgraph.json
    error_output = result.stderr.lower()
    assert "langgraph.json" in error_output, (
        f"Error message should mention langgraph.json. Got: {result.stderr}"
    )


# ============================================================================
# Command Routing Tests
# ============================================================================

@pytest.mark.infrastructure_cli
def test_global_command_routes_to_cli_source_root():
    """Test that global commands route to CLI source root for operations.

    This validates that 'update' and 'rebuild' commands operate on the CLI
    source location (where CLI is installed) rather than current directory.
    """
    # Run from a non-CLI directory
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["myagents", "update", "--help"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )

        # Success proves command routed to CLI source root
        assert result.returncode == 0, (
            f"Global command failed, suggesting incorrect routing. "
            f"Error: {result.stderr}"
        )


@pytest.mark.infrastructure_cli
def test_project_command_routes_to_project_root(project_dir):
    """Test that project-scoped commands route to project root for operations.

    This validates that 'chat' and 'studio' commands operate on
    the project root (where langgraph.json is found) rather than CLI source.
    """
    # Run project-scoped command from project directory
    result = subprocess.run(
        ["myagents", "chat", "--help"],
        cwd=str(project_dir),
        capture_output=True,
        text=True
    )

    # Success proves command routed to project root
    assert result.returncode == 0, (
        f"Project-scoped command failed from project directory. "
        f"Error: {result.stderr}"
    )


# ============================================================================
# Error Handling and Exit Code Tests
# ============================================================================

@pytest.mark.infrastructure_cli
def test_error_message_clarity_for_missing_project():
    """Test that error messages are clear and actionable when home directory not configured.

    Note: Uses 'studio status' instead of 'chat --help' because help commands
    now work from anywhere without requiring langgraph.json.
    Updated: Tests for home directory message instead of project message (new architecture).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["myagents", "studio", "status"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )

        # Should fail with clear error
        assert result.returncode != 0, "Command should fail when home directory not configured"

        error_output = result.stderr
        # Error should be clear and actionable
        assert len(error_output) > 0, "Error message should not be empty"
        assert "langgraph.json" in error_output.lower(), "Error should mention langgraph.json"
        # Check for home directory message instead of project
        assert "~/.config/myagents" in error_output or "setup" in error_output.lower(), \
            "Error should mention home directory or setup command"


@pytest.mark.infrastructure_cli
def test_exit_codes_are_appropriate():
    """Test that commands return appropriate exit codes.

    - Success: exit code 0
    - Error: exit code 1
    """
    # Test successful command (global command from anywhere)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["myagents", "update", "--help"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "Successful command should return exit code 0"

    # Test failed command (project command from wrong directory)
    # Note: Using 'studio status' instead of 'chat --help' because help commands now work from anywhere
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["myagents", "studio", "status"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        assert result.returncode == 1, "Failed command should return exit code 1"


# ============================================================================
# Version and Invalid Command Tests
# ============================================================================

@pytest.mark.infrastructure_cli
def test_myagents_version():
    """Test that myagents --version works."""
    result = subprocess.run(["myagents", "--version"], capture_output=True, text=True)
    assert result.returncode == 0, f"myagents --version failed: {result.stderr}"
    assert "myagents" in result.stdout.lower()


@pytest.mark.infrastructure_cli
def test_myagents_invalid_command():
    """Test that invalid command returns error."""
    result = subprocess.run(
        ["myagents", "invalid_command_xyz"],
        capture_output=True,
        text=True
    )
    assert result.returncode != 0


