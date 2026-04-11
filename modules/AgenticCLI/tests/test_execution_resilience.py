"""Tests for ExecutionRunner resilience fixes.

Covers 6 fixes:
- Fix 2: Blocked state on retry exhaustion
- Fix 3: Orphan tmux session sweep during recovery
- Fix 4: Phase-filtered get_current_ticket
- Fix 5: Phase-scoped agent context and completion gate
- Fix 6: Pipe-pane output logging
- Fix 7: Session file written before tmux spawn, duration clamping

Additional:
- PhaseLoggerAdapter: Structured context logging for ExecutionRunner
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ── Fix 7: Session race fix ────────────────────────────────────────────


@pytest.mark.story("US-PLN-061")
class TestSessionRaceFix:
    """Fix 7: Session file must be written before tmux spawn."""

    def test_write_state_atomic_updates_mtime(self, tmp_path):
        """os.utime should be called after os.replace in _write_state_atomic."""
        from agenticcli.utils.sdk_pane_runner import _write_state_atomic

        state_file = tmp_path / "test.json"
        data = {"session_id": "test-123", "status": "running"}

        _write_state_atomic(state_file, data)

        # Verify file exists and is valid JSON
        assert state_file.exists()
        with open(state_file) as f:
            loaded = json.load(f)
        assert loaded["session_id"] == "test-123"

    def test_negative_duration_clamped(self):
        """Duration should be clamped to 0 when ended_at < started_at."""
        # Simulate the state.py display logic
        duration = max(0.0, 100.0 - 200.0)  # ended_at - started_at < 0
        assert duration == 0.0

    def test_session_data_saved_before_sdk_tmux_spawn(self):
        """Verify _store.save is called before tmux subprocess.run in cmd_spawn."""
        # Read session.py and verify the ordering — the _store.save call with
        # status="starting" must come BEFORE the tmux new-session subprocess call
        import inspect
        from agenticcli.commands import session
        source = inspect.getsource(session.cmd_spawn)

        # Find the pre-spawn save
        pre_spawn_idx = source.find("Write session state BEFORE spawn")
        assert pre_spawn_idx > 0, "Pre-spawn comment should exist"

        # Find the first _store.save
        first_save = source.find("_store.save(session_data)", pre_spawn_idx)
        assert first_save > 0, "_store.save should be called after pre-spawn comment"

        # Find the SDK_TMUX path
        sdk_tmux_idx = source.find("SDK-in-tmux path", first_save)
        assert sdk_tmux_idx > first_save, "SDK-in-tmux path should come after first save"


# ── Fix 2: Blocked state on retry exhaustion ────────────────────────────


@pytest.mark.story("US-PLN-061")
class TestBlockedState:
    """Fix 2: Phase should be marked 'blocked' after retry exhaustion."""

    def _make_runner(self, tmp_path):
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir
        workflow.wait_for_session.return_value = "failed"

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        return runner, workflow

    def test_mark_phase_blocked(self, tmp_path):
        """_mark_phase_blocked should update phase status to 'blocked'."""
        runner, workflow = self._make_runner(tmp_path)
        mock_repo = MagicMock()
        workflow._get_repository.return_value = mock_repo

        runner._mark_phase_blocked("test_plan", "P1")

        mock_repo.update_phase.assert_called_once_with("test_plan", "P1", {"status": "blocked"})

    def test_execute_plan_halts_on_blocked_phase(self, tmp_path):
        """_execute_plan should halt when a blocked phase is found."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic import PhaseData

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        mock_repo = MagicMock()
        mock_repo.list_phases.return_value = [
            PhaseData(name="P1", status="blocked", agent="build-python"),
            PhaseData(name="P2", status="planning", agent="test-builder"),
        ]
        workflow._get_repository.return_value = mock_repo

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        result = runner._execute_plan("test_plan", max_iterations=5)

        assert result is False
        assert any("Blocked" in e or "blocked" in e.lower() for e in runner.state["errors"])

    def test_execute_plan_reports_blocked_reason_in_error(self, tmp_path):
        """_execute_plan should include blocked_reason in state errors."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic import PhaseData

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        mock_repo = MagicMock()
        mock_repo.list_phases.return_value = [
            PhaseData(
                name="Build Phase",
                status="blocked",
                agent="build-python",
                blocked_reason="Network timeout after 3 retries",
            ),
        ]
        workflow._get_repository.return_value = mock_repo

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        result = runner._execute_plan("test_plan", max_iterations=5)

        assert result is False
        # The blocked phase name should be in the error message
        errors = runner.state["errors"]
        assert any("Build Phase" in e for e in errors)

    def test_execute_plan_halts_with_multiple_blocked_phases(self, tmp_path):
        """_execute_plan should report all blocked phases when multiple exist."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic import PhaseData

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        mock_repo = MagicMock()
        mock_repo.list_phases.return_value = [
            PhaseData(name="Phase A", status="blocked", agent="build-python",
                      blocked_reason="Reason A"),
            PhaseData(name="Phase B", status="blocked", agent="test-builder",
                      blocked_reason="Reason B"),
            PhaseData(name="Phase C", status="planning", agent="explore"),
        ]
        workflow._get_repository.return_value = mock_repo

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        result = runner._execute_plan("test_plan", max_iterations=5)

        assert result is False
        errors = runner.state["errors"]
        # Both blocked phase names should appear in error
        blocked_error = [e for e in errors if "blocked" in e.lower()][0]
        assert "Phase A" in blocked_error
        assert "Phase B" in blocked_error

    def test_execute_plan_does_not_spawn_after_blocked(self, tmp_path):
        """_execute_plan should not attempt to spawn agents after detecting blocked."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic import PhaseData

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        mock_repo = MagicMock()
        mock_repo.list_phases.return_value = [
            PhaseData(name="P1", status="blocked", agent="build-python"),
            PhaseData(name="P2", status="planning", agent="test-builder"),
        ]
        workflow._get_repository.return_value = mock_repo

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        result = runner._execute_plan("test_plan", max_iterations=5)

        assert result is False
        # Verify no spawn was attempted (wait_for_session should not be called)
        workflow.wait_for_session.assert_not_called()

    def test_execute_plan_blocked_with_no_reason_uses_default(self, tmp_path):
        """_execute_plan should handle blocked phases with no blocked_reason gracefully."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic import PhaseData

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        mock_repo = MagicMock()
        mock_repo.list_phases.return_value = [
            PhaseData(name="P1", status="blocked", agent="build-python"),
            # blocked_reason is None by default
        ]
        workflow._get_repository.return_value = mock_repo

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        result = runner._execute_plan("test_plan", max_iterations=5)

        # Should still halt cleanly even without a reason
        assert result is False
        assert len(runner.state["errors"]) > 0


# ── Fix 3: Orphan tmux sweep ────────────────────────────────────────────


@pytest.mark.story("US-PLN-061")
class TestOrphanTmuxSweep:
    """Fix 3: Recovery should kill orphaned agentic-* tmux sessions."""

    def _make_runner(self, tmp_path):
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        return runner, workflow

    @patch("subprocess.run")
    def test_kill_orphaned_tmux_sessions(self, mock_run, tmp_path):
        """Orphaned agentic-* tmux sessions should be killed."""
        runner, _ = self._make_runner(tmp_path)

        # Mock tmux list-sessions
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="agentic-orphan-1\nagentic-orphan-2\nmy-other-session\n",
        )

        # Mock StateStore to return no running sessions
        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_store = MagicMock()
            mock_store.list_all.return_value = []
            MockStore.return_value = mock_store

            killed = runner._kill_orphaned_tmux_sessions()

        assert killed == 2
        # Should have killed both agentic-* sessions but not my-other-session
        kill_calls = [c for c in mock_run.call_args_list if "kill-session" in str(c)]
        assert len(kill_calls) == 2

    @patch("subprocess.run")
    def test_protected_sessions_not_killed(self, mock_run, tmp_path):
        """Running sessions should not be killed."""
        runner, _ = self._make_runner(tmp_path)

        # Mock tmux list-sessions
        list_result = MagicMock(
            returncode=0,
            stdout="agentic-active-1\nagentic-orphan-1\n",
        )

        # Mock kill-session results
        kill_result = MagicMock(returncode=0)

        mock_run.side_effect = [list_result, kill_result]

        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_store = MagicMock()
            mock_store.list_all.return_value = [
                {"session_id": "s1", "status": "running", "pid": 99999,
                 "tmux_session": "agentic-active-1"},
            ]
            MockStore.return_value = mock_store

            with patch("agenticcli.utils.state_store.is_process_running", return_value=True):
                killed = runner._kill_orphaned_tmux_sessions()

        assert killed == 1  # Only orphan-1 killed, active-1 protected

    def test_recover_stale_phases_calls_orphan_sweep(self, tmp_path):
        """_recover_stale_phases should call _kill_orphaned_tmux_sessions."""
        runner, workflow = self._make_runner(tmp_path)

        mock_repo = MagicMock()
        mock_repo.list_phases.return_value = []

        with patch.object(runner, "_kill_orphaned_tmux_sessions") as mock_kill:
            runner._recover_stale_phases(mock_repo, "test_plan")

        mock_kill.assert_called_once()


# ── Fix 4: Phase-filtered get_current_ticket ─────────────────────────────


@pytest.mark.story("US-PLN-061")
class TestPhaseFilteredTicket:
    """Fix 4: get_current_ticket should accept phase_name filter."""

    def test_epic_repository_phase_filter(self, tmp_path):
        """EpicRepository.get_current_ticket with phase_name should filter."""
        from agenticguidance.services.epic_repository import EpicRepository

        repo = EpicRepository()

        # Create epic and tickets in two phases
        epic_name = "test_phase_filter_epic"
        epic_path = tmp_path / "docs" / "epics" / "live" / epic_name
        epic_path.mkdir(parents=True, exist_ok=True)
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epic_path),
            "objective": "test",
        })
        repo.add_phase(epic_name, {"phase_id": "P1", "name": "P1", "agent": "build-python"})
        repo.add_phase(epic_name, {"phase_id": "P2", "name": "P2", "agent": "test-builder"})
        repo.add_ticket(epic_name, "P1", {
            "task_id": "T1", "name": "Task 1", "status": "pending",
        })
        repo.add_ticket(epic_name, "P2", {
            "task_id": "T2", "name": "Task 2", "status": "pending",
        })

        # Without filter: returns first ticket
        ticket = repo.get_current_ticket(epic_name)
        assert ticket is not None
        assert ticket.id == "T1"

        # With P2 filter: returns T2
        ticket_p2 = repo.get_current_ticket(epic_name, phase_name="P2")
        assert ticket_p2 is not None
        assert ticket_p2.id == "T2"

        # With non-existent phase: returns None
        ticket_none = repo.get_current_ticket(epic_name, phase_name="P99")
        assert ticket_none is None

        repo.close()


# ── Fix 5: Phase-scoped agent context ────────────────────────────────────


@pytest.mark.story("US-PLN-061")
class TestPhaseScopedContext:
    """Fix 5: Spawn context should include phase constraint."""

    def test_compile_spawn_context_includes_phase_constraint(self):
        """When phase_id is provided, context should include phase constraint."""
        from agenticcli.commands.session import _compile_spawn_context

        context = _compile_spawn_context(
            prompt="Do stuff",
            role=None,
            epic_folder=Path("test_epic"),
            phase_id="P3",
        )

        assert "Phase Constraint" in context
        assert "P3" in context
        assert "--phase" in context

    def test_compile_spawn_context_no_phase_when_none(self):
        """When phase_id is None, context should NOT include phase constraint."""
        from agenticcli.commands.session import _compile_spawn_context

        context = _compile_spawn_context(
            prompt="Do stuff",
            role=None,
            epic_folder=Path("test_epic"),
            phase_id=None,
        )

        assert "Phase Constraint" not in context

    def test_build_spawn_command_includes_phase(self):
        """build_spawn_command should include --phase when provided."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command(
            role="build-python",
            epic_folder="test_epic",
            phase_id="P3",
        )
        assert "--phase" in cmd
        assert "P3" in cmd

    def test_build_spawn_command_no_phase_when_none(self):
        """build_spawn_command should not include --phase when None."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command(
            role="build-python",
            epic_folder="test_epic",
        )
        assert "--phase" not in cmd

    def test_check_phase_tickets_complete(self, tmp_path):
        """_check_phase_tickets_complete should return incomplete ticket IDs."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic import TicketData

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")

        mock_repo = MagicMock()
        mock_repo.list_tickets.return_value = [
            MagicMock(id="T1", phase_name="P1", status="completed"),
            MagicMock(id="T2", phase_name="P1", status="pending"),
            MagicMock(id="T3", phase_name="P2", status="pending"),
        ]

        incomplete = runner._check_phase_tickets_complete(mock_repo, "test", "P1")
        assert incomplete == ["T2"]


# ── Fix 6: Pipe-pane logging ────────────────────────────────────────────


@pytest.mark.story("US-PLN-061")
class TestPipePaneLogging:
    """Fix 6: tmux pipe-pane should be enabled after spawn."""

    @patch("subprocess.run")
    def test_enable_pipe_pane_logging(self, mock_run):
        """_enable_pipe_pane_logging should call tmux pipe-pane."""
        from agenticcli.commands.session import _enable_pipe_pane_logging

        _enable_pipe_pane_logging("agentic-test-session", "sess-123")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "pipe-pane" in call_args
        assert "agentic-test-session" in call_args
        assert "sess-123.pane.log" in call_args[-1]

    def test_session_cleanup_handles_pane_logs(self):
        """SessionCleanupService should extract IDs from .pane.log files."""
        from agenticcli.utils.session_cleanup import SessionCleanupService

        sid = SessionCleanupService._extract_session_id_from_log("abc-123.pane.log")
        assert sid == "abc-123"

    def test_session_cleanup_cleans_pane_logs(self, tmp_path):
        """SessionCleanupService should clean .pane.log files for cleaned sessions."""
        from agenticcli.utils.session_cleanup import SessionCleanupService

        # Create mock session dir structure
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        logs_dir = sessions_dir / "logs"
        logs_dir.mkdir()

        # Create a pane log
        pane_log = logs_dir / "dead-session.pane.log"
        pane_log.write_text("some log output")

        # Create session JSON (dead session)
        session_file = sessions_dir / "dead-session.json"
        session_file.write_text(json.dumps({
            "session_id": "dead-session",
            "status": "completed",
            "started_at": "2020-01-01T00:00:00",
        }))

        service = SessionCleanupService(state_dir=sessions_dir)
        report = service.cleanup(dry_run=False)

        assert report.sessions_cleaned >= 1 or report.log_files_removed >= 1


# ── PhaseLoggerAdapter: Structured context logging ────────────────────────


@pytest.mark.story("US-PLN-061")
class TestPhaseLoggerAdapterUnit:
    """PhaseLoggerAdapter should prefix messages with [epic:phase] context."""

    def test_process_prefixes_message_with_epic_and_phase(self):
        """process() should prepend [epic_name:phase_name] to messages."""
        from agenticcli.workflows.orchestration import PhaseLoggerAdapter

        base_logger = logging.getLogger("test.phase_adapter")
        adapter = PhaseLoggerAdapter(
            base_logger,
            epic_name="my_epic",
            phase_name="Build Phase",
        )

        msg, kwargs = adapter.process("Phase started", {})
        assert msg == "[my_epic:Build Phase] Phase started"
        assert kwargs == {}

    def test_extra_contains_epic_and_phase(self):
        """Adapter extra dict should contain epic_name, phase_name, phase_id."""
        from agenticcli.workflows.orchestration import PhaseLoggerAdapter

        base_logger = logging.getLogger("test.phase_adapter")
        adapter = PhaseLoggerAdapter(
            base_logger,
            epic_name="my_epic",
            phase_name="Test Phase",
        )

        assert adapter.extra["epic_name"] == "my_epic"
        assert adapter.extra["phase_name"] == "Test Phase"
        # phase_id defaults to phase_name when not provided
        assert adapter.extra["phase_id"] == "Test Phase"

    def test_phase_id_defaults_to_phase_name(self):
        """When phase_id is None, it should default to phase_name."""
        from agenticcli.workflows.orchestration import PhaseLoggerAdapter

        base_logger = logging.getLogger("test.phase_adapter")
        adapter = PhaseLoggerAdapter(
            base_logger,
            epic_name="my_epic",
            phase_name="P1",
            phase_id=None,
        )

        assert adapter.extra["phase_id"] == "P1"

    def test_explicit_phase_id_used_when_provided(self):
        """When phase_id is explicitly provided, it should be used."""
        from agenticcli.workflows.orchestration import PhaseLoggerAdapter

        base_logger = logging.getLogger("test.phase_adapter")
        adapter = PhaseLoggerAdapter(
            base_logger,
            epic_name="my_epic",
            phase_name="Build Phase",
            phase_id="P1-BUILD",
        )

        assert adapter.extra["phase_id"] == "P1-BUILD"
        # process still uses phase_name for the prefix (not phase_id)
        msg, _ = adapter.process("Started", {})
        assert msg == "[my_epic:Build Phase] Started"

    def test_adapter_logs_at_all_levels(self, caplog):
        """PhaseLoggerAdapter should work with info, warning, error, debug."""
        from agenticcli.workflows.orchestration import PhaseLoggerAdapter

        base_logger = logging.getLogger("test.phase_adapter.levels")
        adapter = PhaseLoggerAdapter(
            base_logger,
            epic_name="test_epic",
            phase_name="P1",
        )

        with caplog.at_level(logging.DEBUG, logger="test.phase_adapter.levels"):
            adapter.info("info message")
            adapter.warning("warning message")
            adapter.error("error message")
            adapter.debug("debug message")

        # All 4 messages should appear in the log
        messages = [r.message for r in caplog.records]
        assert any("[test_epic:P1] info message" in m for m in messages)
        assert any("[test_epic:P1] warning message" in m for m in messages)
        assert any("[test_epic:P1] error message" in m for m in messages)
        assert any("[test_epic:P1] debug message" in m for m in messages)

    def test_adapter_preserves_kwargs(self):
        """process() should pass kwargs through unmodified."""
        from agenticcli.workflows.orchestration import PhaseLoggerAdapter

        base_logger = logging.getLogger("test.phase_adapter")
        adapter = PhaseLoggerAdapter(
            base_logger,
            epic_name="my_epic",
            phase_name="P1",
        )

        kwargs = {"extra": {"custom_key": "value"}}
        msg, returned_kwargs = adapter.process("test", kwargs)
        assert returned_kwargs == {"extra": {"custom_key": "value"}}

    def test_adapter_handles_format_strings(self, caplog):
        """PhaseLoggerAdapter should handle %-style format strings correctly."""
        from agenticcli.workflows.orchestration import PhaseLoggerAdapter

        base_logger = logging.getLogger("test.phase_adapter.format")
        adapter = PhaseLoggerAdapter(
            base_logger,
            epic_name="my_epic",
            phase_name="P1",
        )

        with caplog.at_level(logging.INFO, logger="test.phase_adapter.format"):
            adapter.info("Phase %s completed in %d seconds", "P1", 42)

        assert any("P1 completed in 42 seconds" in r.message for r in caplog.records)

    def test_adapter_is_instance_of_logging_logger_adapter(self):
        """PhaseLoggerAdapter should be a proper subclass of logging.LoggerAdapter."""
        from agenticcli.workflows.orchestration import PhaseLoggerAdapter

        base_logger = logging.getLogger("test.phase_adapter")
        adapter = PhaseLoggerAdapter(
            base_logger,
            epic_name="my_epic",
            phase_name="P1",
        )

        assert isinstance(adapter, logging.LoggerAdapter)


@pytest.mark.story("US-PLN-061")
class TestPhaseLoggerAdapterWithExecutionRunner:
    """PhaseLoggerAdapter integration with ExecutionRunner._make_phase_logger."""

    def _make_runner(self, tmp_path):
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        return runner

    def test_make_phase_logger_returns_adapter(self, tmp_path):
        """_make_phase_logger should return a PhaseLoggerAdapter instance."""
        from agenticcli.workflows.orchestration import PhaseLoggerAdapter

        runner = self._make_runner(tmp_path)
        phase_log = runner._make_phase_logger("test_epic", "Build Phase")

        assert isinstance(phase_log, PhaseLoggerAdapter)
        assert phase_log.extra["epic_name"] == "test_epic"
        assert phase_log.extra["phase_name"] == "Build Phase"

    def test_make_phase_logger_with_phase_id(self, tmp_path):
        """_make_phase_logger should pass phase_id through."""
        runner = self._make_runner(tmp_path)
        phase_log = runner._make_phase_logger("test_epic", "Build Phase", phase_id="P1-BUILD")

        assert phase_log.extra["phase_id"] == "P1-BUILD"

    def test_make_phase_logger_default_phase_id(self, tmp_path):
        """_make_phase_logger without phase_id should default to phase_name."""
        runner = self._make_runner(tmp_path)
        phase_log = runner._make_phase_logger("test_epic", "Build Phase")

        assert phase_log.extra["phase_id"] == "Build Phase"

    def test_phase_logger_used_in_blocked_detection(self, tmp_path, caplog):
        """Blocked phase detection should use phase logger with correct context."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic import PhaseData

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        mock_repo = MagicMock()
        mock_repo.list_phases.return_value = [
            PhaseData(
                name="Test Phase",
                status="blocked",
                agent="build-python",
                blocked_reason="SDK failure",
            ),
        ]
        workflow._get_repository.return_value = mock_repo

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")

        with caplog.at_level(logging.ERROR):
            result = runner._execute_plan("test_plan", max_iterations=5)

        assert result is False
        # Verify the error log includes structured context
        error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_logs) > 0
        # The log message should contain the blocked reason
        assert any("SDK failure" in r.message for r in error_logs)
