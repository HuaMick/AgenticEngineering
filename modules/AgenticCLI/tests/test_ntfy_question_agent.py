"""Tests for NtfyQuestionAgent - sequential question delivery via ntfy.

Tests intent detection, queue state persistence, reply routing, and
the full next-answer-next sequential delivery flow.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agenticcli.services.ntfy_question_agent import (
    Intent,
    NtfyQueueState,
    NtfyQuestionAgent,
    detect_intent,
    load_state,
    save_state,
)


# ---------------------------------------------------------------------------
# Intent Detection Tests (test_01_01)
# ---------------------------------------------------------------------------

class TestDetectIntent:
    """Tests for detect_intent() pattern matching."""

    @pytest.mark.parametrize("text,expected", [
        ("next", Intent.NEXT_QUESTION),
        ("Next", Intent.NEXT_QUESTION),
        ("NEXT QUESTION", Intent.NEXT_QUESTION),
        ("next question", Intent.NEXT_QUESTION),
        ("skip", Intent.NEXT_QUESTION),
        ("Skip", Intent.NEXT_QUESTION),
    ])
    def test_next_question(self, text, expected):
        assert detect_intent(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("list", Intent.LIST_QUESTIONS),
        ("how many", Intent.LIST_QUESTIONS),
        ("How Many?", Intent.LIST_QUESTIONS),
    ])
    def test_list_questions(self, text, expected):
        assert detect_intent(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("?", Intent.MORE_INFO),
        ("discuss", Intent.MORE_INFO),
        ("more info", Intent.MORE_INFO),
        ("details", Intent.MORE_INFO),
        ("explain", Intent.MORE_INFO),
    ])
    def test_more_info(self, text, expected):
        assert detect_intent(text) == expected

    @pytest.mark.parametrize("text", ["A", "B", "j", "a"])
    def test_answer_letter(self, text):
        assert detect_intent(text) == Intent.ANSWER_LETTER

    @pytest.mark.parametrize("text", [
        "Redis", "I think option B", "AB", "A is best",
        "Use PostgreSQL", "", "  ",
    ])
    def test_answer_text(self, text):
        assert detect_intent(text) == Intent.ANSWER_TEXT


# ---------------------------------------------------------------------------
# State Persistence Tests (test_01_03)
# ---------------------------------------------------------------------------

class TestNtfyQueueState:
    """Tests for NtfyQueueState load/save persistence."""

    def test_load_state_missing_file(self, tmp_path):
        """load_state returns default NtfyQueueState when file doesn't exist."""
        state = load_state(tmp_path)
        assert state.current_question_id is None
        assert state.sent_at is None
        assert state.answered_count == 0

    def test_save_and_load_roundtrip(self, tmp_path):
        """save_state + load_state roundtrip preserves all fields."""
        original = NtfyQueueState(
            current_question_id="Q-20260210-120000-abc1",
            sent_at=1707400000.0,
            answered_count=5,
        )
        save_state(tmp_path, original)
        loaded = load_state(tmp_path)

        assert loaded.current_question_id == original.current_question_id
        assert loaded.sent_at == original.sent_at
        assert loaded.answered_count == original.answered_count

    def test_save_creates_parent_dirs(self, tmp_path):
        """save_state creates parent directories if needed."""
        plan_path = tmp_path / "deep" / "nested" / "plan"
        state = NtfyQueueState(current_question_id="Q-test")
        save_state(plan_path, state)

        state_file = plan_path / "questions" / "ntfy_state.yml"
        assert state_file.exists()

    def test_state_file_is_valid_yaml(self, tmp_path):
        """State file is parseable YAML after save."""
        state = NtfyQueueState(
            current_question_id="Q-20260210-120000-abc1",
            sent_at=1707400000.0,
            answered_count=3,
        )
        save_state(tmp_path, state)

        state_file = tmp_path / "questions" / "ntfy_state.yml"
        data = yaml.safe_load(state_file.read_text())
        assert isinstance(data, dict)
        assert data["current_question_id"] == "Q-20260210-120000-abc1"
        assert data["sent_at"] == 1707400000.0
        assert data["answered_count"] == 3

    def test_save_overwrites_existing(self, tmp_path):
        """save_state overwrites previous state correctly."""
        save_state(tmp_path, NtfyQueueState(answered_count=1))
        save_state(tmp_path, NtfyQueueState(answered_count=2))
        loaded = load_state(tmp_path)
        assert loaded.answered_count == 2


# ---------------------------------------------------------------------------
# Helper: create questions for agent tests
# ---------------------------------------------------------------------------

def _create_test_questions(plan_path: Path, count: int = 3) -> list:
    """Create test questions using the QuestionQueue service."""
    from agenticguidance.services.question import QuestionQueue

    service = QuestionQueue(plan_path)
    questions = []
    for i in range(count):
        q = service.create_question(
            text=f"Test question {i + 1}?",
            context=f"Context for question {i + 1}",
            severity="medium",
            asked_by="test-agent",
            suggested_answers=["Option A", "Option B", "Option C"] if i == 0 else None,
        )
        questions.append(q)
        time.sleep(0.01)  # Ensure different created_at timestamps
    return questions


# ---------------------------------------------------------------------------
# NtfyQuestionAgent Tests (test_01_02)
# ---------------------------------------------------------------------------

class TestNtfyQuestionAgent:
    """Tests for NtfyQuestionAgent handle_reply routing and answer flow."""

    @patch("agenticcli.services.ntfy_question_agent.send_ntfy", return_value=True)
    def test_handle_next_sends_first_question(self, mock_send, tmp_path):
        """handle_reply('next') with pending questions sends first question."""
        questions = _create_test_questions(tmp_path, count=2)
        agent = NtfyQuestionAgent(tmp_path, "test-topic")

        result = agent.handle_reply("next")

        # Notification sent (not the return value)
        assert result is None
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert "Question 1 of 2" in call_kwargs["title"]

        # State updated
        state = load_state(tmp_path)
        assert state.current_question_id == questions[0].id
        assert state.sent_at is not None

    @patch("agenticcli.services.ntfy_question_agent.send_ntfy", return_value=True)
    def test_handle_next_no_pending(self, mock_send, tmp_path):
        """handle_reply('next') with empty queue returns summary."""
        # No questions created
        (tmp_path / "questions" / "pending").mkdir(parents=True, exist_ok=True)
        agent = NtfyQuestionAgent(tmp_path, "test-topic")

        result = agent.handle_reply("next")

        assert "No more questions" in result
        assert "0 answered" in result

    @patch("agenticcli.services.ntfy_question_agent.send_ntfy", return_value=True)
    def test_handle_letter_answer_maps_to_suggestion(self, mock_send, tmp_path):
        """handle_reply('A') maps letter to suggested answer when current question has suggestions."""
        questions = _create_test_questions(tmp_path, count=1)
        # Set current question in state
        save_state(tmp_path, NtfyQueueState(
            current_question_id=questions[0].id,
            sent_at=time.time(),
        ))

        agent = NtfyQuestionAgent(tmp_path, "test-topic")
        result = agent.handle_reply("A")

        assert result is not None
        assert "Option A" in result  # Mapped from letter A

        # State cleared
        state = load_state(tmp_path)
        assert state.current_question_id is None
        assert state.answered_count == 1

    @patch("agenticcli.services.ntfy_question_agent.send_ntfy", return_value=True)
    def test_handle_free_text_answer(self, mock_send, tmp_path):
        """handle_reply('Redis is better') saves free text answer."""
        questions = _create_test_questions(tmp_path, count=1)
        save_state(tmp_path, NtfyQueueState(
            current_question_id=questions[0].id,
            sent_at=time.time(),
        ))

        agent = NtfyQuestionAgent(tmp_path, "test-topic")
        result = agent.handle_reply("Redis is better")

        assert result is not None
        assert "Redis is better" in result

        state = load_state(tmp_path)
        assert state.current_question_id is None
        assert state.answered_count == 1

    @patch("agenticcli.services.ntfy_question_agent.send_ntfy", return_value=True)
    def test_handle_answer_without_current_question(self, mock_send, tmp_path):
        """handle_reply('A') without current question returns hint."""
        (tmp_path / "questions" / "pending").mkdir(parents=True, exist_ok=True)
        agent = NtfyQuestionAgent(tmp_path, "test-topic")

        result = agent.handle_reply("A")

        assert "No question is active" in result
        assert "next" in result.lower()

    @patch("agenticcli.services.ntfy_question_agent.send_ntfy", return_value=True)
    def test_handle_list_returns_count(self, mock_send, tmp_path):
        """handle_reply('list') returns count of pending questions."""
        _create_test_questions(tmp_path, count=3)
        agent = NtfyQuestionAgent(tmp_path, "test-topic")

        result = agent.handle_reply("list")

        assert "3 questions pending" in result

    @patch("agenticcli.services.ntfy_question_agent.send_ntfy", return_value=True)
    def test_handle_more_info_with_current(self, mock_send, tmp_path):
        """handle_reply('?') with current question returns details."""
        questions = _create_test_questions(tmp_path, count=1)
        save_state(tmp_path, NtfyQueueState(
            current_question_id=questions[0].id,
            sent_at=time.time(),
        ))

        agent = NtfyQuestionAgent(tmp_path, "test-topic")
        result = agent.handle_reply("?")

        assert "Test question 1?" in result
        assert "Context for question 1" in result

    @patch("agenticcli.services.ntfy_question_agent.send_ntfy", return_value=True)
    def test_handle_more_info_without_current(self, mock_send, tmp_path):
        """handle_reply('?') without current question returns hint."""
        (tmp_path / "questions" / "pending").mkdir(parents=True, exist_ok=True)
        agent = NtfyQuestionAgent(tmp_path, "test-topic")

        result = agent.handle_reply("?")

        assert "No question is active" in result

    @patch("agenticcli.services.ntfy_question_agent.send_ntfy", return_value=True)
    def test_sequential_flow_next_answer_next(self, mock_send, tmp_path):
        """Sequential flow: next -> answer -> next -> answer -> next (no more)."""
        questions = _create_test_questions(tmp_path, count=2)
        agent = NtfyQuestionAgent(tmp_path, "test-topic")

        # Step 1: next -> get first question
        result1 = agent.handle_reply("next")
        assert result1 is None  # Notification sent
        state = load_state(tmp_path)
        assert state.current_question_id == questions[0].id

        # Step 2: answer first question
        result2 = agent.handle_reply("My answer to Q1")
        assert "Answer saved" in result2
        state = load_state(tmp_path)
        assert state.current_question_id is None
        assert state.answered_count == 1

        # Step 3: next -> get second question
        result3 = agent.handle_reply("next")
        assert result3 is None
        state = load_state(tmp_path)
        assert state.current_question_id == questions[1].id

        # Step 4: answer second question
        result4 = agent.handle_reply("My answer to Q2")
        assert "Answer saved" in result4
        state = load_state(tmp_path)
        assert state.current_question_id is None
        assert state.answered_count == 2

        # Step 5: next -> no more questions
        result5 = agent.handle_reply("next")
        assert "No more questions" in result5
        assert "2 answered" in result5

    @patch("agenticcli.services.ntfy_question_agent.send_ntfy", return_value=True)
    def test_handle_already_answered_question(self, mock_send, tmp_path):
        """Answering an already-answered question returns graceful message."""
        questions = _create_test_questions(tmp_path, count=1)

        # Answer it directly via service first
        from agenticguidance.services.question import QuestionQueue
        service = QuestionQueue(tmp_path)
        service.answer_question(questions[0].id, "direct answer", answered_by="test")

        # Set state as if it was current
        save_state(tmp_path, NtfyQueueState(
            current_question_id=questions[0].id,
            sent_at=time.time(),
        ))

        agent = NtfyQuestionAgent(tmp_path, "test-topic")
        result = agent.handle_reply("Duplicate answer")

        assert "already answered" in result.lower()
