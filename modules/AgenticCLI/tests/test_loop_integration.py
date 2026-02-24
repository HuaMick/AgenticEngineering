"""Integration tests for Ralph Loop CLI commands.

Tests for starting, stopping, and monitoring Ralph Loops.
Uses mock subprocess calls to avoid actual Claude CLI calls.
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

import pytest


@pytest.fixture
def loops_dir(tmp_path):
    """Create a temporary sessions directory (unified store for loops)."""
    loops_dir = tmp_path / ".agentic" / "sessions"
    loops_dir.mkdir(parents=True)
    return loops_dir


@pytest.fixture
def mock_loops_dir(loops_dir, monkeypatch):
    """Patch StateStore.get_dir to use temp directory."""
    from agenticcli.commands import loop

    monkeypatch.setattr(loop._store, "get_dir", lambda override=None: loops_dir)
    return loops_dir


@pytest.fixture
def sample_loop_data():
    """Return sample loop data for testing."""
    return {
        "session_id": "12345678-1234-1234-1234-123456789abc",
        "type": "loop",
        "pid": 12345,
        "prompt": "Implement the feature",
        "prompt_source": "string",
        "max_iterations": 10,
        "completion_promise": "All tests pass",
        "current_iteration": 3,
        "status": "running",
        "started_at": "2024-01-15T10:00:00",
        "ended_at": None,
        "background": True,
        "working_dir": "/home/user/project",
        "output_file": None,
        "command": "claude --print --max-turns 10 --prompt 'Implement the feature'",
        "iterations": [
            {"number": 1, "started_at": "2024-01-15T10:00:00", "ended_at": "2024-01-15T10:05:00", "status": "completed"},
            {"number": 2, "started_at": "2024-01-15T10:05:00", "ended_at": "2024-01-15T10:10:00", "status": "completed"},
            {"number": 3, "started_at": "2024-01-15T10:10:00", "ended_at": None, "status": "running"},
        ],
    }


class TestLoopHelperFunctions:
    """Tests for loop module helper functions."""

    def test_get_loops_dir_creates_directory(self, tmp_path, monkeypatch):
        """Test that StateStore.get_dir creates the directory if it doesn't exist."""
        from agenticcli.commands import loop

        new_home = tmp_path / "home"
        new_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: new_home)

        result = loop._store.get_dir()

        assert result.exists()
        assert result == new_home / ".agentic" / "sessions"

    def test_save_and_load_loop(self, mock_loops_dir, sample_loop_data):
        """Test saving and loading a loop."""
        from agenticcli.commands import loop

        loop._store.save(sample_loop_data)
        loaded = loop._store.load(sample_loop_data["session_id"])

        assert loaded is not None
        assert loaded["session_id"] == sample_loop_data["session_id"]
        assert loaded["prompt"] == sample_loop_data["prompt"]
        assert loaded["iterations"] == sample_loop_data["iterations"]

    def test_load_nonexistent_loop(self, mock_loops_dir):
        """Test loading a loop that doesn't exist."""
        from agenticcli.commands import loop

        result = loop._store.load("nonexistent-id")

        assert result is None

    def test_list_all_loops(self, mock_loops_dir, sample_loop_data):
        """Test listing all loops."""
        from agenticcli.commands import loop

        # Create multiple loops
        loop._store.save(sample_loop_data)

        second_loop = sample_loop_data.copy()
        second_loop["session_id"] = "87654321-4321-4321-4321-cba987654321"
        second_loop["prompt"] = "Another task"
        loop._store.save(second_loop)

        result = loop._store.list_all(filter_fn=lambda r: r.get("type") == "loop")

        assert len(result) == 2
        loop_ids = [lp["session_id"] for lp in result]
        assert sample_loop_data["session_id"] in loop_ids
        assert second_loop["session_id"] in loop_ids

    def test_list_all_loops_skips_invalid_files(self, mock_loops_dir):
        """Test that list_all_loops skips invalid JSON files."""
        from agenticcli.commands import loop

        # Create an invalid JSON file
        invalid_file = mock_loops_dir / "invalid.json"
        invalid_file.write_text("not valid json {{{")

        result = loop._store.list_all()

        assert result == []

    def test_update_loop_status_marks_completed(self, mock_loops_dir, sample_loop_data):
        """Test that update_loop_status marks dead processes as completed."""
        from agenticcli.commands import loop

        # Use a nonexistent PID
        sample_loop_data["pid"] = 99999999
        sample_loop_data["status"] = "running"
        loop._store.save(sample_loop_data)

        result = loop._update_loop_status(sample_loop_data)

        assert result["status"] == "completed"
        assert result["ended_at"] is not None


class TestResolvePrompt:
    """Tests for prompt resolution from various sources."""

    def test_resolve_prompt_direct_string(self, mock_loops_dir):
        """Test resolving prompt from direct string."""
        from agenticcli.commands import loop

        args = SimpleNamespace(prompt="Direct prompt", prompt_file=None, entrypoint=None)

        prompt, source = loop._resolve_prompt(args)

        assert prompt == "Direct prompt"
        assert source == "string"

    def test_resolve_prompt_from_file(self, mock_loops_dir, tmp_path):
        """Test resolving prompt from file."""
        from agenticcli.commands import loop

        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("  Prompt from file\n  ")

        args = SimpleNamespace(prompt=None, prompt_file=str(prompt_file), entrypoint=None)

        prompt, source = loop._resolve_prompt(args)

        assert prompt == "Prompt from file"
        assert source == f"file:{prompt_file}"

    def test_resolve_prompt_file_not_found(self, mock_loops_dir, capsys):
        """Test error when prompt file doesn't exist."""
        from agenticcli.commands import loop

        args = SimpleNamespace(prompt=None, prompt_file="/nonexistent/file.txt", entrypoint=None)

        with pytest.raises(SystemExit) as exc_info:
            loop._resolve_prompt(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Prompt file not found" in captured.err

    def test_resolve_prompt_from_entrypoint_path(self, mock_loops_dir, tmp_path):
        """Test resolving prompt from entrypoint as file path."""
        from agenticcli.commands import loop

        entrypoint_file = tmp_path / "entrypoint.md"
        entrypoint_file.write_text("Entrypoint content")

        args = SimpleNamespace(prompt=None, prompt_file=None, entrypoint=str(entrypoint_file))

        prompt, source = loop._resolve_prompt(args)

        assert prompt == "Entrypoint content"
        assert source == f"entrypoint:{entrypoint_file}"

    def test_resolve_prompt_from_entrypoint_name(self, mock_loops_dir, tmp_path, monkeypatch):
        """Test resolving prompt from entrypoint name in standard locations."""
        from agenticcli.commands import loop

        # Create .claude/entrypoints directory with entrypoint using proper naming convention
        # The entrypoint module expects files like _my-task.md in .claude/entrypoints/
        entrypoints_dir = tmp_path / ".claude" / "entrypoints"
        entrypoints_dir.mkdir(parents=True)
        entrypoint_file = entrypoints_dir / "_my-task.md"
        entrypoint_file.write_text("Task from .claude")

        monkeypatch.chdir(tmp_path)

        args = SimpleNamespace(prompt=None, prompt_file=None, entrypoint="my-task")

        prompt, source = loop._resolve_prompt(args)

        assert prompt == "Task from .claude"
        assert source == "entrypoint:my-task"

    def test_resolve_prompt_entrypoint_not_found(self, mock_loops_dir, tmp_path, monkeypatch, capsys):
        """Test error when entrypoint not found in any location."""
        from agenticcli.commands import loop

        monkeypatch.chdir(tmp_path)

        args = SimpleNamespace(prompt=None, prompt_file=None, entrypoint="nonexistent")

        with pytest.raises(SystemExit) as exc_info:
            loop._resolve_prompt(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Entrypoint not found" in captured.err

    def test_resolve_prompt_no_source_provided(self, mock_loops_dir, capsys):
        """Test error when no prompt source is provided."""
        from agenticcli.commands import loop

        args = SimpleNamespace(prompt=None, prompt_file=None, entrypoint=None)

        with pytest.raises(SystemExit) as exc_info:
            loop._resolve_prompt(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Prompt is required" in captured.err


class TestLoopStartCommand:
    """Tests for the loop start command."""

    @patch("agenticcli.commands.loop.subprocess.Popen")
    def test_start_background_success(self, mock_popen, mock_loops_dir, capsys):
        """Test successful background loop start."""
        from agenticcli.commands import loop

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Implement feature",
            prompt_file=None,
            entrypoint=None,
            max_iterations=5,
            completion_promise="Tests pass",
            background=True,
            directory=None,
            output=None,
        )

        loop.cmd_start(args)

        # Verify Popen was called correctly
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "claude" in cmd
        assert "--print" in cmd
        assert "--max-turns" in cmd

        # Verify loop was saved
        loops = loop._store.list_all()
        assert len(loops) == 1
        assert loops[0]["status"] == "running"
        assert loops[0]["pid"] == 12345
        assert loops[0]["max_iterations"] == 5
        assert len(loops[0]["iterations"]) == 1

    @patch("agenticcli.commands.loop.subprocess.run")
    def test_start_foreground_success(self, mock_run, mock_loops_dir, capsys):
        """Test successful foreground loop start."""
        from agenticcli.commands import loop

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Task completed",
            stderr="",
        )

        args = SimpleNamespace(
            prompt="Quick task",
            prompt_file=None,
            entrypoint=None,
            max_iterations=3,
            completion_promise=None,
            background=False,
            directory=None,
            output=None,
        )

        loop.cmd_start(args)

        # Verify loop was saved with completed status
        loops = loop._store.list_all()
        assert len(loops) == 1
        assert loops[0]["status"] == "completed"
        assert loops[0]["iterations"][0]["status"] == "completed"

    @patch("agenticcli.commands.loop.subprocess.run")
    def test_start_foreground_failure(self, mock_run, mock_loops_dir, capsys):
        """Test foreground loop start with failure."""
        from agenticcli.commands import loop

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error occurred",
        )

        args = SimpleNamespace(
            prompt="Failing task",
            prompt_file=None,
            entrypoint=None,
            max_iterations=10,
            completion_promise=None,
            background=False,
            directory=None,
            output=None,
        )

        loop.cmd_start(args)

        loops = loop._store.list_all()
        assert len(loops) == 1
        assert loops[0]["status"] == "failed"
        assert loops[0]["exit_code"] == 1

    @patch("agenticcli.commands.loop.subprocess.run")
    def test_start_with_output_file(self, mock_run, mock_loops_dir, tmp_path, capsys):
        """Test loop start writes output to file."""
        from agenticcli.commands import loop

        output_file = tmp_path / "output.txt"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Generated output content",
            stderr="",
        )

        args = SimpleNamespace(
            prompt="Generate output",
            prompt_file=None,
            entrypoint=None,
            max_iterations=1,
            completion_promise=None,
            background=False,
            directory=None,
            output=str(output_file),
        )

        loop.cmd_start(args)

        assert output_file.exists()
        assert output_file.read_text() == "Generated output content"

    @patch("agenticcli.commands.loop.subprocess.Popen")
    def test_start_claude_not_found(self, mock_popen, mock_loops_dir, capsys):
        """Test start when claude CLI is not found."""
        from agenticcli.commands import loop

        mock_popen.side_effect = FileNotFoundError()

        args = SimpleNamespace(
            prompt="Test task",
            prompt_file=None,
            entrypoint=None,
            max_iterations=10,
            completion_promise=None,
            background=True,
            directory=None,
            output=None,
        )

        with pytest.raises(SystemExit) as exc_info:
            loop.cmd_start(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Claude CLI not found" in captured.err

    @patch("agenticcli.commands.loop.subprocess.Popen")
    @patch("agenticcli.console.is_json_output")
    def test_start_json_output(self, mock_json_output, mock_popen, mock_loops_dir, capsys):
        """Test start with JSON output."""
        from agenticcli.commands import loop

        mock_json_output.return_value = True
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="JSON test",
            prompt_file=None,
            entrypoint=None,
            max_iterations=5,
            completion_promise="Done",
            background=True,
            directory=None,
            output=None,
        )

        loop.cmd_start(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["pid"] == 12345
        assert output["status"] == "running"
        assert output["max_iterations"] == 5
        assert output["completion_promise"] == "Done"


class TestLoopStopCommand:
    """Tests for the loop stop command."""

    def test_stop_requires_loop_id(self, mock_loops_dir, capsys):
        """Test that stop requires a loop ID."""
        from agenticcli.commands import loop

        args = SimpleNamespace(loop_id=None, force=False)

        with pytest.raises(SystemExit) as exc_info:
            loop.cmd_stop(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Loop ID is required" in captured.err

    def test_stop_loop_not_found(self, mock_loops_dir, capsys):
        """Test stopping a nonexistent loop."""
        from agenticcli.commands import loop

        args = SimpleNamespace(loop_id="nonexistent", force=False)

        with pytest.raises(SystemExit) as exc_info:
            loop.cmd_stop(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Loop not found" in captured.err

    def test_stop_completed_loop(self, mock_loops_dir, sample_loop_data, capsys):
        """Test stopping an already completed loop (idempotent: returns success)."""
        from agenticcli.commands import loop

        sample_loop_data["status"] = "completed"
        loop._store.save(sample_loop_data)

        args = SimpleNamespace(
            loop_id=sample_loop_data["session_id"][:8],
            force=False,
        )

        # Idempotent stop: completed loops return success instead of raising
        loop.cmd_stop(args)

        captured = capsys.readouterr()
        assert "terminal state" in captured.out or "completed" in captured.out

    @patch("os.kill")
    def test_stop_running_loop(self, mock_kill, mock_loops_dir, sample_loop_data, capsys):
        """Test stopping a running loop."""
        from agenticcli.commands import loop

        loop._store.save(sample_loop_data)

        args = SimpleNamespace(
            loop_id=sample_loop_data["session_id"][:8],
            force=False,
        )

        loop.cmd_stop(args)

        # Verify kill was called with SIGTERM
        import signal

        mock_kill.assert_called_once_with(sample_loop_data["pid"], signal.SIGTERM)

        # Verify loop status was updated
        loops = loop._store.list_all()
        assert loops[0]["status"] == "stopped"

        # Verify running iteration was marked as stopped
        running_iters = [i for i in loops[0]["iterations"] if i["status"] == "stopped"]
        assert len(running_iters) == 1

    @patch("os.kill")
    def test_stop_with_force(self, mock_kill, mock_loops_dir, sample_loop_data, capsys):
        """Test stopping a loop with force flag."""
        from agenticcli.commands import loop

        loop._store.save(sample_loop_data)

        args = SimpleNamespace(
            loop_id=sample_loop_data["session_id"][:8],
            force=True,
        )

        loop.cmd_stop(args)

        # Verify kill was called with SIGKILL
        import signal

        mock_kill.assert_called_once_with(sample_loop_data["pid"], signal.SIGKILL)


class TestLoopStatusCommand:
    """Tests for the loop status command."""

    def test_status_requires_loop_id(self, mock_loops_dir, capsys):
        """Test that status requires a loop ID."""
        from agenticcli.commands import loop

        args = SimpleNamespace(loop_id=None)

        with pytest.raises(SystemExit) as exc_info:
            loop.cmd_status(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Loop ID is required" in captured.err

    def test_status_loop_not_found(self, mock_loops_dir, capsys):
        """Test status for a nonexistent loop."""
        from agenticcli.commands import loop

        args = SimpleNamespace(loop_id="nonexistent")

        with pytest.raises(SystemExit) as exc_info:
            loop.cmd_status(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Loop not found" in captured.err

    def test_status_displays_loop_info(self, mock_loops_dir, sample_loop_data, capsys):
        """Test that status displays loop information."""
        from agenticcli.commands import loop

        loop._store.save(sample_loop_data)

        # Mock is_process_running to return True
        with patch.object(loop, "is_process_running", return_value=True):
            args = SimpleNamespace(loop_id=sample_loop_data["session_id"][:8])
            loop.cmd_status(args)

        captured = capsys.readouterr()
        assert "Loop " in captured.out
        assert sample_loop_data["session_id"][:8] in captured.out
        assert "running" in captured.out.lower()
        assert "Max Iterations" in captured.out
        assert "Current Iteration" in captured.out

    def test_status_shows_iterations(self, mock_loops_dir, sample_loop_data, capsys):
        """Test that status shows iteration history."""
        from agenticcli.commands import loop

        loop._store.save(sample_loop_data)

        with patch.object(loop, "is_process_running", return_value=True):
            args = SimpleNamespace(loop_id=sample_loop_data["session_id"][:8])
            loop.cmd_status(args)

        captured = capsys.readouterr()
        assert "Iterations" in captured.out

    @patch("agenticcli.console.is_json_output")
    def test_status_json_output(self, mock_json_output, mock_loops_dir, sample_loop_data, capsys):
        """Test status with JSON output."""
        from agenticcli.commands import loop

        mock_json_output.return_value = True
        loop._store.save(sample_loop_data)

        with patch.object(loop, "is_process_running", return_value=True):
            args = SimpleNamespace(loop_id=sample_loop_data["session_id"][:8])
            loop.cmd_status(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["session_id"] == sample_loop_data["session_id"]
        assert output["status"] == "running"
        assert "iterations" in output


class TestLoopHistoryCommand:
    """Tests for the loop history command."""

    def test_history_empty(self, mock_loops_dir, capsys):
        """Test history when no loops exist."""
        from agenticcli.commands import loop

        args = SimpleNamespace(active=False, status=None, limit=20)

        loop.cmd_history(args)

        captured = capsys.readouterr()
        assert "No loops found" in captured.out

    def test_history_with_loops(self, mock_loops_dir, sample_loop_data, capsys):
        """Test history with existing loops."""
        from agenticcli.commands import loop

        loop._store.save(sample_loop_data)
        args = SimpleNamespace(active=False, status=None, limit=20)

        with patch.object(loop, "is_process_running", return_value=True):
            loop.cmd_history(args)

        captured = capsys.readouterr()
        assert "Ralph Loop History" in captured.out
        assert sample_loop_data["session_id"][:8] in captured.out

    def test_history_active_only(self, mock_loops_dir, sample_loop_data, capsys):
        """Test history with active only filter."""
        from agenticcli.commands import loop

        # Save running loop
        loop._store.save(sample_loop_data)

        # Save completed loop
        completed = sample_loop_data.copy()
        completed["session_id"] = "completed-loop-id-1234"
        completed["status"] = "completed"
        loop._store.save(completed)

        args = SimpleNamespace(active=True, status=None, limit=20)

        with patch.object(loop, "is_process_running", return_value=True):
            loop.cmd_history(args)

        captured = capsys.readouterr()
        assert sample_loop_data["session_id"][:8] in captured.out

    def test_history_filter_by_status(self, mock_loops_dir, sample_loop_data, capsys):
        """Test history with status filter."""
        from agenticcli.commands import loop

        # Save running loop
        loop._store.save(sample_loop_data)

        # Save completed loop
        completed = sample_loop_data.copy()
        completed["session_id"] = "completed-loop-id-1234"
        completed["status"] = "completed"
        loop._store.save(completed)

        args = SimpleNamespace(active=False, status="completed", limit=20)

        with patch.object(loop, "is_process_running", return_value=True):
            loop.cmd_history(args)

        captured = capsys.readouterr()
        assert "completed" in captured.out.lower()

    def test_history_with_limit(self, mock_loops_dir, sample_loop_data, capsys):
        """Test history respects limit."""
        from agenticcli.commands import loop

        # Create multiple loops
        for i in range(5):
            data = sample_loop_data.copy()
            data["session_id"] = f"loop-id-{i}-1234-1234-1234"
            loop._store.save(data)

        args = SimpleNamespace(active=False, status=None, limit=2)

        with patch.object(loop, "is_process_running", return_value=True):
            loop.cmd_history(args)

        # The table should show limited results
        captured = capsys.readouterr()
        assert "Total: 5 loop(s)" in captured.out

    @patch("agenticcli.console.is_json_output")
    def test_history_json_output(self, mock_json_output, mock_loops_dir, sample_loop_data, capsys):
        """Test history with JSON output."""
        from agenticcli.commands import loop

        mock_json_output.return_value = True
        loop._store.save(sample_loop_data)

        with patch.object(loop, "is_process_running", return_value=True):
            args = SimpleNamespace(active=False, status=None, limit=20)
            loop.cmd_history(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "loops" in output
        assert "count" in output
        assert output["count"] == 1


class TestLoopHandleRouting:
    """Tests for the loop handle function routing."""

    def test_handle_routes_to_start(self, mock_loops_dir, capsys):
        """Test that handle routes start command correctly."""
        from agenticcli.commands import loop

        args = SimpleNamespace(
            loop_command="start",
            prompt=None,
            prompt_file=None,
            entrypoint=None,
        )

        with pytest.raises(SystemExit):
            loop.handle(args)

    def test_handle_routes_to_stop(self, mock_loops_dir):
        """Test that handle routes stop command correctly."""
        from agenticcli.commands import loop

        args = SimpleNamespace(loop_command="stop", loop_id=None)

        with pytest.raises(SystemExit):
            loop.handle(args)

    def test_handle_routes_to_status(self, mock_loops_dir):
        """Test that handle routes status command correctly."""
        from agenticcli.commands import loop

        args = SimpleNamespace(loop_command="status", loop_id=None)

        with pytest.raises(SystemExit):
            loop.handle(args)

    def test_handle_routes_to_history(self, mock_loops_dir, capsys):
        """Test that handle routes history command correctly."""
        from agenticcli.commands import loop

        args = SimpleNamespace(
            loop_command="history",
            active=False,
            status=None,
            limit=20,
        )

        loop.handle(args)

        captured = capsys.readouterr()
        assert "No loops found" in captured.out

    def test_handle_invalid_command(self, mock_loops_dir, capsys):
        """Test that handle exits with error for invalid command."""
        from agenticcli.commands import loop

        args = SimpleNamespace(loop_command="invalid")

        with pytest.raises(SystemExit) as exc_info:
            loop.handle(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Usage:" in captured.err


class TestIterationTracking:
    """Tests for iteration tracking functionality."""

    def test_iteration_created_on_start(self, mock_loops_dir):
        """Test that iteration is created when loop starts."""
        from agenticcli.commands import loop

        with patch("agenticcli.commands.loop.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            args = SimpleNamespace(
                prompt="Test",
                prompt_file=None,
                entrypoint=None,
                max_iterations=10,
                completion_promise=None,
                background=True,
                directory=None,
                output=None,
            )

            loop.cmd_start(args)

        loops = loop._store.list_all()
        assert len(loops) == 1
        assert len(loops[0]["iterations"]) == 1
        assert loops[0]["iterations"][0]["number"] == 1
        assert loops[0]["iterations"][0]["status"] == "running"

    def test_iteration_marked_completed_on_success(self, mock_loops_dir):
        """Test that iteration is marked completed on success."""
        from agenticcli.commands import loop

        with patch("agenticcli.commands.loop.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")

            args = SimpleNamespace(
                prompt="Test",
                prompt_file=None,
                entrypoint=None,
                max_iterations=1,
                completion_promise=None,
                background=False,
                directory=None,
                output=None,
            )

            loop.cmd_start(args)

        loops = loop._store.list_all()
        assert loops[0]["iterations"][0]["status"] == "completed"
        assert loops[0]["iterations"][0]["ended_at"] is not None

    def test_iteration_marked_failed_on_error(self, mock_loops_dir):
        """Test that iteration is marked failed on error."""
        from agenticcli.commands import loop

        with patch("agenticcli.commands.loop.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")

            args = SimpleNamespace(
                prompt="Test",
                prompt_file=None,
                entrypoint=None,
                max_iterations=1,
                completion_promise=None,
                background=False,
                directory=None,
                output=None,
            )

            loop.cmd_start(args)

        loops = loop._store.list_all()
        assert loops[0]["iterations"][0]["status"] == "failed"

    @patch("os.kill")
    def test_iteration_marked_stopped_on_stop(self, mock_kill, mock_loops_dir, sample_loop_data):
        """Test that running iteration is marked stopped when loop is stopped."""
        from agenticcli.commands import loop

        loop._store.save(sample_loop_data)

        args = SimpleNamespace(
            loop_id=sample_loop_data["session_id"][:8],
            force=False,
        )

        loop.cmd_stop(args)

        loops = loop._store.list_all()
        stopped_iters = [i for i in loops[0]["iterations"] if i["status"] == "stopped"]
        assert len(stopped_iters) == 1
        assert stopped_iters[0]["ended_at"] is not None
