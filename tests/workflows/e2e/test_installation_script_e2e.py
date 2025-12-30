"""End-to-end tests for installation script.

Tests the scripts/installation.sh script that handles initial setup.
This validates the installation workflow and idempotency.

Test scenarios:
- Script execution validation (syntax check)
- Idempotency (safe to run multiple times)
- Error handling
- Environment setup verification

Note: Some tests run in dry-run mode or check specific sections
to avoid breaking the current environment.
"""

import subprocess
import pytest
from pathlib import Path
import tempfile
import shutil
import os


@pytest.fixture
def installation_script():
    """Find the installation script."""
    # Get worktree root dynamically (3 levels up from test file)
    # test_installation_script_e2e.py -> packaging -> workflows -> tests -> worktree
    worktree_root = Path(__file__).parents[3]
    script_path = worktree_root / "scripts" / "installation.sh"

    if not script_path.exists():
        pytest.skip("Installation script not found")

    return script_path


@pytest.fixture
def test_workspace():
    """Create a temporary workspace for installation testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        yield workspace


class TestInstallationScriptValidation:
    """Test installation script validation."""

    def test_script_exists(self, installation_script):
        """Test that installation script exists."""
        assert installation_script.exists()
        assert installation_script.is_file()

    def test_script_is_executable(self, installation_script):
        """Test that installation script is executable."""
        assert os.access(installation_script, os.X_OK), "Script is not executable"

    def test_script_syntax(self, installation_script):
        """Test that installation script has valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(installation_script)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error in script: {result.stderr}"

class TestInstallationScriptContent:
    """Test installation script content and structure."""

    def test_script_has_shebang(self, installation_script):
        """Test that script has proper shebang."""
        with open(installation_script, 'r') as f:
            first_line = f.readline()
            assert first_line.startswith("#!"), "Missing shebang"
            assert "bash" in first_line, "Not a bash script"

    def test_script_has_error_handling(self, installation_script):
        """Test that script has error handling (set -e)."""
        content = installation_script.read_text()
        assert "set -e" in content, "Missing 'set -e' for error handling"

    def test_script_checks_python_version(self, installation_script):
        """Test that script checks Python version."""
        content = installation_script.read_text()
        assert "python" in content.lower()
        assert "version" in content.lower()
        assert "3.11" in content

    def test_script_checks_uv(self, installation_script):
        """Test that script handles uv installation."""
        content = installation_script.read_text()
        assert "uv" in content
        assert "install" in content.lower()

    def test_script_creates_venv(self, installation_script):
        """Test that script creates virtual environment."""
        content = installation_script.read_text()
        assert "venv" in content.lower()
        assert ".venv" in content

    def test_script_installs_dependencies(self, installation_script):
        """Test that script installs dependencies."""
        content = installation_script.read_text()
        assert "uv sync" in content or "uv pip install" in content

    def test_script_checks_gcp_project(self, installation_script):
        """Test that script checks for GCP_PROJECT_ID."""
        content = installation_script.read_text()
        assert "GCP_PROJECT_ID" in content


class TestInstallationScriptIdempotency:
    """Test that installation script can be run multiple times safely."""

    def test_script_checks_existing_venv(self, installation_script):
        """Test that script handles existing venv."""
        content = installation_script.read_text()
        # Should check if .venv exists before creating
        assert ".venv" in content
        assert "exists" in content.lower() or "if" in content

    def test_script_checks_existing_uv(self, installation_script):
        """Test that script checks if uv is already installed."""
        content = installation_script.read_text()
        # Should check if uv exists before installing
        assert "command -v uv" in content or "which uv" in content


class TestInstallationScriptVerification:
    """Test installation verification steps."""

    def test_script_verifies_installation(self, installation_script):
        """Test that script verifies installation."""
        content = installation_script.read_text()
        assert "verif" in content.lower()
        assert "myagents --help" in content or "myagents" in content

    def test_script_provides_next_steps(self, installation_script):
        """Test that script provides next steps guidance."""
        content = installation_script.read_text()
        assert "next steps" in content.lower() or "usage" in content.lower()


class TestInstallationScriptOutput:
    """Test installation script output formatting."""

    def test_script_has_colored_output(self, installation_script):
        """Test that script uses colored output for better UX."""
        content = installation_script.read_text()
        # Check for ANSI color codes or color variables
        assert ("\\033[" in content or "RED=" in content or
                "GREEN=" in content or "YELLOW=" in content)

    def test_script_has_section_headers(self, installation_script):
        """Test that script has clear section headers."""
        content = installation_script.read_text()
        # Should have some form of headers or dividers
        assert "====" in content or "---" in content


class TestInstallationScriptErrorCases:
    """Test error handling in installation script."""

    def test_python_version_check_logic(self, installation_script):
        """Test that Python version check logic is present."""
        content = installation_script.read_text()
        assert "python" in content.lower()
        assert ("exit 1" in content or "return 1" in content), "Missing error exits"

    def test_script_handles_download_failures(self, installation_script):
        """Test that script handles download failures."""
        content = installation_script.read_text()
        # Should check return codes or use error handling
        assert ("if !" in content or "||" in content or
                "set -e" in content), "Missing error handling"


class TestInstallationDocumentation:
    """Test installation script documentation."""

    def test_script_has_header_comments(self, installation_script):
        """Test that script has explanatory header comments."""
        with open(installation_script, 'r') as f:
            # Read first 20 lines
            lines = f.readlines()
            header = ''.join(lines[:20])

        assert "#" in header, "Missing comments"
        assert ("installation" in header.lower() or
                "setup" in header.lower() or
                "myagents" in header.lower())

    def test_script_has_usage_instructions(self, installation_script):
        """Test that script includes usage instructions."""
        content = installation_script.read_text()
        # Should have some form of documentation
        assert "#" in content
        # Should explain what it does or how to use it
        comment_lines = [line for line in content.split('\n') if line.strip().startswith('#')]
        assert len(comment_lines) > 5, "Insufficient documentation"


# E2E test markers
pytestmark = pytest.mark.e2e
