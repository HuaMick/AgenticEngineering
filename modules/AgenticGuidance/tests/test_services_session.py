"""Tests for session service."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-SES-001")

from agenticguidance.services.session import (
    SessionInfo,
    SessionResult,
    SessionService,
    SessionState,
)


class TestSessionState:
    """Tests for SessionState enum."""

    def test_state_values(self):
        """Test session state enum values."""
        assert SessionState.RUNNING.value == "running"
        assert SessionState.DETACHED.value == "detached"
        assert SessionState.DEAD.value == "dead"


class TestSessionInfo:
    """Tests for SessionInfo dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        session = SessionInfo(
            name="test-session",
            state=SessionState.RUNNING,
            created_at=1704067200.0,
            attached=True,
            worktree="/home/user/project",
            plan_folder="260126AT_test",
            windows=3,
            metadata={"key": "value"},
        )

        result = session.to_dict()

        assert result["name"] == "test-session"
        assert result["state"] == "running"
        assert result["created_at"] == 1704067200.0
        assert result["attached"] is True
        assert result["worktree"] == "/home/user/project"
        assert result["plan_folder"] == "260126AT_test"
        assert result["windows"] == 3
        assert result["metadata"] == {"key": "value"}

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "name": "test-session",
            "state": "running",
            "created_at": 1704067200.0,
            "attached": False,
            "worktree": "/path/to/worktree",
            "plan_folder": None,
            "windows": 2,
            "metadata": {},
        }

        session = SessionInfo.from_dict(data)

        assert session.name == "test-session"
        assert session.state == SessionState.RUNNING
        assert session.created_at == 1704067200.0
        assert session.attached is False

    def test_default_values(self):
        """Test default values for optional fields."""
        session = SessionInfo(
            name="minimal",
            state=SessionState.RUNNING,
            created_at=0,
        )

        assert session.attached is False
        assert session.worktree is None
        assert session.plan_folder is None
        assert session.windows == 1
        assert session.metadata == {}


class TestSessionResult:
    """Tests for SessionResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        session = SessionInfo(
            name="test",
            state=SessionState.RUNNING,
            created_at=0,
        )
        result = SessionResult(
            success=True,
            message="Session created",
            session=session,
        )

        assert result.success is True
        assert result.message == "Session created"
        assert result.session.name == "test"

    def test_failure_result(self):
        """Test failure result."""
        result = SessionResult(
            success=False,
            message="Session already exists",
        )

        assert result.success is False
        assert result.session is None


class TestSessionService:
    """Tests for SessionService class."""

    def test_init_creates_registry(self, tmp_path):
        """Test initialization creates registry file."""
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)

        assert registry_path.exists()
        data = json.loads(registry_path.read_text())
        assert "sessions" in data

    @patch("subprocess.run")
    def test_tmux_exists_returns_true(self, mock_run, tmp_path):
        """Test tmux exists check returns True when available."""
        mock_run.return_value = MagicMock(returncode=0)
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        result = service._tmux_exists()

        assert result is True

    @patch("subprocess.run")
    def test_tmux_exists_returns_false_on_error(self, mock_run, tmp_path):
        """Test tmux exists check returns False when not available."""
        mock_run.side_effect = FileNotFoundError()
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        result = service._tmux_exists()

        assert result is False

    @patch("subprocess.run")
    def test_get_tmux_sessions_parses_output(self, mock_run, tmp_path):
        """Test parsing of tmux session list."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="session1\nsession2\nsession3\n",
        )
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        sessions = service._get_tmux_sessions()

        assert sessions == ["session1", "session2", "session3"]

    @patch("subprocess.run")
    def test_get_tmux_sessions_handles_empty(self, mock_run, tmp_path):
        """Test handling of empty session list."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        sessions = service._get_tmux_sessions()

        assert sessions == []

    @patch.object(SessionService, "_tmux_exists", return_value=True)
    @patch.object(SessionService, "_get_tmux_sessions", return_value=[])
    @patch("subprocess.run")
    def test_create_session_success(self, mock_run, mock_sessions, mock_exists, tmp_path):
        """Test successful session creation."""
        mock_run.return_value = MagicMock(returncode=0)
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        result = service.create("new-session")

        assert result.success is True
        assert result.session is not None
        assert result.session.name == "new-session"

    @patch.object(SessionService, "_tmux_exists", return_value=True)
    @patch.object(SessionService, "_get_tmux_sessions", return_value=["existing-session"])
    def test_create_session_already_exists(self, mock_sessions, mock_exists, tmp_path):
        """Test creation fails for existing session."""
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        result = service.create("existing-session")

        assert result.success is False
        assert "already exists" in result.message

    @patch.object(SessionService, "_tmux_exists", return_value=False)
    def test_create_session_no_tmux(self, mock_exists, tmp_path):
        """Test creation fails when tmux not available."""
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        result = service.create("test")

        assert result.success is False
        assert "not installed" in result.message

    @patch.object(SessionService, "_tmux_exists", return_value=True)
    @patch.object(SessionService, "_get_tmux_sessions", return_value=["my-session"])
    def test_attach_session_success(self, mock_sessions, mock_exists, tmp_path):
        """Test successful session attach."""
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        result = service.attach("my-session")

        assert result.success is True
        assert result.data is not None
        assert "command" in result.data

    @patch.object(SessionService, "_tmux_exists", return_value=True)
    @patch.object(SessionService, "_get_tmux_sessions", return_value=[])
    def test_attach_session_not_found(self, mock_sessions, mock_exists, tmp_path):
        """Test attach fails for non-existent session."""
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        result = service.attach("nonexistent")

        assert result.success is False
        assert "not found" in result.message

    @patch.object(SessionService, "_get_tmux_sessions", return_value=["session1", "session2"])
    @patch.object(SessionService, "_is_session_attached", return_value=False)
    def test_list_sessions(self, mock_attached, mock_sessions, tmp_path):
        """Test listing sessions."""
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        sessions = service.list()

        assert len(sessions) == 2
        assert sessions[0].name == "session1"
        assert sessions[1].name == "session2"

    @patch.object(SessionService, "_get_tmux_sessions", return_value=["test-session"])
    @patch.object(SessionService, "_is_session_attached", return_value=True)
    def test_get_session(self, mock_attached, mock_sessions, tmp_path):
        """Test getting single session."""
        registry_path = tmp_path / "sessions.json"
        registry_path.write_text(json.dumps({
            "sessions": {
                "test-session": {
                    "name": "test-session",
                    "state": "running",
                    "created_at": 1704067200.0,
                }
            }
        }))

        service = SessionService(registry_path=registry_path)
        session = service.get("test-session")

        assert session is not None
        assert session.name == "test-session"
        assert session.attached is True

    def test_get_session_not_found(self, tmp_path):
        """Test getting non-existent session."""
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        session = service.get("nonexistent")

        assert session is None

    @patch.object(SessionService, "_tmux_exists", return_value=True)
    @patch.object(SessionService, "_get_tmux_sessions", return_value=["to-kill"])
    @patch.object(SessionService, "_is_session_attached", return_value=False)
    @patch("subprocess.run")
    def test_kill_session_success(
        self, mock_run, mock_attached, mock_sessions, mock_exists, tmp_path
    ):
        """Test successful session kill."""
        mock_run.return_value = MagicMock(returncode=0)
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        result = service.kill("to-kill")

        assert result.success is True
        assert "Killed" in result.message

    @patch.object(SessionService, "_tmux_exists", return_value=True)
    @patch.object(SessionService, "_get_tmux_sessions", return_value=["attached-session"])
    @patch.object(SessionService, "_is_session_attached", return_value=True)
    def test_kill_session_attached_no_force(
        self, mock_attached, mock_sessions, mock_exists, tmp_path
    ):
        """Test kill fails for attached session without force."""
        registry_path = tmp_path / "sessions.json"

        service = SessionService(registry_path=registry_path)
        result = service.kill("attached-session", force=False)

        assert result.success is False
        assert "attached clients" in result.message

    @pytest.mark.story("US-GDN-087")
    @patch.object(SessionService, "_get_tmux_sessions", return_value=["live"])
    def test_cleanup_dead_removes_stale(self, mock_sessions, tmp_path):
        """Test cleanup removes dead sessions from registry."""
        registry_path = tmp_path / "sessions.json"
        registry_path.write_text(json.dumps({
            "sessions": {
                "live": {"name": "live", "state": "running", "created_at": 0},
                "dead": {"name": "dead", "state": "running", "created_at": 0},
            }
        }))

        service = SessionService(registry_path=registry_path)
        removed = service.cleanup_dead()

        assert removed == 1
        data = json.loads(registry_path.read_text())
        assert "dead" not in data["sessions"]
        assert "live" in data["sessions"]

    @pytest.mark.story("US-GDN-084", "US-GDN-087")
    @patch.object(SessionService, "_get_tmux_sessions", return_value=["my-session"])
    def test_link_worktree(self, mock_sessions, tmp_path):
        """Test linking session to worktree."""
        registry_path = tmp_path / "sessions.json"
        registry_path.write_text(json.dumps({
            "sessions": {
                "my-session": {"name": "my-session", "state": "running", "created_at": 0}
            }
        }))

        service = SessionService(registry_path=registry_path)
        result = service.link_worktree("my-session", "/path/to/worktree")

        assert result.success is True
        data = json.loads(registry_path.read_text())
        assert data["sessions"]["my-session"]["worktree"] == "/path/to/worktree"

    @patch.object(SessionService, "_get_tmux_sessions", return_value=["my-session"])
    def test_link_plan(self, mock_sessions, tmp_path):
        """Test linking session to plan folder."""
        registry_path = tmp_path / "sessions.json"
        registry_path.write_text(json.dumps({
            "sessions": {
                "my-session": {"name": "my-session", "state": "running", "created_at": 0}
            }
        }))

        service = SessionService(registry_path=registry_path)
        result = service.link_plan("my-session", "260126AT_test")

        assert result.success is True
        data = json.loads(registry_path.read_text())
        assert data["sessions"]["my-session"]["plan_folder"] == "260126AT_test"
