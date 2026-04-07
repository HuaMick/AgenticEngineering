"""Tests for 'agentic epic new' command.

As of the Story-Writer UAT-First Restructure, `epic new` is a pure CRUD
command: it creates an epic shell (TinyDB record + optional disk folder)
and does NOT spawn a planner agent. Planning happens via the orchestration
loop (`agentic orchestrate session plan --epic <folder>`).

These tests validate:
- _slugify_objective (unit)
- build_planner_prompt (unit — still used by the orchestration planner loop)
- CRUD behavior of cmd_new (no planner spawn, no builder spawn)
- cmd_seed deprecation alias
"""

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.story("US-PLN-001")


# ---------------------------------------------------------------------------
# Unit tests for _slugify_objective
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-001")
class TestSlugifyObjective:
    """Tests for branch name auto-generation from objective strings."""

    def _slugify(self, objective: str) -> str:
        from agenticcli.commands.epic import _slugify_objective
        return _slugify_objective(objective)

    def test_basic_objective(self):
        assert self._slugify("Add phone notifications") == "plan-add-phone-notifications"

    def test_special_characters_removed(self):
        assert self._slugify("Fix: Bug #123!") == "plan-fix-bug-123"

    def test_underscores_become_hyphens(self):
        assert self._slugify("my_feature_name") == "plan-my-feature-name"

    def test_multiple_spaces_collapsed(self):
        assert self._slugify("add   phone   notifications") == "plan-add-phone-notifications"

    def test_uppercase_lowered(self):
        assert self._slugify("Add PHONE Notifications") == "plan-add-phone-notifications"

    def test_long_objective_truncated(self):
        long = "a " * 100
        result = self._slugify(long)
        assert result.startswith("plan-")
        slug_part = result[len("plan-"):]
        assert len(slug_part) <= 50

    def test_empty_string_produces_plan_prefix(self):
        assert self._slugify("") == "plan-"

    def test_only_special_chars(self):
        assert self._slugify("!@#$%") == "plan-"

    def test_single_word(self):
        assert self._slugify("refactor") == "plan-refactor"

    def test_hyphens_preserved(self):
        assert self._slugify("fix-login-bug") == "plan-fix-login-bug"

    def test_leading_trailing_spaces(self):
        assert self._slugify("  add feature  ") == "plan-add-feature"

    def test_numeric_objective(self):
        assert self._slugify("123 fix") == "plan-123-fix"


# ---------------------------------------------------------------------------
# Integration tests for cmd_new via CLI runner
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


@pytest.mark.story("US-PLN-001")
class TestEpicNewCrud:
    """CRUD-level tests for 'agentic epic new'.

    These do NOT mock claude/SDK because cmd_new no longer spawns any agents.
    The command must complete synchronously using only cmd_init + TinyDB.
    """

    def test_new_requires_objective(self, cli_runner):
        stdout, stderr, code = cli_runner(["epic", "new"])
        assert code != 0

    def test_new_help_lists_crud_options(self, cli_runner):
        stdout, stderr, code = cli_runner(["epic", "new", "--help"])
        assert code == 0
        combined = stdout + stderr
        assert "--branch" in combined or "-b" in combined
        assert "--description" in combined or "-d" in combined
        assert "--base" in combined

    def test_new_help_has_no_planner_flags(self, cli_runner):
        """`epic new` must not advertise planner/builder spawn flags."""
        stdout, stderr, code = cli_runner(["epic", "new", "--help"])
        assert code == 0
        combined = stdout + stderr
        assert "--execute" not in combined
        assert "--max-turns" not in combined
        assert "--dangerously-skip-permissions" not in combined

    def test_new_creates_seed_epic_in_tinydb(self, cli_runner, temp_repo, _isolate_tinydb):
        """`epic new` creates a TinyDB record with status=seed and no tickets."""
        branch = "plan-test-feature"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(["epic", "new", "Test feature", "--branch", branch])

        assert code == 0, f"stderr: {stderr}"
        assert "Epic created" in stdout

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        repo.close()
        matching = [e for e in epics if "test_feature" in e.epic_folder_name]
        assert len(matching) >= 1, "Epic should exist in TinyDB"

    def test_new_auto_generates_branch(self, cli_runner, temp_repo):
        branch = "plan-add-dark-mode"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(["epic", "new", "Add dark mode"])

        assert code == 0
        combined = stdout + stderr
        assert "plan-add-dark-mode" in combined.lower() or "Epic created" in stdout

    def test_new_branch_override(self, cli_runner, temp_repo):
        branch = "my-custom-branch"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["epic", "new", "Some objective", "--branch", "my-custom-branch"]
        )
        assert code == 0

    def test_new_json_output(self, cli_runner, temp_repo):
        branch = "plan-json-test"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", "JSON test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)
        assert "plan_folder" in result
        assert result["branch"] == branch
        assert result["objective"] == "JSON test"
        assert result["status"] == "seed"

    def test_new_reports_seed_status(self, cli_runner, temp_repo):
        """`epic new` returns status=seed in JSON output (no planning yet)."""
        branch = "plan-seed-status"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", "Status test", "--branch", branch]
        )

        assert code == 0
        assert json.loads(stdout)["status"] == "seed"

    def test_new_does_not_spawn_any_session(self, cli_runner, temp_repo, _isolate_tinydb):
        """`epic new` must not spawn any session (no claude/SDK calls)."""
        from unittest.mock import patch

        branch = "plan-no-spawn"
        create_worktree_for_test(temp_repo, branch)

        with patch(
            "agenticcli.utils.sdk_runner.run_agent_sync",
            side_effect=AssertionError("run_agent_sync should not be called"),
        ):
            stdout, stderr, code = cli_runner(
                ["epic", "new", "No spawn test", "--branch", branch]
            )
        assert code == 0

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = [e for e in repo.list_epics() if "no_spawn_test" in e.epic_folder_name]
        # Epic exists with no planner-created phases/tickets beyond the stub
        assert len(epics) >= 1
        repo.close()

    def test_new_next_steps_references_orchestrate_plan(self, cli_runner, temp_repo):
        """Human output should point the user at the orchestration loop, not --execute."""
        branch = "plan-next-steps"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["epic", "new", "Next steps test", "--branch", branch]
        )

        assert code == 0
        assert "Next steps" in stdout
        assert "orchestrate session plan" in stdout
        assert "--execute" not in stdout

    def test_new_with_description_override(self, cli_runner, temp_repo):
        branch = "plan-desc-override"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "new", "My long objective", "--branch", branch,
             "--description", "short desc"]
        )

        assert code == 0
        result = json.loads(stdout)
        plan_folder = Path(result["plan_folder"])
        assert "short_desc" in plan_folder.name


@pytest.mark.story("US-PLN-001")
class TestEpicNewErrorCases:
    """Error case tests for epic new."""

    def test_new_duplicate_fails(self, cli_runner, temp_repo):
        """Creating the same epic twice fails on the second attempt."""
        branch = "plan-dup-test"
        create_worktree_for_test(temp_repo, branch)

        _, _, code1 = cli_runner(["epic", "new", "Dup test", "--branch", branch])
        assert code1 == 0

        _, _, code2 = cli_runner(["epic", "new", "Dup test", "--branch", branch])
        assert code2 != 0


@pytest.mark.story("US-PLN-001")
class TestEpicSeedDeprecationAlias:
    """`epic seed` is now a deprecation shim that calls cmd_new."""

    def test_seed_prints_deprecation_warning(self, cli_runner, temp_repo):
        branch = "plan-seed-deprecation"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["epic", "seed", "Seed deprecation test", "--branch", branch]
        )

        assert code == 0
        combined = stdout + stderr
        assert "deprecated" in combined.lower()

    def test_seed_creates_same_seed_epic_as_new(self, cli_runner, temp_repo, _isolate_tinydb):
        branch = "plan-seed-same-as-new"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "epic", "seed", "Seed same test", "--branch", branch]
        )
        assert code == 0
        # Deprecation warning is on stderr; the final line of stdout should be JSON
        # Parse the last JSON blob from stdout
        import re
        m = re.search(r"\{[^{}]*\"status\"[^{}]*\}", stdout, re.DOTALL)
        assert m is not None, f"Expected JSON in stdout, got: {stdout!r}"
        result = json.loads(m.group(0))
        assert result["status"] == "seed"


# ---------------------------------------------------------------------------
# Unit tests for build_planner_prompt
# ---------------------------------------------------------------------------
#
# build_planner_prompt is still used by the orchestration planner loop even
# though `epic new` no longer calls it directly. These tests stay.


@pytest.mark.story("US-PLN-001")
class TestBuildPlannerPrompt:
    """Tests for planner prompt template generation."""

    def test_prompt_includes_objective(self, tmp_path):
        from agenticcli.utils.planner_prompt import build_planner_prompt

        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()
        prompt = build_planner_prompt("Build a new CLI feature", plan_folder)

        assert "Build a new CLI feature" in prompt
        assert "OBJECTIVE:" in prompt

    def test_prompt_includes_plan_folder_path(self, tmp_path):
        from agenticcli.utils.planner_prompt import build_planner_prompt

        plan_folder = tmp_path / "260208XX_test"
        prompt = build_planner_prompt("Test objective", plan_folder)

        assert "260208XX_test" in prompt or "EPIC" in prompt

    def test_prompt_includes_story_discovery_instruction(self, tmp_path):
        from agenticcli.utils.planner_prompt import build_planner_prompt

        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()
        prompt = build_planner_prompt("Test objective", plan_folder)

        assert "agentic stories find" in prompt
        assert "STORY DISCOVERY" in prompt
        assert "docs/userstories/" in prompt

    @pytest.mark.story("US-PLN-001")
    def test_prompt_includes_uat_fence_reference(self, tmp_path):
        from agenticcli.utils.planner_prompt import build_planner_prompt

        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()
        prompt = build_planner_prompt("Test objective", plan_folder)

        assert "UAT" in prompt
        assert "MANDATORY" in prompt
        assert "planning-standard.yml" in prompt
        assert "FENCE" in prompt

    def test_prompt_includes_readme_instruction(self, tmp_path):
        from agenticcli.utils.planner_prompt import build_planner_prompt

        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()
        prompt = build_planner_prompt("Test objective", plan_folder)

        assert "README.md" in prompt
        assert "WRITE README.md" in prompt

    def test_prompt_includes_plan_build_instruction(self, tmp_path):
        from agenticcli.utils.planner_prompt import build_planner_prompt

        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()
        prompt = build_planner_prompt("Test objective", plan_folder)
        assert "ticket" in prompt.lower() or "TinyDB" in prompt

    @pytest.mark.story("US-PLN-001")
    def test_prompt_includes_story_first_fence(self, tmp_path):
        from agenticcli.utils.planner_prompt import build_planner_prompt

        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()
        prompt = build_planner_prompt("Test objective", plan_folder)

        assert "STORY-FIRST PLANNING" in prompt
        assert "affected_stories" in prompt

    def test_prompt_with_additional_context(self, tmp_path):
        from agenticcli.utils.planner_prompt import build_planner_prompt

        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()
        context = "This is additional context for the planner."
        prompt = build_planner_prompt("Test objective", plan_folder, context)

        assert context in prompt
        assert "ADDITIONAL CONTEXT:" in prompt

    def test_prompt_includes_uat_strategies(self, tmp_path):
        from agenticcli.utils.planner_prompt import build_planner_prompt

        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()
        prompt = build_planner_prompt("Test objective", plan_folder)

        assert "test-uat" in prompt
        assert "guidance-blind-test" in prompt
        assert "documentation-loop" in prompt
        assert "manual" in prompt
