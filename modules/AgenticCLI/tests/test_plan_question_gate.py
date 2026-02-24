"""Tests for plan question gate: has_pending_questions, spawn warning.

Covers:
  P6-T1: has_pending_questions utility
  P6-T3: session spawn warning on pending questions

Note: Auto-archive gating tests (P6-T2) have been removed because
auto-archive was removed from CLI task completion commands.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

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
