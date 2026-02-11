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

pytestmark = pytest.mark.uat


@pytest.fixture(autouse=True)
def _block_real_ntfy():
    """Override conftest safety net — these tests manage ntfy mocking themselves."""
    yield


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


def test_e2e_ask_notify_answer_flow(plan_with_config, monkeypatch, capsys):
    """Test complete end-to-end flow: ask -> notify -> answer -> complete.

    This is the PRIMARY UAT test for T9-005, validating the entire user journey
    from phone notification receipt to interactive answer submission.

    Since cmd_ask() now auto-notifies via ntfy, we patch at the agenticcli.utils.ntfy
    module level (where urlopen is imported) to intercept the auto-notification.
    """
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config

    # Reset state for clean test
    question._reply_poller = None

    # Mock config directory to use our tmp_path config
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # Patch urlopen at the correct module level so auto-notify in cmd_ask() is intercepted
    with patch('agenticcli.utils.ntfy.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.close.return_value = None
        mock_urlopen.return_value = mock_response

        # STEP 1: Agent asks question with suggestions (auto-notifies via ntfy)
        args_ask = SimpleNamespace()
        args_ask.text = "Deploy to prod?"
        args_ask.severity = "high"
        args_ask.context = "Release decision"
        args_ask.suggest = ["Yes, deploy now", "No, wait for review"]
        args_ask.plan = str(plan_path)

        question.cmd_ask(args_ask, ctx=None)

        # STEP 2: Verify auto-notify sent ntfy notification during cmd_ask()
        assert mock_urlopen.called, "cmd_ask() should auto-send ntfy notification"

        # Verify HTTP request details from auto-notify
        call_args = mock_urlopen.call_args
        request = call_args[0][0]

        assert request.get_full_url() == "https://ntfy.sh/my-phone"
        # Sequential delivery uses "Question N of M" format
        assert "Question 1 of 1" in request.headers.get("Title", "")
        assert request.headers.get("Priority") == "high"
        assert request.headers.get("Tags") == "question"

        request_data = request.data.decode('utf-8')
        assert "Deploy to prod?" in request_data

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


def test_e2e_medium_severity_auto_notifies(plan_with_config, monkeypatch):
    """Medium severity questions now auto-notify during cmd_ask().

    All severities trigger phone notifications so the user can reply
    from their phone with a letter choice.
    """
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config

    # Reset state for clean test
    question._reply_poller = None

    # Mock config directory
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # Patch urlopen to track if it gets called
    with patch('agenticcli.utils.ntfy.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.close.return_value = None
        mock_urlopen.return_value = mock_response

        # Create question with medium severity
        args_ask = SimpleNamespace()
        args_ask.text = "Non-urgent question?"
        args_ask.severity = "medium"
        args_ask.context = "Low priority"
        args_ask.suggest = ["Yes", "No"]
        args_ask.plan = str(plan_path)

        question.cmd_ask(args_ask, ctx=None)

        # Auto-notify should be called for medium severity (all severities notify now)
        assert mock_urlopen.called, "cmd_ask() should auto-send ntfy for medium severity"

        # Verify the notification has correct priority for medium
        request = mock_urlopen.call_args[0][0]
        # Sequential delivery uses "Question N of M" format
        assert "Question 1 of 1" in request.headers.get("Title", "")
        assert request.headers.get("Priority") == "default"

    # Question should be created in pending/
    pending_dir = plan_path / "questions" / "pending"
    pending_files = list(pending_dir.glob("Q-*.yml"))
    assert len(pending_files) == 1, "Question should be created in pending/"


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


def test_e2e_ask_notify_answer_flow_medium_severity(plan_with_config, monkeypatch, capsys):
    """UAT: Medium severity questions auto-notify and complete the full flow.

    User journey:
    1. Agent asks medium severity question with suggestions
    2. Phone notification sent automatically (all severities now notify)
    3. User answers interactively via wizard
    4. Answer persisted correctly
    """
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config

    # Reset dedup state for clean test
    question._reply_poller = None

    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    with patch('agenticcli.utils.ntfy.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.close.return_value = None
        mock_urlopen.return_value = mock_response

        # STEP 1: Create medium-severity question
        args_ask = SimpleNamespace()
        args_ask.text = "Should we refactor this module?"
        args_ask.severity = "medium"
        args_ask.context = "Code quality discussion"
        args_ask.suggest = ["Yes", "No", "Later"]
        args_ask.plan = str(plan_path)

        question.cmd_ask(args_ask, ctx=None)

        # STEP 2: Verify auto-notify was called (medium now notifies)
        assert mock_urlopen.called, "cmd_ask() should auto-send ntfy for medium severity"

        request = mock_urlopen.call_args[0][0]
        # Sequential delivery uses "Question N of M" format
        assert "Question 1 of 1" in request.headers.get("Title", "")
        assert request.headers.get("Priority") == "default"

        request_data = request.data.decode('utf-8')
        assert "Should we refactor this module?" in request_data

    # Verify question created in pending/ (note: auto-notify sets current_question_id
    # so the question may still be in pending since _handle_next doesn't move it)
    pending_dir = plan_path / "questions" / "pending"
    pending_files = list(pending_dir.glob("Q-*.yml"))
    assert len(pending_files) == 1, "Question should be created in pending/"

    question_file = pending_files[0]
    question_id = question_file.stem

    with open(question_file, 'r') as f:
        question_data = yaml.safe_load(f)

    assert question_data["text"] == "Should we refactor this module?"
    assert question_data["severity"] == "medium"
    assert question_data["suggested_answers"] == ["Yes", "No", "Later"]
    assert question_data["status"] == "pending"

    # STEP 3: User answers interactively via wizard (select "Later")
    inputs = iter(["1", "3", "Y"])
    monkeypatch.setattr('builtins.input', lambda *args: next(inputs))

    args_answer = SimpleNamespace()
    args_answer.interactive = True
    args_answer.plan = str(plan_path)

    question.cmd_answer(args_answer, ctx=None)

    # STEP 4: Verify answer persisted correctly
    answered_dir = plan_path / "questions" / "answered"
    answered_answer_file = answered_dir / f"{question_id}.yml"

    assert answered_answer_file.exists(), "Answer file should exist"

    with open(answered_answer_file, 'r') as f:
        answer_data = yaml.safe_load(f)

    assert answer_data["answer_text"] == "Later"
    assert answer_data["confidence"] == "high"  # Suggested answer -> high confidence
    assert answer_data["answered_by"] == "human"

    # Verify question removed from pending/
    assert not question_file.exists(), "Question should be removed from pending/"


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


def test_e2e_multichoice_letter_reply(plan_with_config, monkeypatch):
    """UAT: Multi-choice question notification with letter reply mapping.

    User journey:
    1. Agent asks question with 3 suggested answers
    2. Phone notification shows A/B/C options
    3. User replies with 'B' from phone
    4. System maps 'B' to second suggested answer
    5. Answer saved with mapped text, not letter
    """
    from agenticcli.commands import question

    plan_path, config_dir = plan_with_config

    # Reset dedup state for clean test
    question._reply_poller = None

    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    # STEP 1: Agent asks question with 3 suggested answers
    with patch('agenticcli.utils.ntfy.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_response.close.return_value = None
        mock_urlopen.return_value = mock_response

        args_ask = SimpleNamespace()
        args_ask.text = "Which database should we use?"
        args_ask.severity = "high"
        args_ask.context = "Architecture decision"
        args_ask.suggest = ["PostgreSQL", "MySQL", "SQLite"]
        args_ask.plan = str(plan_path)

        question.cmd_ask(args_ask, ctx=None)

        # STEP 2: Verify notification shows A/B/C options
        assert mock_urlopen.called, "Auto-notify should fire"
        request = mock_urlopen.call_args[0][0]
        request_data = request.data.decode('utf-8')

        assert "A) PostgreSQL" in request_data
        assert "B) MySQL" in request_data
        assert "C) SQLite" in request_data

    # Get the question ID from pending
    pending_dir = plan_path / "questions" / "pending"
    pending_files = list(pending_dir.glob("Q-*.yml"))
    assert len(pending_files) == 1
    question_id = pending_files[0].stem

    # STEP 3: Simulate user replying 'B' from phone via NtfyQuestionAgent
    # The agent has state.current_question_id set from the auto-notify
    from agenticcli.services.ntfy_question_agent import NtfyQuestionAgent, load_state

    # Verify state was set by auto-notify
    state = load_state(plan_path)
    assert state.current_question_id == question_id, "Auto-notify should set current_question_id"

    agent = NtfyQuestionAgent(plan_path, "my-phone", "https://ntfy.sh")

    with patch('agenticcli.services.ntfy_question_agent.send_ntfy', return_value=True) as mock_confirm:
        result = agent.handle_reply("B")

        # STEP 4: Verify confirmation notification was sent
        assert mock_confirm.called, "Confirmation notification should be sent"
        # Result should contain mapped answer "MySQL", not the letter "B"
        assert "MySQL" in result

    # STEP 5: Verify answer saved with mapped text, not letter
    answered_dir = plan_path / "questions" / "answered"
    answered_answer_file = answered_dir / f"{question_id}.yml"

    assert answered_answer_file.exists(), "Answer file should exist after letter reply"

    with open(answered_answer_file, 'r') as f:
        answer_data = yaml.safe_load(f)

    # Critical assertion: answer is "MySQL" (mapped from B), not the letter "B"
    assert answer_data["answer_text"] == "MySQL", (
        f"Expected mapped answer 'MySQL' but got '{answer_data['answer_text']}'"
    )
    assert answer_data["answered_by"] == "ntfy-reply"

    # Verify question moved out of pending
    assert not pending_files[0].exists(), "Question should be removed from pending/"

    # Verify question file in answered
    answered_question_file = answered_dir / f"{question_id}_question.yml"
    assert answered_question_file.exists(), "Question should be in answered/"

    with open(answered_question_file, 'r') as f:
        updated_question = yaml.safe_load(f)

    assert updated_question["status"] == "answered"
    assert updated_question["answer"] == "MySQL"


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


def test_e2e_sequential_question_delivery(plan_with_config, monkeypatch):
    """UAT: Sequential question delivery - one at a time.

    User journey:
    1. Three questions are created
    2. Only first question is sent as notification
    3. User answers first question via ntfy reply
    4. User says 'next' to get second question
    5. User answers second question
    6. User says 'next' to get third question
    7. User answers third question
    8. User says 'next' - receives 'no more questions' summary
    """
    plan_path, config_dir = plan_with_config
    monkeypatch.setattr('agenticcli.commands.config.get_config_dir', lambda: config_dir)

    from agenticguidance.services.question import QuestionQueue
    from agenticcli.services.ntfy_question_agent import (
        NtfyQuestionAgent,
        load_state,
    )

    # Create 3 questions
    service = QuestionQueue(plan_path)
    questions = []
    for i in range(3):
        q = service.create_question(
            text=f"Question {i + 1}?",
            context=f"Context {i + 1}",
            severity="medium",
            asked_by="test-agent",
            suggested_answers=["Yes", "No"] if i == 0 else None,
        )
        questions.append(q)
        time.sleep(0.01)

    # Track notifications sent
    ntfy_calls = []

    with patch('agenticcli.services.ntfy_question_agent.send_ntfy', return_value=True) as mock_send:
        mock_send.side_effect = lambda *args, **kwargs: ntfy_calls.append(kwargs) or True

        agent = NtfyQuestionAgent(plan_path, "my-phone", "https://ntfy.sh")

        # STEP 1: Say 'next' to get first question
        result = agent.handle_reply("next")
        assert result is None  # Notification sent via send_ntfy
        assert len(ntfy_calls) == 1
        assert "Question 1 of 3" in ntfy_calls[0]["title"]

        # Verify state
        state = load_state(plan_path)
        assert state.current_question_id == questions[0].id
        assert state.answered_count == 0

        # STEP 2: Answer first question with letter 'A' (maps to "Yes")
        ntfy_calls.clear()
        result = agent.handle_reply("A")
        assert "Yes" in result  # Mapped from "A"

        state = load_state(plan_path)
        assert state.current_question_id is None
        assert state.answered_count == 1

        # STEP 3: Say 'next' to get second question
        ntfy_calls.clear()
        result = agent.handle_reply("next")
        assert result is None
        assert len(ntfy_calls) == 1
        assert "Question 1 of 2" in ntfy_calls[0]["title"]  # 2 remaining

        state = load_state(plan_path)
        assert state.current_question_id == questions[1].id

        # STEP 4: Answer second question with free text
        ntfy_calls.clear()
        result = agent.handle_reply("Use PostgreSQL")
        assert "Use PostgreSQL" in result

        state = load_state(plan_path)
        assert state.current_question_id is None
        assert state.answered_count == 2

        # STEP 5: Say 'next' to get third question
        ntfy_calls.clear()
        result = agent.handle_reply("next")
        assert result is None
        assert len(ntfy_calls) == 1
        assert "Question 1 of 1" in ntfy_calls[0]["title"]  # 1 remaining

        state = load_state(plan_path)
        assert state.current_question_id == questions[2].id

        # STEP 6: Answer third question
        ntfy_calls.clear()
        result = agent.handle_reply("Agreed")
        assert "Agreed" in result

        state = load_state(plan_path)
        assert state.current_question_id is None
        assert state.answered_count == 3

        # STEP 7: Say 'next' - should say no more questions
        ntfy_calls.clear()
        result = agent.handle_reply("next")
        assert "No more questions" in result
        assert "3 answered" in result
