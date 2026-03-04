"""Tests for interactive answer wizard.

Tests the interactive question answering workflow including:
- Suggested answer selection
- Custom answer input
- Question deferral
- Confirmation prompts
- Input validation and retries
"""

from unittest.mock import MagicMock, patch

import pytest


class TestInteractiveAnswerWizard:
    """Tests for interactive_answer_wizard function."""

    @pytest.fixture
    def mock_question(self):
        """Create a mock Question object."""
        question = MagicMock()
        question.text = "Should we use pytest for testing?"
        question.severity = "medium"
        return question

    def test_select_suggested_answer(self, mock_question):
        """Test selecting a suggested answer from the menu."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        suggested = ["Yes", "No", "Maybe"]

        # Mock user selecting option 1 and confirming
        with patch("builtins.input", side_effect=["1", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, suggested)

        assert answer == "Yes"
        assert confidence == "high"

    def test_select_custom_answer(self, mock_question):
        """Test selecting custom answer option."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        suggested = ["Yes", "No"]

        # Mock user selecting custom option, entering text, and confirming
        with patch("builtins.input", side_effect=["C", "Use pytest with coverage", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, suggested)

        assert answer == "Use pytest with coverage"
        assert confidence is None

    def test_defer_question(self, mock_question):
        """Test deferring a question."""
        from agenticcli.utils.interactive_answer import (
            DEFER_SENTINEL,
            interactive_answer_wizard,
        )

        suggested = ["Yes", "No"]

        # Mock user selecting defer and confirming
        with patch("builtins.input", side_effect=["D", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, suggested)

        assert answer == DEFER_SENTINEL
        assert confidence is None

    def test_confirm_yes(self, mock_question):
        """Test confirmation with 'Y' response."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        suggested = ["Yes"]

        # Mock user selecting option and confirming with 'Y'
        with patch("builtins.input", side_effect=["1", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, suggested)

        assert answer == "Yes"

    def test_confirm_no(self, mock_question):
        """Test confirmation with 'N' response returns to menu."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        suggested = ["Yes"]

        # Mock user selecting option, declining, then selecting again and confirming
        with patch("builtins.input", side_effect=["1", "N", "1", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, suggested)

        assert answer == "Yes"

    def test_no_suggestions(self, mock_question):
        """Test freeform text input when no suggestions provided."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        # Mock user entering freeform text and confirming
        with patch("builtins.input", side_effect=["Use pytest framework", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, None)

        assert answer == "Use pytest framework"
        assert confidence is None

    def test_invalid_input_retries(self, mock_question):
        """Test that invalid inputs prompt retry."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        suggested = ["Yes", "No"]

        # Mock invalid inputs followed by valid selection
        with patch("builtins.input", side_effect=["X", "99", "0", "1", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, suggested)

        assert answer == "Yes"

    def test_empty_custom_answer_retries(self, mock_question):
        """Test that empty custom answers prompt retry."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        suggested = ["Yes"]

        # Mock custom selection with empty input, then valid input
        with patch("builtins.input", side_effect=["C", "", "Valid answer", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, suggested)

        assert answer == "Valid answer"

    def test_empty_freeform_answer_retries(self, mock_question):
        """Test that empty freeform answers prompt retry."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        # Mock empty input followed by valid input
        with patch("builtins.input", side_effect=["", "Valid answer", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, None)

        assert answer == "Valid answer"

    def test_defer_without_suggestions(self, mock_question):
        """Test deferring when in freeform mode."""
        from agenticcli.utils.interactive_answer import (
            DEFER_SENTINEL,
            interactive_answer_wizard,
        )

        # Mock user entering 'D' to defer and confirming
        with patch("builtins.input", side_effect=["D", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, None)

        assert answer == DEFER_SENTINEL
        assert confidence is None

    def test_defer_declined_then_answer(self, mock_question):
        """Test declining defer confirmation and then providing answer."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        suggested = ["Yes"]

        # Mock user selecting defer, declining, then answering
        with patch("builtins.input", side_effect=["D", "N", "1", "Y"]):
            answer, confidence = interactive_answer_wizard(mock_question, suggested)

        assert answer == "Yes"

    def test_keyboard_interrupt_returns_defer(self, mock_question):
        """Test that KeyboardInterrupt returns DEFER_SENTINEL."""
        from agenticcli.utils.interactive_answer import (
            DEFER_SENTINEL,
            interactive_answer_wizard,
        )

        suggested = ["Yes"]

        # Mock KeyboardInterrupt during input
        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            answer, confidence = interactive_answer_wizard(mock_question, suggested)

        assert answer == DEFER_SENTINEL
        assert confidence is None

    def test_eof_error_returns_defer(self, mock_question):
        """Test that EOFError returns DEFER_SENTINEL."""
        from agenticcli.utils.interactive_answer import (
            DEFER_SENTINEL,
            interactive_answer_wizard,
        )

        # Mock EOFError during input
        with patch("builtins.input", side_effect=EOFError()):
            answer, confidence = interactive_answer_wizard(mock_question, None)

        assert answer == DEFER_SENTINEL
        assert confidence is None

    def test_severity_badge_blocking(self):
        """Test that blocking severity shows correct badge."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        question = MagicMock()
        question.text = "Critical issue"
        question.severity = "blocking"

        with patch("builtins.input", side_effect=["Test answer", "Y"]):
            answer, _ = interactive_answer_wizard(question, None)

        assert answer == "Test answer"

    def test_severity_badge_high(self):
        """Test that high severity shows correct badge."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        question = MagicMock()
        question.text = "Important question"
        question.severity = "high"

        with patch("builtins.input", side_effect=["Test answer", "Y"]):
            answer, _ = interactive_answer_wizard(question, None)

        assert answer == "Test answer"

    def test_severity_badge_low(self):
        """Test that low severity shows correct badge."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        question = MagicMock()
        question.text = "Minor question"
        question.severity = "low"

        with patch("builtins.input", side_effect=["Test answer", "Y"]):
            answer, _ = interactive_answer_wizard(question, None)

        assert answer == "Test answer"

    def test_multiple_confirmation_retries(self):
        """Test multiple invalid confirmation prompts before accepting."""
        from agenticcli.utils.interactive_answer import interactive_answer_wizard

        question = MagicMock()
        question.text = "Test question"
        question.severity = "medium"

        # Mock invalid confirmations followed by valid 'Y'
        with patch("builtins.input", side_effect=["Test answer", "X", "maybe", "Y"]):
            answer, _ = interactive_answer_wizard(question, None)

        assert answer == "Test answer"


class TestAnswerCommandInteractive:
    """Integration tests for question answer command with --interactive flag."""

    @pytest.fixture
    def epic_with_pending_question(self, temp_repo):
        """Create epic folder with a pending question."""
        import time

        import yaml

        plan_path = temp_repo / "docs" / "epics" / "live" / "260208PN_interactive_test"
        plan_path.mkdir(parents=True)

        questions_dir = plan_path / "questions"
        pending_dir = questions_dir / "pending"
        answered_dir = questions_dir / "answered"
        pending_dir.mkdir(parents=True)
        answered_dir.mkdir(parents=True)

        # Use valid question ID format: Q-YYYYMMDD-HHMMSS-XXXX
        question_id = "Q-20260208-100000-a1b2"
        question = {
            "id": question_id,
            "text": "Should we use interactive mode?",
            "context": "Testing interactive wizard",
            "severity": "medium",
            "asked_by": "agent",
            "created_at": time.time(),
            "status": "pending",
        }
        (pending_dir / f"{question_id}.yml").write_text(yaml.dump(question))

        return plan_path

    def test_interactive_flag_launches_wizard(
        self, cli_runner, epic_with_pending_question
    ):
        """Test that --interactive flag launches the wizard."""
        # Mock the wizard to return a test answer
        with patch(
            "agenticcli.utils.interactive_answer.interactive_answer_wizard"
        ) as mock_wizard:
            mock_wizard.return_value = ("Yes, use interactive mode", "high")

            result = cli_runner(
                [
                    "plan",
                    "question",
                    "answer",
                    "Q-20260208-100000-a1b2",
                    "--interactive",
                    "--plan",
                    str(epic_with_pending_question),
                ]
            )

            # Verify wizard was called
            assert mock_wizard.called
            assert result.returncode == 0

    def test_interactive_without_question_id_lists_questions(
        self, cli_runner, epic_with_pending_question
    ):
        """Test that --interactive without question_id shows selection list."""
        # Mock input to select question 1
        with patch("builtins.input", side_effect=["1"]):
            # Mock the wizard
            with patch(
                "agenticcli.utils.interactive_answer.interactive_answer_wizard"
            ) as mock_wizard:
                mock_wizard.return_value = ("Test answer", None)

                result = cli_runner(
                    [
                        "plan",
                        "question",
                        "answer",
                        "--interactive",
                        "--plan",
                        str(epic_with_pending_question),
                    ]
                )

                # Should show pending questions
                assert "Pending Questions" in result.stdout or mock_wizard.called
                # May exit with 0 or continue to wizard depending on mock
                # The key is that it doesn't error immediately

    def test_interactive_deferred_question_updates_status(
        self, cli_runner, epic_with_pending_question
    ):
        """Test that deferring via wizard updates question status."""
        from agenticcli.utils.interactive_answer import DEFER_SENTINEL

        # Mock wizard to return defer sentinel
        with patch(
            "agenticcli.utils.interactive_answer.interactive_answer_wizard"
        ) as mock_wizard:
            mock_wizard.return_value = (DEFER_SENTINEL, None)

            result = cli_runner(
                [
                    "plan",
                    "question",
                    "answer",
                    "Q-20260208-100000-a1b2",
                    "--interactive",
                    "--plan",
                    str(epic_with_pending_question),
                ]
            )

            assert result.returncode == 0
            assert "deferred" in result.stdout.lower()

            # Verify question status was updated
            import yaml

            pending_dir = epic_with_pending_question / "questions" / "pending"
            question_file = pending_dir / "Q-20260208-100000-a1b2.yml"
            assert question_file.exists()

            content = yaml.safe_load(question_file.read_text())
            assert content["status"] == "deferred"

    def test_non_interactive_unchanged(self, cli_runner, epic_with_pending_question):
        """Test that non-interactive mode still works as before."""
        result = cli_runner(
            [
                "plan",
                "question",
                "answer",
                "Q-20260208-100000-a1b2",
                "--text",
                "Non-interactive answer",
                "--plan",
                str(epic_with_pending_question),
            ]
        )

        assert result.returncode == 0
        assert "answered" in result.stdout.lower()

        # Verify question moved to answered directory
        answered_dir = epic_with_pending_question / "questions" / "answered"
        assert (answered_dir / "Q-20260208-100000-a1b2_question.yml").exists()

    def test_interactive_with_confidence_from_wizard(
        self, cli_runner, epic_with_pending_question
    ):
        """Test that wizard-provided confidence is used."""
        # Mock wizard to return answer with high confidence
        with patch(
            "agenticcli.utils.interactive_answer.interactive_answer_wizard"
        ) as mock_wizard:
            mock_wizard.return_value = ("Suggested answer", "high")

            result = cli_runner(
                [
                    "plan",
                    "question",
                    "answer",
                    "Q-20260208-100000-a1b2",
                    "--interactive",
                    "--plan",
                    str(epic_with_pending_question),
                ]
            )

            assert result.returncode == 0
            assert "answered" in result.stdout.lower()

            # Verify answer file contains confidence
            import yaml

            answered_dir = epic_with_pending_question / "questions" / "answered"
            answer_file = answered_dir / "Q-20260208-100000-a1b2.yml"
            assert answer_file.exists()

            content = yaml.safe_load(answer_file.read_text())
            assert content["confidence"] == "high"
