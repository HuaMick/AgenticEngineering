"""Integration tests for tmux HITL question workflow.

Tests the complete question notification workflow in tmux:
- Tmux environment detection
- Notification pane management
- Question formatting and rendering
- File watcher integration
- End-to-end answer workflow
"""

import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agenticcli.utils.tmux import (
    is_in_tmux,
    get_current_session_name,
    get_or_create_notification_pane,
    send_to_pane,
)
from agenticcli.utils.tmux_notify import (
    notify_questions_in_tmux,
    display_tmux_message,
    clear_notification_pane,
)
from agenticcli.utils.question_formatter import (
    format_question_notification,
    format_question_summary,
)

pytestmark = pytest.mark.integration


def _can_import_watchdog() -> bool:
    """Check if watchdog library can be imported.

    Returns:
        True if watchdog is available, False otherwise.
    """
    try:
        import watchdog
        return True
    except ImportError:
        return False


class TestTmuxDetection:
    """Integration tests for tmux environment detection."""

    def test_tmux_detection_with_env_variable(self):
        """Mock TMUX environment variable and verify detection."""
        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            assert is_in_tmux() is True

    def test_get_session_name_extracts_name(self):
        """Mock tmux commands and verify session name extraction."""
        mock_result = MagicMock()
        mock_result.stdout = "test-session\n"
        mock_result.returncode = 0

        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                session_name = get_current_session_name()

                assert session_name == "test-session"
                mock_run.assert_called_once_with(
                    ["tmux", "display-message", "-p", "#S"],
                    capture_output=True,
                    text=True,
                    check=True,
                )

    def test_detection_returns_false_without_tmux_env(self):
        """Verify is_in_tmux returns False without TMUX env variable."""
        with patch.dict("os.environ", {}, clear=True):
            assert is_in_tmux() is False

    def test_get_session_name_returns_none_without_tmux(self):
        """Verify get_current_session_name returns None when not in tmux."""
        with patch.dict("os.environ", {}, clear=True):
            assert get_current_session_name() is None


class TestNotificationPaneCreation:
    """Integration tests for notification pane creation and reuse."""

    def test_notification_pane_creation(self):
        """Mock tmux commands and verify pane creation."""
        # Mock: pane doesn't exist, so it will be created
        mock_list_panes = MagicMock()
        mock_list_panes.stdout = "%0:shell\n"

        mock_split_window = MagicMock()
        mock_split_window.stdout = "%2\n"

        mock_select_pane = MagicMock()

        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("subprocess.run", side_effect=[mock_list_panes, mock_split_window, mock_select_pane]) as mock_run:
                pane_id = get_or_create_notification_pane("questions")

                assert pane_id == "%2"
                # Verify split-window was called
                assert mock_run.call_count == 3
                # Check that split-window call includes correct arguments
                split_call = mock_run.call_args_list[1]
                assert "split-window" in split_call[0][0]
                assert "-h" in split_call[0][0]
                assert "30" in split_call[0][0]

    def test_notification_pane_reuse_on_second_call(self):
        """Verify existing pane is reused instead of creating new one."""
        # Mock: pane already exists
        mock_list_panes = MagicMock()
        mock_list_panes.stdout = "%0:shell\n%1:questions\n"

        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("subprocess.run", return_value=mock_list_panes) as mock_run:
                pane_id = get_or_create_notification_pane("questions")

                assert pane_id == "%1"
                # Only list-panes should be called, no split-window
                assert mock_run.call_count == 1

    def test_pane_creation_raises_error_outside_tmux(self):
        """Verify RuntimeError is raised when not in tmux session."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="Not running in a tmux session"):
                get_or_create_notification_pane("questions")


class TestQuestionNotificationRendering:
    """Integration tests for question notification formatting."""

    def test_question_notification_rendering(self):
        """Create sample questions and verify formatted output."""
        questions = [
            {
                "question_id": "Q-20260203-100000-aaaa",
                "severity": "high",
                "module": "builder",
                "question": "Should I proceed with this implementation approach?",
                "context": "Building feature X",
            },
            {
                "question_id": "Q-20260203-110000-bbbb",
                "severity": "medium",
                "module": "tester",
                "question": "Do we need integration tests for this component?",
                "context": "Test coverage",
            },
        ]

        formatted = format_question_notification(questions)

        # Verify output contains question IDs
        assert "Q-20260203-100000-aaaa" in formatted
        assert "Q-20260203-110000-bbbb" in formatted

        # Verify severity levels are shown
        assert "(high)" in formatted
        assert "(medium)" in formatted

        # Verify module names are shown
        assert "builder" in formatted
        assert "tester" in formatted

        # Verify CLI commands are in footer
        assert "agentic question answer" in formatted
        assert "agentic question list" in formatted
        assert "agentic question defer" in formatted

        # Verify header is present
        assert "PENDING QUESTIONS" in formatted

    def test_empty_questions_notification(self):
        """Verify correct message when no questions pending."""
        formatted = format_question_notification([])

        assert "NO PENDING QUESTIONS" in formatted
        assert "All questions have been answered or deferred" in formatted

    def test_question_summary_formatting(self):
        """Verify single question summary formatting."""
        question = {
            "question_id": "Q-20260203-120000-cccc",
            "severity": "high",
            "module": "planner",
            "question": "What is the optimal algorithm for this task?",
            "context": "Performance optimization phase",
            "created_at": "2026-02-03T10:00:00Z",
        }

        formatted = format_question_summary(question)

        # Verify all fields are present
        assert "Q-20260203-120000-cccc" in formatted
        assert "high" in formatted
        assert "planner" in formatted
        assert "What is the optimal algorithm" in formatted
        assert "Performance optimization phase" in formatted
        assert "2026-02-03T10:00:00Z" in formatted
        assert "agentic question answer" in formatted


class TestNotificationUpdateOnAnswer:
    """Integration tests for notification updates during question lifecycle."""

    @pytest.fixture
    def questions_folder(self, temp_dir):
        """Create temporary questions folder structure."""
        plan_folder = temp_dir / "plan"
        plan_folder.mkdir()

        questions_dir = plan_folder / "questions"
        pending_dir = questions_dir / "pending"
        answered_dir = questions_dir / "answered"

        questions_dir.mkdir()
        pending_dir.mkdir()
        answered_dir.mkdir()

        return plan_folder

    def test_notification_update_on_answer(self, questions_folder):
        """Test complete workflow: create question, notify, answer, notify again."""
        pending_dir = questions_folder / "questions" / "pending"
        answered_dir = questions_folder / "questions" / "answered"

        # Create pending question
        question = {
            "id": "Q-20260203-140000-dddd",
            "text": "Should we add caching?",
            "context": "Performance optimization",
            "severity": "medium",
            "asked_by": "agent",
            "created_at": time.time(),
            "status": "pending",
        }
        question_file = pending_dir / "Q-20260203-140000-dddd.yml"
        question_file.write_text(yaml.dump(question))

        # Mock tmux session
        mock_list_panes = MagicMock()
        mock_list_panes.stdout = "%0:shell\n%1:questions\n"

        mock_send_keys_clear = MagicMock()
        mock_send_keys_line = MagicMock()
        mock_send_keys_enter = MagicMock()

        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("subprocess.run", return_value=mock_list_panes):
                # First notification - question is pending
                questions_list = [question]
                result = notify_questions_in_tmux(questions_folder, questions_list)
                assert result is True

        # Simulate answering the question (move to answered/)
        answered_question = question.copy()
        answered_question["status"] = "answered"
        answered_question["answer"] = "Yes, we should implement caching"
        answered_question["answered_at"] = time.time()
        answered_question["answered_by"] = "human"

        # Move to answered directory
        answered_file = answered_dir / "Q-20260203-140000-dddd_question.yml"
        answered_file.write_text(yaml.dump(answered_question))
        answer_file = answered_dir / "Q-20260203-140000-dddd.yml"
        answer_file.write_text(yaml.dump({"answer": answered_question["answer"]}))
        question_file.unlink()

        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("subprocess.run", return_value=mock_list_panes):
                # Second notification - no pending questions
                result = notify_questions_in_tmux(questions_folder, [])
                assert result is True

    def test_clear_notification_pane(self, questions_folder):
        """Test clearing notification pane when all questions answered."""
        mock_list_panes = MagicMock()
        mock_list_panes.stdout = "%0:shell\n%1:questions\n"

        mock_send_keys = MagicMock()

        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("subprocess.run", return_value=mock_list_panes):
                result = clear_notification_pane()
                # Should succeed in finding and clearing pane
                assert result is True

    def test_send_to_pane_with_clear(self):
        """Test sending content to pane with clear flag."""
        mock_run = MagicMock()

        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("subprocess.run", return_value=mock_run):
                send_to_pane("%1", "Test content\nLine 2", clear=True)
                # Function should execute without error
                # Actual command verification is in unit tests

    def test_tmux_message_display(self):
        """Test displaying message in tmux status bar."""
        mock_run = MagicMock()

        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("subprocess.run", return_value=mock_run) as mock_subprocess:
                display_tmux_message("Test notification message", duration_ms=3000)

                # Verify display-message was called
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert "display-message" in call_args
                assert "3000" in call_args
                assert "Test notification message" in call_args


class TestFileWatcherDetection:
    """Integration tests for file watcher detection and notification."""

    @pytest.fixture
    def watcher_folder(self, temp_dir):
        """Create folder for file watcher tests."""
        plan_folder = temp_dir / "watcher_test"
        plan_folder.mkdir()

        questions_dir = plan_folder / "questions"
        pending_dir = questions_dir / "pending"
        answered_dir = questions_dir / "answered"

        questions_dir.mkdir()
        pending_dir.mkdir()
        answered_dir.mkdir()

        return plan_folder

    @pytest.mark.skipif(
        not _can_import_watchdog(),
        reason="watchdog library not installed"
    )
    def test_file_watcher_detection(self, watcher_folder):
        """Test file watcher detects new question files."""
        from agenticcli.services.question_watcher import (
            start_question_watcher,
            stop_question_watcher,
        )

        # Track callback invocations
        callback_count = []

        def notification_callback():
            callback_count.append(1)

        # Start watcher
        observer = start_question_watcher(
            watcher_folder,
            notification_callback,
            daemon=True
        )

        try:
            # Create new question file
            pending_dir = watcher_folder / "questions" / "pending"
            new_question = {
                "id": "Q-20260203-150000-eeee",
                "text": "Test question for watcher",
                "severity": "low",
                "asked_by": "test",
                "created_at": time.time(),
                "status": "pending",
            }
            question_file = pending_dir / "Q-20260203-150000-eeee.yml"
            question_file.write_text(yaml.dump(new_question))

            # Wait for debounce (2 seconds) + buffer
            time.sleep(3.5)

            # Verify callback was triggered
            assert len(callback_count) > 0, "Callback should be triggered after file creation"

        finally:
            # Stop watcher
            stop_question_watcher(observer)

    @pytest.mark.skipif(
        not _can_import_watchdog(),
        reason="watchdog library not installed"
    )
    def test_file_watcher_detects_answer_move(self, watcher_folder):
        """Test file watcher detects question being moved to answered."""
        from agenticcli.services.question_watcher import (
            start_question_watcher,
            stop_question_watcher,
        )

        # Create initial question in pending
        pending_dir = watcher_folder / "questions" / "pending"
        answered_dir = watcher_folder / "questions" / "answered"

        question = {
            "id": "Q-20260203-160000-ffff",
            "text": "Will this trigger watcher?",
            "severity": "medium",
            "asked_by": "test",
            "created_at": time.time(),
            "status": "pending",
        }
        question_file = pending_dir / "Q-20260203-160000-ffff.yml"
        question_file.write_text(yaml.dump(question))

        # Track callback invocations
        callback_count = []

        def notification_callback():
            callback_count.append(1)

        # Start watcher
        observer = start_question_watcher(
            watcher_folder,
            notification_callback,
            daemon=True
        )

        try:
            # Wait for initial file creation to settle
            time.sleep(0.5)
            initial_count = len(callback_count)

            # Move question to answered (simulate answering)
            answered_file = answered_dir / "Q-20260203-160000-ffff_question.yml"
            answered_file.write_text(question_file.read_text())
            question_file.unlink()

            # Wait for debounce + buffer
            time.sleep(3.5)

            # Verify callback was triggered for the move/delete
            assert len(callback_count) > initial_count, "Callback should be triggered after file move"

        finally:
            # Stop watcher
            stop_question_watcher(observer)

    @pytest.mark.skipif(
        not _can_import_watchdog(),
        reason="watchdog library not installed"
    )
    def test_file_watcher_ignores_non_yml_files(self, watcher_folder):
        """Test file watcher ignores non-.yml files."""
        from agenticcli.services.question_watcher import (
            start_question_watcher,
            stop_question_watcher,
        )

        # Track callback invocations
        callback_count = []

        def notification_callback():
            callback_count.append(1)

        # Start watcher
        observer = start_question_watcher(
            watcher_folder,
            notification_callback,
            daemon=True
        )

        try:
            # Create non-.yml file (should be ignored)
            pending_dir = watcher_folder / "questions" / "pending"
            temp_file = pending_dir / "temp.txt"
            temp_file.write_text("This should be ignored")

            # Wait for potential debounce
            time.sleep(3.5)

            # Verify callback was NOT triggered
            assert len(callback_count) == 0, "Callback should not trigger for non-.yml files"

        finally:
            # Stop watcher
            stop_question_watcher(observer)
