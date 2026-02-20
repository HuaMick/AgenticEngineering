"""Tests for state management commands and StateRegistry."""

import json
import os


class TestStateRegistry:
    """Tests for StateRegistry class."""

    def test_register_process(self, temp_config_dir):
        """Test registering a process."""
        from agenticcli.workflows.state_workflow import StateRegistry

        registry = StateRegistry(temp_config_dir / "state.json")
        entry = registry.register("test-process", "agentic test")

        assert entry.pid == os.getpid()
        assert entry.name == "test-process"
        assert entry.command == "agentic test"
        assert entry.state.value == "running"

    def test_unregister_process(self, temp_config_dir):
        """Test unregistering a process."""
        from agenticcli.workflows.state_workflow import StateRegistry

        registry = StateRegistry(temp_config_dir / "state.json")
        registry.register("test-process", "agentic test")

        result = registry.unregister()
        assert result is True

        # Verify it's gone
        entry = registry.get(os.getpid())
        assert entry is None

    def test_get_process(self, temp_config_dir):
        """Test getting a registered process."""
        from agenticcli.workflows.state_workflow import StateRegistry

        registry = StateRegistry(temp_config_dir / "state.json")
        registry.register("test-process", "agentic test", metadata={"key": "value"})

        entry = registry.get(os.getpid())
        assert entry is not None
        assert entry.name == "test-process"
        assert entry.metadata == {"key": "value"}

    def test_get_nonexistent_process(self, temp_config_dir):
        """Test getting a process that doesn't exist."""
        from agenticcli.workflows.state_workflow import StateRegistry

        registry = StateRegistry(temp_config_dir / "state.json")
        entry = registry.get(99999)
        assert entry is None

    def test_list_all_processes(self, temp_config_dir):
        """Test listing all registered processes."""
        from agenticcli.workflows.state_workflow import StateRegistry

        registry = StateRegistry(temp_config_dir / "state.json")
        registry.register("process-1", "cmd1")

        entries = registry.list_all()
        assert len(entries) == 1
        assert entries[0].name == "process-1"

    def test_list_active_processes(self, temp_config_dir):
        """Test listing only active processes."""
        from agenticcli.workflows.state_workflow import ProcessState, StateRegistry

        registry = StateRegistry(temp_config_dir / "state.json")
        registry.register("active-process", "cmd1")
        registry.update_state(state=ProcessState.COMPLETED)

        # Register another process
        registry.register("running-process", "cmd2")

        # The second one should override the first since same PID
        entries = registry.list_active()
        assert len(entries) == 1
        assert entries[0].name == "running-process"

    def test_update_state(self, temp_config_dir):
        """Test updating process state."""
        from agenticcli.workflows.state_workflow import ProcessState, StateRegistry

        registry = StateRegistry(temp_config_dir / "state.json")
        registry.register("test-process", "agentic test")

        result = registry.update_state(state=ProcessState.COMPLETED)
        assert result is True

        entry = registry.get(os.getpid())
        assert entry.state == ProcessState.COMPLETED
        assert entry.ended_at is not None

    def test_update_metadata(self, temp_config_dir):
        """Test updating process metadata."""
        from agenticcli.workflows.state_workflow import StateRegistry

        registry = StateRegistry(temp_config_dir / "state.json")
        registry.register("test-process", "agentic test", metadata={"key1": "value1"})

        result = registry.update_state(metadata={"key2": "value2"})
        assert result is True

        entry = registry.get(os.getpid())
        assert entry.metadata == {"key1": "value1", "key2": "value2"}

    def test_clear_completed(self, temp_config_dir):
        """Test clearing completed processes."""
        from agenticcli.workflows.state_workflow import ProcessState, StateRegistry

        registry = StateRegistry(temp_config_dir / "state.json")
        registry.register("completed-process", "cmd1")
        registry.update_state(state=ProcessState.COMPLETED)

        count = registry.clear_completed()
        assert count == 1

        entries = registry.list_all()
        assert len(entries) == 0

    def test_clear_all(self, temp_config_dir):
        """Test clearing all processes."""
        from agenticcli.workflows.state_workflow import StateRegistry

        registry = StateRegistry(temp_config_dir / "state.json")
        registry.register("process-1", "cmd1")

        count = registry.clear_all()
        assert count == 1

        entries = registry.list_all()
        assert len(entries) == 0

    def test_persists_to_file(self, temp_config_dir):
        """Test that state persists to JSON file."""
        from agenticcli.workflows.state_workflow import StateRegistry

        state_file = temp_config_dir / "state.json"
        registry = StateRegistry(state_file)
        registry.register("test-process", "agentic test")

        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert "processes" in data
        assert str(os.getpid()) in data["processes"]


class TestFileLock:
    """Tests for FileLock class."""

    def test_acquire_release(self, temp_config_dir):
        """Test basic lock acquire and release."""
        from agenticcli.workflows.state_workflow import FileLock

        test_file = temp_config_dir / "test.txt"
        test_file.write_text("test")

        lock = FileLock(test_file)
        assert lock.acquire() is True
        assert lock.lock_path.exists()

        lock.release()
        assert not lock.lock_path.exists()

    def test_context_manager(self, temp_config_dir):
        """Test lock as context manager."""
        from agenticcli.workflows.state_workflow import FileLock

        test_file = temp_config_dir / "test.txt"
        test_file.write_text("test")

        with FileLock(test_file) as lock:
            assert lock.lock_path.exists()

        assert not lock.lock_path.exists()

    def test_stale_lock_cleanup(self, temp_config_dir):
        """Test that stale locks are cleaned up."""
        from agenticcli.workflows.state_workflow import FileLock

        test_file = temp_config_dir / "test.txt"
        test_file.write_text("test")

        # Create a stale lock with non-existent PID
        lock_file = test_file.with_suffix(".txt.lock")
        lock_file.write_text("999999")  # Non-existent PID

        # New lock should succeed by cleaning up stale lock
        lock = FileLock(test_file, timeout=1.0)
        assert lock.acquire() is True
        lock.release()


class TestStateCommands:
    """Tests for state CLI commands."""

    def test_state_list_empty(self, cli_runner, temp_config_dir):
        """Test state list with empty registry."""
        stdout, stderr, code = cli_runner(["configure", "state", "list"])
        assert code == 0
        assert "No registered processes" in stdout

    def test_state_list_json(self, cli_runner, temp_config_dir):
        """Test state list with JSON output."""
        result = cli_runner("--json", "configure", "state", "list")
        assert result.returncode == 0

        data = json.loads(result.stdout)
        assert "processes" in data
        assert "count" in data
        assert data["count"] == 0

    def test_state_show_not_found(self, cli_runner, temp_config_dir):
        """Test state show with non-existent PID."""
        stdout, stderr, code = cli_runner(["configure", "state", "show", "99999"])
        assert code == 1
        assert "not found" in stderr.lower()

    def test_state_clear_empty(self, cli_runner, temp_config_dir):
        """Test state clear with empty registry."""
        stdout, stderr, code = cli_runner(["configure", "state", "clear"])
        assert code == 0
        assert "0" in stdout

    def test_state_clear_all_requires_force(self, cli_runner, temp_config_dir):
        """Test that state clear --all requires --force."""
        result = cli_runner("configure", "state", "clear", "--all")
        assert result.returncode == 1
        assert "force" in result.stderr.lower()

    def test_state_clear_all_with_force(self, cli_runner, temp_config_dir):
        """Test state clear --all --force."""
        result = cli_runner("configure", "state", "clear", "--all", "--force")
        assert result.returncode == 0

    def test_state_cleanup_empty(self, cli_runner, temp_config_dir):
        """Test state cleanup with empty registry."""
        stdout, stderr, code = cli_runner(["configure", "state", "cleanup"])
        assert code == 0
        assert "No stale processes" in stdout


class TestProcessEntry:
    """Tests for ProcessEntry dataclass."""

    def test_to_dict(self):
        """Test converting entry to dictionary."""
        from agenticcli.workflows.state_workflow import ProcessEntry, ProcessState

        entry = ProcessEntry(
            pid=12345,
            name="test",
            command="test cmd",
            started_at=1000.0,
            state=ProcessState.RUNNING,
            metadata={"key": "value"},
        )

        data = entry.to_dict()
        assert data["pid"] == 12345
        assert data["name"] == "test"
        assert data["state"] == "running"
        assert data["metadata"] == {"key": "value"}

    def test_from_dict(self):
        """Test creating entry from dictionary."""
        from agenticcli.workflows.state_workflow import ProcessEntry, ProcessState

        data = {
            "pid": 12345,
            "name": "test",
            "command": "test cmd",
            "started_at": 1000.0,
            "state": "completed",
            "metadata": {},
            "ended_at": 1001.0,
        }

        entry = ProcessEntry.from_dict(data)
        assert entry.pid == 12345
        assert entry.state == ProcessState.COMPLETED
        assert entry.ended_at == 1001.0
