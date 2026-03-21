"""Tests for suggested answers feature in Question model and QuestionQueue service.

Tests cover:
- Question dataclass field default None
- to_dict() with and without suggested_answers
- from_dict() reading suggested_answers
- YAML round-trip serialization
- create_question() with and without suggested_answers
- Validation: non-empty list, non-empty strings, max 10 items
- Interactive wizard receives suggested answers
"""

import pytest
import tempfile
import time

pytestmark = pytest.mark.story("US-GDN-021")
from pathlib import Path

from agenticguidance.models.question import (
    Question,
    QuestionSeverity,
    question_to_yaml,
    yaml_to_question,
)
from agenticguidance.services.question import QuestionQueue


class TestQuestionSuggestedAnswers:
    """Test Question model with suggested_answers field."""

    def test_field_default_none(self):
        """Verify suggested_answers defaults to None."""
        question = Question(
            id="Q-20260208-120000-abcd",
            text="Test question?",
            context="Test context",
            severity="medium",
            asked_by="agent",
            created_at=time.time(),
        )
        assert question.suggested_answers is None

    def test_to_dict_without_suggested_answers(self):
        """Verify to_dict() excludes suggested_answers when None."""
        question = Question(
            id="Q-20260208-120000-abcd",
            text="Test question?",
            context="Test context",
            severity="medium",
            asked_by="agent",
            created_at=time.time(),
        )
        data = question.to_dict()
        assert "suggested_answers" not in data

    def test_to_dict_with_suggested_answers(self):
        """Verify to_dict() includes suggested_answers when set."""
        question = Question(
            id="Q-20260208-120000-abcd",
            text="Test question?",
            context="Test context",
            severity="medium",
            asked_by="agent",
            created_at=time.time(),
            suggested_answers=["Option A", "Option B", "Option C"],
        )
        data = question.to_dict()
        assert "suggested_answers" in data
        assert data["suggested_answers"] == ["Option A", "Option B", "Option C"]

    def test_from_dict_without_suggested_answers(self):
        """Verify from_dict() handles missing suggested_answers."""
        data = {
            "id": "Q-20260208-120000-abcd",
            "text": "Test question?",
            "context": "Test context",
            "severity": "medium",
            "asked_by": "agent",
            "created_at": time.time(),
            "status": "pending",
        }
        question = Question.from_dict(data)
        assert question.suggested_answers is None

    def test_from_dict_with_suggested_answers(self):
        """Verify from_dict() reads suggested_answers from dict."""
        data = {
            "id": "Q-20260208-120000-abcd",
            "text": "Test question?",
            "context": "Test context",
            "severity": "medium",
            "asked_by": "agent",
            "created_at": time.time(),
            "status": "pending",
            "suggested_answers": ["Yes", "No", "Maybe"],
        }
        question = Question.from_dict(data)
        assert question.suggested_answers == ["Yes", "No", "Maybe"]

    def test_yaml_roundtrip_without_suggested_answers(self):
        """Verify YAML round-trip without suggested_answers."""
        question = Question(
            id="Q-20260208-120000-abcd",
            text="Test question?",
            context="Test context",
            severity="medium",
            asked_by="agent",
            created_at=1234567890.0,
            status="pending",
        )
        yaml_str = question_to_yaml(question)
        restored = yaml_to_question(yaml_str)

        assert restored.id == question.id
        assert restored.text == question.text
        assert restored.suggested_answers is None

    def test_yaml_roundtrip_with_suggested_answers(self):
        """Verify YAML round-trip with suggested_answers."""
        question = Question(
            id="Q-20260208-120000-abcd",
            text="Should we proceed?",
            context="Decision needed",
            severity="high",
            asked_by="agent",
            created_at=1234567890.0,
            status="pending",
            suggested_answers=["Proceed", "Wait", "Cancel"],
        )
        yaml_str = question_to_yaml(question)
        restored = yaml_to_question(yaml_str)

        assert restored.id == question.id
        assert restored.text == question.text
        assert restored.suggested_answers == ["Proceed", "Wait", "Cancel"]


class TestCreateQuestionSuggested:
    """Test QuestionQueue.create_question() with suggested_answers."""

    def test_create_without_suggested_answers(self, tmp_path):
        """Verify create_question() works without suggested_answers."""
        queue = QuestionQueue(tmp_path)
        question = queue.create_question(
            text="Test question?",
            context="Test context",
            severity="medium",
            asked_by="agent",
        )

        assert question.suggested_answers is None

        # Verify it's persisted without suggested_answers
        question_path = queue.pending_dir / f"{question.id}.yml"
        assert question_path.exists()

        loaded = queue.get_question(question.id)
        assert loaded is not None
        assert loaded.suggested_answers is None

    def test_create_with_suggested_answers(self, tmp_path):
        """Verify create_question() accepts and persists suggested_answers."""
        queue = QuestionQueue(tmp_path)
        suggestions = ["Option A", "Option B", "Option C"]

        question = queue.create_question(
            text="Choose an option",
            context="User needs to pick",
            severity="medium",
            asked_by="agent",
            suggested_answers=suggestions,
        )

        assert question.suggested_answers == suggestions

        # Verify it's persisted with suggested_answers
        loaded = queue.get_question(question.id)
        assert loaded is not None
        assert loaded.suggested_answers == suggestions

    def test_validation_empty_list(self, tmp_path):
        """Verify validation rejects empty list."""
        queue = QuestionQueue(tmp_path)

        with pytest.raises(ValueError, match="must not be empty"):
            queue.create_question(
                text="Test question?",
                context="Test context",
                severity="medium",
                suggested_answers=[],
            )

    def test_validation_not_a_list(self, tmp_path):
        """Verify validation rejects non-list values."""
        queue = QuestionQueue(tmp_path)

        with pytest.raises(ValueError, match="must be a list"):
            queue.create_question(
                text="Test question?",
                context="Test context",
                severity="medium",
                suggested_answers="not a list",
            )

    def test_validation_non_string_items(self, tmp_path):
        """Verify validation rejects non-string items."""
        queue = QuestionQueue(tmp_path)

        with pytest.raises(ValueError, match="must be a string"):
            queue.create_question(
                text="Test question?",
                context="Test context",
                severity="medium",
                suggested_answers=["Valid", 123, "Also valid"],
            )

    def test_validation_empty_string_items(self, tmp_path):
        """Verify validation rejects empty string items."""
        queue = QuestionQueue(tmp_path)

        with pytest.raises(ValueError, match="must not be empty or whitespace"):
            queue.create_question(
                text="Test question?",
                context="Test context",
                severity="medium",
                suggested_answers=["Valid", "   ", "Also valid"],
            )

    def test_validation_max_10_items(self, tmp_path):
        """Verify validation enforces max 10 items."""
        queue = QuestionQueue(tmp_path)

        # 10 items should be OK
        queue.create_question(
            text="Test question?",
            context="Test context",
            severity="medium",
            suggested_answers=[f"Option {i}" for i in range(10)],
        )

        # 11 items should fail
        with pytest.raises(ValueError, match="cannot exceed 10 items"):
            queue.create_question(
                text="Test question?",
                context="Test context",
                severity="medium",
                suggested_answers=[f"Option {i}" for i in range(11)],
            )

    def test_validation_whitespace_only(self, tmp_path):
        """Verify validation rejects whitespace-only strings."""
        queue = QuestionQueue(tmp_path)

        with pytest.raises(ValueError, match="must not be empty or whitespace"):
            queue.create_question(
                text="Test question?",
                context="Test context",
                severity="medium",
                suggested_answers=["Valid", "\t\n", "Also valid"],
            )


class TestInteractiveWithSuggestions:
    """Test that interactive wizard receives suggested answers.

    Note: These tests verify that the suggested_answers are correctly loaded
    from the Question object and would be passed to the wizard. We don't
    test the actual wizard UI here (that's in the CLI integration tests).
    """

    def test_question_has_suggestions_accessible(self, tmp_path):
        """Verify Question object with suggestions is accessible."""
        queue = QuestionQueue(tmp_path)
        suggestions = ["Yes", "No", "Maybe"]

        question = queue.create_question(
            text="Proceed with deployment?",
            context="Production deployment",
            severity="blocking",
            asked_by="agent",
            suggested_answers=suggestions,
        )

        # Verify the question object has suggested_answers attribute
        assert hasattr(question, 'suggested_answers')
        assert question.suggested_answers == suggestions

        # Verify we can retrieve it from the service
        loaded = queue.get_question(question.id)
        assert loaded.suggested_answers == suggestions

    def test_wizard_would_receive_suggestions(self, tmp_path):
        """Verify that cmd_answer logic would pass suggestions to wizard.

        This simulates the flow in cmd_answer() where we:
        1. Load the question
        2. Extract suggested_answers
        3. Pass to interactive_answer_wizard()
        """
        queue = QuestionQueue(tmp_path)
        suggestions = ["Approve", "Reject", "Defer"]

        question = queue.create_question(
            text="Review pull request?",
            context="Code review needed",
            severity="high",
            asked_by="agent",
            suggested_answers=suggestions,
        )

        # Simulate the cmd_answer() flow
        loaded_question = queue.get_question(question.id)
        assert loaded_question is not None

        # This is what cmd_answer would do
        suggested_answers_for_wizard = loaded_question.suggested_answers
        assert suggested_answers_for_wizard == suggestions
        assert isinstance(suggested_answers_for_wizard, list)
        assert len(suggested_answers_for_wizard) == 3

    def test_wizard_receives_none_when_no_suggestions(self, tmp_path):
        """Verify wizard receives None when question has no suggestions."""
        queue = QuestionQueue(tmp_path)

        question = queue.create_question(
            text="Freeform question?",
            context="No preset answers",
            severity="low",
            asked_by="agent",
        )

        # Simulate the cmd_answer() flow
        loaded_question = queue.get_question(question.id)
        suggested_answers_for_wizard = loaded_question.suggested_answers
        assert suggested_answers_for_wizard is None
