"""Integration tests for question CLI commands.

Tests the question command group for managing question queues:
- question list
- question show
- question ask
- question answer
- question defer
"""

import json

import pytest

pytestmark = pytest.mark.integration


class TestQuestionAskCommand:
    """Integration tests for 'agentic question ask'."""

    @pytest.fixture
    def plan_with_questions_dir(self, temp_repo):
        """Create plan folder with questions directory."""
        plan_path = temp_repo / "docs" / "plans" / "live" / "260203QC_question_test"
        plan_path.mkdir(parents=True)

        # Create questions directory structure
        questions_dir = plan_path / "questions"
        questions_dir.mkdir()
        (questions_dir / "pending").mkdir()
        (questions_dir / "answered").mkdir()

        return plan_path

    def test_ask_creates_question(self, cli_runner, plan_with_questions_dir):
        """Test creating a new question."""
        result = cli_runner([
            "agent", "question", "ask",
            "What is the expected behavior?",
            "--plan", str(plan_with_questions_dir),
            "--severity", "high"
        ])

        assert result.returncode == 0
        assert "created" in result.stdout.lower() or "question" in result.stdout.lower()

        # Verify question file was created
        pending_dir = plan_with_questions_dir / "questions" / "pending"
        question_files = list(pending_dir.glob("Q-*.yml"))
        assert len(question_files) == 1

    def test_ask_with_default_severity(self, cli_runner, plan_with_questions_dir):
        """Test creating question with default medium severity."""
        result = cli_runner([
            "agent", "question", "ask",
            "Should we add this feature?",
            "--plan", str(plan_with_questions_dir)
        ])

        assert result.returncode == 0
        assert "created" in result.stdout.lower()

        # Verify severity is medium (default)
        pending_dir = plan_with_questions_dir / "questions" / "pending"
        question_files = list(pending_dir.glob("Q-*.yml"))
        assert len(question_files) == 1

        # Read and verify content
        import yaml
        content = yaml.safe_load(question_files[0].read_text())
        assert content["severity"] == "medium"

    def test_ask_with_json_output(self, cli_runner, plan_with_questions_dir):
        """Test creating question with JSON output."""
        result = cli_runner([
            "--json",
            "agent", "question", "ask",
            "Test question for JSON output",
            "--plan", str(plan_with_questions_dir),
            "--severity", "low"
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "id" in data
        assert data["text"] == "Test question for JSON output"
        assert data["severity"] == "low"
        assert data["status"] == "pending"

    def test_ask_with_invalid_plan_path_fails(self, cli_runner):
        """Test that ask with invalid plan path fails."""
        result = cli_runner([
            "agent", "question", "ask",
            "Test question",
            "--plan", "/nonexistent/path"
        ])

        assert result.returncode != 0
        assert "not exist" in result.stderr.lower() or "error" in result.stderr.lower()


class TestQuestionListCommand:
    """Integration tests for 'agentic question list'."""

    @pytest.fixture
    def plan_with_questions(self, temp_repo):
        """Create plan folder with sample questions."""
        import time
        import yaml

        plan_path = temp_repo / "docs" / "plans" / "live" / "260203QC_list_test"
        plan_path.mkdir(parents=True)

        # Create questions directory structure
        questions_dir = plan_path / "questions"
        pending_dir = questions_dir / "pending"
        answered_dir = questions_dir / "answered"
        pending_dir.mkdir(parents=True)
        answered_dir.mkdir(parents=True)

        # Create pending questions
        pending_q1 = {
            "id": "Q-20260203-100000-aaaa",
            "text": "What is the implementation approach?",
            "context": "Design phase",
            "severity": "high",
            "asked_by": "agent",
            "created_at": time.time() - 3600,
            "status": "pending"
        }
        (pending_dir / "Q-20260203-100000-aaaa.yml").write_text(yaml.dump(pending_q1))

        pending_q2 = {
            "id": "Q-20260203-110000-bbbb",
            "text": "Should we include tests?",
            "context": "Testing phase",
            "severity": "medium",
            "asked_by": "human",
            "created_at": time.time() - 1800,
            "status": "pending"
        }
        (pending_dir / "Q-20260203-110000-bbbb.yml").write_text(yaml.dump(pending_q2))

        # Create answered question
        answered_q = {
            "id": "Q-20260203-090000-cccc",
            "text": "What language should we use?",
            "context": "Initial planning",
            "severity": "blocking",
            "asked_by": "agent",
            "created_at": time.time() - 7200,
            "status": "answered",
            "answer": "Python is the best choice",
            "answered_at": time.time() - 5400,
            "answered_by": "human"
        }
        (answered_dir / "Q-20260203-090000-cccc_question.yml").write_text(yaml.dump(answered_q))

        return plan_path

    def test_list_pending_questions(self, cli_runner, plan_with_questions):
        """Test listing pending questions."""
        result = cli_runner([
            "plan", "question", "list",
            "--plan", str(plan_with_questions)
        ])

        assert result.returncode == 0
        # Rich table may truncate IDs; check for question text instead
        assert "implementation" in result.stdout.lower() or "Q-20260203-1" in result.stdout
        assert "Showing 2 questions" in result.stdout

    def test_list_answered_questions(self, cli_runner, plan_with_questions):
        """Test listing answered questions."""
        result = cli_runner([
            "plan", "question", "list",
            "--plan", str(plan_with_questions),
            "--status", "answered"
        ])

        assert result.returncode == 0
        assert "answered" in result.stdout.lower()
        assert "Showing 1 question" in result.stdout

    def test_list_all_questions(self, cli_runner, plan_with_questions):
        """Test listing all questions."""
        result = cli_runner([
            "plan", "question", "list",
            "--plan", str(plan_with_questions),
            "--status", "all"
        ])

        assert result.returncode == 0
        assert "Showing 3 questions" in result.stdout

    def test_list_with_json_output(self, cli_runner, plan_with_questions):
        """Test listing questions with JSON output."""
        result = cli_runner([
            "--json",
            "plan", "question", "list",
            "--plan", str(plan_with_questions)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "questions" in data
        assert data["count"] == 2  # Two pending questions
        assert len(data["questions"]) == 2


class TestQuestionShowCommand:
    """Integration tests for 'agentic question show'."""

    @pytest.fixture
    def plan_with_question(self, temp_repo):
        """Create plan folder with a single question."""
        import time
        import yaml

        plan_path = temp_repo / "docs" / "plans" / "live" / "260203QC_show_test"
        plan_path.mkdir(parents=True)

        questions_dir = plan_path / "questions"
        pending_dir = questions_dir / "pending"
        pending_dir.mkdir(parents=True)

        question = {
            "id": "Q-20260203-120000-dddd",
            "text": "How should we handle errors?",
            "context": "Error handling design",
            "severity": "high",
            "asked_by": "agent",
            "created_at": time.time(),
            "status": "pending"
        }
        (pending_dir / "Q-20260203-120000-dddd.yml").write_text(yaml.dump(question))

        return plan_path

    def test_show_question_details(self, cli_runner, plan_with_question):
        """Test showing question details."""
        result = cli_runner([
            "plan", "question", "show",
            "Q-20260203-120000-dddd",
            "--plan", str(plan_with_question)
        ])

        assert result.returncode == 0
        assert "Q-20260203-120000-dddd" in result.stdout
        assert "How should we handle errors?" in result.stdout
        assert "Error handling design" in result.stdout

    def test_show_with_json_output(self, cli_runner, plan_with_question):
        """Test showing question with JSON output."""
        result = cli_runner([
            "--json",
            "plan", "question", "show",
            "Q-20260203-120000-dddd",
            "--plan", str(plan_with_question)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == "Q-20260203-120000-dddd"
        assert data["text"] == "How should we handle errors?"
        assert data["severity"] == "high"

    def test_show_nonexistent_question(self, cli_runner, plan_with_question):
        """Test showing nonexistent question fails.

        Note: Using valid ID format but non-existent ID to test file not found.
        Invalid format would trigger ValueError before file check.
        """
        result = cli_runner([
            "plan", "question", "show",
            "Q-20260203-999999-abcd",
            "--plan", str(plan_with_question)
        ])

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()


class TestQuestionAnswerCommand:
    """Integration tests for 'agentic question answer'."""

    @pytest.fixture
    def plan_with_pending_question(self, temp_repo):
        """Create plan folder with a pending question."""
        import time
        import yaml

        plan_path = temp_repo / "docs" / "plans" / "live" / "260203QC_answer_test"
        plan_path.mkdir(parents=True)

        questions_dir = plan_path / "questions"
        pending_dir = questions_dir / "pending"
        answered_dir = questions_dir / "answered"
        pending_dir.mkdir(parents=True)
        answered_dir.mkdir(parents=True)

        question = {
            "id": "Q-20260203-130000-eeee",
            "text": "What testing framework should we use?",
            "context": "Testing setup",
            "severity": "medium",
            "asked_by": "agent",
            "created_at": time.time(),
            "status": "pending"
        }
        (pending_dir / "Q-20260203-130000-eeee.yml").write_text(yaml.dump(question))

        return plan_path

    def test_answer_question(self, cli_runner, plan_with_pending_question):
        """Test answering a question."""
        result = cli_runner([
            "plan", "question", "answer",
            "Q-20260203-130000-eeee",
            "--text", "We should use pytest for testing",
            "--plan", str(plan_with_pending_question)
        ])

        assert result.returncode == 0
        assert "answered" in result.stdout.lower()

        # Verify question moved to answered directory
        answered_dir = plan_with_pending_question / "questions" / "answered"
        assert (answered_dir / "Q-20260203-130000-eeee_question.yml").exists()
        assert (answered_dir / "Q-20260203-130000-eeee.yml").exists()

        # Verify question removed from pending
        pending_dir = plan_with_pending_question / "questions" / "pending"
        assert not (pending_dir / "Q-20260203-130000-eeee.yml").exists()

    def test_answer_with_confidence(self, cli_runner, plan_with_pending_question):
        """Test answering with confidence level."""
        result = cli_runner([
            "plan", "question", "answer",
            "Q-20260203-130000-eeee",
            "--text", "Use pytest",
            "--confidence", "high",
            "--plan", str(plan_with_pending_question)
        ])

        assert result.returncode == 0
        assert "answered" in result.stdout.lower()

    def test_answer_with_json_output(self, cli_runner, plan_with_pending_question):
        """Test answering question with JSON output."""
        result = cli_runner([
            "--json",
            "plan", "question", "answer",
            "Q-20260203-130000-eeee",
            "--text", "Pytest is recommended",
            "--plan", str(plan_with_pending_question)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "question" in data
        assert "answer" in data
        assert data["question"]["status"] == "answered"

    def test_answer_nonexistent_question(self, cli_runner, plan_with_pending_question):
        """Test answering nonexistent question fails."""
        result = cli_runner([
            "plan", "question", "answer",
            "Q-20260203-999999-abcd",
            "--text", "Some answer",
            "--plan", str(plan_with_pending_question)
        ])

        assert result.returncode != 0
        # Can be either "not found" or validation error
        assert "not found" in result.stderr.lower() or "failed" in result.stderr.lower()


class TestQuestionDeferCommand:
    """Integration tests for 'agentic question defer'."""

    @pytest.fixture
    def plan_with_question_to_defer(self, temp_repo):
        """Create plan folder with a question to defer."""
        import time
        import yaml

        plan_path = temp_repo / "docs" / "plans" / "live" / "260203QC_defer_test"
        plan_path.mkdir(parents=True)

        questions_dir = plan_path / "questions"
        pending_dir = questions_dir / "pending"
        pending_dir.mkdir(parents=True)

        question = {
            "id": "Q-20260203-140000-ffff",
            "text": "Should we optimize performance now?",
            "context": "Performance optimization",
            "severity": "low",
            "asked_by": "agent",
            "created_at": time.time(),
            "status": "pending"
        }
        (pending_dir / "Q-20260203-140000-ffff.yml").write_text(yaml.dump(question))

        return plan_path

    def test_defer_question(self, cli_runner, plan_with_question_to_defer):
        """Test deferring a question."""
        result = cli_runner([
            "agent", "question", "defer",
            "Q-20260203-140000-ffff",
            "--plan", str(plan_with_question_to_defer)
        ])

        assert result.returncode == 0
        assert "deferred" in result.stdout.lower()

        # Verify question still exists in pending but status changed
        import yaml
        pending_dir = plan_with_question_to_defer / "questions" / "pending"
        question_file = pending_dir / "Q-20260203-140000-ffff.yml"
        assert question_file.exists()

        content = yaml.safe_load(question_file.read_text())
        assert content["status"] == "deferred"

    def test_defer_with_json_output(self, cli_runner, plan_with_question_to_defer):
        """Test deferring question with JSON output."""
        result = cli_runner([
            "--json",
            "agent", "question", "defer",
            "Q-20260203-140000-ffff",
            "--plan", str(plan_with_question_to_defer)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "deferred"

    def test_defer_nonexistent_question(self, cli_runner, plan_with_question_to_defer):
        """Test deferring nonexistent question fails."""
        result = cli_runner([
            "agent", "question", "defer",
            "Q-20260203-999999-abcd",
            "--plan", str(plan_with_question_to_defer)
        ])

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()
