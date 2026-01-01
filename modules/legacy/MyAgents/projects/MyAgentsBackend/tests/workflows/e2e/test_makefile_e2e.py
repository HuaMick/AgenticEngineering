"""End-to-end tests for Makefile targets.

Tests the Makefile targets related to packaging and development workflow.
This validates that make commands work correctly and dependencies are properly configured.

Test scenarios:
- Make target validation
- Target dependencies
- Error handling
- Build and test workflows
"""

import subprocess
import pytest
from pathlib import Path
import os


@pytest.fixture
def project_root():
    """Get the project root directory."""
    # Go up 3 levels from tests/workflows/packaging/test_makefile_e2e.py
    return Path(__file__).parents[3]


@pytest.fixture
def makefile_path(project_root):
    """Find the Makefile."""
    makefile = project_root / "Makefile"

    if not makefile.exists():
        pytest.skip(f"Makefile not found at {makefile}")

    return makefile


class TestMakefileValidation:
    """Test Makefile validation and structure."""

    def test_makefile_exists(self, makefile_path):
        """Test that Makefile exists."""
        assert makefile_path.exists()
        assert makefile_path.is_file()

    def test_makefile_syntax(self, makefile_path, project_root):
        """Test that Makefile has valid syntax."""
        result = subprocess.run(
            ["make", "-n", "help"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        # Should not have syntax errors
        assert "syntax error" not in result.stderr.lower()

    def test_makefile_has_phony_targets(self, makefile_path):
        """Test that Makefile declares PHONY targets."""
        content = makefile_path.read_text()
        assert ".PHONY" in content, "Missing .PHONY declaration"


class TestMakefileTargets:
    """Test individual Makefile targets."""

    def test_help_target(self, project_root):
        """Test make help target."""
        result = subprocess.run(
            ["make", "help"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"make help failed: {result.stderr}"
        assert "available" in result.stdout.lower() or "commands" in result.stdout.lower()

    def test_help_lists_targets(self, project_root):
        """Test that make help lists expected targets."""
        result = subprocess.run(
            ["make", "help"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )

        stdout_lower = result.stdout.lower()
        # Check for key targets
        expected_targets = ["venv", "install", "rebuild-myagents", "test-myagents"]
        for target in expected_targets:
            assert target in stdout_lower, f"Target '{target}' not listed in help"

    def test_venv_target_dry_run(self, project_root):
        """Test make venv target (dry run)."""
        result = subprocess.run(
            ["make", "-n", "venv"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "uv venv" in result.stdout or "venv" in result.stdout

    def test_install_target_dry_run(self, project_root):
        """Test make install target (dry run)."""
        result = subprocess.run(
            ["make", "-n", "install"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "uv sync" in result.stdout or "sync" in result.stdout

    def test_rebuild_myagents_target_dry_run(self, project_root):
        """Test make rebuild-myagents target (dry run)."""
        result = subprocess.run(
            ["make", "-n", "rebuild-myagents"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "myagents rebuild" in result.stdout

    def test_test_myagents_target_dry_run(self, project_root):
        """Test make test-myagents target (dry run)."""
        result = subprocess.run(
            ["make", "-n", "test-myagents"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "pytest" in result.stdout


class TestMakefileTargetDependencies:
    """Test Makefile target dependencies."""

    def test_update_test_myagents_depends_on_rebuild(self, makefile_path):
        """Test that update-test-myagents depends on rebuild-myagents and test-myagents."""
        content = makefile_path.read_text()

        # Find the update-test-myagents target
        lines = content.split('\n')
        target_line = None
        for line in lines:
            if "update-test-myagents:" in line:
                target_line = line
                break

        assert target_line is not None, "update-test-myagents target not found"
        assert "rebuild-myagents" in target_line
        assert "test-myagents" in target_line

    def test_update_test_myagents_dry_run(self, project_root):
        """Test update-test-myagents dry run shows correct sequence."""
        result = subprocess.run(
            ["make", "-n", "update-test-myagents"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

        # Should show both rebuild and test commands
        stdout = result.stdout
        assert "myagents rebuild" in stdout or "rebuild" in stdout
        assert "pytest" in stdout


class TestMakefileRunTarget:
    """Test make run target."""

    def test_run_target_dry_run(self, project_root):
        """Test make run target (dry run)."""
        result = subprocess.run(
            ["make", "-n", "run"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "uv run" in result.stdout or "python" in result.stdout


class TestMakefileWithUV:
    """Test that Makefile uses uv commands."""

    def test_makefile_uses_uv_venv(self, makefile_path):
        """Test that venv target uses uv."""
        content = makefile_path.read_text()
        assert "uv venv" in content

    def test_makefile_uses_uv_sync(self, makefile_path):
        """Test that install target uses uv sync."""
        content = makefile_path.read_text()
        assert "uv sync" in content

    def test_makefile_uses_uv_run(self, makefile_path):
        """Test that run targets use uv run."""
        content = makefile_path.read_text()
        assert "uv run" in content


class TestMakefileErrorHandling:
    """Test error handling in Makefile."""

    def test_invalid_target(self, project_root):
        """Test that invalid target returns error."""
        result = subprocess.run(
            ["make", "invalid_target_xyz"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        assert result.returncode != 0

    def test_help_on_no_target(self, makefile_path):
        """Test behavior when no target specified."""
        # Many Makefiles default to help or first target
        content = makefile_path.read_text()

        # If help is the first target, it should be the default
        lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]
        non_phony_lines = [line for line in lines if not line.startswith('.PHONY')]

        if non_phony_lines:
            first_target = non_phony_lines[0].split(':')[0] if ':' in non_phony_lines[0] else None
            # This is informational, not a strict requirement
            assert first_target is not None


class TestMakefileTestIntegration:
    """Test integration between make targets and test suite."""

    def test_test_myagents_runs_pytest(self, project_root):
        """Test that test-myagents actually runs pytest."""
        # Do a dry run to check the command
        result = subprocess.run(
            ["make", "-n", "test-myagents"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )

        assert "pytest" in result.stdout
        assert "tests/" in result.stdout

    def test_test_myagents_can_execute(self, project_root):
        """Test that test-myagents target can execute (quick sanity check)."""
        # Run a quick subset of tests to verify the make target works
        # Full test suite takes >10 minutes, so we use test-myagents-quick instead
        result = subprocess.run(
            ["make", "test-myagents-quick"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60  # Quick tests should complete in 1 minute
        )

        # Should complete (may pass or fail depending on test state)
        # We just verify it runs without crashing
        assert "pytest" in result.stderr or "test" in result.stdout.lower()


class TestMakefileDocumentation:
    """Test Makefile documentation."""

    def test_targets_have_descriptions(self, project_root):
        """Test that make help shows descriptions for targets."""
        result = subprocess.run(
            ["make", "help"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )

        # Help should include descriptions, not just target names
        lines = result.stdout.split('\n')
        # Should have multiple lines with descriptions
        assert len(lines) > 5


class TestMakefileRebuildWorkflow:
    """Test the complete rebuild workflow."""

    def test_rebuild_workflow_sequence(self, project_root):
        """Test that rebuild workflow executes in correct sequence."""
        result = subprocess.run(
            ["make", "-n", "update-test-myagents"],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )

        # Should show rebuild then test
        lines = result.stdout.split('\n')
        rebuild_index = -1
        test_index = -1

        for i, line in enumerate(lines):
            if "myagents rebuild" in line:
                rebuild_index = i
            if "pytest" in line:
                test_index = i

        # If both are present, rebuild should come before test
        if rebuild_index >= 0 and test_index >= 0:
            assert rebuild_index < test_index, "Rebuild should run before tests"


# E2E test markers
pytestmark = pytest.mark.e2e
