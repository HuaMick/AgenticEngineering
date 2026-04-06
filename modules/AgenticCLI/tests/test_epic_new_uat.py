"""UAT Tests for 'agentic plan new' command against user stories.

User Acceptance Testing for:
- US-ORCH-001: Initiate Implementation Planning
- US-ORCH-002: Main-First Planning Workflow
- US-CLI-010: Initialize Plan with Worktree (referenced in US-ORCH-002)

These tests validate end-to-end behavior from a user's perspective.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.story("US-PLN-001")


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


def _extract_epic_name_from_prompt(prompt: str) -> str | None:
    """Extract the epic folder name from a planner prompt string.

    The prompt contains a line like:  EPIC NAME: 260329AG_my_epic
    Returns that name, or None if not found.
    """
    import re
    match = re.search(r"EPIC NAME:\s*(\S+)", prompt)
    if match:
        return match.group(1)
    return None


def _populate_tinydb_for_mock(epic_folder_name: str, db_path: Path) -> None:
    """Populate TinyDB with mock planner tickets for epic_folder_name.

    Called by mock planner functions to simulate what a real planner agent
    would write to TinyDB after processing the planning objective.
    """
    from agenticguidance.services.epic_repository import EpicRepository

    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    # Ensure the epic record exists (cmd_init already created it, so upsert safely)
    existing = repo.get_epic(epic_folder_name)
    if not existing:
        repo.create_epic({
            "epic_folder_name": epic_folder_name,
            "epic_folder": "",
            "name": "Mock Plan",
            "status": "planning",
        })

    # Add mock phase + ticket so planner_created_tickets check passes
    repo.add_phase(epic_folder_name, {"name": "Build"})
    repo.add_ticket(epic_folder_name, "Build", {
        "id": "MOCK_001",
        "task_id": "MOCK_001",
        "name": "Mock task",
        "status": "pending",
        "agent": "build-python",
    })
    repo.close()


@pytest.fixture(autouse=True)
def mock_claude_subprocess(_isolate_tinydb):
    """Mock subprocess.run and SDK path in plan.py so claude calls don't hang.

    Git calls pass through to the real subprocess.run.
    Claude subprocess calls and SDK calls return mock results and populate TinyDB
    with mock tickets so the post-planner TinyDB validation passes.
    The epic name is extracted from the planner prompt text (contains "EPIC NAME: <name>").
    """
    real_subprocess_run = subprocess.run
    db_path = _isolate_tinydb

    def patched_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd and cmd[0] == "claude":
            # Extract epic name from the -p <prompt> argument and populate TinyDB
            try:
                p_idx = cmd.index("-p")
                epic_name = _extract_epic_name_from_prompt(cmd[p_idx + 1])
                if epic_name:
                    _populate_tinydb_for_mock(epic_name, db_path)
            except (ValueError, IndexError):
                pass
            mock_result = Mock()
            mock_result.stdout = "Planner output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            return mock_result
        return real_subprocess_run(cmd, *args, **kwargs)

    def mock_sdk_run(prompt, options=None, timeout_seconds=1800):
        """Mock SDK path - populates TinyDB so post-planner validation passes."""
        from agenticcli.utils.sdk_runner import SessionResult
        # Extract the epic name from the prompt text (contains "EPIC NAME: <name>")
        epic_name = _extract_epic_name_from_prompt(prompt)
        if epic_name:
            _populate_tinydb_for_mock(epic_name, db_path)
        return SessionResult(status="completed", result="Mock SDK planner output")

    with patch("agenticcli.commands.epic.subprocess.run", side_effect=patched_run):
        with patch("agenticcli.utils.sdk_runner.run_agent_sync", side_effect=mock_sdk_run):
            yield


# ---------------------------------------------------------------------------
# US-ORCH-001: Initiate Implementation Planning
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-079", "US-GDN-084", "US-GDN-085", "US-GDN-088")
class TestUSORCH001InitiatePlanning:
    """UAT for US-ORCH-001: Initiate Implementation Planning.

    Acceptance criteria:
    - Planning is initiated via _plan_build.yml entrypoint
    - The orchestration-planning agent coordinates the planning process
    - A worktree is created or verified via CLI commands (agentic epic init)
    - A plan folder is created in docs/epics/live/ with YYMMDDXX_description naming
    - The planning objective is captured and validated
    - Required phases are determined based on objective type
    """

    def test_plan_new_creates_folder_with_yymmddxx_naming(self, cli_runner, temp_repo, _isolate_tinydb):
        """Verify epic record created in TinyDB with YYMMDDXX naming (no disk folder needed)."""
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
            ["epic", "new", objective, "--branch", branch]
        )

        assert code == 0, f"Command should succeed. stderr: {stderr}"

        # Verify epic was created in TinyDB with correct naming (no disk folder required)
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        repo.close()

        matching = [e for e in epics if "test_feature_implementation" in e.epic_folder_name]
        assert len(matching) >= 1, "Epic should be created in TinyDB"

        # Verify naming convention: YYMMDDXX_description
        epic_name = matching[0].epic_folder_name
        name_parts = epic_name.split("_", 1)
        assert len(name_parts) == 2, "Epic name should have YYMMDDXX_description format"

        date_code = name_parts[0]
        assert len(date_code) == 8, "Date code should be 8 chars (YYMMDDXX)"
        assert date_code[:6].isdigit(), "First 6 chars should be YYMMDD"
        assert date_code[6:].isalpha(), "Last 2 chars should be XX code (uppercase letters)"

    def test_plan_new_spawns_planner_agent(self, cli_runner, temp_repo, _isolate_tinydb):
        """Verify planner agent is spawned with the objective and creates TinyDB records."""
        branch = "test-uat-planner"
        objective = "Build new CLI command"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", objective, "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        # Verify objective was captured
        assert result["objective"] == objective

        # Verify plan folder path is in result (folder itself not required on disk)
        plan_folder = Path(result["plan_folder"])
        assert "docs/epics/live" in str(plan_folder), "Plan folder path should be in docs/epics/live"

        # Verify planner created tickets in TinyDB (TinyDB is the sole data store)
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epic = repo.get_epic(plan_folder.name)
        assert epic is not None, "Planner should create an epic record in TinyDB"
        tickets = repo.get_tickets(plan_folder.name)
        assert len(tickets) > 0, "Planner should create tickets in TinyDB"
        repo.close()

    def test_plan_new_captures_planning_objective(self, cli_runner, temp_repo, _isolate_tinydb):
        """Verify planning objective is captured and validated."""
        branch = "test-uat-objective"
        objective = "Add dark mode support"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", objective, "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        assert "objective" in result
        assert result["objective"] == objective

        # Verify objective is captured in the result (TinyDB is the sole data store)
        plan_folder = Path(result["plan_folder"])
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epic = repo.get_epic(plan_folder.name)
        assert epic is not None, "Epic should exist in TinyDB"
        repo.close()

    def test_plan_new_determines_required_phases(self, cli_runner, temp_repo, _isolate_tinydb):
        """Verify required phases are determined based on objective type."""
        branch = "test-uat-phases"
        objective = "Implement user authentication"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", objective, "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        # Verify phases created in TinyDB (TinyDB is the sole data store)
        plan_folder = Path(result["plan_folder"])
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        phases = repo.list_phases(plan_folder.name)
        assert len(phases) >= 1, "At least one phase should be created in TinyDB"
        repo.close()


# ---------------------------------------------------------------------------
# US-ORCH-002: Main-First Planning Workflow
# ---------------------------------------------------------------------------


@pytest.mark.story("US-GDN-085")
class TestUSORCH002PlanCreation:
    """UAT for plan creation workflow.

    Acceptance criteria:
    - Plan folders are created in docs/epics/live/
    - Plan creation via agentic plan new works end-to-end
    """

    def test_plan_folder_in_docs_plans_live(self, cli_runner, temp_repo):
        """Verify plan folder is created in docs/epics/live/."""
        branch = "feature-main-first"

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", "Plan creation test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        plan_folder = Path(result["plan_folder"])

        # Verify plan folder is under repo root
        assert temp_repo in plan_folder.parents, "Plan should be in repo root"

        # Verify it's in docs/epics/live/
        assert "docs/epics/live" in str(plan_folder), "Plan should be in docs/epics/live/"


# ---------------------------------------------------------------------------
# US-ORCH-005: Orchestration Phase Tracking
# ---------------------------------------------------------------------------


@pytest.mark.story("US-GDN-097", "US-GDN-098")
class TestUSORCH005OrchestrationPhases:
    """UAT for US-ORCH-005: Orchestration phase tracking via TinyDB.

    After the folder-creation removal (260308MA), orchestration data is stored
    in TinyDB. These tests verify that:
    - plan new completes successfully
    - Phases/tickets are tracked in TinyDB
    - The result JSON includes the plan folder path
    """

    def test_orchestration_phases_created(self, cli_runner, temp_repo, _isolate_tinydb):
        """Verify plan new completes and TinyDB has phase/ticket records."""
        branch = "test-orch-mmd"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", "Orchestration test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        # TinyDB is the canonical data store; verify epic exists
        plan_folder = Path(result["plan_folder"])
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epic = repo.get_epic(plan_folder.name)
        repo.close()
        assert epic is not None, "Epic should be in TinyDB after plan new"

    def test_tinydb_contains_phase_data(self, cli_runner, temp_repo, _isolate_tinydb):
        """Verify TinyDB has phase records after plan new."""
        branch = "test-mmd-phases"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", "MMD phase test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        plan_folder = Path(result["plan_folder"])
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        phases = repo.list_phases(plan_folder.name)
        repo.close()
        assert len(phases) >= 1, "TinyDB should have at least one phase record"

    def test_orchestration_validated_after_creation(self, cli_runner, temp_repo):
        """Verify plan new completes successfully (orchestration validation is best-effort)."""
        branch = "test-mmd-validate"

        create_worktree_for_test(temp_repo, branch)

        # Run plan new
        stdout, stderr, code = cli_runner(
            ["epic", "new", "Validation test", "--branch", branch]
        )

        assert code == 0

    def test_orchestration_generation_in_json_output(self, cli_runner, temp_repo, _isolate_tinydb):
        """Verify plan new returns valid JSON with plan folder and epic in TinyDB."""
        branch = "test-orch-json"

        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", "JSON orch test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        # Verify plan folder path is in result
        plan_folder = Path(result["plan_folder"])
        assert "docs/epics/live" in str(plan_folder), "Plan folder should be in docs/epics/live"

        # Verify epic is in TinyDB
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epic = repo.get_epic(plan_folder.name)
        repo.close()
        assert epic is not None, "Epic should be in TinyDB"


# ---------------------------------------------------------------------------
# Integration: Full workflow validation
# ---------------------------------------------------------------------------


class TestFullWorkflowIntegration:
    """Integration tests validating complete user journey."""

    def test_complete_planning_workflow(self, cli_runner, temp_repo, _isolate_tinydb):
        """Validate complete workflow from objective to ready plan (TinyDB-only)."""
        objective = "Build REST API endpoint"
        branch = "api-endpoint"

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", objective, "--branch", branch]
        )

        assert code == 0, "Plan creation should succeed"
        result = json.loads(stdout)

        # Verify all artifacts
        plan_folder = Path(result["plan_folder"])

        # 1. Plan folder path is in docs/epics/live (folder itself is not on disk)
        assert temp_repo in plan_folder.parents
        assert "docs/epics/live" in str(plan_folder)

        # 2. Planner created tickets in TinyDB (TinyDB is the sole data store)
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        tickets = repo.get_tickets(plan_folder.name)
        assert len(tickets) > 0, "Planner should create tickets in TinyDB"
        repo.close()

        # 3. Objective captured
        assert result["objective"] == objective

        # 4. Branch captured
        assert result["branch"] == branch

    def test_error_recovery_missing_objective(self, cli_runner, temp_repo):
        """Verify clear error when objective is missing."""
        stdout, stderr, code = cli_runner(
            ["epic", "new"]
        )

        assert code != 0, "Should fail without objective"
        combined = stdout + stderr
        assert "objective" in combined.lower() or "required" in combined.lower()

    def test_duplicate_plan_prevention(self, cli_runner, temp_repo):
        """Verify duplicate epic creation is prevented via TinyDB duplicate detection."""
        branch = "duplicate-test"
        objective = "Duplicate test"

        create_worktree_for_test(temp_repo, branch)

        # Create first plan
        stdout1, stderr1, code1 = cli_runner(
            ["epic", "new", objective, "--branch", branch]
        )
        assert code1 == 0

        # Try to create duplicate (same branch = same epic_folder_name)
        stdout2, stderr2, code2 = cli_runner(
            ["epic", "new", objective, "--branch", branch]
        )

        # Should fail - TinyDB detects duplicate epic_folder_name
        assert code2 != 0, "Duplicate plan creation should fail (TinyDB duplicate detection)"
