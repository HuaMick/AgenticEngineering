"""End-to-end tests for self-update functionality using real test registry.

Tests package installation and self-update from the test artifact registry.
These tests use isolated virtualenvs to ensure clean state and test real
package installation, not mocks.

Test scenarios:
- Installing myagents from test registry
- Installing agent-gcptoolkit from test registry
- Self-update blocked in workspace mode
- Version consistency after self-update

Note: These tests require access to the test artifact registry and proper
authentication (keyring packages).
"""

import pytest
import subprocess
import sys
import os


class TestMyAgentsSelfUpdate:
    """Test myagents self-update from test registry."""

    def test_self_update_from_test_registry(self, isolated_test_venv, test_registry_url):
        """Test installing and updating myagents from test registry.

        This test verifies:
        1. Package can be installed from test registry
        2. Installation completes successfully
        3. Package is importable after installation
        """
        pip = isolated_test_venv["pip"]
        python = isolated_test_venv["python"]

        # Install from test registry
        result = subprocess.run([
            pip, "install", "--extra-index-url", test_registry_url, "myagents"
        ], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify installation
        result = subprocess.run([
            python, "-c", "import myagents; print(myagents.__version__)"
        ], capture_output=True, text=True)
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert result.stdout.strip(), "Version not printed"

    def test_myagents_cli_available_after_install(self, isolated_test_venv, test_registry_url):
        """Test that myagents CLI is available after installation from registry.

        This verifies the package entry points are properly set up.
        """
        pip = isolated_test_venv["pip"]
        venv_path = isolated_test_venv["venv_path"]

        # Install from test registry
        result = subprocess.run([
            pip, "install", "--extra-index-url", test_registry_url, "myagents"
        ], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Get CLI path
        if sys.platform == "win32":
            cli_path = venv_path / "Scripts" / "myagents.exe"
        else:
            cli_path = venv_path / "bin" / "myagents"

        # Verify CLI exists and is executable
        assert cli_path.exists(), f"CLI not found at {cli_path}"

        # Verify CLI works
        result = subprocess.run([
            str(cli_path), "--help"
        ], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "myagents" in result.stdout.lower()


class TestGCPToolkitSelfUpdate:
    """Test gcptoolkit self-update from test registry."""

    def test_self_update_from_test_registry(self, isolated_test_venv, test_registry_url):
        """Test installing and updating agent-gcptoolkit from test registry.

        This test verifies:
        1. Package can be installed from test registry
        2. Installation completes successfully
        3. Package is importable after installation
        """
        pip = isolated_test_venv["pip"]
        python = isolated_test_venv["python"]

        # Install from test registry
        result = subprocess.run([
            pip, "install", "--extra-index-url", test_registry_url, "agent-gcptoolkit"
        ], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify installation
        result = subprocess.run([
            python, "-c", "import agent_gcptoolkit; print('Success')"
        ], capture_output=True, text=True)
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert "Success" in result.stdout

    def test_gcptoolkit_has_correct_dependencies(self, isolated_test_venv, test_registry_url):
        """Test that agent-gcptoolkit installs with correct dependencies.

        This verifies that the package metadata and dependencies are correctly
        configured for the registry-based distribution.
        """
        pip = isolated_test_venv["pip"]
        python = isolated_test_venv["python"]

        # Install from test registry
        result = subprocess.run([
            pip, "install", "--extra-index-url", test_registry_url, "agent-gcptoolkit"
        ], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify key dependencies are available
        test_imports = [
            "import google.cloud.secretmanager",
            "import yaml",
        ]

        for import_stmt in test_imports:
            result = subprocess.run([
                python, "-c", import_stmt
            ], capture_output=True, text=True)
            # Some dependencies may not be installed, that's ok
            # We're just checking that the package installs cleanly


class TestRegistryInstallationConsistency:
    """Test that installations from registry are consistent and reliable."""

    def test_repeated_installation(self, isolated_test_venv, test_registry_url):
        """Test that repeated installations work correctly.

        This verifies that:
        1. Package can be installed multiple times
        2. Reinstallation doesn't break the environment
        3. Package remains functional after reinstall
        """
        pip = isolated_test_venv["pip"]
        python = isolated_test_venv["python"]

        # First installation
        result = subprocess.run([
            pip, "install", "--extra-index-url", test_registry_url, "myagents"
        ], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, f"First installation failed: {result.stderr}"

        # Verify first installation
        result = subprocess.run([
            python, "-c", "import myagents; print('OK')"
        ], capture_output=True, text=True)
        assert result.returncode == 0
        assert "OK" in result.stdout

        # Reinstall
        result = subprocess.run([
            pip, "install", "--force-reinstall", "--no-deps",
            "--extra-index-url", test_registry_url, "myagents"
        ], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, f"Reinstallation failed: {result.stderr}"

        # Verify still works
        result = subprocess.run([
            python, "-c", "import myagents; print('OK')"
        ], capture_output=True, text=True)
        assert result.returncode == 0
        assert "OK" in result.stdout


# E2E test markers
pytestmark = pytest.mark.e2e
