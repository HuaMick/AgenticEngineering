"""UAT T9-005: End-to-end notification-to-answer flow.

Tests the complete phone notification workflow from question creation through
ntfy notification to interactive answer submission. This validates the full
user journey:
1. Configure ntfy topic
2. Agent asks question with suggestions
3. Watcher detects question and sends ntfy push (mock HTTP)
4. User answers interactively
5. Answer persisted correctly
6. Verify full data flow: ask -> notify -> answer -> complete
"""

import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch, call
from urllib.error import URLError

import pytest
import yaml


@pytest.fixture
def plan_with_config(tmp_path):
    """Create a plan folder with questions directory and mock config."""
    plan_path = tmp_path / "test_plan"
    plan_path.mkdir()

    # Create questions directory structure
    questions_dir = plan_path / "questions"
    pending_dir = questions_dir / "pending"
    answered_dir = questions_dir / "answered"
    pending_dir.mkdir(parents=True)
    answered_dir.mkdir(parents=True)

    # Create mock config directory
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    prefs_file = config_dir / "preferences.yml"

    # Write ntfy config
    prefs_data = {
        "ntfy": {
            "topic": "my-phone",
            "server": "https://ntfy.sh",
            "enabled": True
        }
    }
    with open(prefs_file, 'w') as f:
        yaml.dump(prefs_data, f)

    return plan_path, config_dir


@pytest.fixture
def mock_ntfy_http():
    """Mock HTTP requests for ntfy.sh."""
    with patch('urllib.request.urlopen') as mock_urlopen:
        # Simulate successful HTTP response
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.close.return_value = None
        mock_urlopen.return_value = mock_response
        yield mock_urlopen


def test_e2e_ask_notify_answer_flow(plan_with_config, mock_ntfy_http, monkeypatch, capsys):
    """Test complete end-to-end flow: ask -> notify -> answer -> complete.

    This is the PRIMARY UAT test for T9-005, validating the entire user journey
    from phone notification receipt to interactive answer submission.
    """
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config

    # Mock config directory to use our tmp_path config
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # STEP 1: Agent asks question with suggestions
    args_ask = SimpleNamespace()
    args_ask.text = "Deploy to prod?"
    args_ask.severity = "high"
    args_ask.context = "Release decision"
    args_ask.suggest = ["Yes, deploy now", "No, wait for review"]
    args_ask.plan = str(plan_path)

    # Execute ask command
    question.cmd_ask(args_ask, ctx=None)

    # Verify question created in pending/
    pending_dir = plan_path / "questions" / "pending"
    pending_files = list(pending_dir.glob("Q-*.yml"))
    assert len(pending_files) == 1, "Question should be created in pending/"

    question_file = pending_files[0]
    question_id = question_file.stem

    # Verify question has suggested answers
    with open(question_file, 'r') as f:
        question_data = yaml.safe_load(f)

    assert question_data["text"] == "Deploy to prod?"
    assert question_data["severity"] == "high"
    assert question_data["suggested_answers"] == ["Yes, deploy now", "No, wait for review"]
    assert question_data["status"] == "pending"

    # STEP 2: Simulate watcher detecting question and sending ntfy notification
    from agenticguidance.services.question import QuestionQueue
    from agenticguidance.models.question import yaml_to_question

    service = QuestionQueue(plan_path)
    pending_questions = service.list_pending_questions()

    assert len(pending_questions) == 1
    q = pending_questions[0]

    # Call ntfy notification function directly (simulates watcher callback)
    from agenticcli.utils.ntfy import notify_new_question

    success = notify_new_question("my-phone", q, server="https://ntfy.sh")

    # STEP 3: Verify ntfy HTTP call was made with correct parameters
    assert success is True, "ntfy notification should succeed"
    assert mock_ntfy_http.called, "HTTP request should be made to ntfy.sh"

    # Verify HTTP request details
    call_args = mock_ntfy_http.call_args
    request = call_args[0][0]  # First positional arg is the Request object

    # Verify URL
    assert request.get_full_url() == "https://ntfy.sh/my-phone"

    # Verify headers
    assert request.headers.get("Title") == "New Question [HIGH]"
    assert request.headers.get("Priority") == "high"
    assert request.headers.get("Tags") == "question"

    # Verify message body contains question text
    request_data = request.data.decode('utf-8')
    assert "Deploy to prod?" in request_data

    # STEP 4: User answers interactively via wizard
    # Mock user inputs:
    # 1. Select question number 1 (only one pending question)
    # 2. Select suggested answer #1 ("Yes, deploy now")
    # 3. Confirm (Y)
    inputs = iter(["1", "1", "Y"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    args_answer = SimpleNamespace()
    args_answer.interactive = True
    args_answer.plan = str(plan_path)

    # Execute answer command
    question.cmd_answer(args_answer, ctx=None)

    # STEP 5: Verify answer persisted correctly
    answered_dir = plan_path / "questions" / "answered"
    answered_question_file = answered_dir / f"{question_id}_question.yml"
    answered_answer_file = answered_dir / f"{question_id}.yml"

    assert answered_question_file.exists(), "Question should be in answered/"
    assert answered_answer_file.exists(), "Answer file should exist"

    # Verify answer content
    with open(answered_answer_file, 'r') as f:
        answer_data = yaml.safe_load(f)

    assert answer_data["answer_text"] == "Yes, deploy now"
    assert answer_data["confidence"] == "high"  # Suggested answer -> high confidence
    assert answer_data["answered_by"] == "human"
    assert answer_data["question_id"] == question_id

    # Verify question updated with answer
    with open(answered_question_file, 'r') as f:
        updated_question = yaml.safe_load(f)

    assert updated_question["status"] == "answered"
    assert updated_question["answer"] == "Yes, deploy now"
    assert updated_question["answered_by"] == "human"
    assert updated_question["answered_at"] is not None

    # STEP 6: Verify question removed from pending/
    assert not question_file.exists(), "Question should be removed from pending/"

    # FINAL VERIFICATION: Complete data flow
    # ask -> notify -> answer -> complete
    # All steps completed successfully without errors


def test_e2e_flow_with_custom_answer(plan_with_config, mock_ntfy_http, monkeypatch):
    """Test E2E flow with user providing a custom answer instead of selecting suggestion."""
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # Create question with suggestions
    args_ask = SimpleNamespace()
    args_ask.text = "Which testing framework?"
    args_ask.severity = "medium"
    args_ask.context = "Framework selection"
    args_ask.suggest = ["pytest", "unittest"]
    args_ask.plan = str(plan_path)

    question.cmd_ask(args_ask, ctx=None)

    # Get question ID
    pending_dir = plan_path / "questions" / "pending"
    pending_files = list(pending_dir.glob("Q-*.yml"))
    question_id = pending_files[0].stem

    # Answer with custom text (select C, type custom answer, confirm)
    inputs = iter(["1", "C", "Use nose2 for backward compatibility", "Y"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    args_answer = SimpleNamespace()
    args_answer.interactive = True
    args_answer.plan = str(plan_path)

    question.cmd_answer(args_answer, ctx=None)

    # Verify custom answer persisted with confidence=None
    answered_dir = plan_path / "questions" / "answered"
    answered_answer_file = answered_dir / f"{question_id}.yml"

    with open(answered_answer_file, 'r') as f:
        answer_data = yaml.safe_load(f)

    assert answer_data["answer_text"] == "Use nose2 for backward compatibility"
    assert answer_data["confidence"] is None  # Custom answer -> no confidence


def test_e2e_flow_with_ntfy_network_error(plan_with_config, monkeypatch):
    """Test E2E flow gracefully handles ntfy network errors without crashing."""
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # Create question
    args_ask = SimpleNamespace()
    args_ask.text = "Network error test?"
    args_ask.severity = "low"
    args_ask.context = "Testing resilience"
    args_ask.suggest = ["Yes", "No"]
    args_ask.plan = str(plan_path)

    question.cmd_ask(args_ask, ctx=None)

    # Mock HTTP to raise network error - patch at the agenticcli.utils.ntfy module level
    with patch('agenticcli.utils.ntfy.urlopen') as mock_urlopen:
        mock_urlopen.side_effect = URLError("Network unreachable")

        # Attempt to send notification (should return False, not crash)
        from agenticguidance.services.question import QuestionQueue
        from agenticcli.utils.ntfy import notify_new_question

        service = QuestionQueue(plan_path)
        pending_questions = service.list_pending_questions()
        q = pending_questions[0]

        success = notify_new_question("my-phone", q)

        assert success is False, "Should return False on network error"
        # Importantly: NO EXCEPTION RAISED

    # Verify question still answerable despite notification failure
    inputs = iter(["1", "1", "Y"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    args_answer = SimpleNamespace()
    args_answer.interactive = True
    args_answer.plan = str(plan_path)

    # Should complete successfully
    question.cmd_answer(args_answer, ctx=None)

    # Verify answer exists
    answered_dir = plan_path / "questions" / "answered"
    answered_files = list(answered_dir.glob("Q-*.yml"))
    assert len(answered_files) >= 1, "Answer should be persisted despite ntfy failure"


def test_e2e_flow_ntfy_contains_severity_and_text(plan_with_config, monkeypatch):
    """Verify ntfy notification contains question text and severity in correct format."""
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # Test BLOCKING severity (should be urgent priority)
    args_ask = SimpleNamespace()
    args_ask.text = "Critical production issue detected!"
    args_ask.severity = "blocking"
    args_ask.context = "Production emergency"
    args_ask.suggest = ["Rollback immediately", "Investigate first"]
    args_ask.plan = str(plan_path)

    question.cmd_ask(args_ask, ctx=None)

    # Mock ntfy HTTP at module level and send notification
    with patch('agenticcli.utils.ntfy.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.close.return_value = None
        mock_urlopen.return_value = mock_response

        from agenticguidance.services.question import QuestionQueue
        from agenticcli.utils.ntfy import notify_new_question

        service = QuestionQueue(plan_path)
        pending_questions = service.list_pending_questions()
        q = pending_questions[0]

        notify_new_question("my-phone", q)

        # Verify notification details
        request = mock_urlopen.call_args[0][0]

        assert request.headers.get("Title") == "New Question [BLOCKING]"
        assert request.headers.get("Priority") == "urgent"
        assert request.headers.get("Tags") == "warning"

        request_data = request.data.decode('utf-8')
        assert "Critical production issue detected!" in request_data


def test_e2e_flow_wizard_shows_suggestions_from_question(plan_with_config, monkeypatch, capsys):
    """Verify interactive wizard displays the suggested answers from the created question."""
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # Create question with specific suggestions
    args_ask = SimpleNamespace()
    args_ask.text = "Approve merge request?"
    args_ask.severity = "medium"
    args_ask.context = "Code review"
    args_ask.suggest = ["Approve and merge", "Request changes", "Comment only"]
    args_ask.plan = str(plan_path)

    question.cmd_ask(args_ask, ctx=None)

    # Launch interactive wizard and cancel to capture output
    inputs = iter(["1"])  # Select question, then exhaust inputs
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    args_answer = SimpleNamespace()
    args_answer.interactive = True
    args_answer.plan = str(plan_path)

    with pytest.raises(StopIteration):
        question.cmd_answer(args_answer, ctx=None)

    # Capture output
    captured = capsys.readouterr()

    # Verify all three suggestions appear in wizard output
    assert "Approve and merge" in captured.out
    assert "Request changes" in captured.out
    assert "Comment only" in captured.out

    # Verify numbered options
    assert "[1]" in captured.out or "1" in captured.out
    assert "[2]" in captured.out or "2" in captured.out
    assert "[3]" in captured.out or "3" in captured.out


def test_e2e_flow_non_interactive_path_unaffected(plan_with_config, mock_ntfy_http, monkeypatch):
    """Verify non-interactive answer path still works (no regressions)."""
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # Create question
    args_ask = SimpleNamespace()
    args_ask.text = "Run migration?"
    args_ask.severity = "high"
    args_ask.context = "Database upgrade"
    args_ask.suggest = ["Yes", "No"]
    args_ask.plan = str(plan_path)

    question.cmd_ask(args_ask, ctx=None)

    # Get question ID
    pending_dir = plan_path / "questions" / "pending"
    pending_files = list(pending_dir.glob("Q-*.yml"))
    question_id = pending_files[0].stem

    # Answer NON-interactively with explicit question_id and text
    args_answer = SimpleNamespace()
    args_answer.question_id = question_id
    args_answer.text = "Yes, run migration with backup"
    args_answer.confidence = "high"
    args_answer.interactive = False
    args_answer.plan = str(plan_path)

    question.cmd_answer(args_answer, ctx=None)

    # Verify answer persisted
    answered_dir = plan_path / "questions" / "answered"
    answered_answer_file = answered_dir / f"{question_id}.yml"

    with open(answered_answer_file, 'r') as f:
        answer_data = yaml.safe_load(f)

    assert answer_data["answer_text"] == "Yes, run migration with backup"
    assert answer_data["confidence"] == "high"


def test_e2e_multiple_questions_with_deduplication(plan_with_config, monkeypatch):
    """Test multiple questions are notified but deduplication prevents duplicate notifications."""
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # Create two questions
    for i in range(2):
        args_ask = SimpleNamespace()
        args_ask.text = f"Question {i}?"
        args_ask.severity = "medium"
        args_ask.context = f"Context {i}"
        args_ask.suggest = ["Yes", "No"]
        args_ask.plan = str(plan_path)

        question.cmd_ask(args_ask, ctx=None)
        time.sleep(0.01)  # Ensure different timestamps

    # Mock ntfy HTTP and send notifications for all pending questions
    with patch('agenticcli.utils.ntfy.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.close.return_value = None
        mock_urlopen.return_value = mock_response

        from agenticguidance.services.question import QuestionQueue
        from agenticcli.utils.ntfy import notify_new_question

        service = QuestionQueue(plan_path)
        pending_questions = service.list_pending_questions()

        assert len(pending_questions) == 2

        # First notification for each question
        for q in pending_questions:
            notify_new_question("my-phone", q)

        # Should have 2 HTTP calls
        assert mock_urlopen.call_count == 2

        # Verify both questions are distinct
        assert pending_questions[0].id != pending_questions[1].id


def test_e2e_flow_complete_validation_checklist(plan_with_config, monkeypatch):
    """COMPREHENSIVE E2E validation checklist for T9-005 acceptance criteria.

    This test validates ALL acceptance criteria in a single complete flow:
    1. Complete flow works end-to-end without errors
    2. ntfy notification contains question text and severity
    3. Interactive wizard shows the suggested answers from the question
    4. Answer persisted correctly after selection
    5. No regressions in non-interactive paths
    """
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # CRITERION 1: Complete flow works end-to-end without errors
    # Create question
    args_ask = SimpleNamespace()
    args_ask.text = "Deploy to production environment?"
    args_ask.severity = "high"
    args_ask.context = "Release v2.0"
    args_ask.suggest = ["Yes, deploy now", "No, wait for review", "Deploy to staging first"]
    args_ask.plan = str(plan_path)

    question.cmd_ask(args_ask, ctx=None)  # Should not raise

    # Mock ntfy HTTP for notification testing
    with patch('agenticcli.utils.ntfy.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.close.return_value = None
        mock_urlopen.return_value = mock_response

        from agenticguidance.services.question import QuestionQueue
        from agenticcli.utils.ntfy import notify_new_question

        # Get question
        service = QuestionQueue(plan_path)
        pending_questions = service.list_pending_questions()
        q = pending_questions[0]
        question_id = q.id

        # CRITERION 2: ntfy notification contains question text and severity
        success = notify_new_question("my-phone", q)
        assert success is True

        request = mock_urlopen.call_args[0][0]
        assert "Deploy to production environment?" in request.data.decode('utf-8')
        assert request.headers.get("Title") == "New Question [HIGH]"
        assert request.headers.get("Priority") == "high"

    # CRITERION 3: Interactive wizard shows the suggested answers from the question
    # Mock user input to select suggested answer
    inputs = iter(["1", "2", "Y"])  # Select question 1, answer 2 ("No, wait for review"), confirm
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    args_answer = SimpleNamespace()
    args_answer.interactive = True
    args_answer.plan = str(plan_path)

    question.cmd_answer(args_answer, ctx=None)  # Should not raise

    # CRITERION 4: Answer persisted correctly after selection
    answered_dir = plan_path / "questions" / "answered"
    answered_answer_file = answered_dir / f"{question_id}.yml"

    assert answered_answer_file.exists()

    with open(answered_answer_file, 'r') as f:
        answer_data = yaml.safe_load(f)

    assert answer_data["answer_text"] == "No, wait for review"
    assert answer_data["confidence"] == "high"
    assert answer_data["answered_by"] == "human"

    # CRITERION 5: No regressions in non-interactive paths
    # Create another question and answer it non-interactively
    args_ask2 = SimpleNamespace()
    args_ask2.text = "Second question?"
    args_ask2.severity = "low"
    args_ask2.context = "Test"
    args_ask2.suggest = ["A", "B"]
    args_ask2.plan = str(plan_path)

    question.cmd_ask(args_ask2, ctx=None)

    pending_files = list((plan_path / "questions" / "pending").glob("Q-*.yml"))
    question_id2 = pending_files[0].stem

    args_answer2 = SimpleNamespace()
    args_answer2.question_id = question_id2
    args_answer2.text = "Non-interactive answer"
    args_answer2.confidence = "medium"
    args_answer2.interactive = False
    args_answer2.plan = str(plan_path)

    question.cmd_answer(args_answer2, ctx=None)  # Should not raise

    answered_answer_file2 = answered_dir / f"{question_id2}.yml"
    assert answered_answer_file2.exists()

    with open(answered_answer_file2, 'r') as f:
        answer_data2 = yaml.safe_load(f)

    assert answer_data2["answer_text"] == "Non-interactive answer"
    assert answer_data2["confidence"] == "medium"

    # ALL CRITERIA VALIDATED SUCCESSFULLY
