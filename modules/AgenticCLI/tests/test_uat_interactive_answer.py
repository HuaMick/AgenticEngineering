"""UAT T9-003: Answer a question interactively (US-CLI-062).

Tests the interactive wizard flow for answering questions with suggested answers,
custom answers, and defer functionality.
"""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import yaml

pytestmark = pytest.mark.uat


@pytest.fixture
def plan_with_pending_question(tmp_path):
    """Create a plan folder with a pending question that has suggested answers."""
    plan_path = tmp_path / "test_plan"
    plan_path.mkdir()

    # Create questions directory structure
    questions_dir = plan_path / "questions"
    pending_dir = questions_dir / "pending"
    answered_dir = questions_dir / "answered"
    pending_dir.mkdir(parents=True)
    answered_dir.mkdir(parents=True)

    # Create a pending question with suggested answers
    question_id = "Q-20260208-120000-abc1"
    question_data = {
        "id": question_id,
        "text": "Use pytest or unittest?",
        "context": "Test framework selection",
        "severity": "medium",
        "asked_by": "agent",
        "created_at": 1707393600.0,
        "status": "pending",
        "answer": None,
        "answered_at": None,
        "answered_by": None,
        "suggested_answers": ["Use pytest", "Use unittest", "Use both"]
    }

    question_file = pending_dir / f"{question_id}.yml"
    with open(question_file, 'w') as f:
        yaml.dump(question_data, f, default_flow_style=False, sort_keys=False)

    return plan_path, question_id


@pytest.fixture
def plan_with_multiple_questions(tmp_path):
    """Create a plan folder with multiple pending questions."""
    plan_path = tmp_path / "test_plan"
    plan_path.mkdir()

    # Create questions directory structure
    questions_dir = plan_path / "questions"
    pending_dir = questions_dir / "pending"
    answered_dir = questions_dir / "answered"
    pending_dir.mkdir(parents=True)
    answered_dir.mkdir(parents=True)

    # Create multiple pending questions
    questions = []
    for i, has_suggestions in enumerate([(True, ["Yes", "No"]), (False, None), (True, ["A", "B", "C"])]):
        question_id = f"Q-20260208-12000{i}-abc{i}"
        has_suggest, suggestions = has_suggestions
        question_data = {
            "id": question_id,
            "text": f"Question {i}?",
            "context": f"Context {i}",
            "severity": "medium",
            "asked_by": "agent",
            "created_at": 1707393600.0 + i,
            "status": "pending",
            "answer": None,
            "answered_at": None,
            "answered_by": None,
        }
        if has_suggest:
            question_data["suggested_answers"] = suggestions

        question_file = pending_dir / f"{question_id}.yml"
        with open(question_file, 'w') as f:
            yaml.dump(question_data, f, default_flow_style=False, sort_keys=False)

        questions.append((question_id, has_suggest))

    return plan_path, questions


def test_interactive_wizard_lists_pending_with_suggest_indicator(plan_with_multiple_questions, monkeypatch, capsys):
    """Test that interactive mode lists pending questions with [S] indicator for suggested answers."""
    from agenticcli.commands import question
    from types import SimpleNamespace

    plan_path, questions = plan_with_multiple_questions

    # Mock user input: cancel the wizard
    inputs = iter([""])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    # Create mock args - use SimpleNamespace to avoid hasattr issues with Mock
    args = SimpleNamespace()
    args.interactive = True
    args.plan = str(plan_path)

    # Run command (should list questions and wait for selection)
    with pytest.raises((SystemExit, StopIteration)):
        question.cmd_answer(args)

    # Capture output
    captured = capsys.readouterr()

    # Verify [S] indicator appears for questions with suggestions
    assert "[S]" in captured.out
    # Question 0 has suggestions -> should have [S]
    assert "Question 0?" in captured.out
    # Question 1 has no suggestions -> should not have [S] for that question
    lines = captured.out.split('\n')
    q0_line = [l for l in lines if "Question 0?" in l][0]
    q1_line = [l for l in lines if "Question 1?" in l][0]
    assert "[S]" in q0_line
    assert "[S]" not in q1_line


def test_interactive_select_suggested_answer(plan_with_pending_question, monkeypatch):
    """Test selecting a suggested answer from the wizard menu."""
    from agenticcli.commands import question

    plan_path, question_id = plan_with_pending_question

    # Mock user inputs:
    # 1. Select question number 1
    # 2. Select suggested answer #1 (Use pytest)
    # 3. Confirm (Y)
    inputs = iter(["1", "1", "Y"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    # Create mock args
    args = SimpleNamespace()
    args.interactive = True
    args.plan = str(plan_path)

    # Run command
    question.cmd_answer(args)

    # Verify question moved to answered/ with correct answer
    answered_dir = plan_path / "questions" / "answered"
    answered_question = answered_dir / f"{question_id}_question.yml"
    answered_answer = answered_dir / f"{question_id}.yml"

    assert answered_question.exists()
    assert answered_answer.exists()

    # Verify answer content
    with open(answered_answer, 'r') as f:
        answer_data = yaml.safe_load(f)

    assert answer_data["answer_text"] == "Use pytest"
    assert answer_data["confidence"] == "high"  # Suggested answers have high confidence
    assert answer_data["answered_by"] == "human"

    # Verify question no longer in pending/
    pending_file = plan_path / "questions" / "pending" / f"{question_id}.yml"
    assert not pending_file.exists()


def test_interactive_custom_answer_flow(plan_with_pending_question, monkeypatch):
    """Test the custom answer flow (select C, type answer)."""
    from agenticcli.commands import question

    plan_path, question_id = plan_with_pending_question

    # Mock user inputs:
    # 1. Select question number 1
    # 2. Select C (custom answer)
    # 3. Type custom answer
    # 4. Confirm (Y)
    inputs = iter(["1", "C", "Use nose2 for better compatibility", "Y"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    # Create mock args
    args = SimpleNamespace()
    args.interactive = True
    args.plan = str(plan_path)

    # Run command
    question.cmd_answer(args)

    # Verify question moved to answered/
    answered_dir = plan_path / "questions" / "answered"
    answered_answer = answered_dir / f"{question_id}.yml"

    assert answered_answer.exists()

    # Verify answer content
    with open(answered_answer, 'r') as f:
        answer_data = yaml.safe_load(f)

    assert answer_data["answer_text"] == "Use nose2 for better compatibility"
    assert answer_data["confidence"] is None  # Custom answers have no confidence
    assert answer_data["answered_by"] == "human"


def test_interactive_defer_flow(plan_with_pending_question, monkeypatch):
    """Test the defer flow (select D)."""
    from agenticcli.commands import question

    plan_path, question_id = plan_with_pending_question

    # Mock user inputs:
    # 1. Select question number 1
    # 2. Select D (defer)
    # 3. Confirm defer (Y)
    inputs = iter(["1", "D", "Y"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    # Create mock args
    args = SimpleNamespace()
    args.interactive = True
    args.plan = str(plan_path)

    # Run command
    question.cmd_answer(args)

    # Verify question still in pending/ with status="deferred"
    pending_file = plan_path / "questions" / "pending" / f"{question_id}.yml"
    assert pending_file.exists()

    with open(pending_file, 'r') as f:
        question_data = yaml.safe_load(f)

    assert question_data["status"] == "deferred"

    # Verify NOT moved to answered/
    answered_dir = plan_path / "questions" / "answered"
    assert not (answered_dir / f"{question_id}.yml").exists()


def test_non_interactive_answer_path_unbroken(plan_with_pending_question):
    """Test that non-interactive answer mode still works (backward compatibility)."""
    from agenticcli.commands import question

    plan_path, question_id = plan_with_pending_question

    # Create mock args for non-interactive mode
    args = SimpleNamespace()
    args.question_id = question_id
    args.text = "Use pytest for better fixtures"
    args.confidence = "medium"
    args.interactive = False
    args.plan = str(plan_path)

    # Run command
    question.cmd_answer(args)

    # Verify question moved to answered/
    answered_dir = plan_path / "questions" / "answered"
    answered_answer = answered_dir / f"{question_id}.yml"

    assert answered_answer.exists()

    # Verify answer content
    with open(answered_answer, 'r') as f:
        answer_data = yaml.safe_load(f)

    assert answer_data["answer_text"] == "Use pytest for better fixtures"
    assert answer_data["confidence"] == "medium"
    assert answer_data["answered_by"] == "human"


def test_wizard_displays_question_severity(plan_with_pending_question, monkeypatch, capsys):
    """Test that wizard displays question text and severity badge."""
    from agenticcli.commands import question

    plan_path, question_id = plan_with_pending_question

    # Mock user inputs: select question, then cancel with Ctrl+C
    inputs = iter(["1"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    # Create mock args
    args = SimpleNamespace()
    args.interactive = True
    args.plan = str(plan_path)

    # Run command (will fail when inputs exhausted)
    with pytest.raises(StopIteration):
        question.cmd_answer(args)

    # Capture output
    captured = capsys.readouterr()

    # Verify severity badge displayed
    assert "MEDIUM" in captured.out or "medium" in captured.out.lower()
    # Verify question text displayed
    assert "Use pytest or unittest?" in captured.out


def test_wizard_displays_suggested_answers_as_numbered_options(plan_with_pending_question, monkeypatch, capsys):
    """Test that wizard displays suggested answers as numbered menu options."""
    from agenticcli.commands import question

    plan_path, question_id = plan_with_pending_question

    # Mock user inputs: select question, then cancel
    inputs = iter(["1"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    # Create mock args
    args = SimpleNamespace()
    args.interactive = True
    args.plan = str(plan_path)

    # Run command
    with pytest.raises(StopIteration):
        question.cmd_answer(args)

    # Capture output
    captured = capsys.readouterr()

    # Verify numbered options displayed (handle ANSI color codes)
    assert "Use pytest" in captured.out
    assert "Use unittest" in captured.out
    assert "Use both" in captured.out
    assert "Custom answer" in captured.out
    assert "Defer question" in captured.out
    # Verify numbering exists
    assert "1" in captured.out and "2" in captured.out and "3" in captured.out


def test_wizard_confirmation_prompt(plan_with_pending_question, monkeypatch, capsys):
    """Test that wizard shows confirmation prompt before submitting."""
    from agenticcli.commands import question

    plan_path, question_id = plan_with_pending_question

    # Mock user inputs: select question, select answer, then cancel confirmation
    inputs = iter(["1", "1", "N"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    # Create mock args
    args = SimpleNamespace()
    args.interactive = True
    args.plan = str(plan_path)

    # Run command (should loop back after cancelling confirmation)
    with pytest.raises(StopIteration):
        question.cmd_answer(args)

    # Capture output
    captured = capsys.readouterr()

    # Verify confirmation prompt displayed
    assert "Your answer:" in captured.out or "Submit?" in captured.out

    # Verify answer NOT submitted (still in pending/)
    pending_file = plan_path / "questions" / "pending" / f"{question_id}.yml"
    assert pending_file.exists()


def test_empty_answer_rejected(plan_with_pending_question, monkeypatch, capsys):
    """Test that empty custom answers are rejected."""
    from agenticcli.commands import question

    plan_path, question_id = plan_with_pending_question

    # Mock user inputs: select question, custom answer, empty text, then real answer
    inputs = iter(["1", "C", "", "Valid answer", "Y"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    # Create mock args
    args = SimpleNamespace()
    args.interactive = True
    args.plan = str(plan_path)

    # Run command
    question.cmd_answer(args)

    # Capture output
    captured = capsys.readouterr()

    # Verify error message for empty answer
    assert "cannot be empty" in captured.out.lower() or "empty" in captured.out.lower()


def test_invalid_selection_rejected(plan_with_pending_question, monkeypatch):
    """Test that invalid menu selections are rejected and user can retry."""
    from agenticcli.commands import question

    plan_path, question_id = plan_with_pending_question

    # Mock user inputs: select question, invalid choice, then valid choice
    inputs = iter(["1", "999", "1", "Y"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    # Create mock args
    args = SimpleNamespace()
    args.interactive = True
    args.plan = str(plan_path)

    # Run command (should succeed after invalid input)
    question.cmd_answer(args)

    # Verify answer submitted
    answered_dir = plan_path / "questions" / "answered"
    assert (answered_dir / f"{question_id}.yml").exists()
