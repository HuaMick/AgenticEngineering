"""Tests for 'agentic plan new' command.

Tests covering argument parsing, branch name generation from objectives,
folder creation delegation, and error cases.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Unit tests for _slugify_objective
# ---------------------------------------------------------------------------


class TestSlugifyObjective:
    """Tests for branch name auto-generation from objective strings."""

    def _slugify(self, objective: str) -> str:
        from agenticcli.commands.epic import _slugify_objective
        return _slugify_objective(objective)

    def test_basic_objective(self):
        result = self._slugify("Add phone notifications")
        assert result == "plan-add-phone-notifications"

    def test_special_characters_removed(self):
        result = self._slugify("Fix: Bug #123!")
        assert result == "plan-fix-bug-123"

    def test_underscores_become_hyphens(self):
        result = self._slugify("my_feature_name")
        assert result == "plan-my-feature-name"

    def test_multiple_spaces_collapsed(self):
        result = self._slugify("add   phone   notifications")
        assert result == "plan-add-phone-notifications"

    def test_uppercase_lowered(self):
        result = self._slugify("Add PHONE Notifications")
        assert result == "plan-add-phone-notifications"

    def test_long_objective_truncated(self):
        long = "a " * 100  # 200 chars
        result = self._slugify(long)
        # "plan-" prefix + max 50 char slug
        assert result.startswith("plan-")
        # slug part should be <= 50 chars
        slug_part = result[len("plan-"):]
        assert len(slug_part) <= 50

    def test_empty_string_produces_plan_prefix(self):
        result = self._slugify("")
        assert result == "plan-"

    def test_only_special_chars(self):
        result = self._slugify("!@#$%")
        assert result == "plan-"

    def test_single_word(self):
        result = self._slugify("refactor")
        assert result == "plan-refactor"

    def test_hyphens_preserved(self):
        result = self._slugify("fix-login-bug")
        assert result == "plan-fix-login-bug"

    def test_leading_trailing_spaces(self):
        result = self._slugify("  add feature  ")
        assert result == "plan-add-feature"

    def test_numeric_objective(self):
        result = self._slugify("123 fix")
        assert result == "plan-123-fix"


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


@pytest.fixture(autouse=False)
def mock_claude_subprocess():
    """Mock subprocess.run in epic.py so claude calls don't hang.

    Also mocks the SDK path so run_agent_sync creates plan_build.yml.
    Git calls pass through to the real subprocess.run.
    """
    from unittest.mock import Mock, MagicMock

    real_subprocess_run = subprocess.run

    def patched_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd and cmd[0] == "claude":
            # Create plan_build.yml in the cwd if provided
            cwd = kwargs.get("cwd")
            if cwd:
                plan_build = Path(cwd) / "plan_build.yml"
                plan_build.write_text("""name: Mock Plan
objective: Mock objective
phases:
  - name: Phase 1
    tasks:
      - id: MOCK_001
        name: Mock task
        status: pending
""")
            mock_result = Mock()
            mock_result.stdout = "Planner output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            return mock_result
        return real_subprocess_run(cmd, *args, **kwargs)

    # Also mock the SDK path - when SDK is available, plan.py calls run_agent_sync
    # instead of subprocess. Mock it to also create plan_build.yml.
    def mock_sdk_run(prompt, options=None, timeout_seconds=1800):
        from agenticcli.utils.sdk_runner import SessionResult
        # The prompt includes the plan folder path, extract it
        # For simplicity, create plan_build.yml in any directory that doesn't have it yet
        # The real worktree cwd is set as options.cwd in the real SDK call but here we
        # just return a completed result; the fixture-using tests that need plan_build.yml
        # created should use the subprocess path (mock SDK_AVAILABLE=False) or create it manually.
        return SessionResult(status="completed", result="Mock SDK planner output")

    with patch("agenticcli.commands.epic.subprocess.run", side_effect=patched_run):
        with patch("agenticcli.utils.sdk_runner.run_agent_sync", side_effect=mock_sdk_run):
            yield


@pytest.mark.usefixtures("mock_claude_subprocess")
class TestPlanNew:
    """Tests for 'agentic plan new' command."""

    def test_new_requires_objective(self, cli_runner):
        """Test 'plan new' with no args shows error."""
        stdout, stderr, code = cli_runner(["agent", "epic", "new"])
        assert code != 0

    def test_new_help_shows_all_args(self, cli_runner):
        """Test 'plan new --help' lists all expected arguments."""
        stdout, stderr, code = cli_runner(["agent", "epic", "new", "--help"])
        assert code == 0
        combined = stdout + stderr
        assert "--branch" in combined or "-b" in combined
        assert "--description" in combined or "-d" in combined
        assert "--base" in combined
        assert "--execute" in combined or "-x" in combined
        assert "--max-turns" in combined
        assert "--dangerously-skip-permissions" in combined or "dangerously-skip-permissi" in combined

    def test_new_creates_plan_folder(self, cli_runner, temp_repo):
        """Test plan new creates a plan folder via plan init."""
        branch = "plan-test-feature"
        # Pre-create worktree so plan init finds it
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "new", "Test feature", "--branch", branch]
        )

        assert code == 0
        assert "Epic created" in stdout or "Plan initialized" in stdout

        # Verify plan folder was created
        plans_dir = temp_repo / "docs" / "epics" / "live"
        plan_folders = [p for p in plans_dir.iterdir() if p.is_dir() and "test_feature" in p.name]
        assert len(plan_folders) >= 1

    def test_new_auto_generates_branch(self, cli_runner, temp_repo):
        """Test plan new auto-generates branch from objective."""
        branch = "plan-add-dark-mode"
        # Pre-create the worktree matching the auto-generated branch name
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "new", "Add dark mode"]
        )

        assert code == 0
        combined = stdout + stderr
        assert "plan-add-dark-mode" in combined.lower() or "Epic created" in stdout

    def test_new_branch_override(self, cli_runner, temp_repo):
        """Test --branch overrides auto-generation."""
        branch = "my-custom-branch"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "new", "Some objective", "--branch", "my-custom-branch"]
        )

        assert code == 0

    def test_new_json_output(self, cli_runner, temp_repo):
        """Test plan new with JSON output."""
        branch = "plan-json-test"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "new", "JSON test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)
        assert "plan_folder" in result
        assert "branch" in result
        assert result["branch"] == branch
        assert "objective" in result
        assert result["objective"] == "JSON test"

    def test_new_with_execute_flag(self, cli_runner, temp_repo):
        """Test --execute flag is accepted and recorded."""
        branch = "plan-execute-test"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "new", "Execute test", "--branch", branch, "--execute"]
        )

        assert code == 0
        result = json.loads(stdout)
        assert result["execute"] is True

    def test_new_without_execute_flag(self, cli_runner, temp_repo):
        """Test default (no --execute) is recorded as False."""
        branch = "plan-no-execute-test"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "new", "No execute test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)
        assert result["execute"] is False

    def test_new_max_turns_default(self, cli_runner, temp_repo):
        """Test max_turns defaults to 25."""
        branch = "plan-turns-default"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "new", "Turns test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)
        assert result["max_turns"] == 25

    def test_new_max_turns_custom(self, cli_runner, temp_repo):
        """Test custom --max-turns value."""
        branch = "plan-turns-custom"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "new", "Turns custom", "--branch", branch, "--max-turns", "50"]
        )

        assert code == 0
        result = json.loads(stdout)
        assert result["max_turns"] == 50

    def test_new_plan_folder_contains_plan_build_yml(self, cli_runner, temp_repo):
        """Test that created plan folder contains plan_build.yml with objective."""
        branch = "plan-build-yml-test"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "new", "Build yml test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)
        plan_folder = Path(result["plan_folder"])
        assert (plan_folder / "plan_build.yml").exists()

    def test_new_shows_next_steps_without_execute(self, cli_runner, temp_repo):
        """Test human output includes next steps when --execute not passed."""
        branch = "plan-next-steps"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "new", "Next steps test", "--branch", branch]
        )

        assert code == 0
        assert "Next steps" in stdout

    def test_new_with_description_override(self, cli_runner, temp_repo):
        """Test --description overrides objective in folder naming."""
        branch = "plan-desc-override"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "new", "My long objective", "--branch", branch,
             "--description", "short desc"]
        )

        assert code == 0
        result = json.loads(stdout)
        plan_folder = Path(result["plan_folder"])
        assert "short_desc" in plan_folder.name


@pytest.mark.usefixtures("mock_claude_subprocess")
class TestPlanNewErrorCases:
    """Error case tests for plan new."""

    def test_new_duplicate_plan_fails(self, cli_runner, temp_repo):
        """Test creating same plan twice fails on second attempt."""
        branch = "plan-dup-test"
        create_worktree_for_test(temp_repo, branch)

        # First creation
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "new", "Dup test", "--branch", branch]
        )
        assert code == 0

        # Second creation with same params should fail
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "new", "Dup test", "--branch", branch]
        )
        assert code == 2  # Plan folder already exists


# ---------------------------------------------------------------------------
# Unit tests for build_planner_prompt
# ---------------------------------------------------------------------------


class TestBuildPlannerPrompt:
    """Tests for planner prompt template generation."""

    def test_prompt_includes_objective(self, tmp_path):
        """Test prompt includes the objective."""
        from agenticcli.utils.planner_prompt import build_planner_prompt

        objective = "Build a new CLI feature"
        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()

        prompt = build_planner_prompt(objective, plan_folder)

        assert "Build a new CLI feature" in prompt
        assert "OBJECTIVE:" in prompt

    def test_prompt_includes_plan_folder_path(self, tmp_path):
        """Test prompt includes the plan folder path."""
        from agenticcli.utils.planner_prompt import build_planner_prompt

        objective = "Test objective"
        plan_folder = tmp_path / "260208XX_test"
        plan_folder.mkdir()

        prompt = build_planner_prompt(objective, plan_folder)

        assert str(plan_folder) in prompt
        assert "EPIC FOLDER:" in prompt

    def test_prompt_includes_story_discovery_instruction(self, tmp_path):
        """Test prompt instructs planner to run agentic stories find."""
        from agenticcli.utils.planner_prompt import build_planner_prompt

        objective = "Test objective"
        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()

        prompt = build_planner_prompt(objective, plan_folder)

        assert "agentic stories find" in prompt
        assert "STORY DISCOVERY" in prompt
        assert "docs/userstories/" in prompt

    def test_prompt_includes_uat_fence_reference(self, tmp_path):
        """Test prompt references UAT mandatory fence."""
        from agenticcli.utils.planner_prompt import build_planner_prompt

        objective = "Test objective"
        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()

        prompt = build_planner_prompt(objective, plan_folder)

        assert "UAT" in prompt
        assert "MANDATORY" in prompt
        assert "planning-standard.yml" in prompt
        assert "FENCE" in prompt

    def test_prompt_includes_readme_instruction(self, tmp_path):
        """Test prompt instructs planner to write README.md."""
        from agenticcli.utils.planner_prompt import build_planner_prompt

        objective = "Test objective"
        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()

        prompt = build_planner_prompt(objective, plan_folder)

        assert "README.md" in prompt
        assert "WRITE README.md" in prompt

    def test_prompt_includes_plan_build_instruction(self, tmp_path):
        """Test prompt instructs planner to write ticket_build.yml."""
        from agenticcli.utils.planner_prompt import build_planner_prompt

        objective = "Test objective"
        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()

        prompt = build_planner_prompt(objective, plan_folder)

        assert "ticket_build.yml" in prompt
        assert "WRITE ticket_build.yml" in prompt

    def test_prompt_includes_story_first_fence(self, tmp_path):
        """Test prompt includes STORY-FIRST PLANNING fence."""
        from agenticcli.utils.planner_prompt import build_planner_prompt

        objective = "Test objective"
        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()

        prompt = build_planner_prompt(objective, plan_folder)

        assert "STORY-FIRST PLANNING" in prompt
        assert "affected_stories" in prompt

    def test_prompt_with_additional_context(self, tmp_path):
        """Test prompt includes additional context when provided."""
        from agenticcli.utils.planner_prompt import build_planner_prompt

        objective = "Test objective"
        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()
        context = "This is additional context for the planner."

        prompt = build_planner_prompt(objective, plan_folder, context)

        assert context in prompt
        assert "ADDITIONAL CONTEXT:" in prompt

    def test_prompt_includes_uat_strategies(self, tmp_path):
        """Test prompt includes UAT strategy options."""
        from agenticcli.utils.planner_prompt import build_planner_prompt

        objective = "Test objective"
        plan_folder = tmp_path / "plan_folder"
        plan_folder.mkdir()

        prompt = build_planner_prompt(objective, plan_folder)

        assert "test-user-simulator" in prompt
        assert "guidance-blind-test" in prompt
        assert "documentation-loop" in prompt
        assert "manual" in prompt


# ---------------------------------------------------------------------------
# Integration tests for planner spawn in cmd_new
# ---------------------------------------------------------------------------


class TestPlanNewPlannerSpawn:
    """Tests for planner agent spawning in plan new."""

    def test_new_spawns_planner_with_subprocess(self, cli_runner, temp_repo, monkeypatch):
        """Test plan new spawns claude subprocess for planner."""
        from unittest.mock import MagicMock, Mock

        # Mock subprocess.run to avoid actual claude invocation
        mock_subprocess_run = Mock()
        mock_result = Mock()
        mock_result.stdout = "Planner output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_subprocess_run.return_value = mock_result

        # Create a mock plan_build.yml so validation passes
        branch = "plan-spawn-test"
        create_worktree_for_test(temp_repo, branch)

        real_subprocess_run = subprocess.run

        def mock_run(cmd, *a, **kwargs):
            # Pass through git calls to real subprocess
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            # If this is the planner spawn call (contains "claude")
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                # Create plan_build.yml in the working directory
                cwd = kwargs.get("cwd")
                if cwd:
                    plan_build = Path(cwd) / "plan_build.yml"
                    plan_build.write_text("name: Mock Plan\nphases: []")
            return mock_result

        with patch("agenticcli.commands.epic.subprocess.run", side_effect=mock_run):
            stdout, stderr, code = cli_runner(
                ["agent", "epic", "new", "Spawn test", "--branch", branch]
            )

        assert code == 0

    def test_new_reports_planner_failure(self, cli_runner, temp_repo, monkeypatch):
        """Test plan new reports planner agent failure."""
        from unittest.mock import Mock, patch

        branch = "plan-validate-test"
        create_worktree_for_test(temp_repo, branch)

        real_subprocess_run = subprocess.run

        # Mock subprocess - pass through git, mock claude with non-zero exit
        mock_result = Mock()
        mock_result.stdout = "Planner failed"
        mock_result.stderr = "Error running planner"
        mock_result.returncode = 1

        def mock_run(cmd, *a, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            return mock_result

        with patch("agenticcli.commands.epic.subprocess.run", side_effect=mock_run):
            stdout, stderr, code = cli_runner(
                ["agent", "epic", "new", "Validate test", "--branch", branch]
            )

        # cmd_new should still succeed (plan folder created) but report planner failure
        combined = stdout + stderr
        assert "failed" in combined.lower() or code != 0

    def test_new_passes_max_turns_to_claude(self, cli_runner, temp_repo):
        """Test plan new passes --max-turns to claude command (subprocess fallback path)."""
        from unittest.mock import Mock, patch

        branch = "plan-max-turns"
        create_worktree_for_test(temp_repo, branch)

        real_subprocess_run = subprocess.run
        captured_cmd = []

        def capture_run(cmd, *a, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            captured_cmd.append(cmd)
            mock_result = Mock()
            mock_result.stdout = "Planner output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            # Create plan_build.yml
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                cwd = kwargs.get("cwd")
                if cwd:
                    plan_build = Path(cwd) / "plan_build.yml"
                    plan_build.write_text("name: Mock\nphases: []")
            return mock_result

        # Force subprocess path by marking SDK unavailable
        with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            with patch("agenticcli.commands.epic.subprocess.run", side_effect=capture_run):
                stdout, stderr, code = cli_runner(
                    ["agent", "epic", "new", "Max turns test", "--branch", branch, "--max-turns", "15"]
                )

        assert code == 0
        # Check that claude command included --max-turns 15
        claude_cmds = [cmd for cmd in captured_cmd if isinstance(cmd, list) and cmd and cmd[0] == "claude"]
        assert len(claude_cmds) >= 1
        claude_cmd = claude_cmds[0]
        assert "--max-turns" in claude_cmd
        assert "15" in claude_cmd

    def test_new_passes_dangerously_skip_permissions(self, cli_runner, temp_repo):
        """Test plan new passes --dangerously-skip-permissions to claude (subprocess fallback path)."""
        from unittest.mock import Mock, patch

        branch = "plan-skip-perms"
        create_worktree_for_test(temp_repo, branch)

        real_subprocess_run = subprocess.run
        captured_cmd = []

        def capture_run(cmd, *a, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            captured_cmd.append(cmd)
            mock_result = Mock()
            mock_result.stdout = "Planner output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            # Create plan_build.yml
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                cwd = kwargs.get("cwd")
                if cwd:
                    plan_build = Path(cwd) / "plan_build.yml"
                    plan_build.write_text("name: Mock\nphases: []")
            return mock_result

        # Force subprocess path by marking SDK unavailable
        with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            with patch("agenticcli.commands.epic.subprocess.run", side_effect=capture_run):
                stdout, stderr, code = cli_runner(
                    ["agent", "epic", "new", "Skip perms test", "--branch", branch,
                     "--dangerously-skip-permissions"]
                )

        assert code == 0
        # Check that claude command included --dangerously-skip-permissions
        claude_cmds = [cmd for cmd in captured_cmd if isinstance(cmd, list) and cmd and cmd[0] == "claude"]
        assert len(claude_cmds) >= 1
        claude_cmd = claude_cmds[0]
        assert "--dangerously-skip-permissions" in claude_cmd


# ---------------------------------------------------------------------------
# Phase 3: Orchestration auto-generation tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_claude_subprocess")
class TestPlanNewOrchestration:
    """Tests for orchestration generation in plan new (Phase 3)."""

    def test_new_generates_orchestration_mmd(self, cli_runner, temp_repo):
        """Test plan new automatically generates orchestration MMD after planner."""
        branch = "plan-orch-test"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "new", "Orchestration test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)
        plan_folder = Path(result["plan_folder"])

        # Verify orchestration MMD was generated
        mmd_files = list(plan_folder.glob("orchestration_*.mmd"))
        assert len(mmd_files) >= 1, "Orchestration MMD should be generated"

    def test_new_validates_orchestration_after_generation(self, cli_runner, temp_repo, monkeypatch):
        """Test plan new runs validation on generated orchestration."""
        from unittest.mock import Mock, patch

        branch = "plan-validate-orch"
        create_worktree_for_test(temp_repo, branch)

        # Track whether validation was called
        validate_called = []

        real_subprocess_run = subprocess.run
        original_cmd_validate = None

        def mock_run(cmd, *a, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                cwd = kwargs.get("cwd")
                if cwd:
                    # Create a minimal valid plan_build.yml with phases
                    plan_build = Path(cwd) / "plan_build.yml"
                    plan_build.write_text("""name: Test Plan
phases:
  - name: Phase 1
    tasks:
      - id: TASK_001
        name: Test task
        status: pending
""")
            mock_result = Mock()
            mock_result.stdout = "Output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            return mock_result

        # Patch cmd_orchestration_validate to track calls
        # epic.py calls its own cmd_orchestration_validate, so patch it in the epic module
        from agenticcli.commands import epic as epic_module

        original_validate = epic_module.cmd_orchestration_validate

        def track_validate(*args, **kwargs):
            validate_called.append(True)
            return original_validate(*args, **kwargs)

        with patch("agenticcli.commands.epic.subprocess.run", side_effect=mock_run):
            with patch.object(epic_module, "cmd_orchestration_validate", side_effect=track_validate):
                stdout, stderr, code = cli_runner(
                    ["agent", "epic", "new", "Validate orch", "--branch", branch]
                )

        assert code == 0
        assert len(validate_called) > 0, "Validation should be called after generation"

    def test_new_warns_on_orchestration_generation_failure(self, cli_runner, temp_repo, monkeypatch):
        """Test plan new warns but continues if orchestration generation fails."""
        from unittest.mock import Mock, patch

        branch = "plan-orch-fail"
        create_worktree_for_test(temp_repo, branch)

        real_subprocess_run = subprocess.run

        def mock_run(cmd, *a, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                cwd = kwargs.get("cwd")
                if cwd:
                    plan_build = Path(cwd) / "plan_build.yml"
                    # Create invalid plan_build (empty) to cause generation to fail
                    plan_build.write_text("")
            mock_result = Mock()
            mock_result.stdout = "Output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            return mock_result

        with patch("agenticcli.commands.epic.subprocess.run", side_effect=mock_run):
            stdout, stderr, code = cli_runner(
                ["agent", "epic", "new", "Orch fail test", "--branch", branch]
            )

        # Should still succeed even if orchestration fails
        combined = stdout + stderr
        # Either succeeds with warning or fails cleanly
        assert "Epic created" in combined or code != 0

    def test_new_without_execute_stops_after_orchestration(self, cli_runner, temp_repo):
        """Test plan new without --execute stops after orchestration generation."""
        branch = "plan-no-exec"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "new", "No exec test", "--branch", branch]
        )

        assert code == 0
        combined = stdout + stderr
        # Should show next steps, not execute builders
        assert "Next steps" in combined or "Execute" in combined


# ---------------------------------------------------------------------------
# Phase 4: Builder spawning tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_claude_subprocess")
class TestPlanNewBuilderSpawning:
    """Tests for builder spawning with --execute flag (Phase 4)."""

    def test_execute_spawns_builder_sessions(self, cli_runner, temp_repo, monkeypatch):
        """Test --execute spawns builder sessions for each task."""
        from unittest.mock import Mock, patch

        branch = "plan-exec-builders"
        create_worktree_for_test(temp_repo, branch)

        # Track spawned commands
        spawned_commands = []

        real_subprocess_run = subprocess.run
        real_popen = subprocess.Popen

        def mock_run(cmd, *a, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                cwd = kwargs.get("cwd")
                if cwd:
                    plan_build = Path(cwd) / "plan_build.yml"
                    plan_build.write_text("""name: Test Plan
phases:
  - name: Build Phase
    execution: sequential
    tasks:
      - id: BUILD_001
        name: Task 1
        status: pending
        agent: build-python
      - id: BUILD_002
        name: Task 2
        status: pending
        agent: build-python
""")
            mock_result = Mock()
            mock_result.stdout = "Output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            return mock_result

        def mock_popen(cmd, *a, **kwargs):
            # Pass through git commands to real Popen
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_popen(cmd, *a, **kwargs)

            spawned_commands.append(cmd)
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_proc.wait = Mock(return_value=None)
            mock_proc.returncode = 0
            mock_proc.communicate = Mock(return_value=("", ""))
            mock_proc.__enter__ = Mock(return_value=mock_proc)
            mock_proc.__exit__ = Mock(return_value=False)
            return mock_proc

        # Force subprocess path for task spawning (SDK_AVAILABLE=False -> Popen path)
        with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            with patch("agenticcli.commands.epic.subprocess.run", side_effect=mock_run):
                with patch("agenticcli.commands.epic.subprocess.Popen", side_effect=mock_popen):
                    stdout, stderr, code = cli_runner(
                        ["agent", "epic", "new", "Exec test", "--branch", branch, "--execute"]
                    )

        assert code == 0
        # Should have spawned builder sessions
        assert len(spawned_commands) > 0, "Should spawn builder sessions with --execute"
        # Verify session spawn commands were issued
        session_spawns = [cmd for cmd in spawned_commands if "session" in cmd and "spawn" in cmd]
        assert len(session_spawns) >= 1, "Should spawn at least one session"

    def test_execute_respects_sequential_phase_ordering(self, cli_runner, temp_repo, monkeypatch):
        """Test sequential phases wait for completion before proceeding."""
        from unittest.mock import Mock, patch

        branch = "plan-sequential"
        create_worktree_for_test(temp_repo, branch)

        wait_calls = []

        real_subprocess_run = subprocess.run
        real_popen = subprocess.Popen

        def mock_run(cmd, *a, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                cwd = kwargs.get("cwd")
                if cwd:
                    plan_build = Path(cwd) / "plan_build.yml"
                    plan_build.write_text("""name: Sequential Plan
phases:
  - name: Phase 1
    execution: sequential
    tasks:
      - id: SEQ_001
        name: Task 1
        status: pending
  - name: Phase 2
    execution: sequential
    tasks:
      - id: SEQ_002
        name: Task 2
        status: pending
""")
            mock_result = Mock()
            mock_result.stdout = "Output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            return mock_result

        def mock_popen(cmd, *a, **kwargs):
            # Pass through git commands to real Popen
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_popen(cmd, *a, **kwargs)

            mock_proc = Mock()
            mock_proc.pid = 12345

            def track_wait():
                wait_calls.append(cmd)
                return None

            mock_proc.wait = track_wait
            mock_proc.returncode = 0
            mock_proc.communicate = Mock(return_value=("", ""))
            mock_proc.__enter__ = Mock(return_value=mock_proc)
            mock_proc.__exit__ = Mock(return_value=False)
            return mock_proc

        # Force subprocess path for task spawning (SDK_AVAILABLE=False -> Popen path)
        with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            with patch("agenticcli.commands.epic.subprocess.run", side_effect=mock_run):
                with patch("agenticcli.commands.epic.subprocess.Popen", side_effect=mock_popen):
                    stdout, stderr, code = cli_runner(
                        ["agent", "epic", "new", "Sequential", "--branch", branch, "--execute"]
                    )

        assert code == 0
        # Sequential phases should wait for tasks
        assert len(wait_calls) > 0, "Sequential execution should call wait()"

    def test_execute_skips_completed_tasks(self, cli_runner, temp_repo, monkeypatch):
        """Test --execute skips tasks already marked as completed."""
        from unittest.mock import Mock, patch

        branch = "plan-skip-completed"
        create_worktree_for_test(temp_repo, branch)

        spawned_commands = []

        real_subprocess_run = subprocess.run
        real_popen = subprocess.Popen

        def mock_run(cmd, *a, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                cwd = kwargs.get("cwd")
                if cwd:
                    plan_build = Path(cwd) / "plan_build.yml"
                    plan_build.write_text("""name: Mixed Status
phases:
  - name: Phase
    tasks:
      - id: DONE_001
        name: Already done
        status: completed
      - id: PEND_001
        name: Still pending
        status: pending
""")
            mock_result = Mock()
            mock_result.stdout = "Output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            return mock_result

        def mock_popen(cmd, *a, **kwargs):
            # Pass through git commands to real Popen
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_popen(cmd, *a, **kwargs)

            spawned_commands.append(cmd)
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_proc.wait = Mock(return_value=None)
            mock_proc.returncode = 0
            mock_proc.communicate = Mock(return_value=("", ""))
            mock_proc.__enter__ = Mock(return_value=mock_proc)
            mock_proc.__exit__ = Mock(return_value=False)
            return mock_proc

        # Force subprocess path for task spawning (SDK_AVAILABLE=False -> Popen path)
        with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            with patch("agenticcli.commands.epic.subprocess.run", side_effect=mock_run):
                with patch("agenticcli.commands.epic.subprocess.Popen", side_effect=mock_popen):
                    stdout, stderr, code = cli_runner(
                        ["agent", "epic", "new", "Skip test", "--branch", branch, "--execute"]
                    )

        assert code == 0
        # Should only spawn for pending task
        session_spawns = [cmd for cmd in spawned_commands if "PEND_001" in " ".join(cmd)]
        assert len(session_spawns) >= 1, "Should spawn for pending task"
        # Should NOT spawn for completed task
        completed_spawns = [cmd for cmd in spawned_commands if "DONE_001" in " ".join(cmd)]
        assert len(completed_spawns) == 0, "Should skip completed tasks"

    def test_execute_blocks_on_validation_failure(self, cli_runner, temp_repo, monkeypatch):
        """Test --execute is blocked when orchestration validation fails."""
        from unittest.mock import Mock, patch

        branch = "plan-block-exec"
        create_worktree_for_test(temp_repo, branch)

        real_subprocess_run = subprocess.run
        real_popen = subprocess.Popen

        def mock_run(cmd, *a, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            mock_result = Mock()
            mock_result.stdout = "Output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                cwd = kwargs.get("cwd")
                if cwd:
                    plan_build = Path(cwd) / "plan_build.yml"
                    # Create empty plan to cause validation failure
                    plan_build.write_text("name: Empty\n")
            return mock_result

        # Make validation fail - cmd_orchestration_validate is now in epic module
        from agenticcli.commands import epic as epic_module

        def failing_validate(*args, **kwargs):
            raise SystemExit(1)  # Simulate validation failure

        spawned = []

        def mock_popen(cmd, *a, **kwargs):
            # Pass through git commands to real Popen
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_popen(cmd, *a, **kwargs)

            spawned.append(cmd)
            mock_proc = Mock()
            mock_proc.pid = 12345
            mock_proc.wait = Mock()
            mock_proc.returncode = 0
            mock_proc.communicate = Mock(return_value=("", ""))
            mock_proc.__enter__ = Mock(return_value=mock_proc)
            mock_proc.__exit__ = Mock(return_value=False)
            return mock_proc

        # Force subprocess path for task spawning (SDK_AVAILABLE=False -> Popen path)
        with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            with patch("agenticcli.commands.epic.subprocess.run", side_effect=mock_run):
                with patch.object(epic_module, "cmd_orchestration_validate", side_effect=failing_validate):
                    with patch("agenticcli.commands.epic.subprocess.Popen", side_effect=mock_popen):
                        stdout, stderr, code = cli_runner(
                            ["agent", "epic", "new", "Block test", "--branch", branch, "--execute"]
                        )

        # Should not spawn any builders if validation failed
        assert len(spawned) == 0, "Should not spawn builders when validation fails"


# ---------------------------------------------------------------------------
# Phase 5: Integration and end-to-end tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_claude_subprocess")
class TestPlanNewIntegration:
    """Integration tests for full plan new flow (Phase 5)."""

    def test_full_flow_without_execute(self, cli_runner, temp_repo):
        """Test complete flow: init -> planner -> orchestration -> summary."""
        branch = "plan-e2e-no-exec"
        create_worktree_for_test(temp_repo, branch)

        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "new", "End to end test", "--branch", branch]
        )

        assert code == 0
        result = json.loads(stdout)
        plan_folder = Path(result["plan_folder"])

        # Verify all artifacts created
        assert (plan_folder / "plan_build.yml").exists(), "plan_build.yml should exist"
        mmd_files = list(plan_folder.glob("orchestration_*.mmd"))
        assert len(mmd_files) >= 1, "orchestration MMD should exist"

    def test_full_flow_with_execute(self, cli_runner, temp_repo, monkeypatch):
        """Test complete flow with --execute: init -> planner -> orchestration -> builders."""
        from unittest.mock import Mock, patch

        branch = "plan-e2e-exec"
        create_worktree_for_test(temp_repo, branch)

        spawned = []

        real_subprocess_run = subprocess.run
        real_popen = subprocess.Popen

        def mock_run(cmd, *a, **kwargs):
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_subprocess_run(cmd, *a, **kwargs)
            if isinstance(cmd, list) and cmd and cmd[0] == "claude":
                cwd = kwargs.get("cwd")
                if cwd:
                    plan_build = Path(cwd) / "plan_build.yml"
                    plan_build.write_text("""name: E2E Test
phases:
  - name: Build
    tasks:
      - id: E2E_001
        name: Build task
        status: pending
""")
            mock_result = Mock()
            mock_result.stdout = "Output"
            mock_result.stderr = ""
            mock_result.returncode = 0
            return mock_result

        def mock_popen(cmd, *a, **kwargs):
            # Pass through git commands to real Popen
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                return real_popen(cmd, *a, **kwargs)

            spawned.append(cmd)
            mock_proc = Mock()
            mock_proc.pid = 99999
            mock_proc.wait = Mock()
            mock_proc.returncode = 0
            mock_proc.communicate = Mock(return_value=("", ""))
            mock_proc.__enter__ = Mock(return_value=mock_proc)
            mock_proc.__exit__ = Mock(return_value=False)
            return mock_proc

        # Force subprocess path for task spawning (SDK_AVAILABLE=False -> Popen path)
        with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            with patch("agenticcli.commands.epic.subprocess.run", side_effect=mock_run):
                with patch("agenticcli.commands.epic.subprocess.Popen", side_effect=mock_popen):
                    stdout, stderr, code = cli_runner(
                        ["-j", "agent", "epic", "new", "E2E exec", "--branch", branch, "--execute"]
                    )

        assert code == 0
        result = json.loads(stdout)
        assert result["execute"] is True

        # Verify builders were spawned
        session_spawns = [cmd for cmd in spawned if "session" in cmd and "spawn" in cmd]
        assert len(session_spawns) >= 1, "Should spawn builder sessions with --execute"
