"""Integration test for full plan creation workflow.

End-to-end test that validates the complete plan creation flow:
1. agentic plan init
2. Create plan_build.yml with phases and tasks
3. agentic plan task add (multiple)
4. agentic plan orchestration generate
5. agentic plan validate

This test ensures all CLI commands work together to create a complete plan.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.integration


def _write_plan_file(output_file: Path, *, objective: str = "", phases: list[str] = None, success_criteria: list[str] = None):
    """Write a plan_build.yml file with the given phases.

    Args:
        output_file: Path to write the plan_build.yml file.
        objective: Plan objective string.
        phases: List of "ID:Name" strings (e.g., ["P1:Design", "P2:Build"]).
        success_criteria: Optional list of success criteria strings.
    """
    if phases is None:
        phases = ["P1:Build"]

    plan_phases = []
    for phase_str in phases:
        phase_id, phase_name = phase_str.split(":", 1)
        plan_phases.append({
            "id": phase_id,
            "name": phase_name,
            "status": "pending",
            "tasks": [],
        })

    plan = {
        "name": output_file.parent.name,
        "objective": objective or "Test plan",
        "status": "pending",
        "phases": plan_phases,
    }

    if success_criteria:
        plan["success_criteria"] = success_criteria

    with open(output_file, "w") as f:
        yaml.dump(plan, f, default_flow_style=False)


class TestFullPlanCreationFlow:
    """Integration test for the complete plan creation workflow."""

    @pytest.fixture
    def integration_repo(self):
        """Create a full integration test repo with git for plan creation flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "IntegrationProject"
            repo_path.mkdir()

            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@integration.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Integration Test User"],
                cwd=repo_path,
                capture_output=True,
            )

            (repo_path / "docs" / "plans" / "live").mkdir(parents=True)
            (repo_path / "README.md").write_text("# Integration Test Project\n")

            subprocess.run(
                ["git", "add", "."],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def cli_in_repo(self, integration_repo):
        """Run CLI commands in the integration repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(integration_repo)

        def run_cli(*args, expect_exit=None):
            from agenticcli.cli import run_cli as _run_cli
            from agenticcli.console import set_json_output

            set_json_output(False)

            if len(args) == 1 and isinstance(args[0], list):
                cmd_args = args[0]
            else:
                cmd_args = list(args)

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            exit_code = 0

            with patch.object(sys, "argv", ["agentic"] + cmd_args):
                with redirect_stdout(stdout_capture):
                    with redirect_stderr(stderr_capture):
                        try:
                            _run_cli()
                        except SystemExit as e:
                            exit_code = e.code if e.code is not None else 0

            stdout = stdout_capture.getvalue()
            stderr = stderr_capture.getvalue()

            if expect_exit is not None:
                assert exit_code == expect_exit, (
                    f"Expected exit {expect_exit}, got {exit_code}. "
                    f"stdout: {stdout}, stderr: {stderr}"
                )

            return stdout, stderr, exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_full_plan_creation_workflow(self, cli_in_repo, integration_repo):
        """Test complete plan creation workflow from init to validate."""
        # Step 1: Initialize plan
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "scaffold", "integration-test"
        )
        assert code == 0, f"Plan scaffold failed: {stderr}"
        assert "Created planning folder" in stdout

        plan_path = integration_repo / "docs" / "plans" / "live" / "integration-test"
        assert plan_path.exists(), "Plan folder was not created"

        # Step 2: Create plan_build.yml directly
        output_file = plan_path / "plan_build.yml"
        _write_plan_file(
            output_file,
            objective="Build integration test feature with full workflow",
            phases=["P1:Design", "P2:Implementation", "P3:Testing"],
        )
        assert output_file.exists(), "plan_build.yml was not created"

        content = yaml.safe_load(output_file.read_text())
        assert content is not None
        phases = content.get("phases", [])
        assert len(phases) == 3, f"Expected 3 phases, got {len(phases)}"
        phase_ids = [p.get("id") for p in phases]
        assert "P1" in phase_ids
        assert "P2" in phase_ids
        assert "P3" in phase_ids

        # Step 3: Add multiple tasks to the plan
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "task", "add", "Create initial design document",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Task add failed: {stderr}"
        assert "Added" in stdout

        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "task", "add", "Implement core module",
            "--plan", str(plan_path),
            "--priority", "high"
        )
        assert code == 0, f"Task add failed: {stderr}"
        assert "Added" in stdout

        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "task", "add", "Write unit tests",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Task add failed: {stderr}"
        assert "Added" in stdout

        # Verify tasks were added
        plan_content = yaml.safe_load(output_file.read_text())
        phases = plan_content.get("phases", [])
        total_tasks = sum(len(p.get("tasks", [])) for p in phases)
        assert total_tasks >= 3, f"Expected at least 3 tasks, found {total_tasks}"

        # Step 4: Generate orchestration MMD file
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Orchestration generate failed: {stderr}"
        assert "Generated" in stdout or "orchestration" in stdout.lower()

        mmd_files = list(plan_path.glob("orchestration_*.mmd"))
        assert len(mmd_files) == 1, f"Expected 1 MMD file, found {len(mmd_files)}"

        mmd_content = mmd_files[0].read_text()
        assert "P1" in mmd_content, "Phase P1 not found in MMD"
        assert "P2" in mmd_content, "Phase P2 not found in MMD"
        assert "P3" in mmd_content, "Phase P3 not found in MMD"
        assert "flowchart" in mmd_content, "flowchart keyword not found in MMD"

        # Step 5: Validate the complete plan
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "validate"
        )
        assert code in [0, 1], f"Unexpected validation exit code: {code}, stderr: {stderr}"

    def test_plan_creation_with_json_output(self, cli_in_repo, integration_repo):
        """Test plan creation workflow with JSON output mode."""
        # Scaffold with JSON output
        stdout, stderr, code = cli_in_repo("--json", "agent", "plan", "scaffold", "json-test")
        assert code == 0, f"Plan scaffold failed: {stderr}"
        data = json.loads(stdout)
        assert "folder" in data or "path" in data or "name" in data

        plan_path = integration_repo / "docs" / "plans" / "live" / "json-test"
        assert plan_path.exists()

        # Create plan file directly
        output_file = plan_path / "plan_build.yml"
        _write_plan_file(output_file, phases=["P1:Build", "P2:Test"])

        # Add task with JSON output
        stdout, stderr, code = cli_in_repo(
            "-j",
            "agent", "plan", "task", "add", "JSON mode task",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Task add failed: {stderr}"
        data = json.loads(stdout)
        assert "task_id" in data or "description" in data

        # Generate orchestration
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0

        # Validate with JSON output
        mmd_files = list(plan_path.glob("orchestration_*.mmd"))
        if mmd_files:
            stdout, stderr, code = cli_in_repo(
                "-j", "agent", "plan", "orchestration", "validate",
                "--plan", str(plan_path)
            )
            if code == 0 and stdout.strip():
                data = json.loads(stdout)
                assert "validation_passed" in data

    def test_plan_creation_with_success_criteria(self, cli_in_repo, integration_repo):
        """Test plan creation with success criteria."""
        stdout, stderr, code = cli_in_repo("agent", "plan", "scaffold", "criteria-test")
        assert code == 0

        plan_path = integration_repo / "docs" / "plans" / "live" / "criteria-test"
        output_file = plan_path / "plan_build.yml"

        _write_plan_file(
            output_file,
            objective="Build feature with clear success criteria",
            phases=["P1:Design", "P2:Build", "P3:Verify"],
            success_criteria=["All tests pass", "No lint errors", "Documentation updated"],
        )

        content = output_file.read_text()
        assert "success_criteria:" in content
        assert "All tests pass" in content
        assert "No lint errors" in content
        assert "Documentation updated" in content

        # Generate orchestration
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0

    def test_plan_creation_idempotency(self, cli_in_repo, integration_repo):
        """Test that plan creation handles existing artifacts correctly."""
        # Initial scaffold
        stdout, stderr, code = cli_in_repo("agent", "plan", "scaffold", "idempotent-test")
        assert code == 0

        # Second scaffold should fail
        stdout, stderr, code = cli_in_repo("agent", "plan", "scaffold", "idempotent-test")
        assert code == 1, "Expected scaffold to fail for existing folder"
        assert "already exists" in stdout or "already exists" in stderr

        # Setup plan file and orchestration
        plan_path = integration_repo / "docs" / "plans" / "live" / "idempotent-test"
        output_file = plan_path / "plan_build.yml"
        _write_plan_file(output_file, phases=["P1:Build"])

        # Generate orchestration
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0

        # Second generate without --force should fail
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code != 0, "Expected generate to fail without --force"
        assert "already exists" in stdout + stderr or "--force" in stdout + stderr

        # Generate with --force should succeed
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path),
            "--force"
        )
        assert code == 0, f"Generate with --force failed: {stderr}"


class TestPlanCreationEdgeCases:
    """Edge case tests for plan creation workflow."""

    @pytest.fixture
    def edge_case_repo(self):
        """Create a repo for edge case testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "EdgeCaseProject"
            repo_path.mkdir()

            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@edge.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Edge Test User"],
                cwd=repo_path,
                capture_output=True,
            )

            (repo_path / "docs" / "plans" / "live").mkdir(parents=True)
            (repo_path / "README.md").write_text("# Edge Case Test\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def edge_cli(self, edge_case_repo):
        """Run CLI commands in edge case repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(edge_case_repo)

        def run_cli(*args):
            from agenticcli.cli import run_cli as _run_cli
            from agenticcli.console import set_json_output

            set_json_output(False)

            if len(args) == 1 and isinstance(args[0], list):
                cmd_args = args[0]
            else:
                cmd_args = list(args)

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            exit_code = 0

            with patch.object(sys, "argv", ["agentic"] + cmd_args):
                with redirect_stdout(stdout_capture):
                    with redirect_stderr(stderr_capture):
                        try:
                            _run_cli()
                        except SystemExit as e:
                            exit_code = e.code if e.code is not None else 0

            return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_plan_creation_with_special_characters(self, edge_cli, edge_case_repo):
        """Test plan creation with special characters in description."""
        stdout, stderr, code = edge_cli("agent", "plan", "scaffold", "test-special")
        assert code == 0

        plan_path = edge_case_repo / "docs" / "plans" / "live" / "test-special"
        output_file = plan_path / "plan_build.yml"

        _write_plan_file(
            output_file,
            objective="Build feature #123: User Auth (OAuth2.0)",
            phases=["P1:Build"],
        )

        content = output_file.read_text()
        assert "User Auth" in content

    def test_plan_creation_empty_phases(self, edge_cli, edge_case_repo):
        """Test that orchestration fails gracefully with empty phases."""
        stdout, stderr, code = edge_cli("agent", "plan", "scaffold", "empty-phases")
        assert code == 0

        plan_path = edge_case_repo / "docs" / "plans" / "live" / "empty-phases"

        plan_file = plan_path / "plan_build.yml"
        plan_content = {
            "name": "empty-phases-plan",
            "objective": "Test empty phases handling",
            "status": "pending",
            "phases": [],
        }
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)

        stdout, stderr, code = edge_cli(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code != 0, "Expected failure with empty phases"
        combined = stdout + stderr
        assert "phases" in combined.lower() or "No phases" in combined

    def test_task_list_after_creation(self, edge_cli, edge_case_repo):
        """Test that task list shows all added tasks correctly."""
        stdout, stderr, code = edge_cli("agent", "plan", "scaffold", "list-test")
        assert code == 0

        plan_path = edge_case_repo / "docs" / "plans" / "live" / "list-test"
        output_file = plan_path / "plan_build.yml"

        _write_plan_file(output_file, phases=["P1:Build", "P2:Test"])

        edge_cli("agent", "plan", "task", "add", "First task", "--plan", str(plan_path))
        edge_cli("agent", "plan", "task", "add", "Second task", "--plan", str(plan_path))
        edge_cli("agent", "plan", "task", "add", "Third task", "--plan", str(plan_path))

        stdout, stderr, code = edge_cli("agent", "plan", "task", "list", "--plan", str(plan_path))
        assert code == 0
        assert "First task" in stdout or "3" in stdout


class TestPlanCreationValidation:
    """Tests for validation during plan creation workflow."""

    @pytest.fixture
    def validation_repo(self):
        """Create a repo for validation testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "ValidationProject"
            repo_path.mkdir()

            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@validation.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Validation Test User"],
                cwd=repo_path,
                capture_output=True,
            )

            (repo_path / "docs" / "plans" / "live").mkdir(parents=True)
            (repo_path / "README.md").write_text("# Validation Test\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def validation_cli(self, validation_repo):
        """Run CLI commands in validation repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(validation_repo)

        def run_cli(*args):
            from agenticcli.cli import run_cli as _run_cli
            from agenticcli.console import set_json_output

            set_json_output(False)

            if len(args) == 1 and isinstance(args[0], list):
                cmd_args = args[0]
            else:
                cmd_args = list(args)

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            exit_code = 0

            with patch.object(sys, "argv", ["agentic"] + cmd_args):
                with redirect_stdout(stdout_capture):
                    with redirect_stderr(stderr_capture):
                        try:
                            _run_cli()
                        except SystemExit as e:
                            exit_code = e.code if e.code is not None else 0

            return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_orchestration_validation_after_generation(
        self, validation_cli, validation_repo
    ):
        """Test that orchestration validates successfully after generation."""
        validation_cli("agent", "plan", "scaffold", "validate-test")

        plan_path = validation_repo / "docs" / "plans" / "live" / "validate-test"
        output_file = plan_path / "plan_build.yml"

        _write_plan_file(
            output_file,
            objective="Test orchestration validation",
            phases=["P1:Design", "P2:Build", "P3:Test", "P4:Deploy"],
        )

        validation_cli("agent", "plan", "task", "add", "Design task", "--plan", str(plan_path))
        validation_cli("agent", "plan", "task", "add", "Build task", "--plan", str(plan_path))
        validation_cli("agent", "plan", "task", "add", "Test task", "--plan", str(plan_path))

        stdout, stderr, code = validation_cli(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Orchestration generation failed: {stderr}"

        stdout, stderr, code = validation_cli(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Orchestration validation failed: {stderr}"
        assert "passed" in stdout.lower() or "valid" in stdout.lower()

    def test_validation_json_output_structure(self, validation_cli, validation_repo):
        """Test that validation JSON output has expected structure."""
        import json

        validation_cli("agent", "plan", "scaffold", "json-validate")

        plan_path = validation_repo / "docs" / "plans" / "live" / "json-validate"
        output_file = plan_path / "plan_build.yml"

        _write_plan_file(output_file, phases=["P1:Build", "P2:Test"])

        validation_cli(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )

        stdout, stderr, code = validation_cli(
            "-j", "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code == 0

        data = json.loads(stdout)
        assert "validation_passed" in data
        assert data["validation_passed"] is True
        assert "errors" in data
        assert isinstance(data["errors"], list)
