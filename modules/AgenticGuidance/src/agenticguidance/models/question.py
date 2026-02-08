"""Question Model - structured question/answer tracking.

This module defines the Question dataclass used for tracking questions that arise
during agent workflows. Questions are stored in YAML files and can be answered
through CLI, voice interface, or other means.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import yaml


class QuestionSeverity(Enum):
    """Severity level for a question."""

    BLOCKING = "blocking"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QuestionStatus(Enum):
    """Status of a question."""

    PENDING = "pending"
    ANSWERED = "answered"
    DEFERRED = "deferred"


class AnswerConfidence(Enum):
    """Confidence level for an answer."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Question:
    """Question entry in the question queue.

    Tracks questions raised by agents or humans during workflow execution.
    Questions have severity levels indicating urgency and status tracking
    for workflow management.
    """

    id: str
    text: str
    context: str
    severity: str
    asked_by: str
    created_at: float
    status: str = "pending"
    answer: Optional[str] = None
    answered_at: Optional[float] = None
    answered_by: Optional[str] = None
    suggested_answers: Optional[list[str]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization.

        Returns:
            Dictionary representation of the question.
        """
        result = {
            "id": self.id,
            "text": self.text,
            "context": self.context,
            "severity": self.severity,
            "asked_by": self.asked_by,
            "created_at": self.created_at,
            "status": self.status,
            "answer": self.answer,
            "answered_at": self.answered_at,
            "answered_by": self.answered_by,
        }
        # Only include suggested_answers if not None (keep YAML clean)
        if self.suggested_answers is not None:
            result["suggested_answers"] = self.suggested_answers
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        """Create Question from dictionary.

        Args:
            data: Dictionary with question data.

        Returns:
            Question instance.
        """
        return cls(
            id=data["id"],
            text=data["text"],
            context=data["context"],
            severity=data["severity"],
            asked_by=data["asked_by"],
            created_at=data["created_at"],
            status=data.get("status", "pending"),
            answer=data.get("answer"),
            answered_at=data.get("answered_at"),
            answered_by=data.get("answered_by"),
            suggested_answers=data.get("suggested_answers"),
        )

    def mark_answered(self, answer: str, answered_by: str) -> None:
        """Mark question as answered.

        Args:
            answer: The answer text.
            answered_by: Who provided the answer (agent role or "human").
        """
        self.answer = answer
        self.answered_by = answered_by
        self.answered_at = time.time()
        self.status = QuestionStatus.ANSWERED.value

    def mark_deferred(self) -> None:
        """Mark question as deferred (skipped for now)."""
        self.status = QuestionStatus.DEFERRED.value


@dataclass
class Answer:
    """Answer entry for a question.

    Tracks answers provided to questions with metadata about who answered,
    when, and optional confidence level.
    """

    question_id: str
    answer_text: str
    answered_by: str
    answered_at: float
    confidence: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization.

        Returns:
            Dictionary representation of the answer.
        """
        return {
            "question_id": self.question_id,
            "answer_text": self.answer_text,
            "answered_by": self.answered_by,
            "answered_at": self.answered_at,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Answer":
        """Create Answer from dictionary.

        Args:
            data: Dictionary with answer data.

        Returns:
            Answer instance.
        """
        return cls(
            question_id=data["question_id"],
            answer_text=data["answer_text"],
            answered_by=data["answered_by"],
            answered_at=data["answered_at"],
            confidence=data.get("confidence"),
        )


def question_to_yaml(question: Question) -> str:
    """Convert Question to YAML string with metadata header.

    Args:
        question: Question instance to serialize.

    Returns:
        YAML string representation with metadata comment header.
    """
    # Create metadata header comment
    header = f"# Question ID: {question.id}\n"
    header += f"# Created: {question.created_at}\n"
    header += f"# Status: {question.status}\n\n"

    # Convert question to YAML
    yaml_content = yaml.safe_dump(
        question.to_dict(),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )

    return header + yaml_content


def yaml_to_question(yaml_str: str) -> Question:
    """Parse YAML string to Question instance.

    Args:
        yaml_str: YAML string containing question data.

    Returns:
        Question instance.

    Raises:
        ValueError: If YAML parsing fails or data is invalid.
    """
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML: {e}") from e

    if not data:
        raise ValueError("YAML data is empty or null")

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML object (dict), got {type(data).__name__}")

    try:
        return Question.from_dict(data)
    except (KeyError, TypeError) as e:
        raise ValueError(f"Invalid question data structure: {e}") from e


def answer_to_yaml(answer: Answer, question: Question) -> str:
    """Convert Answer to YAML string with question context header.

    Args:
        answer: Answer instance to serialize.
        question: Original Question for context in header.

    Returns:
        YAML string representation with question context in comment header.
    """
    # Create header with original question text
    header = f"# Answer to Question: {question.id}\n"
    header += f"# Question: {question.text}\n"
    header += f"# Answered by: {answer.answered_by}\n"
    header += f"# Answered at: {answer.answered_at}\n\n"

    # Convert answer to YAML
    yaml_content = yaml.safe_dump(
        answer.to_dict(),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )

    return header + yaml_content


def yaml_to_answer(yaml_str: str) -> Answer:
    """Parse YAML string to Answer instance.

    Args:
        yaml_str: YAML string containing answer data.

    Returns:
        Answer instance.

    Raises:
        ValueError: If YAML parsing fails or data is invalid.
    """
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML: {e}") from e

    if not data:
        raise ValueError("YAML data is empty or null")

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML object (dict), got {type(data).__name__}")

    try:
        return Answer.from_dict(data)
    except (KeyError, TypeError) as e:
        raise ValueError(f"Invalid answer data structure: {e}") from e
