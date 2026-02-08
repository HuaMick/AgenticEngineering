"""UAT T9-004: Ask a question with suggested answers (US-CLI-060).

Tests the --suggest flag for creating questions with suggested answer options.
"""

import os
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml


@pytest.fixture
def plan_folder(tmp_path):
    """Create a test plan folder."""
    plan_path = tmp_path / "test_plan"
    plan_path.mkdir()

    # Create questions directory structure
    questions_dir = plan_path / "questions"
    pending_dir = questions_dir / "pending"
    answered_dir = questions_dir / "answered"
    pending_dir.mkdir(parents=True)
    answered_dir.mkdir(parents=True)

    return plan_path


def test_ask_question_with_multiple_suggestions(plan_folder):
    """Test creating a question with multiple --suggest options."""
    from agenticcli.commands import question

    # Create mock args
    args = Mock()
    args.text = "Use pytest or unittest?"
    args.severity = "medium"
    args.context = "Test framework selection"
    args.suggest = ["Use pytest", "Use unittest", "Use both"]
    args.plan = str(plan_folder)

    # Run command
    question.cmd_ask(args)

    # Find the created question file
    pending_dir = plan_folder / "questions" / "pending"
    question_files = list(pending_dir.glob("Q-*.yml"))

    assert len(question_files) == 1

    # Read and verify question content
    with open(question_files[0], 'r') as f:
        question_data = yaml.safe_load(f)

    assert question_data["text"] == "Use pytest or unittest?"
    assert question_data["severity"] == "medium"
    assert question_data["context"] == "Test framework selection"
    assert "suggested_answers" in question_data
    assert question_data["suggested_answers"] == ["Use pytest", "Use unittest", "Use both"]


def test_ask_question_without_suggestions_backward_compatible(plan_folder):
    """Test that questions without --suggest still work (backward compatibility)."""
    from agenticcli.commands import question

    # Create mock args without suggestions
    args = Mock()
    args.text = "Should we refactor this module?"
    args.severity = "low"
    args.context = "Code quality improvement"
    args.suggest = None
    args.plan = str(plan_folder)

    # Run command
    question.cmd_ask(args)

    # Find the created question file
    pending_dir = plan_folder / "questions" / "pending"
    question_files = list(pending_dir.glob("Q-*.yml"))

    assert len(question_files) == 1

    # Read and verify question content
    with open(question_files[0], 'r') as f:
        question_data = yaml.safe_load(f)

    assert question_data["text"] == "Should we refactor this module?"
    assert question_data["severity"] == "low"
    # suggested_answers should not be present (None values not serialized)
    assert "suggested_answers" not in question_data or question_data["suggested_answers"] is None


def test_ask_question_single_suggestion(plan_folder):
    """Test creating a question with a single --suggest option."""
    from agenticcli.commands import question

    # Create mock args with single suggestion
    args = Mock()
    args.text = "Continue with this approach?"
    args.severity = "high"
    args.context = "Architecture decision"
    args.suggest = ["Yes"]
    args.plan = str(plan_folder)

    # Run command
    question.cmd_ask(args)

    # Find the created question file
    pending_dir = plan_folder / "questions" / "pending"
    question_files = list(pending_dir.glob("Q-*.yml"))

    assert len(question_files) == 1

    # Read and verify question content
    with open(question_files[0], 'r') as f:
        question_data = yaml.safe_load(f)

    assert question_data["suggested_answers"] == ["Yes"]


def test_yaml_file_contains_suggested_answers_field(plan_folder):
    """Test that the YAML file explicitly contains suggested_answers field."""
    from agenticcli.commands import question

    # Create mock args
    args = Mock()
    args.text = "Pick a database?"
    args.severity = "medium"
    args.context = "Database selection"
    args.suggest = ["PostgreSQL", "MySQL", "SQLite"]
    args.plan = str(plan_folder)

    # Run command
    question.cmd_ask(args)

    # Find the created question file
    pending_dir = plan_folder / "questions" / "pending"
    question_files = list(pending_dir.glob("Q-*.yml"))

    # Read raw YAML content
    with open(question_files[0], 'r') as f:
        yaml_content = f.read()

    # Verify field exists in raw YAML
    assert "suggested_answers:" in yaml_content or "suggested_answers" in yaml_content


def test_validation_empty_suggest_rejected():
    """Test that empty --suggest values are rejected."""
    from agenticguidance.services.question import QuestionQueue

    # Create a temporary plan path
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "test_plan"
        plan_path.mkdir()

        service = QuestionQueue(plan_path)

        # Try to create question with empty suggestion list
        with pytest.raises(ValueError, match="suggested_answers must not be empty"):
            service.create_question(
                text="Test question?",
                context="Test",
                severity="medium",
                suggested_answers=[]
            )


def test_validation_max_suggestions_enforced():
    """Test that more than 10 suggestions are rejected."""
    from agenticguidance.services.question import QuestionQueue

    # Create a temporary plan path
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "test_plan"
        plan_path.mkdir()

        service = QuestionQueue(plan_path)

        # Try to create question with 11 suggestions
        too_many = [f"Option {i}" for i in range(11)]
        with pytest.raises(ValueError, match="cannot exceed 10 items"):
            service.create_question(
                text="Test question?",
                context="Test",
                severity="medium",
                suggested_answers=too_many
            )


def test_validation_empty_string_suggestion_rejected():
    """Test that empty string suggestions are rejected."""
    from agenticguidance.services.question import QuestionQueue

    # Create a temporary plan path
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "test_plan"
        plan_path.mkdir()

        service = QuestionQueue(plan_path)

        # Try to create question with empty string suggestion
        with pytest.raises(ValueError, match="must not be empty or whitespace-only"):
            service.create_question(
                text="Test question?",
                context="Test",
                severity="medium",
                suggested_answers=["Valid option", ""]
            )


def test_validation_whitespace_only_suggestion_rejected():
    """Test that whitespace-only suggestions are rejected."""
    from agenticguidance.services.question import QuestionQueue

    # Create a temporary plan path
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "test_plan"
        plan_path.mkdir()

        service = QuestionQueue(plan_path)

        # Try to create question with whitespace-only suggestion
        with pytest.raises(ValueError, match="must not be empty or whitespace-only"):
            service.create_question(
                text="Test question?",
                context="Test",
                severity="medium",
                suggested_answers=["Valid option", "   "]
            )


def test_validation_non_string_suggestion_rejected():
    """Test that non-string suggestions are rejected."""
    from agenticguidance.services.question import QuestionQueue

    # Create a temporary plan path
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "test_plan"
        plan_path.mkdir()

        service = QuestionQueue(plan_path)

        # Try to create question with non-string suggestion
        with pytest.raises(ValueError, match="must be a string"):
            service.create_question(
                text="Test question?",
                context="Test",
                severity="medium",
                suggested_answers=["Valid option", 123]
            )


def test_suggested_answers_stored_as_list(plan_folder):
    """Test that multiple --suggest values are stored as a list in YAML."""
    from agenticcli.commands import question

    # Create mock args
    args = Mock()
    args.text = "Choose deployment strategy?"
    args.severity = "medium"
    args.context = "Deployment planning"
    args.suggest = ["Blue-green", "Canary", "Rolling"]
    args.plan = str(plan_folder)

    # Run command
    question.cmd_ask(args)

    # Find the created question file
    pending_dir = plan_folder / "questions" / "pending"
    question_files = list(pending_dir.glob("Q-*.yml"))

    # Read and verify
    with open(question_files[0], 'r') as f:
        question_data = yaml.safe_load(f)

    # Verify it's a list
    assert isinstance(question_data["suggested_answers"], list)
    assert len(question_data["suggested_answers"]) == 3


def test_question_without_suggestions_parses_correctly(plan_folder):
    """Test that questions without suggestions parse correctly (backward compatibility)."""
    from agenticguidance.models.question import yaml_to_question

    # Manually create a question file without suggested_answers field
    question_id = "Q-20260208-120000-test"
    question_data = {
        "id": question_id,
        "text": "Legacy question without suggestions",
        "context": "Backward compatibility test",
        "severity": "medium",
        "asked_by": "agent",
        "created_at": 1707393600.0,
        "status": "pending",
        "answer": None,
        "answered_at": None,
        "answered_by": None,
        # No suggested_answers field
    }

    pending_dir = plan_folder / "questions" / "pending"
    question_file = pending_dir / f"{question_id}.yml"
    with open(question_file, 'w') as f:
        yaml.dump(question_data, f, default_flow_style=False, sort_keys=False)

    # Read and parse
    with open(question_file, 'r') as f:
        yaml_content = f.read()

    question = yaml_to_question(yaml_content)

    # Verify parsing succeeds
    assert question.id == question_id
    assert question.text == "Legacy question without suggestions"
    assert question.suggested_answers is None


def test_cli_output_shows_suggestion_count(plan_folder, capsys):
    """Test that CLI output shows count of suggested answers."""
    from agenticcli.commands import question

    # Create mock args
    args = Mock()
    args.text = "Select authentication method?"
    args.severity = "medium"
    args.context = "Security architecture"
    args.suggest = ["OAuth2", "JWT", "Session-based"]
    args.plan = str(plan_folder)

    # Run command
    question.cmd_ask(args)

    # Capture output
    captured = capsys.readouterr()

    # Verify output mentions suggested answers
    assert "3 options" in captured.out or "Suggested answers" in captured.out


def test_max_10_suggestions_accepted():
    """Test that exactly 10 suggestions are accepted (boundary test)."""
    from agenticguidance.services.question import QuestionQueue

    # Create a temporary plan path
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_path = Path(tmpdir) / "test_plan"
        plan_path.mkdir()

        service = QuestionQueue(plan_path)

        # Create question with exactly 10 suggestions
        ten_suggestions = [f"Option {i}" for i in range(10)]
        question = service.create_question(
            text="Test question?",
            context="Test",
            severity="medium",
            suggested_answers=ten_suggestions
        )

        # Verify it was created successfully
        assert question.suggested_answers == ten_suggestions
        assert len(question.suggested_answers) == 10
