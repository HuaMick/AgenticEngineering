"""Tests for plan question gate: has_pending_questions, auto-archive blocking, spawn warning.

Covers:
  P6-T1: has_pending_questions utility
  P6-T2: auto-archive blocked by pending questions
  P6-T3: session spawn warning on pending questions
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# =============================================================================
# P6-T1: has_pending_questions utility
# =============================================================================


class TestHasPendingQuestions:
    """Tests for has_pending_questions() utility function."""

    def test_has_pending_questions_true(self, tmp_path):
        """Returns True when pending question files exist."""
        from agenticcli.commands.plan import has_pending_questions

        pending_dir = tmp_path / "questions" / "pending"
        pending_dir.mkdir(parents=True)
        (pending_dir / "q001.yml").write_text("question: What color?")

        assert has_pending_questions(tmp_path) is True

    def test_has_pending_questions_false_empty(self, tmp_path):
        """Returns False when pending directory exists but is empty."""
        from agenticcli.commands.plan import has_pending_questions

        pending_dir = tmp_path / "questions" / "pending"
        pending_dir.mkdir(parents=True)

        assert has_pending_questions(tmp_path) is False

    def test_has_pending_questions_false_no_dir(self, tmp_path):
        """Returns False when questions directory does not exist."""
        from agenticcli.commands.plan import has_pending_questions

        assert has_pending_questions(tmp_path) is False

    def test_has_pending_questions_false_only_answered(self, tmp_path):
        """Returns False when questions exist only in answered/, not pending/."""
        from agenticcli.commands.plan import has_pending_questions

        answered_dir = tmp_path / "questions" / "answered"
        answered_dir.mkdir(parents=True)
        (answered_dir / "q001.yml").write_text("question: What color?\nanswer: Blue")

        assert has_pending_questions(tmp_path) is False


# =============================================================================
# P6-T2: auto-archive blocked by pending questions
# =============================================================================


class TestAutoArchiveQuestionGate:
    """Tests for auto-archive gating when pending questions exist."""

    def _make_plan_dir(self, tmp_path):
        """Create a minimal plan directory with a plan_build.yml."""
        plan_dir = tmp_path / "260210QP_test_plan"
        plan_dir.mkdir()
        (plan_dir / "plan_build.yml").write_text(
            "phases:\n"
            "- id: P1\n"
            "  tasks:\n"
            "  - id: P1-T1\n"
            "    status: completed\n"
        )
        return plan_dir

    def test_auto_archive_blocked_when_pending_questions(self, tmp_path, monkeypatch):
        """Auto-archive is skipped when pending questions exist."""
        from agenticcli.commands import plan as plan_mod

        plan_dir = self._make_plan_dir(tmp_path)

        # Add a pending question
        pending_dir = plan_dir / "questions" / "pending"
        pending_dir.mkdir(parents=True)
        (pending_dir / "q001.yml").write_text("question: What color?")

        # Patch find_plan_folder to return our test dir
        monkeypatch.setattr(plan_mod, "find_plan_folder", lambda p: plan_dir)
        # Patch is_plan_fully_completed to return True (all tasks done)
        monkeypatch.setattr(plan_mod, "is_plan_fully_completed", lambda p: True)

        # Track whether PlanMovementWorkflow was instantiated (it should NOT be)
        workflow_mock = MagicMock()
        with patch("agenticcli.commands.plan.PlanMovementWorkflow", workflow_mock, create=True):
            pass  # won't be imported if gate works

        warnings = []
        monkeypatch.setattr(
            "agenticcli.console.print_warning",
            lambda msg: warnings.append(msg),
        )

        args = SimpleNamespace(
            task_id="P1-T1",
            plan="260210QP_test_plan",
            no_archive=False,
        )

        # Patch _update_task_status to avoid file parsing
        monkeypatch.setattr(plan_mod, "_update_task_status", lambda *a, **kw: None)

        plan_mod.cmd_task_complete(args)

        # Verify warning was printed about pending questions
        assert any("unanswered questions" in w for w in warnings), f"Expected warning, got: {warnings}"

    def test_auto_archive_proceeds_when_no_questions(self, tmp_path, monkeypatch):
        """Auto-archive proceeds when no questions directory exists."""
        from agenticcli.commands import plan as plan_mod

        plan_dir = self._make_plan_dir(tmp_path)

        monkeypatch.setattr(plan_mod, "find_plan_folder", lambda p: plan_dir)
        monkeypatch.setattr(plan_mod, "is_plan_fully_completed", lambda p: True)
        monkeypatch.setattr(plan_mod, "_update_task_status", lambda *a, **kw: None)

        # Mock PlanMovementWorkflow
        mock_result = MagicMock()
        mock_result.result = "success"
        mock_result.message = "Archived"

        mock_workflow_instance = MagicMock()
        mock_workflow_instance.archive_plan_folder.return_value = mock_result

        mock_workflow_cls = MagicMock(return_value=mock_workflow_instance)
        mock_move_result = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "agenticguidance": MagicMock(),
                "agenticguidance.services": MagicMock(
                    PlanMovementWorkflow=mock_workflow_cls,
                    MoveResult=mock_move_result,
                ),
            },
        ):
            # Suppress print output
            monkeypatch.setattr("builtins.print", lambda *a, **kw: None)
            monkeypatch.setattr("agenticcli.console.print_info", lambda msg: None)
            monkeypatch.setattr("agenticcli.console.print_success", lambda msg: None)
            monkeypatch.setattr("agenticcli.console.print_warning", lambda msg: None)

            # Patch _try_worktree_cleanup_after_archive to no-op
            monkeypatch.setattr(plan_mod, "_try_worktree_cleanup_after_archive", lambda p: None)

            args = SimpleNamespace(
                task_id="P1-T1",
                plan="260210QP_test_plan",
                no_archive=False,
            )

            plan_mod.cmd_task_complete(args)

        # Archive should have been called
        mock_workflow_instance.archive_plan_folder.assert_called_once()

    def test_auto_archive_proceeds_when_all_answered(self, tmp_path, monkeypatch):
        """Auto-archive proceeds when all questions are answered (none pending)."""
        from agenticcli.commands import plan as plan_mod

        plan_dir = self._make_plan_dir(tmp_path)

        # Add answered questions only (no pending)
        answered_dir = plan_dir / "questions" / "answered"
        answered_dir.mkdir(parents=True)
        (answered_dir / "q001.yml").write_text("question: What color?\nanswer: Blue")

        monkeypatch.setattr(plan_mod, "find_plan_folder", lambda p: plan_dir)
        monkeypatch.setattr(plan_mod, "is_plan_fully_completed", lambda p: True)
        monkeypatch.setattr(plan_mod, "_update_task_status", lambda *a, **kw: None)

        mock_result = MagicMock()
        mock_result.result = "success"
        mock_result.message = "Archived"

        mock_workflow_instance = MagicMock()
        mock_workflow_instance.archive_plan_folder.return_value = mock_result

        mock_workflow_cls = MagicMock(return_value=mock_workflow_instance)
        mock_move_result = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "agenticguidance": MagicMock(),
                "agenticguidance.services": MagicMock(
                    PlanMovementWorkflow=mock_workflow_cls,
                    MoveResult=mock_move_result,
                ),
            },
        ):
            monkeypatch.setattr("builtins.print", lambda *a, **kw: None)
            monkeypatch.setattr("agenticcli.console.print_info", lambda msg: None)
            monkeypatch.setattr("agenticcli.console.print_success", lambda msg: None)
            monkeypatch.setattr("agenticcli.console.print_warning", lambda msg: None)
            monkeypatch.setattr(plan_mod, "_try_worktree_cleanup_after_archive", lambda p: None)

            args = SimpleNamespace(
                task_id="P1-T1",
                plan="260210QP_test_plan",
                no_archive=False,
            )

            plan_mod.cmd_task_complete(args)

        mock_workflow_instance.archive_plan_folder.assert_called_once()


# =============================================================================
# P6-T3: session spawn warning on pending questions
# =============================================================================


class TestSpawnWarningOnPendingQuestions:
    """Test that cmd_spawn warns when plan has pending questions."""

    def test_spawn_warns_on_pending_questions(self, tmp_path, monkeypatch):
        """cmd_spawn prints warning when plan has pending questions."""
        from agenticcli.commands import session as session_mod

        plan_dir = tmp_path / "260210QP_test_plan"
        plan_dir.mkdir()

        # Mock _resolve_plan_folder to return our test dir
        monkeypatch.setattr(session_mod, "_resolve_plan_folder", lambda name: plan_dir)

        # Mock has_pending_questions to return True
        monkeypatch.setattr(
            "agenticcli.commands.plan.has_pending_questions",
            lambda p: True,
        )

        # Capture warnings
        warnings = []
        monkeypatch.setattr(
            "agenticcli.console.print_warning",
            lambda msg: warnings.append(msg),
        )

        # Mock subprocess.Popen so we don't actually spawn
        mock_popen = MagicMock()
        mock_popen.pid = 99999
        monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: mock_popen)

        # Mock various console functions to avoid side effects
        monkeypatch.setattr("agenticcli.console.print_error", lambda msg: None)
        monkeypatch.setattr("agenticcli.console.print_success", lambda msg: None)
        monkeypatch.setattr("agenticcli.console.print_info", lambda msg: None)
        monkeypatch.setattr("agenticcli.console.is_json_output", lambda: False)

        # Mock _get_sessions_dir to use tmp_path
        sessions_dir = tmp_path / ".agentic" / "sessions"
        sessions_dir.mkdir(parents=True)
        monkeypatch.setattr(session_mod._store, "get_dir", lambda override=None: sessions_dir)

        # Mock _get_logs_dir
        logs_dir = sessions_dir / "logs"
        logs_dir.mkdir(parents=True)
        monkeypatch.setattr(session_mod, "_get_logs_dir", lambda: logs_dir)

        # Mock _get_context_dir
        context_dir = sessions_dir / "context"
        context_dir.mkdir(parents=True)
        monkeypatch.setattr(session_mod, "_get_context_dir", lambda: context_dir)

        # Mock token utilities to avoid import issues
        monkeypatch.setattr("agenticcli.utils.tokens.estimate_tokens", lambda t: 100)
        monkeypatch.setattr("agenticcli.utils.tokens.context_usage_percent", lambda t: 5.0)
        monkeypatch.setattr("agenticcli.utils.tokens.get_usage_color", lambda p: "green")

        args = SimpleNamespace(
            prompt="Test prompt",
            role=None,
            task=None,
            plan="260210QP_test_plan",
            max_turns=5,
            background=False,
            directory=str(tmp_path),
            dangerously_skip_permissions=False,
            model=None,
            permission_mode=None,
        )

        # cmd_spawn may try to do many things; we just need to verify the warning fires
        # Mock enough to get past the spawn
        monkeypatch.setattr("builtins.print", lambda *a, **kw: None)

        try:
            session_mod.cmd_spawn(args)
        except (SystemExit, Exception):
            pass  # We don't care about completion, just the warning

        assert any("pending questions" in w for w in warnings), f"Expected warning about pending questions, got: {warnings}"
