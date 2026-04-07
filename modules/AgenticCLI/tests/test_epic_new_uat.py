"""UAT tests for 'agentic epic new' command.

As of the Story-Writer UAT-First Restructure, `epic new` is a pure CRUD
command that creates an epic shell and does NOT spawn a planner. These UAT
tests validate the seed-epic user journey end-to-end: objective captured,
TinyDB record created, epic discoverable via `agentic epic list`, and the
orchestration loop's "discover seeded epics" pathway is left intact.
"""

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.story("US-PLN-001")


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


# ---------------------------------------------------------------------------
# US-PLN-001 (post-restructure): epic new creates a seed epic
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-001")
class TestEpicNewSeedJourney:
    """UAT for the seed-epic journey.

    Acceptance criteria (post-Story-Writer UAT-First Restructure):
    - `agentic epic new "<objective>"` creates a TinyDB record with status=seed
    - The epic folder name follows YYMMDDXX_description naming
    - The planning objective is captured
    - NO planner agent is spawned
    - The epic is discoverable via `agentic epic list`
    - The orchestration loop can pick up the seeded epic and invoke planners
    """

    def test_epic_new_creates_tinydb_record_with_yymmddxx_naming(
        self, cli_runner, temp_repo, _isolate_tinydb
    ):
        branch = "test-uat-naming"
        worktree_path = temp_repo.parent / "repo-AgenticTestNaming"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_path), "main"],
            cwd=temp_repo,
            capture_output=True,
            check=True,
        )

        stdout, stderr, code = cli_runner(
            ["epic", "new", "Test feature implementation", "--branch", branch]
        )
        assert code == 0, f"stderr: {stderr}"

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        repo.close()

        matching = [e for e in epics if "test_feature_implementation" in e.epic_folder_name]
        assert len(matching) >= 1

        epic_name = matching[0].epic_folder_name
        name_parts = epic_name.split("_", 1)
        assert len(name_parts) == 2
        date_code = name_parts[0]
        assert len(date_code) == 8
        assert date_code[:6].isdigit()
        assert date_code[6:].isalpha()

    def test_epic_new_does_not_spawn_planner(self, cli_runner, temp_repo, _isolate_tinydb):
        """Regression fence: cmd_new must not call run_agent_sync (no planner spawn)."""
        from unittest.mock import patch

        branch = "test-uat-no-planner"
        create_worktree_for_test(temp_repo, branch)

        with patch(
            "agenticcli.utils.sdk_runner.run_agent_sync",
            side_effect=AssertionError("epic new must not spawn a planner"),
        ):
            stdout, stderr, code = cli_runner(
                ["-j", "epic", "new", "No planner test", "--branch", branch]
            )

        assert code == 0
        result = json.loads(stdout)
        assert result["status"] == "seed"

    def test_epic_new_captures_objective(self, cli_runner, temp_repo, _isolate_tinydb):
        branch = "test-uat-objective"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", "Add dark mode support", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)
        assert result["objective"] == "Add dark mode support"

        plan_folder = Path(result["plan_folder"])
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epic = repo.get_epic(plan_folder.name)
        repo.close()
        assert epic is not None

    def test_seeded_epic_is_discoverable_via_epic_list(
        self, cli_runner, temp_repo, _isolate_tinydb
    ):
        """After `epic new`, the epic appears in `epic list` output."""
        branch = "test-uat-discoverable"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", "Discoverable test", "--branch", branch]
        )
        assert code == 0
        created = json.loads(stdout)

        # Verify discoverability via the listing path that the orchestration
        # loop relies on: EpicRepository.list_epics()
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        repo.close()
        names = [e.epic_folder_name for e in epics]
        assert Path(created["plan_folder"]).name in names


# ---------------------------------------------------------------------------
# Orchestration-loop handoff: discover_plans_needing_orchestration
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-001")
class TestOrchestrationLoopHandoff:
    """Verify the orchestration loop still picks up seeded epics.

    This is the critical downstream check from the plan:
    modules/AgenticCLI/src/agenticcli/workflows/orchestration.py:244-265
    (`discover_plans_needing_orchestration`) must continue to find epics in
    status `seed` or `planning`. We don't re-test orchestration internals;
    we just verify that seeded epics are reachable from that discovery path.
    """

    def test_seeded_epic_shows_up_for_orchestration_discovery(
        self, cli_runner, temp_repo, _isolate_tinydb
    ):
        branch = "test-uat-discovery"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", "Orchestration discovery test", "--branch", branch]
        )
        assert code == 0
        created = json.loads(stdout)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epic = repo.get_epic(Path(created["plan_folder"]).name)
        repo.close()

        assert epic is not None
        assert epic.status in ("seed", "planning"), (
            f"Expected status in (seed, planning) so orchestration loop picks it up, "
            f"got: {epic.status}"
        )


# ---------------------------------------------------------------------------
# Integration: full workflow validation
# ---------------------------------------------------------------------------


class TestFullWorkflowIntegration:
    """End-to-end CRUD journey: objective -> seed epic -> discoverable."""

    def test_complete_seed_workflow(self, cli_runner, temp_repo, _isolate_tinydb):
        objective = "Build REST API endpoint"
        branch = "api-endpoint"

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", objective, "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)

        plan_folder = Path(result["plan_folder"])
        assert temp_repo in plan_folder.parents
        assert "docs/epics/live" in str(plan_folder)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epic = repo.get_epic(plan_folder.name)
        repo.close()
        assert epic is not None

        assert result["objective"] == objective
        assert result["branch"] == branch
        assert result["status"] == "seed"

    def test_error_recovery_missing_objective(self, cli_runner, temp_repo):
        stdout, stderr, code = cli_runner(["epic", "new"])
        assert code != 0
        combined = stdout + stderr
        assert "objective" in combined.lower() or "required" in combined.lower()

    def test_duplicate_plan_prevention(self, cli_runner, temp_repo):
        branch = "duplicate-test"
        objective = "Duplicate test"
        create_worktree_for_test(temp_repo, branch)

        _, _, code1 = cli_runner(["epic", "new", objective, "--branch", branch])
        assert code1 == 0

        _, _, code2 = cli_runner(["epic", "new", objective, "--branch", branch])
        assert code2 != 0, "Duplicate epic creation should fail (TinyDB duplicate detection)"
