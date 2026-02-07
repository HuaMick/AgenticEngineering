"""Tests for question notification formatter.

Tests the formatting of question notifications for tmux display.
"""

import pytest

from agenticcli.utils.question_formatter import (
    format_question_notification,
    format_question_summary,
    _get_severity_color,
    COLOR_HIGH,
    COLOR_MEDIUM,
    COLOR_LOW,
    COLOR_RESET,
)


class TestFormatQuestionNotification:
    """Tests for format_question_notification function."""

    def test_formats_single_question(self):
        """Test formatting a single question."""
        questions = [
            {
                "question_id": "Q001",
                "severity": "high",
                "module": "builder",
                "question": "Should I proceed with this approach?",
                "context": "Building feature X",
            }
        ]

        result = format_question_notification(questions)

        # Verify header
        assert "PENDING QUESTIONS" in result
        assert "=" * 78 in result

        # Verify question appears
        assert "Q001" in result
        assert "high" in result
        assert "builder" in result
        assert "Should I proceed" in result

        # Verify footer commands
        assert "agentic question answer" in result
        assert "agentic question list" in result
        assert "agentic question defer" in result

    def test_formats_multiple_questions(self):
        """Test formatting multiple questions."""
        questions = [
            {
                "question_id": "Q001",
                "severity": "high",
                "module": "builder",
                "question": "Question 1",
            },
            {
                "question_id": "Q002",
                "severity": "medium",
                "module": "tester",
                "question": "Question 2",
            },
            {
                "question_id": "Q003",
                "severity": "low",
                "module": "deployer",
                "question": "Question 3",
            },
        ]

        result = format_question_notification(questions)

        # Verify all questions appear
        assert "Q001" in result
        assert "Q002" in result
        assert "Q003" in result

        # Verify indexing
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result

    def test_truncates_long_questions(self):
        """Test that long questions are truncated to 100 characters."""
        long_question = "A" * 150  # 150 character question

        questions = [
            {
                "question_id": "Q001",
                "severity": "medium",
                "module": "builder",
                "question": long_question,
            }
        ]

        result = format_question_notification(questions)

        # Should contain truncation indicator
        assert "..." in result

        # Should not contain the full question
        lines = result.split("\n")
        question_lines = [l for l in lines if "A" * 50 in l]
        for line in question_lines:
            # Account for wrapping - check that no single segment is too long
            assert len(line) <= 78

    def test_applies_severity_colors(self):
        """Test that severity colors are applied."""
        questions = [
            {
                "question_id": "Q001",
                "severity": "high",
                "module": "builder",
                "question": "Test question",
            }
        ]

        result = format_question_notification(questions)

        # Should contain red color code for high severity
        assert COLOR_HIGH in result
        assert COLOR_RESET in result

    def test_handles_empty_question_list(self):
        """Test formatting when no questions are pending."""
        result = format_question_notification([])

        assert "NO PENDING QUESTIONS" in result
        assert "All questions have been answered" in result

    def test_handles_missing_fields(self):
        """Test formatting with missing optional fields."""
        questions = [
            {
                "question_id": "Q001",
                # Missing severity, module, context
                "question": "Minimal question",
            }
        ]

        result = format_question_notification(questions)

        # Should use defaults
        assert "Q001" in result
        assert "medium" in result  # Default severity
        assert "unknown" in result  # Default module

    def test_output_width_constraint(self):
        """Test that output stays within 78 column width."""
        questions = [
            {
                "question_id": "Q001",
                "severity": "high",
                "module": "builder",
                "question": "This is a question that needs to be wrapped properly to fit within the column constraints",
            }
        ]

        result = format_question_notification(questions)

        # Check each line
        for line in result.split("\n"):
            # Remove ANSI codes for length check
            clean_line = line.replace(COLOR_HIGH, "").replace(COLOR_MEDIUM, "")
            clean_line = clean_line.replace(COLOR_LOW, "").replace(COLOR_RESET, "")
            assert len(clean_line) <= 78, f"Line too long: {len(clean_line)} chars"


class TestFormatQuestionSummary:
    """Tests for format_question_summary function."""

    def test_formats_complete_question(self):
        """Test formatting a question with all fields."""
        question = {
            "question_id": "Q001",
            "severity": "high",
            "module": "builder",
            "question": "Should I proceed with this approach?",
            "context": "Building feature X requires dependency Y",
            "created_at": "2026-02-06T10:30:00Z",
        }

        result = format_question_summary(question)

        # Verify all fields appear
        assert "Q001" in result
        assert "high" in result
        assert "builder" in result
        assert "Should I proceed" in result
        assert "Building feature X" in result
        assert "2026-02-06T10:30:00Z" in result

        # Verify command
        assert "agentic question answer Q001" in result

    def test_formats_minimal_question(self):
        """Test formatting a question with only required fields."""
        question = {
            "question_id": "Q002",
            "severity": "low",
            "module": "tester",
            "question": "Run tests?",
        }

        result = format_question_summary(question)

        # Verify required fields
        assert "Q002" in result
        assert "low" in result
        assert "tester" in result
        assert "Run tests?" in result

    def test_wraps_long_text(self):
        """Test that long question and context text are wrapped."""
        question = {
            "question_id": "Q003",
            "severity": "medium",
            "module": "builder",
            "question": "A" * 200,  # Very long question
            "context": "B" * 200,   # Very long context
        }

        result = format_question_summary(question)

        # Check each line stays within bounds
        for line in result.split("\n"):
            # Remove ANSI codes for length check
            clean_line = line.replace(COLOR_MEDIUM, "").replace(COLOR_RESET, "")
            assert len(clean_line) <= 78

    def test_applies_severity_color(self):
        """Test that severity color is applied to header."""
        question = {
            "question_id": "Q004",
            "severity": "medium",
            "module": "builder",
            "question": "Test",
        }

        result = format_question_summary(question)

        assert COLOR_MEDIUM in result
        assert COLOR_RESET in result


class TestGetSeverityColor:
    """Tests for _get_severity_color helper function."""

    def test_high_severity(self):
        """Test high severity returns red."""
        assert _get_severity_color("high") == COLOR_HIGH
        assert _get_severity_color("HIGH") == COLOR_HIGH

    def test_medium_severity(self):
        """Test medium severity returns yellow."""
        assert _get_severity_color("medium") == COLOR_MEDIUM
        assert _get_severity_color("MEDIUM") == COLOR_MEDIUM

    def test_low_severity(self):
        """Test low severity returns green."""
        assert _get_severity_color("low") == COLOR_LOW
        assert _get_severity_color("LOW") == COLOR_LOW

    def test_unknown_severity(self):
        """Test unknown severity returns reset."""
        assert _get_severity_color("unknown") == COLOR_RESET
        assert _get_severity_color("") == COLOR_RESET


class TestIntegration:
    """Integration tests for formatter functions."""

    def test_formatter_with_realistic_questions(self):
        """Test with realistic question data."""
        questions = [
            {
                "question_id": "260206-1030-Q001",
                "severity": "high",
                "module": "build-python",
                "question": "Unable to resolve import for 'agenticguidance.services.ralph'. Should I create this module or use a different import path?",
                "context": "Building ralph loop integration for CLI commands. The service module doesn't exist yet.",
                "created_at": "2026-02-06T10:30:15Z",
            },
            {
                "question_id": "260206-1045-Q002",
                "severity": "medium",
                "module": "test-unit",
                "question": "Test test_ralph_commands.py is failing due to missing fixture. Should I create the fixture or modify the test?",
                "context": "Unit test expects a 'mock_ralph_service' fixture that wasn't defined.",
                "created_at": "2026-02-06T10:45:22Z",
            },
        ]

        # Test notification format
        notification = format_question_notification(questions)
        assert "260206-1030-Q001" in notification
        assert "260206-1045-Q002" in notification
        assert len(notification.split("\n")) > 10  # Should have multiple lines

        # Test summary format
        summary = format_question_summary(questions[0])
        assert "build-python" in summary
        assert "Unable to resolve import" in summary
        assert "2026-02-06T10:30:15Z" in summary
