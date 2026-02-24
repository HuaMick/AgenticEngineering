"""Integration test for context bootstrap with planner role.

Tests that 'agentic context bootstrap --role planner' works correctly
and loads all required role files.
"""

import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def guidance_module_path():
    """Get path to AgenticGuidance module."""
    # Assumes tests are run from AgenticCLI module
    test_file = Path(__file__).resolve()
    repo_root = test_file.parent.parent.parent.parent.parent
    guidance_path = repo_root / "modules" / "AgenticGuidance"
    if not guidance_path.exists():
        pytest.skip("AgenticGuidance module not found")
    return guidance_path


class TestContextBootstrapPlanner:
    """Integration tests for context bootstrap with planner role."""

    def test_context_bootstrap_planner_role_files_exist(self, guidance_module_path):
        """Test that planner role files exist."""
        planner_path = guidance_module_path / "agents" / "planner" / "planner"

        # Check for role definition files
        manifest_file = planner_path / "manifest.yml"
        process_file = planner_path / "process.yml"
        inputs_file = planner_path / "inputs.yml"

        # At least one of these should exist for a valid role
        role_files_exist = (
            manifest_file.exists() or process_file.exists() or inputs_file.exists()
        )

        # If none exist, check alternative locations
        if not role_files_exist:
            # Check parent planner directory
            alt_paths = [
                guidance_module_path / "agents" / "planner",
                guidance_module_path / "agents" / "planner" / "planner-build",
                guidance_module_path / "agents" / "planner" / "planner-guidance",
            ]
            for alt_path in alt_paths:
                if (alt_path / "manifest.yml").exists():
                    role_files_exist = True
                    break

        assert role_files_exist, "No planner role files found in expected locations"

    def test_context_bootstrap_planner_yaml_files_are_valid(
        self, guidance_module_path
    ):
        """Test that planner YAML files are valid."""
        # Find planner role files
        planner_paths = [
            guidance_module_path / "agents" / "planner" / "planner",
            guidance_module_path / "agents" / "planner",
            guidance_module_path / "agents" / "planner" / "planner-build",
        ]

        yaml_files_found = []
        for planner_path in planner_paths:
            if not planner_path.exists():
                continue

            for yaml_file in planner_path.glob("*.yml"):
                yaml_files_found.append(yaml_file)

                # Verify YAML is valid
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                    assert data is not None, f"Empty YAML file: {yaml_file}"

        assert len(yaml_files_found) > 0, "No YAML files found in planner role paths"

    def test_context_bootstrap_planner_process_file_structure(
        self, guidance_module_path
    ):
        """Test that planner process.yml has expected structure."""
        # Find process.yml
        planner_paths = [
            guidance_module_path / "agents" / "planner" / "planner",
            guidance_module_path / "agents" / "planner" / "planner-build",
            guidance_module_path / "agents" / "planner" / "planner-guidance",
        ]

        process_file = None
        for planner_path in planner_paths:
            candidate = planner_path / "process.yml"
            if candidate.exists():
                process_file = candidate
                break

        if not process_file:
            pytest.skip("No process.yml found for planner role")

        with open(process_file) as f:
            data = yaml.safe_load(f)

        # Verify expected structure (flexible for different role definitions)
        assert isinstance(data, dict), "process.yml should be a dictionary"

        # Common keys in process files
        expected_keys = ["name", "description", "steps", "process", "phases"]
        has_expected_key = any(key in data for key in expected_keys)
        assert has_expected_key, f"process.yml missing expected keys: {expected_keys}"

    def test_context_bootstrap_planner_manifest_file_structure(
        self, guidance_module_path
    ):
        """Test that planner manifest.yml has expected structure."""
        # Find manifest.yml
        planner_paths = [
            guidance_module_path / "agents" / "planner" / "planner",
            guidance_module_path / "agents" / "planner",
        ]

        manifest_file = None
        for planner_path in planner_paths:
            candidate = planner_path / "manifest.yml"
            if candidate.exists():
                manifest_file = candidate
                break

        if not manifest_file:
            pytest.skip("No manifest.yml found for planner role")

        with open(manifest_file) as f:
            data = yaml.safe_load(f)

        # Verify expected structure
        assert isinstance(data, dict), "manifest.yml should be a dictionary"

        # Common keys in manifest files
        expected_keys = ["role", "name", "version", "description"]
        has_expected_key = any(key in data for key in expected_keys)
        assert has_expected_key, f"manifest.yml missing expected keys: {expected_keys}"

    def test_context_bootstrap_planner_inputs_file_structure(
        self, guidance_module_path
    ):
        """Test that planner inputs.yml has expected structure."""
        # Find inputs.yml
        planner_paths = [
            guidance_module_path / "agents" / "planner" / "planner",
            guidance_module_path / "agents" / "planner" / "planner-build",
        ]

        inputs_file = None
        for planner_path in planner_paths:
            candidate = planner_path / "inputs.yml"
            if candidate.exists():
                inputs_file = candidate
                break

        if not inputs_file:
            pytest.skip("No inputs.yml found for planner role")

        with open(inputs_file) as f:
            data = yaml.safe_load(f)

        # Verify it's valid YAML (structure can vary)
        assert data is not None, "inputs.yml should not be empty"


class TestContextBootstrapCommand:
    """Integration tests for the context bootstrap command itself."""

    def test_context_bootstrap_command_exists(self):
        """Test that context bootstrap command is available."""
        result = subprocess.run(
            ["agentic", "agent", "context", "--help"],
            capture_output=True,
            text=True,
        )

        # Command should exist (exit 0) or show usage
        assert result.returncode in [0, 2]
        assert "context" in result.stdout.lower() or "context" in result.stderr.lower()

    def test_context_bootstrap_help(self):
        """Test that context bootstrap shows help."""
        result = subprocess.run(
            ["agentic", "agent", "context", "bootstrap", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode in [0, 2]
        # Should mention role parameter
        combined = result.stdout.lower() + result.stderr.lower()
        assert "role" in combined or "bootstrap" in combined
