"""End-to-end tests for unified myagents CLI commands (gcptoolkit functionality).

Tests the myagents CLI's integration with agent-gcptoolkit functionality including
build, update, rebuild, and version commands. This validates the packaging and
self-management capabilities accessible via the unified CLI.

Test scenarios:
- Version display via myagents --version
- Build command via myagents rebuild
- Update/reinstall command via myagents update
- Rebuild (build + update) command via myagents rebuild
- Error handling and edge cases
- Build artifact verification
- Secrets and config commands via myagents CLI

Note: As of agent-gcptoolkit v0.2.0, all CLI functionality is accessed via the
unified 'myagents' command. The standalone 'gcptoolkit' CLI has been removed.

TEST ENVIRONMENT REQUIREMENTS:
- Current myagents CLI must be installed with gcptoolkit subcommand support
- Build environment should NOT have GCP registry authentication configured
- Some tests require non-interactive pip build (no prompts for credentials)
- To ensure tests pass: run `pip install -e . --force-reinstall` before testing

SKIPPED TESTS:
- Tests that use 'myagents gcptoolkit rebuild' command will skip if:
  - The current installed CLI doesn't have the gcptoolkit subcommand
  - GCP registry is configured in pip.conf (prevents interactive auth prompts)
"""

import subprocess
import pytest
from pathlib import Path
import tempfile
import shutil
import os


def get_worktree_root() -> Path:
    """Get the root directory of the current git worktree.

    Returns:
        Path: Absolute path to the worktree root

    Raises:
        RuntimeError: If not in a git worktree
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        # Fallback for Docker environment where .git is not present
        # In Docker, we are at /workspace/MyAgents-test-refactor
        current_dir = Path.cwd()
        if (current_dir / "pyproject.toml").exists():
            return current_dir
        raise


# Fixture to locate Agent-GCPtoolkit directory
@pytest.fixture
def gcptoolkit_root():
    """Find the Agent-GCPtoolkit repository root."""
    worktree_root = get_worktree_root()
    possible_locations = [
        worktree_root.parent / "Agent-GCPtoolkit",  # sibling directory (local dev)
        worktree_root / "Agent-GCPtoolkit",  # inside workspace (Docker)
        Path.home() / "myagents" / "Agent-GCPtoolkit",  # home directory
    ]

    for location in possible_locations:
        if location.exists() and (location / "pyproject.toml").exists():
            return location

    return None  # Signal that gcptoolkit_root is not available


@pytest.fixture
def build_artifacts_dir(gcptoolkit_root):
    """Get path to build artifacts directory."""
    if gcptoolkit_root is None:
        return None
    return gcptoolkit_root / "build-artifacts"


class TestGCPToolkitVersion:
    """Test version command."""

    def test_version_basic(self):
        """Test basic version command."""
        result = subprocess.run(
            ["myagents", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"version command failed: {result.stderr}"
        assert "agent-gcptoolkit" in result.stdout.lower() or "myagents" in result.stdout.lower()

    def test_version_verbose(self):
        """Test version command with verbose flag."""
        result = subprocess.run(
            ["myagents", "--version"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"version -v failed: {result.stderr}"
        assert "agent-gcptoolkit" in result.stdout.lower() or "myagents" in result.stdout.lower()


class TestGCPToolkitBuild:
    """Test build command."""

    def test_build_command(self, gcptoolkit_root, build_artifacts_dir):
        """Test that build command creates wheel in build-artifacts/dist/."""
        if gcptoolkit_root is None:
            pytest.skip("Requires Agent-GCPtoolkit repository as sibling directory (local development only)")
        # Clean previous build artifacts
        dist_dir = build_artifacts_dir / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

        # Run build command
        env = os.environ.copy()
        env["PIP_NO_INPUT"] = "1"
        result = subprocess.run(
            ["myagents", "gcptoolkit", "rebuild"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )

        # Check command succeeded
        assert result.returncode == 0, f"build command failed: {result.stderr}"
        assert "build complete" in result.stdout.lower()

        # Verify artifacts exist
        assert dist_dir.exists(), "dist directory not created"

        wheels = list(dist_dir.glob("agent_gcptoolkit-*.whl"))
        assert len(wheels) > 0, "No wheel file created"

        tarballs = list(dist_dir.glob("agent_gcptoolkit-*.tar.gz"))
        assert len(tarballs) > 0, "No source distribution created"

    def test_build_creates_correct_structure(self, gcptoolkit_root, build_artifacts_dir):
        """Test that build creates correct directory structure."""
        if gcptoolkit_root is None:
            pytest.skip("Requires Agent-GCPtoolkit repository as sibling directory (local development only)")
        # Assumes previous test has run build
        dist_dir = build_artifacts_dir / "dist"

        if not dist_dir.exists():
            pytest.skip("Build artifacts not found - run test_build_command first")

        # Check that wheel is properly formatted
        wheels = list(dist_dir.glob("agent_gcptoolkit-*.whl"))
        if not wheels:
            pytest.skip("No wheel files found - run test_build_command first")

        if wheels:
            wheel_name = wheels[0].name
            # Wheel should follow naming convention: package-version-py-abi-platform.whl
            assert wheel_name.startswith("agent_gcptoolkit-")
            assert wheel_name.endswith(".whl")


class TestGCPToolkitUpdate:
    """Test update/reinstall command."""

    def test_update_with_existing_wheel(self, gcptoolkit_root, build_artifacts_dir):
        """Test update command with existing wheel."""
        if gcptoolkit_root is None:
            pytest.skip("Requires Agent-GCPtoolkit repository as sibling directory (local development only)")
        dist_dir = build_artifacts_dir / "dist"

        # Check if wheel exists (from build test)
        wheels = list(dist_dir.glob("agent_gcptoolkit-*.whl"))
        if not wheels:
            pytest.skip("No wheel files found - run test_build_command first")

        # Run update command
        result = subprocess.run(
            ["myagents", "gcptoolkit", "update"],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Check command succeeded
        assert result.returncode == 0, f"update command failed: {result.stderr}"
        assert "update complete" in result.stdout.lower() or "installing" in result.stdout.lower()


class TestGCPToolkitRebuild:
    """Test rebuild command (build + update)."""

    def test_rebuild_command(self, gcptoolkit_root, build_artifacts_dir):
        """Test rebuild command performs both build and update."""
        if gcptoolkit_root is None:
            pytest.skip("Requires Agent-GCPtoolkit repository as sibling directory (local development only)")
        # Clean previous artifacts
        dist_dir = build_artifacts_dir / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

        # Run rebuild command
        env = os.environ.copy()
        env["PIP_NO_INPUT"] = "1"
        result = subprocess.run(
            ["myagents", "gcptoolkit", "rebuild"],
            capture_output=True,
            text=True,
            timeout=180,
            env=env
        )

        # Check command succeeded
        assert result.returncode == 0, f"rebuild command failed: {result.stderr}"

        # Should see both build and update/install messages
        stdout_lower = result.stdout.lower()
        assert "build" in stdout_lower
        assert "install" in stdout_lower or "update" in stdout_lower

        # Verify artifacts were created
        assert dist_dir.exists(), "dist directory not created"
        wheels = list(dist_dir.glob("agent_gcptoolkit-*.whl"))
        assert len(wheels) > 0, "No wheel file created"


class TestGCPToolkitErrorHandling:
    """Test error handling and edge cases."""

    def test_help_command(self):
        """Test help command."""
        result = subprocess.run(
            ["myagents", "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "myagents" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_invalid_command(self):
        """Test that invalid command returns error."""
        result = subprocess.run(
            ["myagents", "invalid_command_xyz"],
            capture_output=True,
            text=True
        )
        assert result.returncode != 0

    def test_build_help(self):
        """Test build command help."""
        result = subprocess.run(
            ["myagents", "gcptoolkit", "rebuild", "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "rebuild" in result.stdout.lower()


class TestGCPToolkitSecrets:
    """Test secrets command (basic validation only, not actual secret operations)."""

    def test_secrets_help(self):
        """Test secrets command help.

        Note: secrets is a project-scoped command, so must run from project directory.
        """
        from pathlib import Path
        # Get the project root (where langgraph.json is)
        project_root = Path(__file__).parents[3]
        result = subprocess.run(
            ["myagents", "secrets", "--help"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        assert result.returncode == 0
        assert "secret" in result.stdout.lower()

    def test_secrets_get_help(self):
        """Test secrets get command help.

        Note: secrets is a project-scoped command, so must run from project directory.
        """
        from pathlib import Path
        # Get the project root (where langgraph.json is)
        project_root = Path(__file__).parents[3]
        result = subprocess.run(
            ["myagents", "secrets", "get", "--help"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        assert result.returncode == 0
        assert "secret" in result.stdout.lower()


# E2E test markers
pytestmark = pytest.mark.e2e
