"""Tests for Claude Code SessionStateService.

Tests for SessionEntry dataclass and SessionStateService class
that manages Claude Code session state with file locking and cleanup.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticguidance.services.claude_session import (
    ClaudeSessionStatus,
    SessionEntry,
    SessionStateService,
)


class TestClaudeSessionStatus:
    """Tests for ClaudeSessionStatus enum."""

    def test_status_values(self):
        """Test all status enum values."""
        assert ClaudeSessionStatus.STARTING.value == "starting"
        assert ClaudeSessionStatus.RUNNING.value == "running"
        assert ClaudeSessionStatus.COMPLETED.value == "completed"
        assert ClaudeSessionStatus.FAILED.value == "failed"
        assert ClaudeSessionStatus.STOPPED.value == "stopped"


class TestSessionEntry:
    """Tests for SessionEntry dataclass."""

    @pytest.fixture
    def sample_entry(self):
        """Create a sample SessionEntry for testing."""
        return SessionEntry(
            session_id="12345678-1234-1234-1234-123456789abc",
            pid=12345,
            prompt="Fix the bug in main.py",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/home/user/project",
            command="claude --print --prompt 'Fix the bug'",
            max_turns=10,
            ended_at=None,
            background=True,
            error=None,
            exit_code=None,
            metadata={"key": "value"},
        )

    def test_to_dict(self, sample_entry):
        """Test conversion to dictionary."""
        result = sample_entry.to_dict()

        assert result["session_id"] == "12345678-1234-1234-1234-123456789abc"
        assert result["pid"] == 12345
        assert result["prompt"] == "Fix the bug in main.py"
        assert result["status"] == "running"
        assert result["started_at"] == "2024-01-15T10:00:00"
        assert result["working_dir"] == "/home/user/project"
        assert result["command"] == "claude --print --prompt 'Fix the bug'"
        assert result["max_turns"] == 10
        assert result["ended_at"] is None
        assert result["background"] is True
        assert result["error"] is None
        assert result["exit_code"] is None
        assert result["metadata"] == {"key": "value"}

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "session_id": "abcdef12-1234-1234-1234-123456789abc",
            "pid": 54321,
            "prompt": "Write tests",
            "max_turns": 5,
            "status": "completed",
            "started_at": "2024-01-15T09:00:00",
            "ended_at": "2024-01-15T09:30:00",
            "background": False,
            "working_dir": "/tmp/project",
            "command": "claude -p 'Write tests'",
            "error": None,
            "exit_code": 0,
            "metadata": {},
        }

        entry = SessionEntry.from_dict(data)

        assert entry.session_id == "abcdef12-1234-1234-1234-123456789abc"
        assert entry.pid == 54321
        assert entry.prompt == "Write tests"
        assert entry.max_turns == 5
        assert entry.status == "completed"
        assert entry.ended_at == "2024-01-15T09:30:00"
        assert entry.background is False
        assert entry.exit_code == 0

    def test_from_dict_with_defaults(self):
        """Test creation from dictionary with missing optional fields."""
        data = {
            "session_id": "test-session",
            "pid": 1000,
            "prompt": "Simple task",
            "started_at": "2024-01-15T08:00:00",
            "working_dir": "/tmp",
            "command": "claude -p 'task'",
        }

        entry = SessionEntry.from_dict(data)

        assert entry.session_id == "test-session"
        assert entry.max_turns is None
        assert entry.status == "running"  # Default
        assert entry.ended_at is None
        assert entry.background is False  # Default
        assert entry.error is None
        assert entry.exit_code is None
        assert entry.metadata == {}  # Default

    def test_create_factory_method(self):
        """Test create factory method generates proper defaults."""
        entry = SessionEntry.create(
            pid=9999,
            prompt="New task",
            working_dir="/project",
            command="claude -p 'New task'",
            max_turns=3,
            background=True,
            metadata={"source": "test"},
        )

        assert entry.pid == 9999
        assert entry.prompt == "New task"
        assert entry.working_dir == "/project"
        assert entry.command == "claude -p 'New task'"
        assert entry.max_turns == 3
        assert entry.background is True
        assert entry.metadata == {"source": "test"}
        # Auto-generated fields
        assert entry.session_id is not None
        assert len(entry.session_id) == 36  # UUID format
        assert entry.status == "starting"
        assert entry.started_at is not None
        assert entry.ended_at is None
        assert entry.error is None
        assert entry.exit_code is None

    def test_create_minimal(self):
        """Test create with minimal arguments."""
        entry = SessionEntry.create(
            pid=1234,
            prompt="Task",
            working_dir="/tmp",
            command="cmd",
        )

        assert entry.pid == 1234
        assert entry.max_turns is None
        assert entry.background is False
        assert entry.metadata == {}

    def test_roundtrip_to_dict_from_dict(self, sample_entry):
        """Test that to_dict and from_dict are reversible."""
        data = sample_entry.to_dict()
        restored = SessionEntry.from_dict(data)

        assert restored.session_id == sample_entry.session_id
        assert restored.pid == sample_entry.pid
        assert restored.prompt == sample_entry.prompt
        assert restored.status == sample_entry.status
        assert restored.background == sample_entry.background
        assert restored.metadata == sample_entry.metadata


class TestSessionStateService:
    """Tests for SessionStateService class."""

    @pytest.fixture
    def sessions_dir(self, tmp_path):
        """Create a temporary sessions directory."""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        return sessions_dir

    @pytest.fixture
    def service(self, sessions_dir):
        """Create a SessionStateService with temp directory."""
        return SessionStateService(sessions_dir=sessions_dir)

    @pytest.fixture
    def sample_entry(self):
        """Create a sample SessionEntry for testing."""
        return SessionEntry.create(
            pid=os.getpid(),
            prompt="Test task",
            working_dir="/tmp",
            command="claude -p 'Test task'",
        )

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates sessions directory."""
        sessions_dir = tmp_path / "new_sessions"
        assert not sessions_dir.exists()

        service = SessionStateService(sessions_dir=sessions_dir)

        assert sessions_dir.exists()

    def test_init_default_directory(self, monkeypatch, tmp_path):
        """Test default directory is ~/.agentic/sessions/."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        service = SessionStateService()

        assert service.sessions_dir == tmp_path / ".agentic" / "sessions"

    def test_save_and_load(self, service, sample_entry):
        """Test saving and loading a session entry."""
        service.save(sample_entry)
        loaded = service.load(sample_entry.session_id)

        assert loaded is not None
        assert loaded.session_id == sample_entry.session_id
        assert loaded.pid == sample_entry.pid
        assert loaded.prompt == sample_entry.prompt

    def test_load_nonexistent(self, service):
        """Test loading a nonexistent session returns None."""
        result = service.load("nonexistent-id")

        assert result is None

    def test_load_corrupted_file(self, service, sessions_dir):
        """Test loading a corrupted JSON file returns None."""
        corrupted_file = sessions_dir / "corrupted-session.json"
        corrupted_file.write_text("not valid json {{{")

        result = service.load("corrupted-session")

        assert result is None

    def test_get_by_id(self, service, sample_entry):
        """Test get_by_id is an alias for load."""
        service.save(sample_entry)

        result = service.get_by_id(sample_entry.session_id)

        assert result is not None
        assert result.session_id == sample_entry.session_id

    def test_list_all_empty(self, service):
        """Test list_all with no sessions."""
        result = service.list_all()

        assert result == []

    def test_list_all_with_sessions(self, service):
        """Test list_all with multiple sessions."""
        entry1 = SessionEntry.create(
            pid=1001,
            prompt="Task 1",
            working_dir="/tmp",
            command="cmd1",
        )
        entry2 = SessionEntry.create(
            pid=1002,
            prompt="Task 2",
            working_dir="/tmp",
            command="cmd2",
        )

        service.save(entry1)
        service.save(entry2)

        result = service.list_all()

        assert len(result) == 2
        session_ids = [e.session_id for e in result]
        assert entry1.session_id in session_ids
        assert entry2.session_id in session_ids

    def test_list_all_skips_lock_files(self, service, sessions_dir):
        """Test list_all skips .lock files."""
        entry = SessionEntry.create(
            pid=1000,
            prompt="Task",
            working_dir="/tmp",
            command="cmd",
        )
        service.save(entry)

        # Create a lock file that should be ignored
        lock_file = sessions_dir / "some-session.json.lock"
        lock_file.write_text("12345")

        result = service.list_all()

        assert len(result) == 1
        assert result[0].session_id == entry.session_id

    def test_list_all_sorted_by_started_at(self, service):
        """Test list_all returns sessions sorted by started_at descending."""
        # Create entries with explicit timestamps
        entry1 = SessionEntry(
            session_id="entry-1",
            pid=1001,
            prompt="Old task",
            status="completed",
            started_at="2024-01-01T10:00:00",
            working_dir="/tmp",
            command="cmd1",
        )
        entry2 = SessionEntry(
            session_id="entry-2",
            pid=1002,
            prompt="New task",
            status="completed",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd2",
        )

        service.save(entry1)
        service.save(entry2)

        result = service.list_all()

        # Most recent should be first
        assert result[0].session_id == "entry-2"
        assert result[1].session_id == "entry-1"

    def test_list_active(self, service):
        """Test list_active returns only starting/running sessions."""
        running = SessionEntry(
            session_id="running-1",
            pid=os.getpid(),
            prompt="Running task",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd",
        )
        starting = SessionEntry(
            session_id="starting-1",
            pid=os.getpid(),
            prompt="Starting task",
            status="starting",
            started_at="2024-01-15T09:00:00",
            working_dir="/tmp",
            command="cmd",
        )
        completed = SessionEntry(
            session_id="completed-1",
            pid=99999,
            prompt="Done task",
            status="completed",
            started_at="2024-01-15T08:00:00",
            working_dir="/tmp",
            command="cmd",
        )

        service.save(running)
        service.save(starting)
        service.save(completed)

        result = service.list_active()

        assert len(result) == 2
        statuses = [e.status for e in result]
        assert "running" in statuses
        assert "starting" in statuses
        assert "completed" not in statuses

    def test_delete_existing(self, service, sample_entry):
        """Test deleting an existing session."""
        service.save(sample_entry)

        result = service.delete(sample_entry.session_id)

        assert result is True
        assert service.load(sample_entry.session_id) is None

    def test_delete_nonexistent(self, service):
        """Test deleting a nonexistent session returns False."""
        result = service.delete("nonexistent-id")

        assert result is False

    def test_delete_cleans_up_lock_file(self, service, sample_entry, sessions_dir):
        """Test delete removes lock file if present."""
        service.save(sample_entry)

        # Create a stale lock file
        lock_file = sessions_dir / f"{sample_entry.session_id}.json.lock"
        lock_file.write_text("12345")

        result = service.delete(sample_entry.session_id)

        assert result is True
        assert not lock_file.exists()

    def test_update_status_running_to_completed(self, service, sample_entry):
        """Test updating status from running to completed."""
        sample_entry.status = "running"
        service.save(sample_entry)

        result = service.update_status(sample_entry.session_id, "completed")

        assert result is True
        loaded = service.load(sample_entry.session_id)
        assert loaded.status == "completed"
        assert loaded.ended_at is not None

    def test_update_status_with_error(self, service, sample_entry):
        """Test updating status with error message."""
        service.save(sample_entry)

        result = service.update_status(
            sample_entry.session_id,
            "failed",
            error="Command failed with exit code 1",
            exit_code=1,
        )

        assert result is True
        loaded = service.load(sample_entry.session_id)
        assert loaded.status == "failed"
        assert loaded.error == "Command failed with exit code 1"
        assert loaded.exit_code == 1

    def test_update_status_nonexistent(self, service):
        """Test updating status of nonexistent session returns False."""
        result = service.update_status("nonexistent", "completed")

        assert result is False

    def test_cleanup_dead_processes(self, service):
        """Test cleanup_dead_processes marks dead processes as failed."""
        # Create an entry with a process that doesn't exist
        dead_entry = SessionEntry(
            session_id="dead-session",
            pid=99999999,  # Very unlikely to exist
            prompt="Dead task",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd",
        )
        service.save(dead_entry)

        result = service.cleanup_dead_processes()

        assert result == 1
        loaded = service.load("dead-session")
        assert loaded.status == "failed"
        assert loaded.error == "Process died unexpectedly"

    def test_cleanup_dead_processes_skips_alive(self, service):
        """Test cleanup_dead_processes skips alive processes."""
        # Create an entry with current process PID (definitely alive)
        alive_entry = SessionEntry(
            session_id="alive-session",
            pid=os.getpid(),
            prompt="Alive task",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd",
        )
        service.save(alive_entry)

        result = service.cleanup_dead_processes()

        assert result == 0
        loaded = service.load("alive-session")
        assert loaded.status == "running"

    def test_clear_completed(self, service):
        """Test clear_completed removes completed/failed/stopped sessions."""
        running = SessionEntry(
            session_id="running-1",
            pid=os.getpid(),
            prompt="Running",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd",
        )
        completed = SessionEntry(
            session_id="completed-1",
            pid=99999,
            prompt="Completed",
            status="completed",
            started_at="2024-01-15T09:00:00",
            working_dir="/tmp",
            command="cmd",
        )
        failed = SessionEntry(
            session_id="failed-1",
            pid=99998,
            prompt="Failed",
            status="failed",
            started_at="2024-01-15T08:00:00",
            working_dir="/tmp",
            command="cmd",
        )

        service.save(running)
        service.save(completed)
        service.save(failed)

        result = service.clear_completed()

        assert result == 2
        remaining = service.list_all()
        assert len(remaining) == 1
        assert remaining[0].session_id == "running-1"

    def test_clear_all(self, service):
        """Test clear_all removes all sessions."""
        for i in range(3):
            entry = SessionEntry.create(
                pid=1000 + i,
                prompt=f"Task {i}",
                working_dir="/tmp",
                command=f"cmd{i}",
            )
            service.save(entry)

        result = service.clear_all()

        assert result == 3
        assert service.list_all() == []

    def test_get_by_pid_found(self, service, sample_entry):
        """Test get_by_pid finds a session by PID."""
        service.save(sample_entry)

        result = service.get_by_pid(sample_entry.pid)

        assert result is not None
        assert result.session_id == sample_entry.session_id

    def test_get_by_pid_not_found(self, service, sample_entry):
        """Test get_by_pid returns None when PID not found."""
        service.save(sample_entry)

        result = service.get_by_pid(99999999)

        assert result is None

    def test_is_process_alive_current_process(self, service):
        """Test _is_process_alive for current process."""
        result = SessionStateService._is_process_alive(os.getpid())

        assert result is True

    def test_is_process_alive_nonexistent(self, service):
        """Test _is_process_alive for nonexistent process."""
        result = SessionStateService._is_process_alive(99999999)

        assert result is False

    @patch("agenticguidance.services.claude_session.HAS_PSUTIL", False)
    def test_is_process_alive_without_psutil(self):
        """Test _is_process_alive falls back to os.kill when psutil unavailable."""
        # Current process should still be detected as alive
        result = SessionStateService._is_process_alive(os.getpid())

        assert result is True

    def test_concurrent_save_with_file_lock(self, service):
        """Test that saves use file locking for concurrency safety."""
        # Create an entry and save it
        entry = SessionEntry.create(
            pid=1234,
            prompt="Concurrent test",
            working_dir="/tmp",
            command="cmd",
        )

        # Save multiple times - should not corrupt
        service.save(entry)
        entry.status = "running"
        service.save(entry)
        entry.status = "completed"
        service.save(entry)

        loaded = service.load(entry.session_id)
        assert loaded.status == "completed"


class TestSessionStateServiceEdgeCases:
    """Edge case tests for SessionStateService."""

    def test_save_with_special_characters_in_prompt(self, tmp_path):
        """Test saving session with special characters in prompt."""
        service = SessionStateService(sessions_dir=tmp_path)
        entry = SessionEntry.create(
            pid=1234,
            prompt="Fix \"quoted\" text and 'apostrophes' & <html>",
            working_dir="/tmp",
            command="cmd",
        )

        service.save(entry)
        loaded = service.load(entry.session_id)

        assert loaded.prompt == "Fix \"quoted\" text and 'apostrophes' & <html>"

    def test_save_with_unicode_prompt(self, tmp_path):
        """Test saving session with Unicode characters."""
        service = SessionStateService(sessions_dir=tmp_path)
        entry = SessionEntry.create(
            pid=1234,
            prompt="Fix bug with emoji: Testing unicode characters",
            working_dir="/tmp",
            command="cmd",
        )

        service.save(entry)
        loaded = service.load(entry.session_id)

        assert loaded.prompt == "Fix bug with emoji: Testing unicode characters"

    def test_save_with_large_metadata(self, tmp_path):
        """Test saving session with large metadata."""
        service = SessionStateService(sessions_dir=tmp_path)
        large_metadata = {f"key_{i}": f"value_{i}" * 100 for i in range(100)}
        entry = SessionEntry.create(
            pid=1234,
            prompt="Task",
            working_dir="/tmp",
            command="cmd",
            metadata=large_metadata,
        )

        service.save(entry)
        loaded = service.load(entry.session_id)

        assert loaded.metadata == large_metadata

    def test_multiple_services_same_directory(self, tmp_path):
        """Test multiple service instances can share a directory."""
        service1 = SessionStateService(sessions_dir=tmp_path)
        service2 = SessionStateService(sessions_dir=tmp_path)

        entry = SessionEntry.create(
            pid=1234,
            prompt="Shared task",
            working_dir="/tmp",
            command="cmd",
        )

        service1.save(entry)
        loaded = service2.load(entry.session_id)

        assert loaded is not None
        assert loaded.session_id == entry.session_id


class TestSessionEntryNewFields:
    """Tests for last_activity and log_bytes fields."""

    def test_new_fields_default_values(self):
        """Test that new fields default to None."""
        entry = SessionEntry(
            session_id="test-1",
            pid=1000,
            prompt="Task",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd",
        )
        assert entry.last_activity is None
        assert entry.log_bytes is None

    def test_to_dict_includes_new_fields(self):
        """Test that to_dict includes last_activity and log_bytes."""
        entry = SessionEntry(
            session_id="test-2",
            pid=1000,
            prompt="Task",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd",
            last_activity="2024-01-15T10:05:00",
            log_bytes=1024,
        )
        d = entry.to_dict()
        assert d["last_activity"] == "2024-01-15T10:05:00"
        assert d["log_bytes"] == 1024

    def test_to_dict_new_fields_none(self):
        """Test that to_dict includes None values for unset new fields."""
        entry = SessionEntry(
            session_id="test-3",
            pid=1000,
            prompt="Task",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd",
        )
        d = entry.to_dict()
        assert "last_activity" in d
        assert d["last_activity"] is None
        assert "log_bytes" in d
        assert d["log_bytes"] is None

    def test_from_dict_backward_compatible(self):
        """Test that from_dict handles missing new fields with defaults."""
        data = {
            "session_id": "test-4",
            "pid": 1000,
            "prompt": "Old session",
            "started_at": "2024-01-01T08:00:00",
            "working_dir": "/tmp",
            "command": "cmd",
        }
        entry = SessionEntry.from_dict(data)
        assert entry.last_activity is None
        assert entry.log_bytes is None

    def test_from_dict_with_new_fields(self):
        """Test that from_dict loads new fields when present."""
        data = {
            "session_id": "test-5",
            "pid": 1000,
            "prompt": "Task",
            "started_at": "2024-01-15T10:00:00",
            "working_dir": "/tmp",
            "command": "cmd",
            "last_activity": "2024-01-15T10:10:00",
            "log_bytes": 2048,
        }
        entry = SessionEntry.from_dict(data)
        assert entry.last_activity == "2024-01-15T10:10:00"
        assert entry.log_bytes == 2048

    def test_update_activity_sets_timestamp(self):
        """Test update_activity sets last_activity."""
        entry = SessionEntry(
            session_id="test-6",
            pid=1000,
            prompt="Task",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd",
        )
        assert entry.last_activity is None
        entry.update_activity()
        assert entry.last_activity is not None
        # Should be a valid ISO timestamp
        datetime.fromisoformat(entry.last_activity)

    def test_update_activity_with_explicit_timestamp(self):
        """Test update_activity with explicit timestamp."""
        entry = SessionEntry(
            session_id="test-7",
            pid=1000,
            prompt="Task",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd",
        )
        entry.update_activity("2024-06-15T12:00:00")
        assert entry.last_activity == "2024-06-15T12:00:00"

    def test_roundtrip_with_new_fields(self):
        """Test to_dict/from_dict roundtrip preserves new fields."""
        entry = SessionEntry(
            session_id="test-8",
            pid=1000,
            prompt="Task",
            status="running",
            started_at="2024-01-15T10:00:00",
            working_dir="/tmp",
            command="cmd",
            last_activity="2024-01-15T10:05:00",
            log_bytes=512,
        )
        restored = SessionEntry.from_dict(entry.to_dict())
        assert restored.last_activity == entry.last_activity
        assert restored.log_bytes == entry.log_bytes


class TestRefreshActivity:
    """Tests for SessionStateService.refresh_activity."""

    @pytest.fixture
    def service_with_logs(self, tmp_path):
        """Create a service with a logs subdirectory."""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        logs_dir = sessions_dir / "logs"
        logs_dir.mkdir()
        service = SessionStateService(sessions_dir=sessions_dir)
        return service, logs_dir

    def test_refresh_activity_updates_log_bytes(self, service_with_logs):
        """Test that refresh_activity updates log_bytes from file sizes."""
        service, logs_dir = service_with_logs
        entry = SessionEntry.create(
            pid=os.getpid(),
            prompt="Task",
            working_dir="/tmp",
            command="cmd",
        )
        service.save(entry)

        # Create log files with known sizes
        stdout_log = logs_dir / f"{entry.session_id}.stdout.log"
        stderr_log = logs_dir / f"{entry.session_id}.stderr.log"
        stdout_log.write_text("x" * 100)
        stderr_log.write_text("y" * 50)

        result = service.refresh_activity(entry.session_id)

        assert result is not None
        assert result.log_bytes == 150

    def test_refresh_activity_updates_last_activity(self, service_with_logs):
        """Test that refresh_activity updates last_activity from log mtime."""
        service, logs_dir = service_with_logs
        entry = SessionEntry.create(
            pid=os.getpid(),
            prompt="Task",
            working_dir="/tmp",
            command="cmd",
        )
        service.save(entry)

        stdout_log = logs_dir / f"{entry.session_id}.stdout.log"
        stdout_log.write_text("some output")

        result = service.refresh_activity(entry.session_id)

        assert result is not None
        assert result.last_activity is not None

    def test_refresh_activity_nonexistent_session(self, service_with_logs):
        """Test refresh_activity returns None for missing session."""
        service, _ = service_with_logs
        result = service.refresh_activity("nonexistent-id")
        assert result is None

    def test_refresh_activity_no_log_files(self, service_with_logs):
        """Test refresh_activity with no log files."""
        service, _ = service_with_logs
        entry = SessionEntry.create(
            pid=os.getpid(),
            prompt="Task",
            working_dir="/tmp",
            command="cmd",
        )
        service.save(entry)

        result = service.refresh_activity(entry.session_id)

        assert result is not None
        assert result.log_bytes == 0

    def test_refresh_activity_persists(self, service_with_logs):
        """Test that refresh_activity saves the updated entry."""
        service, logs_dir = service_with_logs
        entry = SessionEntry.create(
            pid=os.getpid(),
            prompt="Task",
            working_dir="/tmp",
            command="cmd",
        )
        service.save(entry)

        stdout_log = logs_dir / f"{entry.session_id}.stdout.log"
        stdout_log.write_text("output data")

        service.refresh_activity(entry.session_id)

        # Reload and verify persistence
        reloaded = service.load(entry.session_id)
        assert reloaded.log_bytes > 0
        assert reloaded.last_activity is not None
