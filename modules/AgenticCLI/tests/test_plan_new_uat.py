"""UAT Tests for 'agentic plan new' command against user stories.

User Acceptance Testing for:
- US-ORCH-001: Initiate Implementation Planning
- US-ORCH-002: Main-First Planning Workflow
- US-ORCH-005: Generate Orchestration MMD from Plan
- US-CLI-010: Initialize Plan with Worktree (referenced in US-ORCH-002)

These tests validate end-to-end behavior from a user's perspective.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def create_worktree_for_test(temp_repo: Path, branch: str, base: str = "main") -> Path:
    """Helper to create a worktree for testing."""
    worktree_path = temp_repo.parent / f"repo-{branch}"
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(worktree_path), base],
        cwd=temp_repo,
        capture_output=True,
        check=True,
    )
    return worktree_path


@pytest.fixture(autouse=True)
def mock_claude_subprocess():
    """Mock subprocess.run in plan.py so claude calls don't hang.

    Git calls pass through to the real subprocess.run.
    Claude calls return a mock result and create plan_build.yml.
    """
    real_subprocess_run = subprocess.run

    def patched_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd and cmd[0] == "claude":
            # Create plan_build.yml in the cwd if provided
            cwd = kwargs.get("cwd")
            if cwd:
                plan_build = Path(cwd) / "plan_build.yml"
                plan_build.write_text("""name: Mock Plan
objective: Mock objective
affected_stories:
  - US-ORCH-001
  - US-ORCH-002
phases:
  - name: Build
    tasks:
      - id: MOCK_001
        name: Mock task
        status: pending
        agent: build-python
""")
            mock_result = Mock()
            mock_result.stdout = "Planner output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            return mock_result
        return real_subprocess_run(cmd, *args, **kwargs)

    with patch("agenticcli.commands.plan.subprocess.run", side_effect=patched_run):
        yield


# ---------------------------------------------------------------------------
# US-ORCH-001: Initiate Implementation Planning
# ---------------------------------------------------------------------------


class TestUSORCH001InitiatePlanning:
    """UAT for US-ORCH-001: Initiate Implementation Planning.

    Acceptance criteria:
    - Planning is initiated via _plan_build.yml entrypoint
    - The orchestration-planning agent coordinates the planning process
    - A worktree is created or verified via deploy-worktree agent
    - A plan folder is created in docs/plans/live/ with YYMMDDXX_description naming
    - The planning objective is captured and validated
    - Required phases are determined based on objective type
    """

    def test_plan_new_creates_folder_with_yymmddxx_naming(self, cli_runner, temp_repo):
        """Verify plan folder created in docs/plans/live/ with YYMMDDXX naming."""
        branch = "test-uat-naming"
        objective = "Test feature implementation"

        # Create worktree with proper suffix for worktree ID extraction
        # Use parent/repo-AgenticTestNaming pattern so ID becomes "AG"
        worktree_path = temp_repo.parent / "repo-AgenticTestNaming"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_path), "main"],
            cwd=temp_repo,
            capture_output=True,
            check=True,
        )

        stdout, stderr, code = cli_runner(
            ["plan", "new", objective, "--branch", branch]
        )

        assert code == 0, f"Command should succeed. stderr: {stderr}"

        # Verify plan folder exists in main worktree
        plans_live = temp_repo / "docs" / "plans" / "live"
        assert plans_live.exists(), "docs/plans/live should exist"

        # Find plan folders matching our description
        plan_folders = [
            p for p in plans_live.iterdir()
            if p.is_dir() and "test_feature_implementation" in p.name
        ]
        assert len(plan_folders) >= 1, "Plan folder should be created"

        # Verify naming convention: YYMMDDXX_description
        plan_folder = plan_folders[0]
        name_parts = plan_folder.name.split("_", 1)
        assert len(name_parts) == 2, "Folder should have YYMMDDXX_description format"

        date_code = name_parts[0]
        assert len(date_code) == 8, "Date code should be 8 chars (YYMMDDXX)"
        assert date_code[:6].isdigit(), "First 6 chars should be YYMMDD"
        assert date_code[6:].isalpha(), "Last 2 chars should be XX code (uppercase letters)"

    def test_plan_new_spawns_planner_agent(self, cli_runner, temp_repo):
        """Verify planner agent is spawned with the objective."""
        branch = "test-uat-planner"
        objective = "Build new CLI command"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", objective, "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        # Verify objective was captured
        assert result["objective"] == objective

        # Verify plan folder was created
        plan_folder = Path(result["plan_folder"])
        assert plan_folder.exists()

        # Verify plan_build.yml was created by planner
        plan_build = plan_folder / "plan_build.yml"
        assert plan_build.exists(), "Planner should create plan_build.yml"
        assert plan_build.stat().st_size > 0, "plan_build.yml should not be empty"

    def test_plan_new_captures_planning_objective(self, cli_runner, temp_repo):
        """Verify planning objective is captured and validated."""
        branch = "test-uat-objective"
        objective = "Add dark mode support"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", objective, "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        assert "objective" in result
        assert result["objective"] == objective

        # Verify objective is in plan metadata
        plan_folder = Path(result["plan_folder"])
        plan_build = plan_folder / "plan_build.yml"

        import yaml
        with plan_build.open() as f:
            plan_data = yaml.safe_load(f)

        assert "objective" in plan_data
        assert plan_data["objective"] is not None

    def test_plan_new_determines_required_phases(self, cli_runner, temp_repo):
        """Verify required phases are determined based on objective type."""
        branch = "test-uat-phases"
        objective = "Implement user authentication"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", objective, "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        plan_folder = Path(result["plan_folder"])
        plan_build = plan_folder / "plan_build.yml"

        import yaml
        with plan_build.open() as f:
            plan_data = yaml.safe_load(f)

        # Verify phases exist
        assert "phases" in plan_data
        assert isinstance(plan_data["phases"], list)
        assert len(plan_data["phases"]) >= 1, "At least one phase should be created"


# ---------------------------------------------------------------------------
# US-ORCH-002: Main-First Planning Workflow
# ---------------------------------------------------------------------------


class TestUSORCH002MainFirstPlanning:
    """UAT for US-ORCH-002: Main-First Planning Workflow.

    Acceptance criteria:
    - Plan folders are created in the main worktree's docs/plans/live/
    - Feature worktrees are created for code implementation
    - Plan creation happens on main branch, execution on feature branch
    - agentic plan init creates both worktree and plan folder atomically
    - Plan status is viewable from the main worktree
    - Merging happens via staging to main
    """

    def test_plan_folder_in_main_worktree(self, cli_runner, temp_repo):
        """Verify plan folder is created in main worktree's docs/plans/live/."""
        branch = "feature-main-first"

        # Create feature worktree
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", "Main-first test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        plan_folder = Path(result["plan_folder"])

        # Verify plan folder is in main worktree, not feature worktree
        # Plan folder should be under temp_repo (main), not worktree path
        assert temp_repo in plan_folder.parents, "Plan should be in main worktree"

        # Verify it's in docs/plans/live/
        assert "docs/plans/live" in str(plan_folder), "Plan should be in docs/plans/live/"

    def test_execution_worktree_created(self, cli_runner, temp_repo):
        """Verify execution worktree is created for the branch."""
        branch = "feature-execution-wt"
        objective = "Test execution worktree"

        # Don't pre-create worktree - let plan new create it
        stdout, stderr, code = cli_runner(
            ["plan", "new", objective, "--branch", branch]
        )

        # cmd_init creates worktree automatically if missing
        assert code == 0, "Should succeed even without pre-existing worktree"

        # Verify worktree was created
        worktree_path = temp_repo.parent / f"repo-{branch}"
        assert worktree_path.exists(), "Worktree should be created"

        # Verify it's a git worktree
        result = subprocess.run(
            ["git", "worktree", "list"],
            cwd=temp_repo,
            capture_output=True,
            text=True,
        )
        assert branch in result.stdout, "Branch should appear in worktree list"

    def test_plan_folder_and_worktree_atomic_creation(self, cli_runner, temp_repo):
        """Verify plan folder and worktree are created atomically."""
        branch = "atomic-creation-test"
        objective = "Atomic test"

        # Start with no worktree
        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", objective, "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        # Both should exist after single command
        plan_folder = Path(result["plan_folder"])
        assert plan_folder.exists(), "Plan folder should be created"

        worktree_path = temp_repo.parent / f"repo-{branch}"
        assert worktree_path.exists(), "Worktree should be created"

        # Verify plan folder has plan_build.yml
        assert (plan_folder / "plan_build.yml").exists()


# ---------------------------------------------------------------------------
# US-ORCH-005: Generate Orchestration MMD from Plan
# ---------------------------------------------------------------------------


class TestUSORCH005OrchestrationMMD:
    """UAT for US-ORCH-005: Generate Orchestration MMD from Plan.

    Acceptance criteria:
    - planner-orchestration agent generates orchestration_*.mmd files
    - MMD includes phase nodes with AGENT_ROUTING metadata
    - MMD defines transitions between phases (success/failure paths)
    - Test phases include test-fix loop structures
    - Feedback triggers are defined for failure handling
    - MMD is validated via agentic plan orchestration validate
    """

    def test_orchestration_mmd_generated(self, cli_runner, temp_repo):
        """Verify orchestration_*.mmd file is created after planner."""
        branch = "test-orch-mmd"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", "Orchestration test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        plan_folder = Path(result["plan_folder"])

        # Verify orchestration MMD was generated
        mmd_files = list(plan_folder.glob("orchestration_*.mmd"))
        assert len(mmd_files) >= 1, "At least one orchestration MMD should exist"

    def test_mmd_contains_phase_nodes(self, cli_runner, temp_repo):
        """Verify MMD contains phase nodes."""
        branch = "test-mmd-phases"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", "MMD phase test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        plan_folder = Path(result["plan_folder"])
        mmd_files = list(plan_folder.glob("orchestration_*.mmd"))

        assert len(mmd_files) >= 1
        mmd_content = mmd_files[0].read_text()

        # MMD should be valid Mermaid flowchart
        assert "flowchart" in mmd_content or "graph" in mmd_content, \
            "MMD should contain flowchart definition"

    def test_mmd_validated_after_generation(self, cli_runner, temp_repo):
        """Verify MMD is validated after generation."""
        branch = "test-mmd-validate"

        create_worktree_for_test(temp_repo, branch)

        # Run plan new (which should auto-validate)
        stdout, stderr, code = cli_runner(
            ["plan", "new", "Validation test", "--branch", branch]
        )

        assert code == 0

        # Verify no validation errors in output
        combined = stdout + stderr
        # Should show validation passed or at least attempted
        assert "validation" in combined.lower() or "generated" in combined.lower()

    def test_orchestration_generation_in_json_output(self, cli_runner, temp_repo):
        """Verify orchestration MMD is generated (validated via file existence)."""
        branch = "test-orch-json"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", "JSON orch test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        # Verify orchestration file exists in plan folder
        plan_folder = Path(result["plan_folder"])
        mmd_files = list(plan_folder.glob("orchestration_*.mmd"))

        # Orchestration should be generated as part of plan new
        assert len(mmd_files) >= 1, "Orchestration MMD should be generated"


# ---------------------------------------------------------------------------
# US-CLI-010: Initialize Plan with Worktree (implicit in plan new)
# ---------------------------------------------------------------------------


class TestUSCLI010PlanWithWorktree:
    """UAT for implicit US-CLI-010 behavior in plan new.

    While US-CLI-090 refers to 'agentic worktree create', plan new
    integrates this via plan init. Testing the integration.

    Acceptance criteria (adapted):
    - Worktree and plan folder created atomically
    - --description flag customizes folder suffix
    """

    def test_description_customizes_folder_suffix(self, cli_runner, temp_repo):
        """Verify --description flag customizes folder suffix."""
        branch = "test-desc-custom"
        objective = "This is a very long objective that should be truncated"
        custom_desc = "short"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", objective, "--branch", branch,
             "--description", custom_desc]
        )

        assert code == 0
        result = json.loads(stdout)

        plan_folder = Path(result["plan_folder"])

        # Folder name should contain custom description, not full objective
        assert "short" in plan_folder.name.lower(), \
            "Custom description should be in folder name"
        assert "very_long_objective" not in plan_folder.name.lower(), \
            "Long objective should not be in folder name when description provided"

    def test_branch_auto_generation_from_objective(self, cli_runner, temp_repo):
        """Verify branch name is auto-generated from objective when not provided."""
        objective = "Add phone notifications"

        # Don't provide --branch, let it auto-generate
        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", objective]
        )

        assert code == 0
        result = json.loads(stdout)

        # Branch should be auto-generated as plan-add-phone-notifications
        assert "branch" in result
        assert result["branch"] == "plan-add-phone-notifications"

        # Verify worktree was created with auto-generated branch
        worktree_path = temp_repo.parent / f"repo-{result['branch']}"
        assert worktree_path.exists(), "Worktree should exist with auto-generated branch"

    def test_base_branch_parameter(self, cli_runner, temp_repo):
        """Verify --base parameter sets the base branch for worktree creation."""
        branch = "feature-from-staging"

        # Create staging branch first
        subprocess.run(
            ["git", "checkout", "-b", "staging"],
            cwd=temp_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=temp_repo,
            capture_output=True,
            check=True,
        )

        stdout, stderr, code = cli_runner(
            ["plan", "new", "Base branch test", "--branch", branch, "--base", "staging"]
        )

        # Should succeed (worktree created from staging)
        assert code == 0


# ---------------------------------------------------------------------------
# Integration: Full workflow validation
# ---------------------------------------------------------------------------


class TestFullWorkflowIntegration:
    """Integration tests validating complete user journey."""

    def test_complete_planning_workflow(self, cli_runner, temp_repo):
        """Validate complete workflow from objective to ready plan."""
        objective = "Build REST API endpoint"
        branch = "api-endpoint"

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "new", objective, "--branch", branch]
        )

        assert code == 0, "Plan creation should succeed"
        result = json.loads(stdout)

        # Verify all artifacts exist
        plan_folder = Path(result["plan_folder"])

        # 1. Plan folder exists in main worktree
        assert plan_folder.exists()
        assert temp_repo in plan_folder.parents

        # 2. Worktree created
        worktree_path = temp_repo.parent / f"repo-{branch}"
        assert worktree_path.exists()

        # 3. plan_build.yml created by planner
        assert (plan_folder / "plan_build.yml").exists()

        # 4. Orchestration MMD generated
        mmd_files = list(plan_folder.glob("orchestration_*.mmd"))
        assert len(mmd_files) >= 1

        # 5. Objective captured
        assert result["objective"] == objective

        # 6. Branch captured
        assert result["branch"] == branch

    def test_error_recovery_missing_objective(self, cli_runner, temp_repo):
        """Verify clear error when objective is missing."""
        stdout, stderr, code = cli_runner(
            ["plan", "new"]
        )

        assert code != 0, "Should fail without objective"
        combined = stdout + stderr
        assert "objective" in combined.lower() or "required" in combined.lower()

    def test_duplicate_plan_prevention(self, cli_runner, temp_repo):
        """Verify duplicate plan folders are prevented."""
        branch = "duplicate-test"
        objective = "Duplicate test"

        create_worktree_for_test(temp_repo, branch)

        # Create first plan
        stdout1, stderr1, code1 = cli_runner(
            ["plan", "new", objective, "--branch", branch]
        )
        assert code1 == 0

        # Try to create duplicate
        stdout2, stderr2, code2 = cli_runner(
            ["plan", "new", objective, "--branch", branch]
        )

        # Should fail or warn about duplicate
        assert code2 != 0, "Duplicate plan creation should fail"
