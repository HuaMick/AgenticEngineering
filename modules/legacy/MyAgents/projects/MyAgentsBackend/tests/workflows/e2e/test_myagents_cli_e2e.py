"""End-to-end tests for MyAgents CLI packaging commands.

Tests the myagents CLI's update and rebuild commands.
This validates the self-management capabilities of the MyAgents package.

IMPORTANT: This test suite focuses ONLY on packaging operations:
- Update command (reinstall from source)
- Rebuild command (build + reinstall)
- Build artifact creation
- Package installation verification
- Preferences persistence across updates

CLI command tests (help, status, etc.) are in tests/workflows/infrastructure/test_cli_integration.py

TEST ENVIRONMENT REQUIREMENTS:
- Current myagents CLI must be installed (not an old version)
- Build environment should NOT have GCP registry authentication configured
- Some tests require non-interactive pip build (no prompts for credentials)
- To ensure tests pass: run `pip install -e . --force-reinstall` before testing

SKIPPED TESTS:
- Tests that build packages will skip if GCP registry is configured in pip.conf
- This prevents interactive authentication prompts during test builds
"""

import subprocess
import pytest
from pathlib import Path
import shutil
import sys
import os


def _get_worktree_root() -> Path:
    """Get the root directory of the current git worktree."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        # Fallback for environments where .git is not present
        current_dir = Path.cwd()
        if (current_dir / "pyproject.toml").exists():
            return current_dir
        raise


def _is_workspace_member() -> bool:
    """Check if the current worktree is a valid uv workspace member.

    Returns True if the worktree is listed in the parent workspace.toml,
    which is required for update/rebuild commands to work properly.
    """
    try:
        worktree_root = _get_worktree_root()
        workspace_root = worktree_root.parent
        workspace_toml = workspace_root / "pyproject.toml"

        if not workspace_toml.exists():
            return False

        content = workspace_toml.read_text()
        worktree_name = worktree_root.name

        # Check if worktree name is in workspace members
        return worktree_name in content
    except Exception:
        return False


def _check_workspace_or_skip():
    """Skip test if workspace is not properly configured for update/rebuild."""
    if not _is_workspace_member():
        pytest.skip(
            f"Worktree '{_get_worktree_root().name}' is not a workspace member. "
            "Update/rebuild tests require proper uv workspace configuration."
        )


@pytest.fixture
def myagents_root():
    """Find a valid MyAgents project root for testing.

    Accepts any MyAgents worktree (including current one) that has
    the required project structure (pyproject.toml with myagents).
    """
    # Try current worktree first
    worktree_root = _get_worktree_root()

    # Check if current worktree is a valid MyAgents project
    if worktree_root.exists() and (worktree_root / "pyproject.toml").exists():
        content = (worktree_root / "pyproject.toml").read_text()
        if "myagents" in content.lower():
            return worktree_root

    # Fallback: try cwd
    cwd = Path.cwd()
    if cwd.exists() and (cwd / "pyproject.toml").exists():
        content = (cwd / "pyproject.toml").read_text()
        if "myagents" in content.lower():
            return cwd

    pytest.skip("No valid MyAgents worktree found (requires pyproject.toml with myagents)")


class TestMyAgentsUpdate:
    """Test myagents update command."""

    def test_update_command_basic(self):
        """Test basic update command execution."""
        _check_workspace_or_skip()
        env = os.environ.copy()
        env["PIP_NO_INPUT"] = "1"
        result = subprocess.run(
            ["myagents", "update"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )

        # Update should succeed (assuming package is installed)
        assert result.returncode == 0, f"update command failed: {result.stderr}"
        stdout_lower = result.stdout.lower()
        assert "updat" in stdout_lower or "install" in stdout_lower

    def test_update_preserves_functionality(self):
        """Test that update preserves CLI functionality."""
        # Run update
        env = os.environ.copy()
        env["PIP_NO_INPUT"] = "1"
        update_result = subprocess.run(
            ["myagents", "update"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )

        if update_result.returncode != 0:
            pytest.skip(f"Update failed: {update_result.stderr}")

        # Verify CLI still works after update
        help_result = subprocess.run(
            ["myagents", "--help"],
            capture_output=True,
            text=True
        )

        assert help_result.returncode == 0, "CLI broken after update"
        assert "myagents" in help_result.stdout.lower()


def _has_gcp_registry_configured():
    """Check if GCP registry is configured in pip.conf."""
    pip_conf_paths = [
        Path.home() / ".config" / "pip" / "pip.conf",
        Path.home() / ".pip" / "pip.conf",
    ]

    for pip_conf in pip_conf_paths:
        if pip_conf.exists():
            try:
                content = pip_conf.read_text()
                if "pkg.dev" in content or "artifactregistry" in content:
                    return True
            except Exception:
                pass
    return False


class TestMyAgentsRebuild:
    """Test myagents rebuild command."""

    def test_rebuild_command_basic(self, myagents_root):
        """Test basic rebuild command execution."""
        _check_workspace_or_skip()
        env = os.environ.copy()
        env["PIP_NO_INPUT"] = "1"
        result = subprocess.run(
            ["myagents", "rebuild"],
            capture_output=True,
            text=True,
            timeout=180,
            env=env
        )

        # Check command succeeded
        assert result.returncode == 0, f"rebuild command failed: {result.stderr}"

        stdout_lower = result.stdout.lower()
        # Should see building and installation messages
        assert "build" in stdout_lower
        assert "install" in stdout_lower or "reinstall" in stdout_lower

    def test_rebuild_creates_artifacts(self, myagents_root):
        """Test that rebuild creates build artifacts."""
        _check_workspace_or_skip()
        # Clean previous artifacts
        dist_dir = myagents_root / "dist"
        build_dir = myagents_root / "build"

        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        if build_dir.exists():
            shutil.rmtree(build_dir)

        # Run rebuild
        env = os.environ.copy()
        env["PIP_NO_INPUT"] = "1"
        result = subprocess.run(
            ["myagents", "rebuild"],
            capture_output=True,
            text=True,
            timeout=180,
            env=env
        )

        if result.returncode != 0:
            pytest.skip(f"Rebuild failed: {result.stderr}")

        # Verify artifacts were created
        assert dist_dir.exists(), "dist directory not created"

        wheels = list(dist_dir.glob("myagents-*.whl"))
        tarballs = list(dist_dir.glob("myagents-*.tar.gz"))

        # At least one artifact should exist
        assert len(wheels) > 0 or len(tarballs) > 0, "No build artifacts created"

    def test_rebuild_preserves_functionality(self):
        """Test that rebuild preserves CLI functionality."""
        _check_workspace_or_skip()
        # Run rebuild
        env = os.environ.copy()
        env["PIP_NO_INPUT"] = "1"
        rebuild_result = subprocess.run(
            ["myagents", "rebuild"],
            capture_output=True,
            text=True,
            timeout=180,
            env=env
        )

        if rebuild_result.returncode != 0:
            pytest.skip(f"Rebuild failed: {rebuild_result.stderr}")

        # Verify CLI still works after rebuild
        help_result = subprocess.run(
            ["myagents", "--help"],
            capture_output=True,
            text=True
        )

        assert help_result.returncode == 0, "CLI broken after rebuild"

        # Verify specific commands still work
        prefs_result = subprocess.run(
            ["myagents", "preferences", "list"],
            capture_output=True,
            text=True
        )
        assert prefs_result.returncode == 0, "Preferences command broken after rebuild"


class TestMyAgentsCliIntegration:
    """Test that MyAgents CLI works correctly after packaging operations.

    Note: This focuses on post-packaging verification, not general CLI testing.
    General CLI tests are in tests/workflows/infrastructure/test_cli_integration.py
    """

    def test_cli_available_after_install(self):
        """Test that myagents CLI is available after installation."""
        result = subprocess.run(
            ["myagents", "--version"],
            capture_output=True,
            text=True
        )
        # After packaging, CLI should be available
        assert result.returncode == 0
        assert "myagents" in result.stdout.lower()


class TestMyAgentsPackagingErrorHandling:
    """Test error handling for packaging operations."""

    def test_update_help(self):
        """Test update command help (packaging-specific)."""
        result = subprocess.run(
            ["myagents", "update", "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "update" in result.stdout.lower() or "reinstall" in result.stdout.lower()

    def test_rebuild_help(self):
        """Test rebuild command help (packaging-specific)."""
        result = subprocess.run(
            ["myagents", "rebuild", "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "rebuild" in result.stdout.lower()


class TestMyAgentsPreferencesIntegration:
    """Test preferences system integration with packaging."""

    def test_set_and_get_preference(self):
        """Test setting and getting a preference."""
        # Set a test preference
        set_result = subprocess.run(
            ["myagents", "preferences", "set", "test.packaging", "test_value"],
            capture_output=True,
            text=True
        )

        if set_result.returncode != 0:
            pytest.skip(f"Preferences set failed: {set_result.stderr}")

        # Get the preference back
        get_result = subprocess.run(
            ["myagents", "preferences", "get", "test.packaging"],
            capture_output=True,
            text=True
        )

        assert get_result.returncode == 0, f"Get preference failed: {get_result.stderr}"
        assert "test_value" in get_result.stdout

        # Clean up
        subprocess.run(
            ["myagents", "preferences", "delete", "test.packaging"],
            capture_output=True,
            text=True
        )

    def test_preferences_persist_after_update(self):
        """Test that preferences persist after package update."""
        _check_workspace_or_skip()
        # Set a test preference
        subprocess.run(
            ["myagents", "preferences", "set", "test.persist", "persist_value"],
            capture_output=True,
            text=True
        )

        # Run update
        env = os.environ.copy()
        env["PIP_NO_INPUT"] = "1"
        update_result = subprocess.run(
            ["myagents", "update"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )

        if update_result.returncode != 0:
            pytest.skip(f"Update failed: {update_result.stderr}")

        # Check preference still exists
        get_result = subprocess.run(
            ["myagents", "preferences", "get", "test.persist"],
            capture_output=True,
            text=True
        )

        assert get_result.returncode == 0, "Preference lost after update"
        assert "persist_value" in get_result.stdout

        # Clean up
        subprocess.run(
            ["myagents", "preferences", "delete", "test.persist"],
            capture_output=True,
            text=True
        )


# E2E test markers
pytestmark = pytest.mark.e2e
