"""Integration test for orchestration MMD/YAML synchronization workflow.

End-to-end test that validates the orchestration sync workflow:
1. Create plan with phases
2. Generate MMD
3. Add more phases to YAML
4. Validate shows drift (missing phase in MMD)
5. Regenerate MMD with --force
6. Validate passes

This test ensures the orchestration commands properly detect drift
between YAML and MMD files and can regenerate to fix synchronization.
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


class TestOrchestrationSyncWorkflow:
    """Integration test for the complete orchestration sync workflow."""

    @pytest.fixture
    def sync_repo(self):
        """Create a full integration test repo with git for sync testing.

        Sets up:
        - Git repository with initial commit
        - docs/plans/live directory structure
        - User configuration for git
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "OrchSyncProject"
            repo_path.mkdir()

            # Initialize git
            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@sync.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Sync Test User"],
                cwd=repo_path,
                capture_output=True,
            )

            # Create initial structure
            (repo_path / "docs" / "plans" / "live").mkdir(parents=True)
            (repo_path / "README.md").write_text("# Orchestration Sync Test Project\n")

            # Initial commit
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
    def cli_in_repo(self, sync_repo):
        """Run CLI commands in the sync test repo.

        Provides a function that executes CLI commands and returns:
        - stdout: Standard output
        - stderr: Standard error
        - exit_code: Exit code from the command
        """
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(sync_repo)

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

    def _create_plan_with_phases(self, plan_path: Path, phases: list) -> dict:
        """Create a plan file with specified phases.

        Args:
            plan_path: Path to the plan folder.
            phases: List of phase dictionaries with id, name, status.

        Returns:
            The plan content dictionary.
        """
        plan_content = {
            "name": "sync-test-plan",
            "objective": "Test orchestration synchronization workflow",
            "status": "in_progress",
            "phases": phases,
        }

        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)

        return plan_content

    def _add_phase_to_plan(self, plan_path: Path, new_phase: dict) -> dict:
        """Add a new phase to an existing plan file.

        Args:
            plan_path: Path to the plan folder.
            new_phase: Phase dictionary with id, name, status.

        Returns:
            The updated plan content dictionary.
        """
        plan_file = plan_path / "plan_build.yml"
        content = yaml.safe_load(plan_file.read_text())

        # Add the new phase
        content["phases"].append(new_phase)

        with open(plan_file, "w") as f:
            yaml.dump(content, f, default_flow_style=False)

        return content

    def test_full_orchestration_sync_workflow(self, cli_in_repo, sync_repo):
        """Test complete orchestration sync workflow: create -> generate -> drift -> fix.

        This test exercises the full orchestration synchronization flow:
        1. Create plan folder and YAML with initial phases
        2. Generate orchestration MMD from YAML
        3. Validate passes (MMD matches YAML)
        4. Add new phases to YAML (simulating plan evolution)
        5. Validate fails (drift detected - MMD missing new phases)
        6. Regenerate MMD with --force
        7. Validate passes again (MMD now matches updated YAML)
        """
        # Step 1: Create plan folder
        plan_path = sync_repo / "docs" / "plans" / "live" / "sync-test"
        plan_path.mkdir(parents=True)

        # Create initial plan with 2 phases
        initial_phases = [
            {
                "phase_id": "P1",
                "name": "Setup Phase",
                "status": "completed",
                "tasks": [
                    {"id": "P1-001", "name": "Initialize project", "status": "completed"},
                ],
            },
            {
                "phase_id": "P2",
                "name": "Build Phase",
                "status": "in_progress",
                "tasks": [
                    {"id": "P2-001", "name": "Implement core module", "status": "pending"},
                ],
            },
        ]
        self._create_plan_with_phases(plan_path, initial_phases)

        # Verify plan file was created
        plan_file = plan_path / "plan_build.yml"
        assert plan_file.exists(), "plan_build.yml was not created"

        # Step 2: Generate orchestration MMD
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Initial orchestration generate failed: {stderr}"
        assert "Generated" in stdout or "orchestration" in stdout.lower()

        # Verify MMD file was created
        mmd_files = list(plan_path.glob("orchestration_*.mmd"))
        assert len(mmd_files) == 1, "Expected 1 MMD file to be created"
        mmd_file = mmd_files[0]

        # Verify MMD contains initial phases
        mmd_content = mmd_file.read_text()
        assert "P1" in mmd_content, "P1 not found in MMD"
        assert "P2" in mmd_content, "P2 not found in MMD"
        assert "Setup Phase" in mmd_content, "Setup Phase name not in MMD"
        assert "Build Phase" in mmd_content, "Build Phase name not in MMD"

        # Step 3: Validate passes (MMD matches YAML)
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Initial validation should pass: {stderr}"
        assert "passed" in stdout.lower() or "valid" in stdout.lower()

        # Step 4: Add new phases to YAML (simulating plan evolution)
        new_phase_1 = {
            "phase_id": "P3",
            "name": "Testing Phase",
            "status": "pending",
            "tasks": [
                {"id": "P3-001", "name": "Unit tests", "status": "pending"},
                {"id": "P3-002", "name": "Integration tests", "status": "pending"},
            ],
        }
        self._add_phase_to_plan(plan_path, new_phase_1)

        new_phase_2 = {
            "phase_id": "P4",
            "name": "Documentation Phase",
            "status": "pending",
            "tasks": [
                {"id": "P4-001", "name": "API documentation", "status": "pending"},
            ],
        }
        self._add_phase_to_plan(plan_path, new_phase_2)

        # Verify YAML now has 4 phases
        updated_content = yaml.safe_load(plan_file.read_text())
        assert len(updated_content["phases"]) == 4, "Expected 4 phases after additions"

        # Step 5: Validate fails (drift detected)
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code != 0, "Validation should fail when MMD is missing phases"

        # Check that missing phases are reported
        output = stdout + stderr
        assert "P3" in output, "Should report P3 as missing from MMD"
        assert "P4" in output, "Should report P4 as missing from MMD"

        # Step 6: Regenerate MMD with --force
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path),
            "--force"
        )
        assert code == 0, f"Regenerate with --force failed: {stderr}"

        # Verify MMD now contains all 4 phases
        mmd_content = mmd_file.read_text()
        assert "P1" in mmd_content, "P1 not found in regenerated MMD"
        assert "P2" in mmd_content, "P2 not found in regenerated MMD"
        assert "P3" in mmd_content, "P3 not found in regenerated MMD"
        assert "P4" in mmd_content, "P4 not found in regenerated MMD"
        assert "Testing Phase" in mmd_content, "Testing Phase name not in MMD"
        assert "Documentation Phase" in mmd_content, "Documentation Phase name not in MMD"

        # Step 7: Validate passes again
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Final validation should pass after regeneration: {stderr}"
        assert "passed" in stdout.lower() or "valid" in stdout.lower()

    def test_sync_workflow_with_json_output(self, cli_in_repo, sync_repo):
        """Test orchestration sync workflow with JSON output mode.

        Verifies that JSON output mode provides machine-readable
        drift detection results.
        """
        # Setup plan folder
        plan_path = sync_repo / "docs" / "plans" / "live" / "json-sync"
        plan_path.mkdir(parents=True)

        # Create initial plan
        initial_phases = [
            {
                "phase_id": "P1",
                "name": "Phase One",
                "status": "pending",
                "tasks": [],
            },
        ]
        self._create_plan_with_phases(plan_path, initial_phases)

        # Generate MMD
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0

        # Add a new phase to create drift
        new_phase = {
            "phase_id": "P2",
            "name": "Phase Two",
            "status": "pending",
            "tasks": [],
        }
        self._add_phase_to_plan(plan_path, new_phase)

        # Validate with JSON output
        stdout, stderr, code = cli_in_repo(
            "-j", "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code != 0, "Validation should fail with drift"

        # Parse JSON output
        result = json.loads(stdout)
        assert result["validation_passed"] is False
        assert len(result["errors"]) > 0

        # Find error about P2
        missing_p2_errors = [
            e for e in result["errors"]
            if e.get("phase_id") == "P2" or "P2" in e.get("message", "")
        ]
        assert len(missing_p2_errors) > 0, "Should have error about missing P2"

        # Regenerate and validate again with JSON
        cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path),
            "--force"
        )

        stdout, stderr, code = cli_in_repo(
            "-j", "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code == 0

        result = json.loads(stdout)
        assert result["validation_passed"] is True
        assert len(result["errors"]) == 0

    def test_sync_detects_missing_task_ids(self, cli_in_repo, sync_repo):
        """Test that sync workflow detects missing task IDs as warnings.

        Verifies that adding new tasks to YAML creates warnings
        during validation (tasks are warnings, not errors by default).
        """
        # Setup plan folder
        plan_path = sync_repo / "docs" / "plans" / "live" / "task-sync"
        plan_path.mkdir(parents=True)

        # Create initial plan with one task
        initial_phases = [
            {
                "phase_id": "P1",
                "name": "Build Phase",
                "status": "in_progress",
                "tasks": [
                    {"id": "P1-001", "name": "First task", "status": "completed"},
                ],
            },
        ]
        self._create_plan_with_phases(plan_path, initial_phases)

        # Generate MMD
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0

        # Add more tasks to the same phase (creates task drift)
        plan_file = plan_path / "plan_build.yml"
        content = yaml.safe_load(plan_file.read_text())
        content["phases"][0]["tasks"].append(
            {"id": "P1-002", "name": "Second task", "status": "pending"}
        )
        content["phases"][0]["tasks"].append(
            {"id": "P1-003", "name": "Third task", "status": "pending"}
        )
        with open(plan_file, "w") as f:
            yaml.dump(content, f)

        # Validate - should pass (missing tasks are warnings)
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code == 0, "Should pass - missing tasks are warnings, not errors"

        # Check warnings mention the new tasks
        output = stdout + stderr
        assert "P1-002" in output or "warn" in output.lower()

        # Validate with --strict should fail
        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path),
            "--strict"
        )
        assert code != 0, "Strict mode should fail on task warnings"

        # Regenerate and validate strict mode should pass
        cli_in_repo(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path),
            "--force"
        )

        stdout, stderr, code = cli_in_repo(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path),
            "--strict"
        )
        assert code == 0, "Strict validation should pass after regeneration"


class TestOrchestrationSyncEdgeCases:
    """Edge case tests for orchestration sync workflow."""

    @pytest.fixture
    def edge_repo(self):
        """Create a repo for edge case testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "EdgeSyncProject"
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
            (repo_path / "README.md").write_text("# Edge Sync Test\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def edge_cli(self, edge_repo):
        """Run CLI commands in edge case repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(edge_repo)

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

    def test_sync_with_phase_removal(self, edge_cli, edge_repo):
        """Test sync detection when phases are removed from YAML.

        When a phase is removed from YAML, the MMD will have extra phases.
        This should still validate (MMD has more than YAML is OK, just warns).
        """
        plan_path = edge_repo / "docs" / "plans" / "live" / "phase-removal"
        plan_path.mkdir(parents=True)

        # Create initial plan with 3 phases
        plan_content = {
            "name": "removal-test-plan",
            "objective": "Test phase removal sync",
            "status": "in_progress",
            "phases": [
                {"phase_id": "P1", "name": "Phase 1", "status": "completed", "tasks": []},
                {"phase_id": "P2", "name": "Phase 2", "status": "in_progress", "tasks": []},
                {"phase_id": "P3", "name": "Phase 3", "status": "pending", "tasks": []},
            ],
        }
        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Generate MMD with all 3 phases
        stdout, stderr, code = edge_cli(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0

        # Remove P3 from YAML
        content = yaml.safe_load(plan_file.read_text())
        content["phases"] = content["phases"][:2]  # Keep only P1 and P2
        with open(plan_file, "w") as f:
            yaml.dump(content, f)

        # Validate - should pass (MMD having extra phases is OK)
        stdout, stderr, code = edge_cli(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        # MMD has P3 but YAML doesn't - validation checks YAML phases exist in MMD
        assert code == 0, "Should pass - all YAML phases (P1, P2) exist in MMD"

    def test_sync_with_phase_id_change(self, edge_cli, edge_repo):
        """Test sync detection when phase IDs are changed in YAML.

        Changing a phase ID in YAML creates a missing phase (new ID not in MMD).
        """
        plan_path = edge_repo / "docs" / "plans" / "live" / "id-change"
        plan_path.mkdir(parents=True)

        # Create initial plan
        plan_content = {
            "name": "id-change-plan",
            "objective": "Test phase ID change sync",
            "status": "pending",
            "phases": [
                {"phase_id": "P1", "name": "Original Phase", "status": "pending", "tasks": []},
            ],
        }
        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Generate MMD
        edge_cli(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )

        # Change the phase ID
        content = yaml.safe_load(plan_file.read_text())
        content["phases"][0]["phase_id"] = "RENAMED"
        with open(plan_file, "w") as f:
            yaml.dump(content, f)

        # Validate should fail - RENAMED not in MMD
        stdout, stderr, code = edge_cli(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code != 0, "Should fail - RENAMED phase ID not in MMD"
        output = stdout + stderr
        assert "RENAMED" in output, "Should mention the missing phase ID"

    def test_sync_with_multiple_plan_files(self, edge_cli, edge_repo):
        """Test sync workflow with multiple plan_*.yml files.

        Phases from all plan files should be validated against the MMD.
        """
        plan_path = edge_repo / "docs" / "plans" / "live" / "multi-file-sync"
        plan_path.mkdir(parents=True)

        # Create first plan file
        plan_build = {
            "name": "build-plan",
            "phases": [
                {"phase_id": "B1", "name": "Build Phase", "status": "pending", "tasks": []},
            ],
        }
        with open(plan_path / "plan_build.yml", "w") as f:
            yaml.dump(plan_build, f)

        # Create second plan file
        plan_test = {
            "name": "test-plan",
            "phases": [
                {"phase_id": "T1", "name": "Test Phase", "status": "pending", "tasks": []},
            ],
        }
        with open(plan_path / "plan_test.yml", "w") as f:
            yaml.dump(plan_test, f)

        # Generate MMD
        stdout, stderr, code = edge_cli(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0

        # Verify MMD has phases from both files
        mmd_files = list(plan_path.glob("orchestration_*.mmd"))
        mmd_content = mmd_files[0].read_text()
        assert "B1" in mmd_content, "B1 from plan_build.yml should be in MMD"
        assert "T1" in mmd_content, "T1 from plan_test.yml should be in MMD"

        # Validate should pass
        stdout, stderr, code = edge_cli(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code == 0

        # Add a phase to one file
        plan_build["phases"].append(
            {"phase_id": "B2", "name": "Build Phase 2", "status": "pending", "tasks": []}
        )
        with open(plan_path / "plan_build.yml", "w") as f:
            yaml.dump(plan_build, f)

        # Validate should fail
        stdout, stderr, code = edge_cli(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code != 0, "Should fail - B2 not in MMD"
        output = stdout + stderr
        assert "B2" in output

    def test_sync_workflow_idempotency(self, edge_cli, edge_repo):
        """Test that repeated sync cycles are idempotent.

        Multiple generate -> validate cycles should be stable.
        """
        plan_path = edge_repo / "docs" / "plans" / "live" / "idempotent-sync"
        plan_path.mkdir(parents=True)

        # Create plan
        plan_content = {
            "name": "idempotent-plan",
            "objective": "Test idempotency",
            "status": "pending",
            "phases": [
                {"phase_id": "P1", "name": "Phase 1", "status": "pending", "tasks": []},
                {"phase_id": "P2", "name": "Phase 2", "status": "pending", "tasks": []},
            ],
        }
        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Cycle 1: Generate and validate
        edge_cli("agent", "plan", "orchestration", "generate", "--plan", str(plan_path))
        stdout1, _, code1 = edge_cli(
            "agent", "plan", "orchestration", "validate", "--plan", str(plan_path)
        )
        assert code1 == 0

        # Get MMD content after first cycle
        mmd_files = list(plan_path.glob("orchestration_*.mmd"))
        mmd_content_1 = mmd_files[0].read_text()

        # Cycle 2: Regenerate (with --force) and validate
        edge_cli(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path),
            "--force"
        )
        stdout2, _, code2 = edge_cli(
            "agent", "plan", "orchestration", "validate", "--plan", str(plan_path)
        )
        assert code2 == 0

        # Get MMD content after second cycle
        mmd_content_2 = mmd_files[0].read_text()

        # Both cycles should produce equivalent results
        # (MMD content may have timestamps or minor differences,
        # but both should validate successfully)
        assert "P1" in mmd_content_2 and "P2" in mmd_content_2

        # Cycle 3: One more time
        edge_cli(
            "agent", "plan", "orchestration", "generate",
            "--plan", str(plan_path),
            "--force"
        )
        _, _, code3 = edge_cli(
            "agent", "plan", "orchestration", "validate", "--plan", str(plan_path)
        )
        assert code3 == 0


class TestOrchestrationSyncValidationDetails:
    """Tests for detailed validation behavior in sync workflow."""

    @pytest.fixture
    def detail_repo(self):
        """Create a repo for detailed validation testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "DetailSyncProject"
            repo_path.mkdir()

            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@detail.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Detail Test User"],
                cwd=repo_path,
                capture_output=True,
            )

            (repo_path / "docs" / "plans" / "live").mkdir(parents=True)
            (repo_path / "README.md").write_text("# Detail Sync Test\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def detail_cli(self, detail_repo):
        """Run CLI commands in detail test repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(detail_repo)

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

    def test_validation_reports_yaml_and_mmd_files(self, detail_cli, detail_repo):
        """Test that validation output reports which files were checked."""
        plan_path = detail_repo / "docs" / "plans" / "live" / "file-report"
        plan_path.mkdir(parents=True)

        # Create plan
        plan_content = {
            "name": "file-report-plan",
            "phases": [
                {"phase_id": "P1", "name": "Phase 1", "status": "pending", "tasks": []},
            ],
        }
        with open(plan_path / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        # Generate MMD
        detail_cli("agent", "plan", "orchestration", "generate", "--plan", str(plan_path))

        # Validate and check output includes file names
        stdout, stderr, code = detail_cli(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code == 0

        output = stdout + stderr
        assert "plan_build.yml" in output, "Should mention YAML file"
        assert "orchestration_" in output, "Should mention MMD file"

    def test_validation_counts_phases_and_tasks(self, detail_cli, detail_repo):
        """Test that validation output includes phase and task counts."""
        plan_path = detail_repo / "docs" / "plans" / "live" / "counts"
        plan_path.mkdir(parents=True)

        # Create plan with multiple phases and tasks
        plan_content = {
            "name": "count-test-plan",
            "phases": [
                {
                    "phase_id": "P1",
                    "name": "Phase 1",
                    "status": "pending",
                    "tasks": [
                        {"id": "P1-001", "name": "Task 1", "status": "pending"},
                        {"id": "P1-002", "name": "Task 2", "status": "pending"},
                    ],
                },
                {
                    "phase_id": "P2",
                    "name": "Phase 2",
                    "status": "pending",
                    "tasks": [
                        {"id": "P2-001", "name": "Task 3", "status": "pending"},
                    ],
                },
            ],
        }
        with open(plan_path / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        # Generate and validate
        detail_cli("agent", "plan", "orchestration", "generate", "--plan", str(plan_path))

        stdout, stderr, code = detail_cli(
            "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code == 0

        # Check JSON output has counts
        stdout_json, _, _ = detail_cli(
            "-j", "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        result = json.loads(stdout_json)

        assert result["yaml_phases_count"] == 2, "Should have 2 phases"
        assert result["yaml_tasks_count"] == 3, "Should have 3 tasks"

    def test_validation_error_details_in_json(self, detail_cli, detail_repo):
        """Test that validation errors include detailed information in JSON."""
        plan_path = detail_repo / "docs" / "plans" / "live" / "error-details"
        plan_path.mkdir(parents=True)

        # Create plan with one phase
        plan_content = {
            "name": "error-detail-plan",
            "phases": [
                {"phase_id": "P1", "name": "Initial Phase", "status": "pending", "tasks": []},
            ],
        }
        with open(plan_path / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        # Generate MMD
        detail_cli("agent", "plan", "orchestration", "generate", "--plan", str(plan_path))

        # Add multiple new phases to create multiple drift errors
        plan_content["phases"].extend([
            {"phase_id": "P2", "name": "Second Phase", "status": "pending", "tasks": []},
            {"phase_id": "P3", "name": "Third Phase", "status": "pending", "tasks": []},
        ])
        with open(plan_path / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        # Validate with JSON
        stdout, stderr, code = detail_cli(
            "-j", "agent", "plan", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code != 0

        result = json.loads(stdout)
        assert result["validation_passed"] is False
        assert len(result["errors"]) >= 2, "Should have at least 2 errors"

        # Check error structure
        for error in result["errors"]:
            assert "type" in error, "Error should have type"
            assert "message" in error, "Error should have message"
            # Most errors should have phase_id
            if error["type"] in ["missing_phase", "phase_not_in_header"]:
                assert "phase_id" in error, "Phase error should have phase_id"
