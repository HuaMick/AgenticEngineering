"""Tests for question service."""

import os
import random
import re
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-PLN-090")

from agenticguidance.models.question import (
    Answer,
    AnswerConfidence,
    Question,
    QuestionSeverity,
    answer_to_yaml,
    question_to_yaml,
)
from agenticguidance.services.question import QuestionQueue


class TestQuestionQueueInit:
    """Tests for QuestionQueue initialization."""

    def test_init_creates_directories(self, tmp_path):
        """Test initialization creates pending/ and answered/ directories."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        assert queue.questions_dir.exists()
        assert queue.pending_dir.exists()
        assert queue.answered_dir.exists()
        assert queue.pending_dir == plan_path / "questions" / "pending"
        assert queue.answered_dir == plan_path / "questions" / "answered"

    def test_init_with_existing_directories(self, tmp_path):
        """Test initialization with existing directories causes no errors."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        # Create directories first
        (plan_path / "questions" / "pending").mkdir(parents=True)
        (plan_path / "questions" / "answered").mkdir(parents=True)

        # Should not raise any errors
        queue = QuestionQueue(plan_path)

        assert queue.pending_dir.exists()
        assert queue.answered_dir.exists()


class TestCreateQuestion:
    """Tests for creating questions."""

    def test_create_question_success(self, tmp_path):
        """Test question created and persisted successfully."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        question = queue.create_question(
            text="What is the answer?",
            context="Testing context",
            severity=QuestionSeverity.HIGH.value,
            asked_by="test-agent",
        )

        assert question.text == "What is the answer?"
        assert question.context == "Testing context"
        assert question.severity == QuestionSeverity.HIGH.value
        assert question.asked_by == "test-agent"
        assert question.status == "pending"
        assert question.id.startswith("Q-")
        assert isinstance(question.created_at, float)

    def test_create_question_file_exists(self, tmp_path):
        """Test question YAML file written correctly."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        question = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.MEDIUM.value,
        )

        question_file = queue.pending_dir / f"{question.id}.yml"
        assert question_file.exists()

        content = question_file.read_text()
        assert "Test question" in content
        assert "Context" in content
        assert "medium" in content

    def test_create_question_unique_ids(self, tmp_path):
        """Test multiple questions have unique IDs."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        q1 = queue.create_question(
            text="Question 1",
            context="Context 1",
            severity=QuestionSeverity.LOW.value,
        )
        q2 = queue.create_question(
            text="Question 2",
            context="Context 2",
            severity=QuestionSeverity.LOW.value,
        )

        assert q1.id != q2.id
        assert q1.id.startswith("Q-")
        assert q2.id.startswith("Q-")

    def test_create_question_invalid_severity(self, tmp_path):
        """Test ValueError raised for invalid severity."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        with pytest.raises(ValueError) as exc_info:
            queue.create_question(
                text="Question",
                context="Context",
                severity="invalid",
            )

        assert "Invalid severity" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)

    def test_create_question_default_asked_by(self, tmp_path):
        """Test default asked_by is 'agent'."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        question = queue.create_question(
            text="Question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        assert question.asked_by == "agent"

    def test_create_question_timeout_on_lock_failure(self, tmp_path):
        """Test TimeoutError raised when lock cannot be acquired."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Mock FileLock.acquire to return False (lock failed)
        with patch("agenticguidance.services.question.FileLock.acquire", return_value=False):
            with pytest.raises(TimeoutError) as exc_info:
                queue.create_question(
                    text="Question",
                    context="Context",
                    severity=QuestionSeverity.LOW.value,
                )

            assert "Could not acquire lock" in str(exc_info.value)


class TestListPendingQuestions:
    """Tests for listing pending questions."""

    def test_list_empty(self, tmp_path):
        """Test returns empty list when no questions."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        questions = queue.list_pending_questions()

        assert questions == []

    def test_list_multiple(self, tmp_path):
        """Test returns all pending questions."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        q1 = queue.create_question(
            text="Question 1",
            context="Context 1",
            severity=QuestionSeverity.HIGH.value,
        )
        q2 = queue.create_question(
            text="Question 2",
            context="Context 2",
            severity=QuestionSeverity.MEDIUM.value,
        )

        questions = queue.list_pending_questions()

        assert len(questions) == 2
        question_ids = [q.id for q in questions]
        assert q1.id in question_ids
        assert q2.id in question_ids

    def test_list_sorted(self, tmp_path):
        """Test questions sorted by created_at (oldest first)."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Mock time.time() to create questions with different timestamps
        with patch("agenticguidance.services.question.time.time") as mock_time:
            mock_time.return_value = 1000.0
            q1 = queue.create_question(
                text="Question 1",
                context="Context 1",
                severity=QuestionSeverity.LOW.value,
            )

            mock_time.return_value = 2000.0
            q2 = queue.create_question(
                text="Question 2",
                context="Context 2",
                severity=QuestionSeverity.LOW.value,
            )

        questions = queue.list_pending_questions()

        assert len(questions) == 2
        assert questions[0].id == q1.id
        assert questions[1].id == q2.id
        assert questions[0].created_at < questions[1].created_at

    def test_list_severity_filter(self, tmp_path):
        """Test filter by severity works."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        q_high = queue.create_question(
            text="High priority",
            context="Context",
            severity=QuestionSeverity.HIGH.value,
        )
        q_low = queue.create_question(
            text="Low priority",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        high_questions = queue.list_pending_questions(
            severity_filter=QuestionSeverity.HIGH.value
        )

        assert len(high_questions) == 1
        assert high_questions[0].id == q_high.id
        assert high_questions[0].severity == QuestionSeverity.HIGH.value

    def test_list_severity_filter_invalid(self, tmp_path):
        """Test ValueError raised for invalid severity filter."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        with pytest.raises(ValueError) as exc_info:
            queue.list_pending_questions(severity_filter="invalid")

        assert "Invalid severity filter" in str(exc_info.value)

    def test_list_skips_corrupted(self, tmp_path):
        """Test corrupted files skipped gracefully."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Create a valid question
        q1 = queue.create_question(
            text="Valid question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        # Create a corrupted file
        corrupted_file = queue.pending_dir / "Q-20260203-120000-abcd.yml"
        corrupted_file.write_text("invalid: yaml: content: [unclosed")

        questions = queue.list_pending_questions()

        # Should return only the valid question
        assert len(questions) == 1
        assert questions[0].id == q1.id

    def test_list_with_no_pending_directory(self, tmp_path):
        """Test returns empty list when pending directory doesn't exist."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Remove the pending directory
        import shutil
        shutil.rmtree(queue.pending_dir)

        questions = queue.list_pending_questions()

        assert questions == []


class TestGetQuestion:
    """Tests for getting a specific question."""

    def test_get_from_pending(self, tmp_path):
        """Test finds question in pending/ directory."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        retrieved = queue.get_question(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.text == "Test question"
        assert retrieved.status == "pending"

    def test_get_from_answered(self, tmp_path):
        """Test finds question in answered/ directory."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        # Answer the question
        queue.answer_question(created.id, "Answer text")

        # Should still be able to get it from answered/
        retrieved = queue.get_question(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.status == "answered"

    def test_get_not_found(self, tmp_path):
        """Test returns None when question not found."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        retrieved = queue.get_question("Q-20260203-120000-abcd")

        assert retrieved is None

    def test_get_corrupted_file(self, tmp_path):
        """Test returns None for corrupted files."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Create a corrupted file
        question_id = "Q-20260203-120000-abcd"
        corrupted_file = queue.pending_dir / f"{question_id}.yml"
        corrupted_file.write_text("invalid: yaml: [unclosed")

        retrieved = queue.get_question(question_id)

        assert retrieved is None

    def test_get_invalid_id_format(self, tmp_path):
        """Test ValueError raised for invalid question ID format."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        with pytest.raises(ValueError) as exc_info:
            queue.get_question("invalid-id")

        assert "Invalid question ID format" in str(exc_info.value)


class TestAnswerQuestion:
    """Tests for answering questions."""

    def test_answer_question_success(self, tmp_path):
        """Test question answered and moved successfully."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        question, answer = queue.answer_question(
            created.id,
            "This is the answer",
            answered_by="test-user",
            confidence=AnswerConfidence.HIGH.value,
        )

        assert question.status == "answered"
        assert question.answer == "This is the answer"
        assert question.answered_by == "test-user"
        assert answer.answer_text == "This is the answer"
        assert answer.confidence == AnswerConfidence.HIGH.value

    def test_answer_creates_answer_file(self, tmp_path):
        """Test answer YAML file written to answered/ directory."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        queue.answer_question(created.id, "Answer text")

        answer_file = queue.answered_dir / f"{created.id}.yml"
        assert answer_file.exists()

        content = answer_file.read_text()
        assert "Answer text" in content
        assert created.id in content

    def test_answer_moves_question(self, tmp_path):
        """Test question moved to answered/ directory."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        queue.answer_question(created.id, "Answer text")

        question_file = queue.answered_dir / f"{created.id}_question.yml"
        assert question_file.exists()

        content = question_file.read_text()
        assert "Test question" in content
        assert "answered" in content

    def test_answer_deletes_pending(self, tmp_path):
        """Test pending file removed after answering."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        pending_file = queue.pending_dir / f"{created.id}.yml"
        assert pending_file.exists()

        queue.answer_question(created.id, "Answer text")

        assert not pending_file.exists()

    def test_answer_not_found(self, tmp_path):
        """Test FileNotFoundError raised when question not found."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        with pytest.raises(FileNotFoundError) as exc_info:
            queue.answer_question("Q-20260203-120000-abcd", "Answer")

        assert "not found in pending directory" in str(exc_info.value)

    def test_answer_invalid_confidence(self, tmp_path):
        """Test ValueError raised for invalid confidence."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        with pytest.raises(ValueError) as exc_info:
            queue.answer_question(
                created.id,
                "Answer",
                confidence="invalid",
            )

        assert "Invalid confidence" in str(exc_info.value)

    def test_answer_returns_tuple(self, tmp_path):
        """Test returns (Question, Answer) tuple."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        result = queue.answer_question(created.id, "Answer")

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], Question)
        assert isinstance(result[1], Answer)

    def test_answer_default_answered_by(self, tmp_path):
        """Test default answered_by is 'human'."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        question, answer = queue.answer_question(created.id, "Answer")

        assert answer.answered_by == "human"
        assert question.answered_by == "human"

    def test_answer_invalid_id_format(self, tmp_path):
        """Test ValueError raised for invalid question ID format."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        with pytest.raises(ValueError) as exc_info:
            queue.answer_question("invalid-id", "Answer")

        assert "Invalid question ID format" in str(exc_info.value)

    def test_answer_confidence_optional(self, tmp_path):
        """Test confidence is optional (can be None)."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        question, answer = queue.answer_question(created.id, "Answer")

        assert answer.confidence is None


class TestAtomicOperations:
    """Tests for atomic file operations."""

    def test_atomic_write(self, tmp_path):
        """Test temp file pattern used for atomic writes."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Mock write_text to track temp file usage
        original_write = Path.write_text
        temp_files_used = []

        def mock_write_text(self, content, **kwargs):
            if ".tmp" in str(self):
                temp_files_used.append(str(self))
            return original_write(self, content, **kwargs)

        with patch.object(Path, "write_text", mock_write_text):
            queue.create_question(
                text="Test",
                context="Context",
                severity=QuestionSeverity.LOW.value,
            )

        # Verify temp file was used
        assert len(temp_files_used) > 0
        assert any(".tmp" in f for f in temp_files_used)

    def test_concurrent_create(self, tmp_path):
        """Test multiple threads don't collide when creating questions."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        created_questions = []
        errors = []

        def create_question(index):
            try:
                q = queue.create_question(
                    text=f"Question {index}",
                    context=f"Context {index}",
                    severity=QuestionSeverity.LOW.value,
                )
                created_questions.append(q)
            except Exception as e:
                errors.append(e)

        # Create questions concurrently
        threads = []
        for i in range(5):
            t = threading.Thread(target=create_question, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All questions should be created successfully
        assert len(errors) == 0
        assert len(created_questions) == 5

        # All IDs should be unique
        ids = [q.id for q in created_questions]
        assert len(ids) == len(set(ids))

    def test_concurrent_answer(self, tmp_path):
        """Test multiple threads don't corrupt when answering questions."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Create multiple questions
        questions = []
        for i in range(3):
            q = queue.create_question(
                text=f"Question {i}",
                context=f"Context {i}",
                severity=QuestionSeverity.LOW.value,
            )
            questions.append(q)

        answered_results = []
        errors = []

        def answer_question(question):
            try:
                result = queue.answer_question(
                    question.id,
                    f"Answer to {question.text}",
                )
                answered_results.append(result)
            except Exception as e:
                errors.append(e)

        # Answer questions concurrently
        threads = []
        for q in questions:
            t = threading.Thread(target=answer_question, args=(q,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All questions should be answered successfully
        assert len(errors) == 0
        assert len(answered_results) == 3

        # Verify all questions were moved to answered/
        pending_files = list(queue.pending_dir.glob("*.yml"))
        assert len(pending_files) == 0


class TestGenerateQuestionId:
    """Tests for question ID generation."""

    def test_id_format(self, tmp_path):
        """Test generated ID follows expected format."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        question_id = queue._generate_question_id()

        # Format: Q-YYYYMMDD-HHMMSS-RAND
        pattern = r'^Q-\d{8}-\d{6}-[0-9a-f]{4}$'
        assert re.match(pattern, question_id)

    def test_id_timestamp_component(self, tmp_path):
        """Test ID contains correct timestamp component."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        with patch("agenticguidance.services.question.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.strftime.return_value = "20260203-143022"
            mock_datetime.now.return_value = mock_now

            question_id = queue._generate_question_id()

            assert "20260203-143022" in question_id

    def test_id_random_component(self, tmp_path):
        """Test ID contains random hex component."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Generate multiple IDs with same timestamp
        with patch("agenticguidance.services.question.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.strftime.return_value = "20260203-143022"
            mock_datetime.now.return_value = mock_now

            id1 = queue._generate_question_id()
            id2 = queue._generate_question_id()

            # IDs should differ due to random component
            # (very low probability of collision)
            assert id1 != id2


class TestGetQuestionPath:
    """Tests for getting question file paths."""

    def test_pending_path(self, tmp_path):
        """Test returns correct path for pending status."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        path = queue._get_question_path("Q-20260203-143022-abcd", "pending")

        assert path == queue.pending_dir / "Q-20260203-143022-abcd.yml"

    def test_answered_path(self, tmp_path):
        """Test returns correct path for answered status."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        path = queue._get_question_path("Q-20260203-143022-abcd", "answered")

        assert path == queue.answered_dir / "Q-20260203-143022-abcd.yml"

    def test_invalid_status(self, tmp_path):
        """Test ValueError raised for invalid status."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        with pytest.raises(ValueError) as exc_info:
            queue._get_question_path("Q-20260203-143022-abcd", "invalid")

        assert "Invalid status" in str(exc_info.value)


class TestErrorHandling:
    """Tests for error handling and recovery in question service."""

    def test_atomic_write_failure_cleanup(self, tmp_path):
        """Test _atomic_write cleans up temp file on failure."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)
        target_path = queue.pending_dir / "test.yml"
        temp_path = target_path.with_suffix('.tmp')

        # Mock os.replace to raise OSError during atomic rename
        with patch("agenticguidance.services.question.os.replace", side_effect=OSError("Disk full")):
            with pytest.raises(RuntimeError) as exc_info:
                queue._atomic_write(target_path, "test content")

            assert "Failed to write file atomically" in str(exc_info.value)
            assert "Disk full" in str(exc_info.value)

        # Verify temp file was cleaned up
        assert not temp_path.exists()

    def test_create_question_write_failure_cleanup(self, tmp_path):
        """Test create_question cleans up temp file on write failure."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Mock os.replace to raise OSError during file write
        with patch("agenticguidance.services.question.os.replace", side_effect=OSError("Permission denied")):
            with pytest.raises(RuntimeError) as exc_info:
                queue.create_question(
                    text="Test question",
                    context="Context",
                    severity=QuestionSeverity.LOW.value,
                )

            assert "Failed to write question file" in str(exc_info.value)
            assert "Permission denied" in str(exc_info.value)

        # Verify no temp files left behind
        temp_files = list(queue.pending_dir.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_answer_question_corrupted_file(self, tmp_path):
        """Test answer_question handles corrupted question file gracefully."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Create a corrupted question file
        question_id = "Q-20260203-120000-abcd"
        corrupted_file = queue.pending_dir / f"{question_id}.yml"
        corrupted_file.write_text("invalid: yaml: content: [unclosed")

        # Attempt to answer should raise RuntimeError with helpful message
        with pytest.raises(RuntimeError) as exc_info:
            queue.answer_question(question_id, "Answer")

        assert "Failed to read question file" in str(exc_info.value)
        assert "may be corrupted" in str(exc_info.value)

    def test_answer_question_answered_lock_timeout(self, tmp_path):
        """Test answer_question raises TimeoutError when answered lock fails."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Create a valid question first
        question = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        # Mock FileLock.acquire to return False for answered directory lock
        with patch("agenticguidance.services.question.FileLock.acquire") as mock_acquire:
            # First call (answered lock) returns False, simulating timeout
            mock_acquire.return_value = False

            with pytest.raises(TimeoutError) as exc_info:
                queue.answer_question(question.id, "Answer")

            assert "Could not acquire lock for answered directory" in str(exc_info.value)

    def test_answer_question_pending_lock_timeout(self, tmp_path):
        """Test answer_question raises TimeoutError when pending lock fails."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Create a valid question first
        question = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        # Mock FileLock.acquire to return True for answered lock, False for pending lock
        with patch("agenticguidance.services.question.FileLock.acquire") as mock_acquire:
            # First call (answered lock) succeeds, second call (pending lock) fails
            mock_acquire.side_effect = [True, False]

            with pytest.raises(TimeoutError) as exc_info:
                queue.answer_question(question.id, "Answer")

            assert "Could not acquire lock for pending directory" in str(exc_info.value)

    def test_answer_question_write_failure_cleanup(self, tmp_path):
        """Test answer_question cleans up temp files on write failure."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Create a valid question
        question = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        # Mock os.replace to fail on first call (answer write), succeed on subsequent calls
        original_replace = os.replace
        call_count = [0]

        def mock_replace(src, dst):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call fails (answer file write)
                raise OSError("Disk full")
            else:
                # Subsequent calls succeed
                return original_replace(src, dst)

        with patch("agenticguidance.services.question.os.replace", side_effect=mock_replace):
            with pytest.raises(RuntimeError) as exc_info:
                queue.answer_question(question.id, "Answer")

            assert "Failed to answer question" in str(exc_info.value)

        # Verify no temp files left behind in answered directory
        temp_files = list(queue.answered_dir.glob("*.tmp"))
        assert len(temp_files) == 0

        # Verify original question still exists in pending
        pending_file = queue.pending_dir / f"{question.id}.yml"
        assert pending_file.exists()
