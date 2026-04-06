"""Tests for Question and Answer dataclasses."""

import time
from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.story("US-SET-028", "US-PLN-090")

from agenticguidance.models.question import (
    Answer,
    AnswerConfidence,
    Question,
    QuestionSeverity,
    QuestionStatus,
    answer_to_yaml,
    question_to_yaml,
    yaml_to_answer,
    yaml_to_question,
)


@pytest.fixture
def sample_question():
    """Create a sample Question instance for testing."""
    return Question(
        id="q_001",
        text="What is the deployment strategy?",
        context="Working on deployment phase of project",
        severity="high",
        asked_by="orchestrator",
        created_at=1706745600.0,
        status="pending",
        answer=None,
        answered_at=None,
        answered_by=None,
    )


@pytest.fixture
def sample_answered_question():
    """Create a sample Question instance that has been answered."""
    return Question(
        id="q_002",
        text="Should we use blue-green deployment?",
        context="Evaluating deployment options",
        severity="medium",
        asked_by="test-builder",
        created_at=1706745600.0,
        status="answered",
        answer="Yes, use blue-green deployment for zero downtime",
        answered_at=1706749200.0,
        answered_by="human",
    )


@pytest.fixture
def sample_answer():
    """Create a sample Answer instance for testing."""
    return Answer(
        question_id="q_001",
        answer_text="Use blue-green deployment strategy",
        answered_by="human",
        answered_at=1706749200.0,
        confidence="high",
    )


@pytest.fixture
def sample_answer_no_confidence():
    """Create a sample Answer instance without confidence."""
    return Answer(
        question_id="q_001",
        answer_text="Use blue-green deployment strategy",
        answered_by="human",
        answered_at=1706749200.0,
        confidence=None,
    )


class TestQuestionDataclass:
    """Tests for Question dataclass."""

    def test_create_question(self):
        """Test creating Question with all fields."""
        question = Question(
            id="q_test",
            text="Test question?",
            context="Test context",
            severity="blocking",
            asked_by="test-agent",
            created_at=1706745600.0,
            status="pending",
            answer="Test answer",
            answered_at=1706749200.0,
            answered_by="human",
        )

        assert question.id == "q_test"
        assert question.text == "Test question?"
        assert question.context == "Test context"
        assert question.severity == "blocking"
        assert question.asked_by == "test-agent"
        assert question.created_at == 1706745600.0
        assert question.status == "pending"
        assert question.answer == "Test answer"
        assert question.answered_at == 1706749200.0
        assert question.answered_by == "human"

    def test_to_dict(self, sample_question):
        """Test to_dict() output."""
        result = sample_question.to_dict()

        assert isinstance(result, dict)
        assert result["id"] == "q_001"
        assert result["text"] == "What is the deployment strategy?"
        assert result["context"] == "Working on deployment phase of project"
        assert result["severity"] == "high"
        assert result["asked_by"] == "orchestrator"
        assert result["created_at"] == 1706745600.0
        assert result["status"] == "pending"
        assert result["answer"] is None
        assert result["answered_at"] is None
        assert result["answered_by"] is None

    def test_from_dict(self):
        """Test from_dict() reconstruction."""
        data = {
            "id": "q_003",
            "text": "What database to use?",
            "context": "Database selection phase",
            "severity": "low",
            "asked_by": "architect",
            "created_at": 1706745600.0,
            "status": "deferred",
            "answer": None,
            "answered_at": None,
            "answered_by": None,
        }

        question = Question.from_dict(data)

        assert question.id == "q_003"
        assert question.text == "What database to use?"
        assert question.context == "Database selection phase"
        assert question.severity == "low"
        assert question.asked_by == "architect"
        assert question.created_at == 1706745600.0
        assert question.status == "deferred"
        assert question.answer is None

    def test_from_dict_with_defaults(self):
        """Test from_dict() handles missing optional fields with defaults."""
        data = {
            "id": "q_004",
            "text": "Test question",
            "context": "Test context",
            "severity": "medium",
            "asked_by": "test-agent",
            "created_at": 1706745600.0,
        }

        question = Question.from_dict(data)

        assert question.id == "q_004"
        assert question.status == "pending"  # Default
        assert question.answer is None
        assert question.answered_at is None
        assert question.answered_by is None

    def test_round_trip(self, sample_question):
        """Test Question -> dict -> Question preserves data."""
        data = sample_question.to_dict()
        reconstructed = Question.from_dict(data)

        assert reconstructed.id == sample_question.id
        assert reconstructed.text == sample_question.text
        assert reconstructed.context == sample_question.context
        assert reconstructed.severity == sample_question.severity
        assert reconstructed.asked_by == sample_question.asked_by
        assert reconstructed.created_at == sample_question.created_at
        assert reconstructed.status == sample_question.status
        assert reconstructed.answer == sample_question.answer
        assert reconstructed.answered_at == sample_question.answered_at
        assert reconstructed.answered_by == sample_question.answered_by

    def test_round_trip_answered_question(self, sample_answered_question):
        """Test round-trip with answered question preserves all data."""
        data = sample_answered_question.to_dict()
        reconstructed = Question.from_dict(data)

        assert reconstructed.id == sample_answered_question.id
        assert reconstructed.answer == sample_answered_question.answer
        assert reconstructed.answered_at == sample_answered_question.answered_at
        assert reconstructed.answered_by == sample_answered_question.answered_by
        assert reconstructed.status == "answered"

    def test_mark_answered(self, sample_question):
        """Test mark_answered() updates question state."""
        with patch("time.time", return_value=1706749200.0):
            sample_question.mark_answered(
                answer="Deploy using Kubernetes",
                answered_by="human",
            )

        assert sample_question.answer == "Deploy using Kubernetes"
        assert sample_question.answered_by == "human"
        assert sample_question.answered_at == 1706749200.0
        assert sample_question.status == QuestionStatus.ANSWERED.value

    def test_mark_deferred(self, sample_question):
        """Test mark_deferred() updates question status."""
        sample_question.mark_deferred()

        assert sample_question.status == QuestionStatus.DEFERRED.value
        # Other fields should remain unchanged
        assert sample_question.answer is None
        assert sample_question.answered_at is None
        assert sample_question.answered_by is None


class TestAnswerDataclass:
    """Tests for Answer dataclass."""

    def test_create_answer(self):
        """Test creating Answer with all fields."""
        answer = Answer(
            question_id="q_005",
            answer_text="Use PostgreSQL for relational data",
            answered_by="architect",
            answered_at=1706749200.0,
            confidence="medium",
        )

        assert answer.question_id == "q_005"
        assert answer.answer_text == "Use PostgreSQL for relational data"
        assert answer.answered_by == "architect"
        assert answer.answered_at == 1706749200.0
        assert answer.confidence == "medium"

    def test_to_dict(self, sample_answer):
        """Test to_dict() output."""
        result = sample_answer.to_dict()

        assert isinstance(result, dict)
        assert result["question_id"] == "q_001"
        assert result["answer_text"] == "Use blue-green deployment strategy"
        assert result["answered_by"] == "human"
        assert result["answered_at"] == 1706749200.0
        assert result["confidence"] == "high"

    def test_from_dict(self):
        """Test from_dict() reconstruction."""
        data = {
            "question_id": "q_006",
            "answer_text": "Yes, proceed with the plan",
            "answered_by": "orchestrator",
            "answered_at": 1706749200.0,
            "confidence": "low",
        }

        answer = Answer.from_dict(data)

        assert answer.question_id == "q_006"
        assert answer.answer_text == "Yes, proceed with the plan"
        assert answer.answered_by == "orchestrator"
        assert answer.answered_at == 1706749200.0
        assert answer.confidence == "low"

    def test_round_trip(self, sample_answer):
        """Test Answer -> dict -> Answer preserves data."""
        data = sample_answer.to_dict()
        reconstructed = Answer.from_dict(data)

        assert reconstructed.question_id == sample_answer.question_id
        assert reconstructed.answer_text == sample_answer.answer_text
        assert reconstructed.answered_by == sample_answer.answered_by
        assert reconstructed.answered_at == sample_answer.answered_at
        assert reconstructed.confidence == sample_answer.confidence

    def test_optional_confidence(self, sample_answer_no_confidence):
        """Test confidence=None handled correctly."""
        assert sample_answer_no_confidence.confidence is None

        # Test to_dict preserves None
        data = sample_answer_no_confidence.to_dict()
        assert data["confidence"] is None

        # Test from_dict handles missing confidence
        reconstructed = Answer.from_dict(data)
        assert reconstructed.confidence is None

    def test_from_dict_missing_confidence(self):
        """Test from_dict() handles missing confidence field."""
        data = {
            "question_id": "q_007",
            "answer_text": "Answer without confidence",
            "answered_by": "human",
            "answered_at": 1706749200.0,
        }

        answer = Answer.from_dict(data)

        assert answer.question_id == "q_007"
        assert answer.confidence is None


class TestQuestionSeverity:
    """Tests for QuestionSeverity enum."""

    def test_severity_values(self):
        """Test all 4 severities present."""
        assert QuestionSeverity.BLOCKING.value == "blocking"
        assert QuestionSeverity.HIGH.value == "high"
        assert QuestionSeverity.MEDIUM.value == "medium"
        assert QuestionSeverity.LOW.value == "low"

    def test_severity_count(self):
        """Test there are exactly 4 severity levels."""
        assert len(QuestionSeverity) == 4

    def test_invalid_severity(self):
        """Test invalid value raises error."""
        with pytest.raises(ValueError):
            QuestionSeverity("critical")


class TestQuestionStatus:
    """Tests for QuestionStatus enum."""

    def test_status_values(self):
        """Test all 3 statuses present."""
        assert QuestionStatus.PENDING.value == "pending"
        assert QuestionStatus.ANSWERED.value == "answered"
        assert QuestionStatus.DEFERRED.value == "deferred"

    def test_status_count(self):
        """Test there are exactly 3 status values."""
        assert len(QuestionStatus) == 3

    def test_invalid_status(self):
        """Test invalid value raises error."""
        with pytest.raises(ValueError):
            QuestionStatus("archived")


class TestAnswerConfidence:
    """Tests for AnswerConfidence enum."""

    def test_confidence_values(self):
        """Test all 3 confidence levels present."""
        assert AnswerConfidence.HIGH.value == "high"
        assert AnswerConfidence.MEDIUM.value == "medium"
        assert AnswerConfidence.LOW.value == "low"

    def test_confidence_count(self):
        """Test there are exactly 3 confidence levels."""
        assert len(AnswerConfidence) == 3

    def test_invalid_confidence(self):
        """Test invalid value raises error."""
        with pytest.raises(ValueError):
            AnswerConfidence("very_high")


class TestYAMLSerialization:
    """Tests for YAML serialization functions."""

    def test_question_to_yaml(self, sample_question):
        """Test valid YAML produced."""
        yaml_str = question_to_yaml(sample_question)

        # Check header comments are present
        assert "# Question ID: q_001" in yaml_str
        assert "# Created: 1706745600.0" in yaml_str
        assert "# Status: pending" in yaml_str

        # Check YAML content can be parsed
        lines = yaml_str.split("\n")
        yaml_content = "\n".join(line for line in lines if not line.startswith("#"))
        data = yaml.safe_load(yaml_content)

        assert data["id"] == "q_001"
        assert data["text"] == "What is the deployment strategy?"

    def test_yaml_to_question(self, sample_question):
        """Test YAML parsed correctly."""
        yaml_str = question_to_yaml(sample_question)
        reconstructed = yaml_to_question(yaml_str)

        assert reconstructed.id == sample_question.id
        assert reconstructed.text == sample_question.text
        assert reconstructed.context == sample_question.context
        assert reconstructed.severity == sample_question.severity

    def test_question_round_trip(self, sample_question):
        """Test Question -> YAML -> Question."""
        yaml_str = question_to_yaml(sample_question)
        reconstructed = yaml_to_question(yaml_str)

        assert reconstructed.id == sample_question.id
        assert reconstructed.text == sample_question.text
        assert reconstructed.context == sample_question.context
        assert reconstructed.severity == sample_question.severity
        assert reconstructed.asked_by == sample_question.asked_by
        assert reconstructed.created_at == sample_question.created_at
        assert reconstructed.status == sample_question.status
        assert reconstructed.answer == sample_question.answer
        assert reconstructed.answered_at == sample_question.answered_at
        assert reconstructed.answered_by == sample_question.answered_by

    def test_question_round_trip_answered(self, sample_answered_question):
        """Test round-trip with answered question."""
        yaml_str = question_to_yaml(sample_answered_question)
        reconstructed = yaml_to_question(yaml_str)

        assert reconstructed.id == sample_answered_question.id
        assert reconstructed.answer == sample_answered_question.answer
        assert reconstructed.answered_by == sample_answered_question.answered_by
        assert reconstructed.status == "answered"

    def test_answer_to_yaml(self, sample_answer, sample_question):
        """Test valid YAML with question header."""
        yaml_str = answer_to_yaml(sample_answer, sample_question)

        # Check header comments are present
        assert "# Answer to Question: q_001" in yaml_str
        assert "# Question: What is the deployment strategy?" in yaml_str
        assert "# Answered by: human" in yaml_str
        assert "# Answered at: 1706749200.0" in yaml_str

        # Check YAML content can be parsed
        lines = yaml_str.split("\n")
        yaml_content = "\n".join(line for line in lines if not line.startswith("#"))
        data = yaml.safe_load(yaml_content)

        assert data["question_id"] == "q_001"
        assert data["answer_text"] == "Use blue-green deployment strategy"

    def test_yaml_to_answer(self, sample_answer, sample_question):
        """Test YAML parsed correctly."""
        yaml_str = answer_to_yaml(sample_answer, sample_question)
        reconstructed = yaml_to_answer(yaml_str)

        assert reconstructed.question_id == sample_answer.question_id
        assert reconstructed.answer_text == sample_answer.answer_text
        assert reconstructed.answered_by == sample_answer.answered_by
        assert reconstructed.confidence == sample_answer.confidence

    def test_answer_round_trip(self, sample_answer, sample_question):
        """Test Answer -> YAML -> Answer."""
        yaml_str = answer_to_yaml(sample_answer, sample_question)
        reconstructed = yaml_to_answer(yaml_str)

        assert reconstructed.question_id == sample_answer.question_id
        assert reconstructed.answer_text == sample_answer.answer_text
        assert reconstructed.answered_by == sample_answer.answered_by
        assert reconstructed.answered_at == sample_answer.answered_at
        assert reconstructed.confidence == sample_answer.confidence

    def test_answer_round_trip_no_confidence(
        self, sample_answer_no_confidence, sample_question
    ):
        """Test round-trip with answer that has no confidence."""
        yaml_str = answer_to_yaml(sample_answer_no_confidence, sample_question)
        reconstructed = yaml_to_answer(yaml_str)

        assert reconstructed.question_id == sample_answer_no_confidence.question_id
        assert reconstructed.confidence is None

    def test_invalid_yaml_empty(self):
        """Test empty YAML raises ValueError."""
        with pytest.raises(ValueError, match="YAML data is empty or null"):
            yaml_to_question("")

    def test_invalid_yaml_null(self):
        """Test null YAML raises ValueError."""
        with pytest.raises(ValueError, match="YAML data is empty or null"):
            yaml_to_question("null")

    def test_invalid_yaml_syntax(self):
        """Test malformed YAML raises ValueError."""
        invalid_yaml = "id: test\n  invalid: indentation:\n bad"
        with pytest.raises(ValueError, match="Failed to parse YAML"):
            yaml_to_question(invalid_yaml)

    def test_invalid_yaml_wrong_type(self):
        """Test YAML with wrong type raises ValueError."""
        yaml_str = "- item1\n- item2\n"  # List instead of dict
        with pytest.raises(ValueError, match="Expected YAML object"):
            yaml_to_question(yaml_str)

    def test_invalid_question_structure(self):
        """Test YAML missing required fields raises ValueError."""
        yaml_str = "id: test\ntext: question"  # Missing required fields
        with pytest.raises(ValueError, match="Invalid question data structure"):
            yaml_to_question(yaml_str)

    def test_invalid_answer_structure(self):
        """Test YAML missing required answer fields raises ValueError."""
        yaml_str = "question_id: q_001\nanswer_text: answer"  # Missing required fields
        with pytest.raises(ValueError, match="Invalid answer data structure"):
            yaml_to_answer(yaml_str)

    def test_question_yaml_unicode(self):
        """Test YAML handles unicode characters."""
        question = Question(
            id="q_unicode",
            text="What is the déploiement strategy? 你好",
            context="Testing unicode 日本語",
            severity="low",
            asked_by="test",
            created_at=1706745600.0,
        )

        yaml_str = question_to_yaml(question)
        reconstructed = yaml_to_question(yaml_str)

        assert reconstructed.text == question.text
        assert reconstructed.context == question.context

    def test_answer_yaml_unicode(self):
        """Test Answer YAML handles unicode characters."""
        question = Question(
            id="q_001",
            text="Test question",
            context="Test",
            severity="low",
            asked_by="test",
            created_at=1706745600.0,
        )

        answer = Answer(
            question_id="q_001",
            answer_text="Réponse avec unicode 日本語",
            answered_by="human",
            answered_at=1706749200.0,
        )

        yaml_str = answer_to_yaml(answer, question)
        reconstructed = yaml_to_answer(yaml_str)

        assert reconstructed.answer_text == answer.answer_text
