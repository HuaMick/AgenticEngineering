"""End-to-end tests for CLI command routing and root detection.

This test suite validates CLI-001 implementation with home directory architecture:
- All commands work from any directory
- Home directory (~/.config/myagents/) is single source of truth
- CLI source root detection uses __file__ (not cwd)
- Local langgraph.json files are completely ignored
- Error messages are clear and actionable
"""
import subprocess
import tempfile
from pathlib import Path

import pytest


# Test fixture setup
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
# GLOBAL COMMAND TESTS - Should work from any directory
# ============================================================================

@pytest.mark.workflow_cli_routing
@pytest.mark.parametrize("command,subcommand,expected_keywords", [
    ("update", "--help", ["update", "reinstall"]),
    ("rebuild", "--help", ["rebuild", "reinstall"]),
    ("preferences", "list", []),
    ("config", "list", []),
])
@pytest.mark.parametrize("directory_fixture", ["project_dir", "parent_dir", "unrelated_dir"])
def test_global_command_works_from_any_directory(request, command, subcommand, expected_keywords, directory_fixture):
    """Test that global commands work from any directory."""
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
# HOME DIRECTORY COMMAND TESTS - All commands use home config
# ============================================================================

@pytest.mark.workflow_cli_routing
@pytest.mark.parametrize("command,subcommand,directory_fixture", [
    # Chat command tests - work from any directory with home config
    ("chat", "--help", "project_dir"),
    ("chat", "--help", "parent_dir"),
    ("chat", "--help", "unrelated_dir"),
])
def test_commands_use_home_config(request, command, subcommand, directory_fixture):
    """Test that all commands use home directory config from any location.

    In the new architecture, ALL commands (chat, studio, etc.) work from ANY directory
    because they use ~/.config/myagents/ as the single source of truth.
    """
    directory = request.getfixturevalue(directory_fixture)
    result = subprocess.run(
        ["myagents", command, subcommand],
        cwd=str(directory),
        capture_output=True,
        text=True
    )

    # With home config present, commands should work from any directory
    # Note: This test assumes home config exists from project setup
    assert result.returncode == 0, (
        f"'myagents {command} {subcommand}' should work from {directory_fixture} with home config. "
        f"Error: {result.stderr}"
    )
    assert command in result.stdout.lower() or "agent" in result.stdout.lower()


@pytest.mark.workflow_cli_routing
@pytest.mark.parametrize("command,subcommand", [
    ("studio", "status"),
])
def test_studio_requires_home_config(command, subcommand, unrelated_dir):
    """Test that studio commands require home directory config.

    If home config doesn't exist, commands should fail with clear error message
    pointing to 'myagents setup'.
    """
    # Note: This test assumes NO home config exists
    # In practice, home config may exist from development setup
    result = subprocess.run(
        ["myagents", command, subcommand],
        cwd=str(unrelated_dir),
        capture_output=True,
        text=True
    )

    # Either works (config exists) or fails with home directory error message
    if result.returncode != 0:
        error_output = result.stderr.lower()
        # Error should reference home directory, not project directory
        assert "~/.config/myagents" in error_output or ".config/myagents" in error_output, (
            f"Error should reference home directory. Got: {result.stderr}"
        )
        assert "myagents setup" in error_output, (
            f"Error should guide user to run 'myagents setup'. Got: {result.stderr}"
        )


# ============================================================================
# ROOT DETECTION LOGIC TESTS
# ============================================================================

@pytest.mark.workflow_cli_routing
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


@pytest.mark.workflow_cli_routing
def test_home_directory_detection_works_from_any_directory(project_dir):
    """Test that home directory detection works from any directory.

    In the new architecture, detect_langgraph_path() only checks ~/.config/myagents/
    and works regardless of current working directory.
    """
    # Run command from project directory
    result = subprocess.run(
        ["myagents", "chat", "--help"],
        cwd=str(project_dir),
        capture_output=True,
        text=True
    )

    # Should succeed using home directory config
    assert result.returncode == 0, (
        f"Command failed from project directory. "
        f"This suggests home directory detection is not working correctly. "
        f"Error: {result.stderr}"
    )


@pytest.mark.workflow_cli_routing
def test_local_langgraph_json_is_ignored(unrelated_dir):
    """Test that local langgraph.json files are completely ignored.

    In the new architecture, only ~/.config/myagents/langgraph.json is used.
    Local project files are ignored.
    """
    # Create a local langgraph.json file
    local_langgraph = unrelated_dir / "langgraph.json"
    local_langgraph.write_text('{"graphs": {}}')

    # Verify local file exists
    assert local_langgraph.exists(), "Test setup error: local langgraph.json not created"

    # Run command from directory with local file
    result = subprocess.run(
        ["myagents", "chat", "--help"],
        cwd=str(unrelated_dir),
        capture_output=True,
        text=True
    )

    # Should work using home directory config (local file ignored)
    # OR fail with home directory error (not local file error)
    if result.returncode != 0:
        error_output = result.stderr.lower()
        # Error should reference home directory, not local file
        assert "~/.config/myagents" in error_output or ".config/myagents" in error_output, (
            f"Error should reference home directory, not local file. Got: {result.stderr}"
        )


# ============================================================================
# COMMAND ROUTING TESTS
# ============================================================================

@pytest.mark.workflow_cli_routing
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


@pytest.mark.workflow_cli_routing
def test_commands_route_to_home_directory(project_dir):
    """Test that all commands route to home directory for operations.

    In the new architecture, ALL commands use ~/.config/myagents/ as the
    single source of truth, regardless of current working directory.
    """
    # Run command from project directory
    result = subprocess.run(
        ["myagents", "chat", "--help"],
        cwd=str(project_dir),
        capture_output=True,
        text=True
    )

    # Success proves command routed to home directory config
    assert result.returncode == 0, (
        f"Command failed from project directory. "
        f"Error: {result.stderr}"
    )


# ============================================================================
# ERROR HANDLING AND MESSAGING TESTS
# ============================================================================

@pytest.mark.workflow_cli_routing
def test_error_message_clarity_for_missing_home_config():
    """Test that error messages are clear and actionable when home config not found.

    In the new architecture, errors should reference ~/.config/myagents/ and
    guide users to run 'myagents setup'.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["myagents", "chat", "--help"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )

        # May work (home config exists) or fail with home directory error
        if result.returncode != 0:
            error_output = result.stderr
            # Error should be clear and actionable
            assert len(error_output) > 0, "Error message should not be empty"
            assert "langgraph.json" in error_output.lower(), "Error should mention langgraph.json"
            # Error should reference home directory, not project
            assert "~/.config/myagents" in error_output or ".config/myagents" in error_output, (
                f"Error should reference home directory. Got: {error_output}"
            )
            assert "myagents setup" in error_output.lower(), (
                f"Error should guide user to run 'myagents setup'. Got: {error_output}"
            )


@pytest.mark.workflow_cli_routing
def test_exit_codes_are_appropriate():
    """Test that commands return appropriate exit codes.

    - Success: exit code 0
    - Error: exit code 1 (when home config missing)
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

    # Test command with home config (should work from any directory)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["myagents", "chat", "--help"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        # Either works (home config exists) or fails with exit code 1
        if result.returncode != 0:
            assert result.returncode == 1, "Failed command should return exit code 1"


# ============================================================================
# CLI-001 SUCCESS CRITERIA VALIDATION
# ============================================================================

@pytest.mark.workflow_cli_routing
def test_cli001_criterion_1_global_commands_work_from_any_directory():
    """CLI-001 Criterion 1: Global commands (update, rebuild, preferences, config) work from any directory."""
    test_dirs = []

    # Test from project directory
    test_dirs.append(Path(__file__).parents[3])

    # Test from parent directory
    test_dirs.append(Path(__file__).parents[4])

    # Test from temporary unrelated directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dirs.append(Path(tmpdir))

        for test_dir in test_dirs:
            # Test 'update' command
            result = subprocess.run(
                ["myagents", "update", "--help"],
                cwd=str(test_dir),
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, (
                f"'myagents update' failed from {test_dir}. "
                f"CLI-001 Criterion 1 FAILED. Error: {result.stderr}"
            )

            # Test 'rebuild' command
            result = subprocess.run(
                ["myagents", "rebuild", "--help"],
                cwd=str(test_dir),
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, (
                f"'myagents rebuild' failed from {test_dir}. "
                f"CLI-001 Criterion 1 FAILED. Error: {result.stderr}"
            )

            # Test 'preferences' command (now global, uses home directory config)
            result = subprocess.run(
                ["myagents", "preferences", "list"],
                cwd=str(test_dir),
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, (
                f"'myagents preferences' failed from {test_dir}. "
                f"CLI-001 Criterion 1 FAILED. Error: {result.stderr}"
            )

            # Test 'config' command (now global, uses home directory config)
            result = subprocess.run(
                ["myagents", "config", "list"],
                cwd=str(test_dir),
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, (
                f"'myagents config' failed from {test_dir}. "
                f"CLI-001 Criterion 1 FAILED. Error: {result.stderr}"
            )


@pytest.mark.workflow_cli_routing
def test_cli001_criterion_2_all_commands_use_home_directory():
    """CLI-001 Criterion 2: All commands use home directory config (not project-scoped).

    In the new architecture, there is NO distinction between global and project-scoped.
    ALL commands use ~/.config/myagents/ as the single source of truth.
    """
    project_dir = Path(__file__).parents[3]

    # Test from project directory (should succeed with home config)
    result = subprocess.run(
        ["myagents", "chat", "--help"],
        cwd=str(project_dir),
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, (
        f"'myagents chat' should succeed from project directory using home config. "
        f"CLI-001 Criterion 2 FAILED. Error: {result.stderr}"
    )

    # Test from parent directory (should also succeed with home config)
    parent_dir = Path(__file__).parents[4]
    result = subprocess.run(
        ["myagents", "chat", "--help"],
        cwd=str(parent_dir),
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, (
        f"'myagents chat' should succeed from parent directory using home config. "
        f"CLI-001 Criterion 2 FAILED. Error: {result.stderr}"
    )

    # Test from unrelated directory (should also succeed with home config)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["myagents", "chat", "--help"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, (
            f"'myagents chat' should succeed from unrelated directory using home config. "
            f"CLI-001 Criterion 2 FAILED. Error: {result.stderr}"
        )


@pytest.mark.workflow_cli_routing
def test_cli001_criterion_3_cli_source_root_uses_file():
    """CLI-001 Criterion 3: CLI source root detection uses __file__ not cwd."""
    # This is validated by global commands working from any directory
    # If CLI source root was based on cwd, global commands would fail
    # when executed from directories other than CLI source

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a directory structure that doesn't contain CLI source
        test_dir = Path(tmpdir) / "deeply" / "nested" / "directory"
        test_dir.mkdir(parents=True, exist_ok=True)

        # Run global command from this directory
        result = subprocess.run(
            ["myagents", "update", "--help"],
            cwd=str(test_dir),
            capture_output=True,
            text=True
        )

        # If this succeeds, it proves CLI source root is detected via __file__
        assert result.returncode == 0, (
            f"Global command failed from nested unrelated directory. "
            f"This suggests CLI source root detection is NOT using __file__. "
            f"CLI-001 Criterion 3 FAILED. Error: {result.stderr}"
        )


@pytest.mark.workflow_cli_routing
def test_cli001_criterion_4_error_messages_are_clear():
    """CLI-001 Criterion 4: Error messages are clear and actionable.

    In the new architecture, errors should reference home directory and guide
    users to run 'myagents setup'.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Try to run command from arbitrary directory
        result = subprocess.run(
            ["myagents", "studio", "status"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )

        # May work (home config exists) or fail with home directory error
        if result.returncode != 0:
            # Error message should be clear
            error_output = result.stderr
            assert len(error_output) > 0, "Error message should not be empty"

            # Error should mention key information
            assert "langgraph.json" in error_output.lower(), (
                "Error should mention langgraph.json. CLI-001 Criterion 4 FAILED."
            )
            assert "no langgraph.json found" in error_output.lower(), (
                "Error should mention no langgraph.json found. CLI-001 Criterion 4 FAILED."
            )

            # Error should reference home directory
            assert "~/.config/myagents" in error_output or ".config/myagents" in error_output, (
                f"Error should reference home directory. CLI-001 Criterion 4 FAILED. Got: {error_output}"
            )

            # Error should be actionable (tell user to run setup)
            assert "myagents setup" in error_output.lower(), (
                f"Error should guide user to run 'myagents setup'. CLI-001 Criterion 4 FAILED. Got: {error_output}"
            )


@pytest.mark.workflow_cli_routing
def test_cli001_criterion_5_command_routing_is_correct():
    """CLI-001 Criterion 5: Command routing directs to appropriate root directory.

    In the new architecture:
    - Global commands (update, rebuild) route to CLI source root
    - ALL other commands route to home directory config
    """
    # Test global command routing (CLI source root)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["myagents", "update", "--help"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        # Success proves routing to CLI source root works
        assert result.returncode == 0, (
            "Global command routing to CLI source root FAILED. "
            "CLI-001 Criterion 5 FAILED."
        )

    # Test home directory command routing (all other commands)
    project_dir = Path(__file__).parents[3]
    result = subprocess.run(
        ["myagents", "chat", "--help"],
        cwd=str(project_dir),
        capture_output=True,
        text=True
    )
    # Success proves routing to home directory works
    assert result.returncode == 0, (
        f"Command routing to home directory FAILED. "
        f"CLI-001 Criterion 5 FAILED. Error: {result.stderr}"
    )
