"""Tests for orchestrate session plan/implement epic auto-detection from git branch.

Covers US-PLN-046 step 6: when --epic is not specified, the orchestrate commands
attempt to auto-detect the active epic from the current branch; if no match is
found, exit non-zero with a "cannot infer epic — pass --epic <folder>" message.
"""

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-PLN-046")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_epic_metadata(epic_folder_name: str, branch: str | None):
    """Return a minimal EpicMetadata-like object for mocking."""
    m = MagicMock()
    m.epic_folder_name = epic_folder_name
    m.branch = branch
    return m


def _args_without_plan(action="planning", **kwargs) -> SimpleNamespace:
    """Build a minimal args namespace with plan=None (no --epic passed)."""
    return SimpleNamespace(
        action=action,
        plan=None,
        background=False,
        max_iterations=1,
        completion_promise=None,
        project=None,
        directory="/tmp",
        dangerously_skip_permissions=False,
        dry_run=False,
        json=False,
        budget_usd=50.0,
        **kwargs,
    )


def _args_with_plan(plan: str, action="planning", **kwargs) -> SimpleNamespace:
    """Build a minimal args namespace with plan=<folder> (explicit --epic)."""
    return SimpleNamespace(
        action=action,
        plan=plan,
        background=False,
        max_iterations=1,
        completion_promise=None,
        project=None,
        directory="/tmp",
        dangerously_skip_permissions=False,
        dry_run=False,
        json=False,
        budget_usd=50.0,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Test: explicit --epic is honored without running auto-detect
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestExplicitEpicBypassesAutoDetect:
    """When --epic is explicitly provided, auto-detect must not run."""

    def test_explicit_plan_no_branch_query(self, monkeypatch):
        """--epic <folder> is passed straight through; git is never invoked."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        git_called = []

        def fake_git(*a, **kw):
            git_called.append(True)
            raise AssertionError("git should not be called when --epic is explicit")

        monkeypatch.setattr(subprocess, "run", fake_git)

        mock_runner = MagicMock()
        mock_runner.run.return_value = True
        mock_runner.state = {
            "iteration": 1,
            "plans_processed": ["my_epic"],
            "plans_failed": [],
            "errors": [],
        }

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockPR, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWF:
            MockPR.return_value = mock_runner
            MockWF.return_value = MagicMock()

            args = _args_with_plan("my_epic")
            cmd_orchestrate(args)

        assert not git_called, "git must not be invoked when --epic is explicit"
        assert args.plan == "my_epic", "plan must remain unchanged"

    def test_explicit_plan_implement_no_branch_query(self, monkeypatch):
        """--epic <folder> on implement action bypasses auto-detect."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        git_called = []

        def fake_git(*a, **kw):
            git_called.append(True)
            raise AssertionError("git should not be called when --epic is explicit")

        monkeypatch.setattr(subprocess, "run", fake_git)

        mock_runner = MagicMock()
        mock_runner.run.return_value = True
        mock_runner.state = {
            "iteration": 1,
            "plans_processed": ["my_epic"],
            "plans_failed": [],
            "phases_completed": [],
            "phases_failed": [],
            "errors": [],
        }

        with patch("agenticcli.workflows.orchestration.ExecutionRunner") as MockER, \
             patch("agenticcli.workflows.orchestration.OrchestrationWorkflow") as MockOW:
            MockER.return_value = mock_runner
            MockOW.return_value = MagicMock()

            args = _args_with_plan("my_epic", action="executing")
            cmd_orchestrate(args)

        assert not git_called, "git must not be invoked when --epic is explicit"


# ---------------------------------------------------------------------------
# Test: missing --epic + branch matches exactly one epic
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestAutoDetectSingleMatch:
    """When --epic is absent and the branch matches exactly one epic, resolve it."""

    def test_resolves_plan_from_branch(self, monkeypatch, capsys):
        """Branch matches one epic → args.plan is set and info line is printed."""
        from agenticcli.commands.orchestrate import _resolve_epic_from_branch

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._get_current_branch",
            lambda: "feature/my-branch",
        )

        epic_meta = _make_epic_metadata("260401AB_my_epic", "feature/my-branch")

        mock_repo = MagicMock()
        mock_repo.list_epics.return_value = [epic_meta]

        with patch("agenticguidance.services.epic_repository.EpicRepository", return_value=mock_repo):
            args = _args_without_plan()
            _resolve_epic_from_branch(args)

        assert args.plan == "260401AB_my_epic"
        captured = capsys.readouterr()
        assert "auto-detected epic 260401AB_my_epic from branch feature/my-branch" in captured.out

    def test_cmd_orchestrate_uses_resolved_plan(self, monkeypatch):
        """Full cmd_orchestrate call resolves plan and passes it to PlanningRunner."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._get_current_branch",
            lambda: "feature/auto-branch",
        )

        epic_meta = _make_epic_metadata("260401AB_auto_epic", "feature/auto-branch")
        mock_repo = MagicMock()
        mock_repo.list_epics.return_value = [epic_meta]

        mock_runner = MagicMock()
        mock_runner.run.return_value = True
        mock_runner.state = {
            "iteration": 1,
            "plans_processed": ["260401AB_auto_epic"],
            "plans_failed": [],
            "errors": [],
        }

        with patch("agenticguidance.services.epic_repository.EpicRepository", return_value=mock_repo), \
             patch("agenticcli.workflows.orchestration.PlanningRunner") as MockPR, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWF:
            MockPR.return_value = mock_runner
            MockWF.return_value = MagicMock()

            args = _args_without_plan(action="planning")
            cmd_orchestrate(args)

        assert args.plan == "260401AB_auto_epic"
        # Runner must be constructed with the resolved plan_folder
        MockPR.assert_called_once()
        call_kwargs = MockPR.call_args[1]
        assert call_kwargs["plan_folder"] == "260401AB_auto_epic"


# ---------------------------------------------------------------------------
# Test: missing --epic + no branch match → non-zero exit
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestAutoDetectNoMatch:
    """When --epic is absent and no epic matches the branch, exit non-zero."""

    def test_no_matching_epic_exits_nonzero(self, monkeypatch):
        """Zero matching epics → sys.exit(1) with named error."""
        from agenticcli.commands.orchestrate import _resolve_epic_from_branch

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._get_current_branch",
            lambda: "feature/unknown-branch",
        )

        mock_repo = MagicMock()
        mock_repo.list_epics.return_value = [
            _make_epic_metadata("260401AB_other", "feature/other-branch"),
        ]

        with patch("agenticguidance.services.epic_repository.EpicRepository", return_value=mock_repo):
            args = _args_without_plan()
            with pytest.raises(SystemExit) as exc_info:
                _resolve_epic_from_branch(args)

        assert exc_info.value.code == 1

    def test_no_matching_epic_error_message(self, monkeypatch, capsys):
        """Error message names the --epic flag explicitly."""
        from agenticcli.commands.orchestrate import _resolve_epic_from_branch

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._get_current_branch",
            lambda: "feature/unknown-branch",
        )

        mock_repo = MagicMock()
        mock_repo.list_epics.return_value = []

        with patch("agenticguidance.services.epic_repository.EpicRepository", return_value=mock_repo):
            args = _args_without_plan()
            with pytest.raises(SystemExit):
                _resolve_epic_from_branch(args)

        # Error is written via print_error which writes to stderr or stdout
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "cannot infer epic" in combined
        assert "--epic" in combined


# ---------------------------------------------------------------------------
# Test: missing --epic + multiple epics match → non-zero, names candidates
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestAutoDetectMultipleMatches:
    """When --epic is absent and multiple epics match the branch, exit non-zero."""

    def test_multiple_matches_exits_nonzero(self, monkeypatch):
        """Multiple matching epics → sys.exit(1)."""
        from agenticcli.commands.orchestrate import _resolve_epic_from_branch

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._get_current_branch",
            lambda: "feature/shared-branch",
        )

        mock_repo = MagicMock()
        mock_repo.list_epics.return_value = [
            _make_epic_metadata("260401AA_epic_one", "feature/shared-branch"),
            _make_epic_metadata("260401BB_epic_two", "feature/shared-branch"),
        ]

        with patch("agenticguidance.services.epic_repository.EpicRepository", return_value=mock_repo):
            args = _args_without_plan()
            with pytest.raises(SystemExit) as exc_info:
                _resolve_epic_from_branch(args)

        assert exc_info.value.code == 1

    def test_multiple_matches_names_candidates(self, monkeypatch, capsys):
        """Error message names all candidate epic folders."""
        from agenticcli.commands.orchestrate import _resolve_epic_from_branch

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._get_current_branch",
            lambda: "feature/shared-branch",
        )

        mock_repo = MagicMock()
        mock_repo.list_epics.return_value = [
            _make_epic_metadata("260401AA_epic_one", "feature/shared-branch"),
            _make_epic_metadata("260401BB_epic_two", "feature/shared-branch"),
        ]

        with patch("agenticguidance.services.epic_repository.EpicRepository", return_value=mock_repo):
            args = _args_without_plan()
            with pytest.raises(SystemExit):
                _resolve_epic_from_branch(args)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "260401AA_epic_one" in combined
        assert "260401BB_epic_two" in combined
        assert "cannot infer epic" in combined


# ---------------------------------------------------------------------------
# Test: missing --epic + git fails → non-zero exit with named error
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestAutoDetectGitFailure:
    """When --epic is absent and git fails, exit non-zero with named error."""

    def test_git_command_fails_exits_nonzero(self, monkeypatch):
        """subprocess.CalledProcessError from git → sys.exit(1)."""
        from agenticcli.commands.orchestrate import _resolve_epic_from_branch

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._get_current_branch",
            lambda: None,  # Simulates git failure returning None
        )

        mock_repo = MagicMock()

        with patch("agenticguidance.services.epic_repository.EpicRepository", return_value=mock_repo):
            args = _args_without_plan()
            with pytest.raises(SystemExit) as exc_info:
                _resolve_epic_from_branch(args)

        assert exc_info.value.code == 1
        # Repo should not even be queried when branch is unknown
        mock_repo.list_epics.assert_not_called()

    def test_git_command_fails_error_message(self, monkeypatch, capsys):
        """Error message names the --epic flag when git fails."""
        from agenticcli.commands.orchestrate import _resolve_epic_from_branch

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._get_current_branch",
            lambda: None,
        )

        with patch("agenticguidance.services.epic_repository.EpicRepository", return_value=MagicMock()):
            args = _args_without_plan()
            with pytest.raises(SystemExit):
                _resolve_epic_from_branch(args)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "cannot infer epic" in combined
        assert "--epic" in combined

    def test_get_current_branch_returns_none_on_git_error(self, monkeypatch):
        """_get_current_branch returns None when git raises CalledProcessError."""
        from agenticcli.commands.orchestrate import _get_current_branch

        monkeypatch.setattr(
            subprocess,
            "run",
            MagicMock(side_effect=subprocess.CalledProcessError(128, "git")),
        )

        result = _get_current_branch()
        assert result is None

    def test_get_current_branch_returns_none_when_git_missing(self, monkeypatch):
        """_get_current_branch returns None when git binary is not found."""
        from agenticcli.commands.orchestrate import _get_current_branch

        monkeypatch.setattr(
            subprocess,
            "run",
            MagicMock(side_effect=FileNotFoundError("git not found")),
        )

        result = _get_current_branch()
        assert result is None
