"""Integration tests for complete question/answer workflow.

This module tests end-to-end workflows for the question queue system,
verifying that the full create -> list -> answer cycle works correctly
in real-world scenarios including persistence, multiple questions,
severity filtering, and error recovery.
"""

import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.story("US-PLN-001")

from agenticguidance.models.question import (
    AnswerConfidence,
    Question,
    QuestionSeverity,
)
from agenticguidance.services.question import QuestionQueue


class TestCompleteWorkflowSingleQuestion:
    """Tests for complete workflow with a single question."""

    def test_complete_workflow_single_question(self, tmp_path):
        """Test complete create -> list -> get -> answer workflow.

        This test verifies the full user journey through the question/answer
        system with a single question:
        1. Create question
        2. List pending (verify present)
        3. Get question by ID
        4. Answer question
        5. List pending (verify absent)
        6. Verify answer file exists
        """
        plan_path = tmp_path / "plan"
        plan_path.mkdir()
        queue = QuestionQueue(plan_path)

        # Step 1: Create question
        question = queue.create_question(
            text="What is the deployment strategy?",
            context="Planning production deployment",
            severity=QuestionSeverity.HIGH.value,
            asked_by="deploy-agent",
        )

        assert question.id is not None
        assert question.status == "pending"

        # Step 2: List pending (verify present)
        pending_questions = queue.list_pending_questions()
        assert len(pending_questions) == 1
        assert pending_questions[0].id == question.id
        assert pending_questions[0].text == "What is the deployment strategy?"

        # Step 3: Get question by ID
        retrieved = queue.get_question(question.id)
        assert retrieved is not None
        assert retrieved.id == question.id
        assert retrieved.text == question.text
        assert retrieved.severity == QuestionSeverity.HIGH.value
        assert retrieved.status == "pending"

        # Step 4: Answer question
        answered_question, answer = queue.answer_question(
            question.id,
            "Use blue-green deployment with health checks",
            answered_by="human",
            confidence=AnswerConfidence.HIGH.value,
        )

        assert answered_question.status == "answered"
        assert answered_question.answer == "Use blue-green deployment with health checks"
        assert answer.answer_text == "Use blue-green deployment with health checks"

        # Step 5: List pending (verify absent)
        pending_after_answer = queue.list_pending_questions()
        assert len(pending_after_answer) == 0

        # Step 6: Verify answer file exists
        answer_file = queue.answered_dir / f"{question.id}.yml"
        assert answer_file.exists()

        answer_content = answer_file.read_text()
        assert "Use blue-green deployment with health checks" in answer_content
        assert question.id in answer_content

        # Also verify question moved to answered directory
        question_file = queue.answered_dir / f"{question.id}_question.yml"
        assert question_file.exists()


class TestCompleteWorkflowMultipleQuestions:
    """Tests for complete workflow with multiple questions."""

    def test_complete_workflow_multiple_questions(self, tmp_path):
        """Test workflow with multiple questions of different severities.

        This test verifies:
        1. Create 3 questions (different severities)
        2. List pending (verify all 3)
        3. Answer first question
        4. List pending (verify 2 remaining)
        5. Filter by severity
        6. Answer remaining questions
        """
        plan_path = tmp_path / "plan"
        plan_path.mkdir()
        queue = QuestionQueue(plan_path)

        # Step 1: Create 3 questions with different severities
        q1 = queue.create_question(
            text="Database schema decision?",
            context="Need to finalize schema",
            severity=QuestionSeverity.BLOCKING.value,
            asked_by="db-agent",
        )

        q2 = queue.create_question(
            text="Logging format preference?",
            context="Configuring logging",
            severity=QuestionSeverity.MEDIUM.value,
            asked_by="config-agent",
        )

        q3 = queue.create_question(
            text="Documentation style?",
            context="Setting up docs",
            severity=QuestionSeverity.LOW.value,
            asked_by="docs-agent",
        )

        # Step 2: List pending (verify all 3)
        all_pending = queue.list_pending_questions()
        assert len(all_pending) == 3

        pending_ids = {q.id for q in all_pending}
        assert q1.id in pending_ids
        assert q2.id in pending_ids
        assert q3.id in pending_ids

        # Step 3: Answer first question
        queue.answer_question(
            q1.id,
            "Use PostgreSQL with normalized schema",
            answered_by="human",
        )

        # Step 4: List pending (verify 2 remaining)
        remaining = queue.list_pending_questions()
        assert len(remaining) == 2
        remaining_ids = {q.id for q in remaining}
        assert q1.id not in remaining_ids
        assert q2.id in remaining_ids
        assert q3.id in remaining_ids

        # Step 5: Filter by severity
        medium_questions = queue.list_pending_questions(
            severity_filter=QuestionSeverity.MEDIUM.value
        )
        assert len(medium_questions) == 1
        assert medium_questions[0].id == q2.id

        low_questions = queue.list_pending_questions(
            severity_filter=QuestionSeverity.LOW.value
        )
        assert len(low_questions) == 1
        assert low_questions[0].id == q3.id

        # Step 6: Answer remaining questions
        queue.answer_question(
            q2.id,
            "Use structured JSON logging",
            answered_by="human",
        )

        queue.answer_question(
            q3.id,
            "Use Google style docstrings",
            answered_by="human",
        )

        # Verify all questions answered
        final_pending = queue.list_pending_questions()
        assert len(final_pending) == 0

        # Verify all answer files exist
        for question_id in [q1.id, q2.id, q3.id]:
            answer_file = queue.answered_dir / f"{question_id}.yml"
            assert answer_file.exists()


class TestWorkflowWithBlockingQuestion:
    """Tests for workflow with blocking questions."""

    def test_workflow_with_blocking_question(self, tmp_path):
        """Test workflow prioritizes blocking questions.

        This test verifies:
        1. Create blocking question
        2. List with severity filter
        3. Verify blocking question prioritized
        4. Answer and verify workflow completes
        """
        plan_path = tmp_path / "plan"
        plan_path.mkdir()
        queue = QuestionQueue(plan_path)

        # Step 1: Create multiple questions including blocking
        q_low = queue.create_question(
            text="Low priority question",
            context="Non-critical info",
            severity=QuestionSeverity.LOW.value,
        )

        # Sleep briefly to ensure timestamp difference
        time.sleep(0.01)

        q_blocking = queue.create_question(
            text="Critical blocker: API key missing",
            context="Cannot proceed without API key",
            severity=QuestionSeverity.BLOCKING.value,
        )

        time.sleep(0.01)

        q_medium = queue.create_question(
            text="Medium priority question",
            context="Should address soon",
            severity=QuestionSeverity.MEDIUM.value,
        )

        # Step 2: List with severity filter to find blockers
        blocking_questions = queue.list_pending_questions(
            severity_filter=QuestionSeverity.BLOCKING.value
        )

        # Step 3: Verify blocking question identified
        assert len(blocking_questions) == 1
        assert blocking_questions[0].id == q_blocking.id
        assert blocking_questions[0].severity == QuestionSeverity.BLOCKING.value
        assert "Critical blocker" in blocking_questions[0].text

        # Verify all questions still present in unfiltered list
        all_questions = queue.list_pending_questions()
        assert len(all_questions) == 3

        # Step 4: Answer blocking question first
        answered, answer = queue.answer_question(
            q_blocking.id,
            "API key: sk-test-1234567890",
            answered_by="human",
            confidence=AnswerConfidence.HIGH.value,
        )

        assert answered.status == "answered"
        assert answer.confidence == AnswerConfidence.HIGH.value

        # Verify blocking question no longer in pending
        remaining = queue.list_pending_questions()
        assert len(remaining) == 2
        remaining_ids = {q.id for q in remaining}
        assert q_blocking.id not in remaining_ids

        # Verify no more blockers
        remaining_blockers = queue.list_pending_questions(
            severity_filter=QuestionSeverity.BLOCKING.value
        )
        assert len(remaining_blockers) == 0


class TestPersistenceAcrossInstances:
    """Tests for persistence across QuestionQueue instances."""

    def test_persistence_across_instances(self, tmp_path):
        """Test questions persist across QuestionQueue instances.

        This test verifies:
        1. Create question with queue1
        2. Create new QuestionQueue instance (queue2)
        3. List with queue2 (verify question visible)
        4. Answer with queue2
        5. Create queue3 and verify answer persisted
        """
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        # Step 1: Create question with first instance
        queue1 = QuestionQueue(plan_path)
        question = queue1.create_question(
            text="What is the cache strategy?",
            context="Designing cache layer",
            severity=QuestionSeverity.MEDIUM.value,
            asked_by="cache-agent",
        )

        question_id = question.id
        assert question_id is not None

        # Verify file created
        pending_file = queue1.pending_dir / f"{question_id}.yml"
        assert pending_file.exists()

        # Step 2 & 3: Create new instance and verify question visible
        queue2 = QuestionQueue(plan_path)
        questions = queue2.list_pending_questions()

        assert len(questions) == 1
        assert questions[0].id == question_id
        assert questions[0].text == "What is the cache strategy?"
        assert questions[0].severity == QuestionSeverity.MEDIUM.value

        # Also verify get_question works
        retrieved = queue2.get_question(question_id)
        assert retrieved is not None
        assert retrieved.id == question_id

        # Step 4: Answer with second instance
        answered, answer = queue2.answer_question(
            question_id,
            "Use Redis with LRU eviction",
            answered_by="human",
        )

        assert answered.status == "answered"

        # Verify pending file deleted
        assert not pending_file.exists()

        # Step 5: Create third instance and verify answer persisted
        queue3 = QuestionQueue(plan_path)

        # Verify no pending questions
        pending = queue3.list_pending_questions()
        assert len(pending) == 0

        # Verify answer file exists
        answer_file = queue3.answered_dir / f"{question_id}.yml"
        assert answer_file.exists()

        # Verify question moved to answered
        question_file = queue3.answered_dir / f"{question_id}_question.yml"
        assert question_file.exists()

        # Verify can retrieve answered question
        answered_question = queue3.get_question(question_id)
        assert answered_question is not None
        assert answered_question.status == "answered"
        assert answered_question.answer == "Use Redis with LRU eviction"


class TestErrorRecovery:
    """Tests for error recovery in workflow."""

    def test_error_recovery(self, tmp_path):
        """Test workflow handles corrupted files gracefully.

        This test verifies:
        1. Create question
        2. Simulate corrupted pending file
        3. List pending (corrupted file skipped)
        4. Create new question (still works)
        """
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        # Step 1: Create valid question
        queue = QuestionQueue(plan_path)
        valid_question = queue.create_question(
            text="Valid question text",
            context="Valid context",
            severity=QuestionSeverity.MEDIUM.value,
        )

        # Step 2: Simulate corrupted pending file
        corrupted_id = "Q-20260203-120000-dead"
        corrupted_file = queue.pending_dir / f"{corrupted_id}.yml"
        corrupted_file.write_text("invalid: yaml: [[[unclosed brackets")

        # Also create another valid question for more realistic scenario
        valid_question2 = queue.create_question(
            text="Another valid question",
            context="Another context",
            severity=QuestionSeverity.LOW.value,
        )

        # Step 3: List pending (corrupted file skipped)
        pending = queue.list_pending_questions()

        # Should return only the two valid questions
        assert len(pending) == 2
        pending_ids = {q.id for q in pending}
        assert valid_question.id in pending_ids
        assert valid_question2.id in pending_ids
        assert corrupted_id not in pending_ids

        # Verify get_question returns None for corrupted
        corrupted_question = queue.get_question(corrupted_id)
        assert corrupted_question is None

        # Step 4: Create new question (still works)
        new_question = queue.create_question(
            text="Created after corruption",
            context="System resilient",
            severity=QuestionSeverity.HIGH.value,
        )

        assert new_question.id is not None
        assert new_question.status == "pending"

        # Verify new question in list
        updated_pending = queue.list_pending_questions()
        assert len(updated_pending) == 3

        # Verify can answer valid questions despite corruption
        queue.answer_question(
            valid_question.id,
            "Answer to valid question",
        )

        # Should now have 2 pending (skipping corrupted)
        final_pending = queue.list_pending_questions()
        assert len(final_pending) == 2

    def test_error_recovery_with_missing_pending_directory(self, tmp_path):
        """Test handles missing pending directory gracefully."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        # Create queue and question
        queue = QuestionQueue(plan_path)
        question = queue.create_question(
            text="Test question",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        # Remove pending directory
        import shutil
        shutil.rmtree(queue.pending_dir)

        # Should return empty list, not crash
        pending = queue.list_pending_questions()
        assert len(pending) == 0

        # Recreate directories and verify system recovers
        queue2 = QuestionQueue(plan_path)
        assert queue2.pending_dir.exists()

        # Can create new questions
        new_question = queue2.create_question(
            text="After recovery",
            context="Context",
            severity=QuestionSeverity.MEDIUM.value,
        )
        assert new_question.id is not None

    def test_error_recovery_with_corrupted_answer_file(self, tmp_path):
        """Test workflow continues when answer files are corrupted."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        queue = QuestionQueue(plan_path)

        # Create and answer a question
        question = queue.create_question(
            text="Question 1",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )
        queue.answer_question(question.id, "Answer 1")

        # Corrupt the answered question file
        question_file = queue.answered_dir / f"{question.id}_question.yml"
        question_file.write_text("corrupted: [[[invalid yaml")

        # Create new instance to test recovery
        queue2 = QuestionQueue(plan_path)

        # get_question should handle corruption gracefully
        retrieved = queue2.get_question(question.id)
        assert retrieved is None

        # System should still work for new questions
        new_question = queue2.create_question(
            text="New question after corruption",
            context="Context",
            severity=QuestionSeverity.MEDIUM.value,
        )

        pending = queue2.list_pending_questions()
        assert len(pending) == 1
        assert pending[0].id == new_question.id


class TestWorkflowSorting:
    """Tests for question sorting in workflow."""

    def test_workflow_chronological_ordering(self, tmp_path):
        """Test questions are processed in chronological order.

        This verifies that oldest questions appear first in listings,
        which is important for fair FIFO processing.
        """
        plan_path = tmp_path / "plan"
        plan_path.mkdir()
        queue = QuestionQueue(plan_path)

        # Create questions with slight delays to ensure timestamp differences
        q1 = queue.create_question(
            text="First question",
            context="Context 1",
            severity=QuestionSeverity.MEDIUM.value,
        )

        time.sleep(0.01)

        q2 = queue.create_question(
            text="Second question",
            context="Context 2",
            severity=QuestionSeverity.MEDIUM.value,
        )

        time.sleep(0.01)

        q3 = queue.create_question(
            text="Third question",
            context="Context 3",
            severity=QuestionSeverity.MEDIUM.value,
        )

        # List pending questions
        pending = queue.list_pending_questions()

        # Verify chronological order (oldest first)
        assert len(pending) == 3
        assert pending[0].id == q1.id
        assert pending[1].id == q2.id
        assert pending[2].id == q3.id

        # Verify timestamps are in ascending order
        assert pending[0].created_at < pending[1].created_at
        assert pending[1].created_at < pending[2].created_at


class TestWorkflowEdgeCases:
    """Tests for edge cases in workflow."""

    def test_workflow_with_empty_queue(self, tmp_path):
        """Test workflow handles empty queue gracefully."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()
        queue = QuestionQueue(plan_path)

        # List empty queue
        pending = queue.list_pending_questions()
        assert len(pending) == 0
        assert isinstance(pending, list)

        # Create and immediately answer question
        question = queue.create_question(
            text="Immediate answer",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        queue.answer_question(question.id, "Quick answer")

        # Queue should be empty again
        pending = queue.list_pending_questions()
        assert len(pending) == 0

    def test_workflow_with_all_severities(self, tmp_path):
        """Test workflow with questions of all severity levels."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()
        queue = QuestionQueue(plan_path)

        # Create one question for each severity level
        questions = {}
        for severity in QuestionSeverity:
            q = queue.create_question(
                text=f"Question with {severity.value} severity",
                context=f"Context for {severity.value}",
                severity=severity.value,
            )
            questions[severity.value] = q

        # Verify all created
        pending = queue.list_pending_questions()
        assert len(pending) == 4

        # Filter by each severity
        for severity in QuestionSeverity:
            filtered = queue.list_pending_questions(
                severity_filter=severity.value
            )
            assert len(filtered) == 1
            assert filtered[0].severity == severity.value
            assert filtered[0].id == questions[severity.value].id

    def test_workflow_answer_with_all_confidence_levels(self, tmp_path):
        """Test answering with all confidence levels."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()
        queue = QuestionQueue(plan_path)

        # Create questions and answer with different confidence levels
        for confidence in AnswerConfidence:
            question = queue.create_question(
                text=f"Question for {confidence.value} confidence",
                context="Context",
                severity=QuestionSeverity.MEDIUM.value,
            )

            answered_q, answer = queue.answer_question(
                question.id,
                f"Answer with {confidence.value} confidence",
                confidence=confidence.value,
            )

            assert answer.confidence == confidence.value

        # Also test with None confidence
        question = queue.create_question(
            text="Question with no confidence",
            context="Context",
            severity=QuestionSeverity.LOW.value,
        )

        answered_q, answer = queue.answer_question(
            question.id,
            "Answer without confidence",
        )

        assert answer.confidence is None

        # Verify all questions answered
        pending = queue.list_pending_questions()
        assert len(pending) == 0
