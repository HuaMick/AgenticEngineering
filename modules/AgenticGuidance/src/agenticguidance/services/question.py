"""Question Queue Service - manage question/answer workflow.

This service provides a queue-based system for managing questions that arise during
agent workflows. Questions are stored as YAML files in a plan's questions/ directory
with separate pending/ and answered/ subdirectories for status tracking.

The QuestionQueue service enables:
- Creating and storing questions with unique IDs
- Moving questions between pending and answered states
- Tracking question lifecycle through filesystem organization
- Supporting multiple consumers (CLI, voice interface, etc.)

Directory Structure:
    plan_folder/
        questions/
            pending/        # Unanswered questions
                Q-20260203-143022-a1b2.yml
            answered/       # Answered questions
                Q-20260203-150945-c3d4.yml

Question IDs follow the format: Q-YYYYMMDD-HHMMSS-RAND
where RAND is a 4-character random hex string for uniqueness.

This service is independent of CLI and voice modules, providing
a foundation layer for question/answer workflows.
"""

import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from agenticguidance.models.question import (
    Answer,
    AnswerConfidence,
    Question,
    QuestionSeverity,
    answer_to_yaml,
    question_to_yaml,
    yaml_to_question,
)
from agenticguidance.services.state import FileLock

logger = logging.getLogger(__name__)


class QuestionQueue:
    """Queue service for managing questions within a plan.

    Provides question lifecycle management including creation, storage,
    and status transitions. Each queue is associated with a specific plan
    folder and maintains questions in a structured directory hierarchy.
    """

    def __init__(self, plan_path: Path):
        """Initialize queue for a specific plan.

        Creates the necessary directory structure for storing pending
        and answered questions. Directories are created if they don't exist.

        Args:
            plan_path: Path to plan folder (e.g., docs/plans/live/260203QF_feature).
                      Must be an existing directory or parent of where questions will be stored.
        """
        self.plan_path = plan_path
        self.questions_dir = plan_path / "questions"
        self.pending_dir = self.questions_dir / "pending"
        self.answered_dir = self.questions_dir / "answered"

        # Create directories if they don't exist
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.answered_dir.mkdir(parents=True, exist_ok=True)

    def _generate_question_id(self) -> str:
        """Generate unique question ID with timestamp and random component.

        Creates IDs in the format: Q-YYYYMMDD-HHMMSS-RAND
        where RAND is a 4-character random hexadecimal string.

        The timestamp provides chronological ordering while the random
        component ensures uniqueness if multiple questions are created
        in the same second.

        Returns:
            Unique question ID string.

        Example:
            >>> queue._generate_question_id()
            'Q-20260203-143022-a1b2'
        """
        # Get current time for timestamp portion
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d-%H%M%S")

        # Generate random 4-character hex string for uniqueness
        random_suffix = "".join(random.choices("0123456789abcdef", k=4))

        return f"Q-{timestamp}-{random_suffix}"

    def _get_question_path(self, question_id: str, status: str) -> Path:
        """Get file path for a question based on its ID and status.

        Determines the appropriate directory (pending or answered) and
        constructs the full path to the question YAML file.

        Args:
            question_id: The question's unique identifier.
            status: Question status, either 'pending' or 'answered'.

        Returns:
            Path object pointing to the question file.

        Raises:
            ValueError: If status is not 'pending' or 'answered'.

        Example:
            >>> queue._get_question_path('Q-20260203-143022-a1b2', 'pending')
            PosixPath('docs/plans/live/260203QF_feature/questions/pending/Q-20260203-143022-a1b2.yml')
        """
        if status == "pending":
            return self.pending_dir / f"{question_id}.yml"
        elif status == "answered":
            return self.answered_dir / f"{question_id}.yml"
        else:
            raise ValueError(f"Invalid status: {status}. Must be 'pending' or 'answered'.")

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write content to file atomically.

        Uses temp file + rename pattern for atomicity, ensuring no partial
        writes are visible to other processes. The fsync operation guarantees
        data is persisted to disk before the atomic rename.

        Args:
            path: Target file path
            content: Content to write

        Raises:
            RuntimeError: If write operation fails. Temp file is cleaned up on failure.

        Implementation:
            1. Create temp file in same directory (path.with_suffix('.tmp'))
            2. Write content to temp file
            3. fsync to ensure write is on disk
            4. Rename temp file to target path (atomic operation on POSIX)
            5. Clean up temp file on errors

        Atomicity guarantee:
            On POSIX systems, os.replace() is atomic. Other processes will
            see either the old file or the complete new file, never partial
            content. The fsync ensures data survives system crashes.
        """
        # Create temp file in same directory as target
        temp_path = path.with_suffix('.tmp')

        try:
            # Write content to temp file
            temp_path.write_text(content, encoding="utf-8")

            # fsync to ensure data is on disk before rename
            # This ensures durability even in case of system crash
            with open(temp_path, 'r+b') as f:
                os.fsync(f.fileno())

            # Atomic rename (POSIX guarantee)
            os.replace(temp_path, path)

        except Exception as e:
            logger.error(
                f"Failed to write file atomically to {path}: {e}. "
                f"Ensure directory exists and has write permissions."
            )
            # Clean up temp file if it exists
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                # Ignore cleanup errors, raise original error
                pass
            raise RuntimeError(
                f"Failed to write file atomically to {path}: {e}. "
                f"Check directory permissions and available disk space."
            ) from e

    def create_question(
        self,
        text: str,
        context: str,
        severity: str,
        asked_by: str = "agent",
        suggested_answers: list[str] | None = None
    ) -> Question:
        """Create and persist a new question.

        Args:
            text: The question text
            context: Contextual information
            severity: Question severity (blocking/high/medium/low)
            asked_by: Who asked the question (default: "agent")
            suggested_answers: Optional list of suggested answers (max 10 non-empty strings)

        Returns:
            Created Question object

        Raises:
            ValueError: If severity is invalid or suggested_answers validation fails
            TimeoutError: If lock acquisition fails
        """
        # Validate severity against QuestionSeverity enum
        valid_severities = [s.value for s in QuestionSeverity]
        if severity not in valid_severities:
            error_msg = (
                f"Invalid severity '{severity}'. "
                f"Must be one of: {', '.join(valid_severities)}. "
                f"Use QuestionSeverity enum values (e.g., QuestionSeverity.BLOCKING.value)."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Validate suggested_answers if provided
        if suggested_answers is not None:
            if not isinstance(suggested_answers, list):
                error_msg = "suggested_answers must be a list"
                logger.error(error_msg)
                raise ValueError(error_msg)

            if len(suggested_answers) == 0:
                error_msg = "suggested_answers must not be empty (use None for no suggestions)"
                logger.error(error_msg)
                raise ValueError(error_msg)

            if len(suggested_answers) > 10:
                error_msg = "suggested_answers cannot exceed 10 items (prevent abuse)"
                logger.error(error_msg)
                raise ValueError(error_msg)

            for i, answer in enumerate(suggested_answers):
                if not isinstance(answer, str):
                    error_msg = f"suggested_answers[{i}] must be a string, got {type(answer).__name__}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                if not answer.strip():
                    error_msg = f"suggested_answers[{i}] must not be empty or whitespace-only"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

        # Use FileLock to prevent concurrent ID collisions
        lock = FileLock(self.pending_dir / ".lock")
        try:
            if not lock.acquire():
                error_msg = (
                    "Could not acquire lock for creating question. "
                    "Another process may be creating a question. "
                    "Retry after a brief delay or check for stuck locks in "
                    f"{self.pending_dir}/.lock"
                )
                logger.error(error_msg)
                raise TimeoutError(error_msg)

            # Generate unique question ID
            question_id = self._generate_question_id()

            # Create Question object with status="pending"
            question = Question(
                id=question_id,
                text=text,
                context=context,
                severity=severity,
                asked_by=asked_by,
                created_at=time.time(),
                status="pending",
                suggested_answers=suggested_answers
            )

            # Convert to YAML using question_to_yaml()
            yaml_content = question_to_yaml(question)

            # Write to pending/{question_id}.yml atomically
            question_path = self._get_question_path(question_id, "pending")
            temp_path = question_path.with_suffix(".yml.tmp")

            try:
                # Write to temporary file
                temp_path.write_text(yaml_content, encoding="utf-8")

                # Atomic rename
                os.replace(temp_path, question_path)

                logger.debug(
                    f"Question created successfully: {question_id} "
                    f"(severity={severity}, asked_by={asked_by})"
                )
            except Exception as e:
                error_msg = (
                    f"Failed to write question file to {question_path}: {e}. "
                    f"Ensure directory exists and has write permissions."
                )
                logger.error(error_msg)
                # Clean up temp file if it exists
                if temp_path.exists():
                    temp_path.unlink()
                raise RuntimeError(error_msg) from e

            # Return Question object
            return question
        finally:
            lock.release()

    def get_question(self, question_id: str) -> Optional[Question]:
        """Get a specific question by ID.

        Args:
            question_id: Question ID to retrieve

        Returns:
            Question object if found, None otherwise

        Raises:
            ValueError: If question_id format is invalid
        """
        # Validate question ID format (Q-YYYYMMDD-HHMMSS-XXXX)
        if not re.match(r'^Q-\d{8}-\d{6}-[0-9a-f]{4}$', question_id):
            error_msg = (
                f"Invalid question ID format: '{question_id}'. "
                f"Expected format: Q-YYYYMMDD-HHMMSS-XXXX (e.g., Q-20260203-143022-a1b2)"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Check pending/{question_id}.yml first
        pending_path = self._get_question_path(question_id, "pending")
        if pending_path.exists():
            try:
                yaml_content = pending_path.read_text(encoding="utf-8")
                question = yaml_to_question(yaml_content)
                logger.debug(f"Question retrieved from pending: {question_id}")
                return question
            except Exception as e:
                logger.warning(
                    f"Corrupted question file {pending_path.name}: {e}. "
                    f"File will be skipped. Consider removing or repairing the file."
                )
                return None

        # If not found, check answered/{question_id}_question.yml
        # Note: answered directory contains both {question_id}.yml (Answer) and
        # {question_id}_question.yml (Question). We need the Question file.
        answered_path = self.answered_dir / f"{question_id}_question.yml"
        if answered_path.exists():
            try:
                yaml_content = answered_path.read_text(encoding="utf-8")
                question = yaml_to_question(yaml_content)
                logger.debug(f"Question retrieved from answered: {question_id}")
                return question
            except Exception as e:
                logger.warning(
                    f"Corrupted question file {answered_path.name}: {e}. "
                    f"File will be skipped. Consider removing or repairing the file."
                )
                return None

        # Return None if not found
        logger.debug(f"Question not found: {question_id}")
        return None

    def list_pending_questions(self, severity_filter: Optional[str] = None) -> list[Question]:
        """List all pending questions.

        Args:
            severity_filter: Optional severity filter (e.g., "blocking")

        Returns:
            List of Question objects, sorted by created_at (oldest first)

        Raises:
            ValueError: If severity_filter is invalid
        """
        # Validate severity_filter if provided
        if severity_filter is not None:
            valid_severities = [s.value for s in QuestionSeverity]
            if severity_filter not in valid_severities:
                error_msg = (
                    f"Invalid severity filter '{severity_filter}'. "
                    f"Must be one of: {', '.join(valid_severities)} or None."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

        questions = []

        # Check if pending directory exists
        if not self.pending_dir.exists():
            logger.debug(f"Pending directory does not exist: {self.pending_dir}")
            return questions

        # Scan pending/ directory for *.yml files
        for yml_file in self.pending_dir.glob("*.yml"):
            try:
                # Read and parse each file using yaml_to_question()
                yaml_content = yml_file.read_text(encoding="utf-8")
                question = yaml_to_question(yaml_content)

                # Filter by severity if severity_filter provided
                if severity_filter is None or question.severity == severity_filter:
                    questions.append(question)

            except Exception as e:
                # Handle file read errors gracefully (skip corrupted files, log warning)
                logger.warning(
                    f"Skipping corrupted question file {yml_file.name}: {e}. "
                    f"File will be ignored in listing. Consider removing or repairing: {yml_file}"
                )
                continue

        # Sort by created_at (oldest questions first)
        questions.sort(key=lambda q: q.created_at)

        logger.debug(
            f"Listed {len(questions)} pending questions "
            f"(filter: {severity_filter or 'none'})"
        )

        return questions

    def answer_question(
        self,
        question_id: str,
        answer_text: str,
        answered_by: str = "human",
        confidence: Optional[str] = None,
    ) -> tuple[Question, Answer]:
        """Answer a pending question.

        Args:
            question_id: ID of question to answer
            answer_text: The answer text
            answered_by: Who answered (default: "human")
            confidence: Answer confidence (high/medium/low, optional)

        Returns:
            Tuple of (updated Question, Answer)

        Raises:
            FileNotFoundError: If question not found in pending/
            ValueError: If confidence is invalid or question_id format is invalid
            TimeoutError: If lock acquisition fails
        """
        # Validate question ID format
        if not re.match(r'^Q-\d{8}-\d{6}-[0-9a-f]{4}$', question_id):
            error_msg = (
                f"Invalid question ID format: '{question_id}'. "
                f"Expected format: Q-YYYYMMDD-HHMMSS-XXXX (e.g., Q-20260203-143022-a1b2)"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Step 1: Read question from pending/{question_id}.yml
        pending_path = self._get_question_path(question_id, "pending")
        if not pending_path.exists():
            error_msg = (
                f"Question '{question_id}' not found in pending directory. "
                f"It may have already been answered or does not exist. "
                f"Check {self.pending_dir} for available questions."
            )
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # Read and parse question
        try:
            yaml_content = pending_path.read_text(encoding="utf-8")
            question = yaml_to_question(yaml_content)
        except Exception as e:
            error_msg = (
                f"Failed to read question file {pending_path}: {e}. "
                f"File may be corrupted. Consider removing and recreating the question."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        # Step 2: Validate confidence if provided
        if confidence is not None:
            valid_confidences = [c.value for c in AnswerConfidence]
            if confidence not in valid_confidences:
                error_msg = (
                    f"Invalid confidence '{confidence}'. "
                    f"Must be one of: {', '.join(valid_confidences)} or None. "
                    f"Use AnswerConfidence enum values (e.g., AnswerConfidence.HIGH.value)."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

        # Step 3: Create Answer object
        answer = Answer(
            question_id=question_id,
            answer_text=answer_text,
            answered_by=answered_by,
            answered_at=time.time(),
            confidence=confidence,
        )

        # Step 4: Update Question status to "answered"
        question.status = "answered"
        question.answered_at = answer.answered_at
        question.answered_by = answered_by
        question.answer = answer_text

        # Step 5-7: Atomic file operations using FileLock
        # Lock both directories in consistent order (answered < pending alphabetically)
        # to prevent deadlocks
        answered_question_path = self.answered_dir / f"{question_id}_question.yml"
        answered_answer_path = self.answered_dir / f"{question_id}.yml"

        # Acquire locks in consistent order: answered directory first, then pending
        answered_lock = FileLock(self.answered_dir / ".lock")
        pending_lock = FileLock(self.pending_dir / ".lock")

        try:
            # Acquire answered lock first (alphabetical order)
            if not answered_lock.acquire():
                error_msg = (
                    "Could not acquire lock for answered directory. "
                    "Another process may be answering a question. "
                    "Retry after a brief delay or check for stuck locks in "
                    f"{self.answered_dir}/.lock"
                )
                logger.error(error_msg)
                raise TimeoutError(error_msg)

            try:
                # Then acquire pending lock
                if not pending_lock.acquire():
                    error_msg = (
                        "Could not acquire lock for pending directory. "
                        "Another process may be creating or answering a question. "
                        "Retry after a brief delay or check for stuck locks in "
                        f"{self.pending_dir}/.lock"
                    )
                    logger.error(error_msg)
                    raise TimeoutError(error_msg)

                try:
                    # Step 5: Write Answer to answered/{question_id}.yml using answer_to_yaml()
                    answer_yaml = answer_to_yaml(answer, question)
                    temp_answer_path = answered_answer_path.with_suffix(".yml.tmp")
                    temp_question_path = None  # Initialize to None for cleanup safety

                    try:
                        # Write answer atomically
                        temp_answer_path.write_text(answer_yaml, encoding="utf-8")
                        os.replace(temp_answer_path, answered_answer_path)

                        # Step 6: Move Question to answered/{question_id}_question.yml (atomic move)
                        question_yaml = question_to_yaml(question)
                        temp_question_path = answered_question_path.with_suffix(".yml.tmp")
                        temp_question_path.write_text(question_yaml, encoding="utf-8")
                        os.replace(temp_question_path, answered_question_path)

                        # Step 7: Delete pending/{question_id}.yml
                        pending_path.unlink()

                        logger.debug(
                            f"Question answered successfully: {question_id} "
                            f"(answered_by={answered_by}, confidence={confidence})"
                        )

                    except Exception as e:
                        error_msg = (
                            f"Failed to answer question {question_id}: {e}. "
                            f"Ensure directories exist and have write permissions."
                        )
                        logger.error(error_msg)
                        # Clean up temp files if they exist
                        if temp_answer_path.exists():
                            temp_answer_path.unlink()
                        if temp_question_path is not None and temp_question_path.exists():
                            temp_question_path.unlink()
                        raise RuntimeError(error_msg) from e

                finally:
                    pending_lock.release()
            finally:
                answered_lock.release()
        finally:
            # Ensure both locks are released even if acquisition fails
            pass

        # Step 8: Return (Question, Answer) tuple
        return (question, answer)
