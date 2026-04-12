# story: US-PLN-061
"""Tests for FIX-005 and FIX-006.

FIX-005a: Atomic writeback — phase status commits even on SIGINT.
FIX-005b: Startup reconciliation — stuck in_progress auto-promoted when
          last session completed successfully.
FIX-006:  Foreground tee — stdout.log written by _run_executing_loop.
"""

import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── FIX-005a: Atomic writeback ──────────────────────────────────────────────


@pytest.mark.story("US-PLN-061")
class TestAtomicWriteback:
    """Phase status commits even when KeyboardInterrupt arrives after agent success."""

    def _make_runner(self, tmp_path):
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir
        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        return runner

    def test_commit_phase_result_atomic_commits_on_keyboard_interrupt(self, tmp_path):
        """_commit_phase_result_atomic must write status even if KeyboardInterrupt fires."""
        runner = self._make_runner(tmp_path)
        mock_repo = MagicMock()

        call_count = [0]

        def side_effect(plan_folder, phase_name, updates):
            call_count[0] += 1
            if call_count[0] == 1:
                raise KeyboardInterrupt()

        mock_repo.update_phase.side_effect = side_effect

        with pytest.raises(KeyboardInterrupt):
            runner._commit_phase_result_atomic(mock_repo, "test_plan", "P1", "completed")

        # Must have attempted the write twice (first raised KI, second committed)
        assert mock_repo.update_phase.call_count == 2

    def test_commit_phase_result_atomic_no_interrupt(self, tmp_path):
        """Normal path: update called once, no exception."""
        runner = self._make_runner(tmp_path)
        mock_repo = MagicMock()

        runner._commit_phase_result_atomic(mock_repo, "test_plan", "P1", "completed")

        mock_repo.update_phase.assert_called_once_with("test_plan", "P1", {"status": "completed"})

    def test_execute_plan_uses_atomic_commit_for_success(self, tmp_path):
        """_execute_plan success path calls _commit_phase_result_atomic, not bare update_phase."""
        import inspect
        from agenticcli.workflows.orchestration import ExecutionRunner

        source = inspect.getsource(ExecutionRunner._execute_plan)
        assert "_commit_phase_result_atomic" in source, (
            "_execute_plan must use _commit_phase_result_atomic for the success writeback"
        )

    def test_atomic_writeback_with_real_tinydb(self, tmp_path, monkeypatch):
        """Phase status lands in TinyDB even when KeyboardInterrupt arrives mid-write."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic import PhaseData
        from agenticguidance.services.epic_repository import EpicRepository

        # Use a real TinyDB to verify the write actually persists
        db_path = tmp_path / "epics.db"
        monkeypatch.setenv("AGENTIC_DB_PATH", str(db_path))

        repo = EpicRepository(db_path=db_path)
        epic_name = "test_atomic_epic"
        epic_path = tmp_path / epic_name
        epic_path.mkdir()
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epic_path),
            "objective": "test",
        })
        repo.add_phase(epic_name, {
            "phase_id": "P1", "name": "P1", "agent": "build-python", "status": "in_progress",
        })

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        runner = ExecutionRunner(workflow=workflow, plan_folder=epic_name)

        # Patch update_phase to raise KI on first call, then succeed
        original_update = repo.update_phase
        call_count = [0]

        def patched_update(plan_folder, phase_name, updates):
            call_count[0] += 1
            if call_count[0] == 1:
                raise KeyboardInterrupt()
            return original_update(plan_folder, phase_name, updates)

        repo.update_phase = patched_update

        with pytest.raises(KeyboardInterrupt):
            runner._commit_phase_result_atomic(repo, epic_name, "P1", "completed")

        phase = repo.get_phase(epic_name, "P1")
        assert phase is not None
        assert phase.status == "completed", (
            f"Phase must be completed after atomic writeback, got {phase.status!r}"
        )
        repo.close()


# ── FIX-005b: Startup reconciliation ───────────────────────────────────────


@pytest.mark.story("US-PLN-061")
class TestStartupReconciliation:
    """Stuck in_progress phases auto-promoted when last session completed."""

    def _make_runner(self, tmp_path):
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir
        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        return runner

    def test_reconcile_promotes_phase_when_session_completed(self, tmp_path, caplog):
        """A stuck in_progress phase is promoted to completed if last session succeeded."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic_repository import EpicRepository
        from agenticcli.utils.state_store import StateStore

        # Seed TinyDB with an in_progress phase that has last_session_id
        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path)
        epic_name = "test_reconcile_epic"
        epic_path = tmp_path / epic_name
        epic_path.mkdir()
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epic_path),
            "objective": "test",
        })
        repo.add_phase(epic_name, {
            "phase_id": "P1", "name": "P1", "agent": "build-python",
            "status": "in_progress",
        })
        # Store last_session_id via update_phase (add_phase schema doesn't pass it through)
        repo.update_phase(epic_name, "P1", {"last_session_id": "sess-abc123"})

        # Seed StateStore with a completed session record
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        session_file = sessions_dir / "sess-abc123.json"
        session_file.write_text(json.dumps({
            "session_id": "sess-abc123",
            "status": "completed",
            "exit_code": 0,
            "epic_folder": epic_name,
        }))

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        runner = ExecutionRunner(workflow=workflow, plan_folder=epic_name)

        # Patch StateStore.get_dir to use our tmp sessions dir
        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_store_instance = MagicMock()
            mock_store_instance.load.return_value = {
                "session_id": "sess-abc123",
                "status": "completed",
                "exit_code": 0,
            }
            MockStore.return_value = mock_store_instance

            with patch.object(runner, "_kill_orphaned_tmux_sessions"):
                with caplog.at_level(logging.WARNING):
                    runner._recover_stale_phases(repo, epic_name)

        phase = repo.get_phase(epic_name, "P1")
        assert phase is not None
        assert phase.status == "completed", (
            f"Phase should be promoted to completed, got {phase.status!r}"
        )
        # Warning should be logged about reconciliation
        assert any("Reconciled" in r.message or "reconcil" in r.message.lower()
                   for r in caplog.records)
        repo.close()

    def test_reconcile_resets_to_planning_when_session_failed(self, tmp_path):
        """A stuck phase with a failed last session is reset to planning."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path)
        epic_name = "test_reset_epic"
        epic_path = tmp_path / epic_name
        epic_path.mkdir()
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epic_path),
            "objective": "test",
        })
        repo.add_phase(epic_name, {
            "phase_id": "P1", "name": "P1", "agent": "build-python",
            "status": "in_progress", "last_session_id": "sess-failed",
        })

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        runner = ExecutionRunner(workflow=workflow, plan_folder=epic_name)

        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_store_instance = MagicMock()
            mock_store_instance.load.return_value = {
                "session_id": "sess-failed",
                "status": "failed",
                "exit_code": 1,
            }
            MockStore.return_value = mock_store_instance

            with patch.object(runner, "_kill_orphaned_tmux_sessions"):
                runner._recover_stale_phases(repo, epic_name)

        phase = repo.get_phase(epic_name, "P1")
        assert phase is not None
        assert phase.status == "planning", (
            f"Phase with failed session should be reset to planning, got {phase.status!r}"
        )
        repo.close()

    def test_reconcile_resets_to_planning_when_no_session_record(self, tmp_path):
        """A stuck phase with no session record is reset to planning (original behaviour)."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "epics.db"
        repo = EpicRepository(db_path=db_path)
        epic_name = "test_no_session_epic"
        epic_path = tmp_path / epic_name
        epic_path.mkdir()
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epic_path),
            "objective": "test",
        })
        repo.add_phase(epic_name, {
            "phase_id": "P1", "name": "P1", "agent": "build-python",
            "status": "in_progress",
            # No last_session_id stored
        })

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        runner = ExecutionRunner(workflow=workflow, plan_folder=epic_name)

        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_store_instance = MagicMock()
            mock_store_instance.load.return_value = None  # No session found
            MockStore.return_value = mock_store_instance

            with patch.object(runner, "_kill_orphaned_tmux_sessions"):
                runner._recover_stale_phases(repo, epic_name)

        phase = repo.get_phase(epic_name, "P1")
        assert phase is not None
        assert phase.status == "planning"
        repo.close()


# ── FIX-006: Foreground log tee ──────────────────────────────────────────


@pytest.mark.story("US-PLN-061")
class TestForegroundLogTee:
    """_run_executing_loop writes stdout.log under ~/.agentic/sessions/<loop_id>/."""

    def test_tee_stream_writes_to_file_and_original(self, tmp_path):
        """_TeeStream duplicates writes to both original stream and log file."""
        import io
        from agenticcli.commands.orchestrate import _TeeStream

        buf = io.StringIO()
        log_file = tmp_path / "stdout.log"
        tee = _TeeStream(buf, log_file)

        tee.write("hello world\n")
        tee.flush()
        tee.close()

        assert buf.getvalue() == "hello world\n"
        assert log_file.exists()
        assert "hello world" in log_file.read_text()

    def test_tee_stream_append_mode(self, tmp_path):
        """_TeeStream append=True opens file in append mode."""
        import io
        from agenticcli.commands.orchestrate import _TeeStream

        log_file = tmp_path / "stdout.log"
        log_file.write_text("existing content\n")

        buf = io.StringIO()
        tee = _TeeStream(buf, log_file, append=True)
        tee.write("new line\n")
        tee.close()

        content = log_file.read_text()
        assert "existing content" in content
        assert "new line" in content

    def test_tee_stream_proxies_attributes(self, tmp_path):
        """_TeeStream proxies unknown attributes to the original stream."""
        import io
        from agenticcli.commands.orchestrate import _TeeStream

        buf = io.StringIO()
        log_file = tmp_path / "stdout.log"
        tee = _TeeStream(buf, log_file)

        # StringIO has .getvalue() — not defined on _TeeStream
        tee.write("data")
        assert tee.getvalue() == "data"
        tee.close()

    def test_run_executing_loop_creates_stdout_log(self, tmp_path, monkeypatch):
        """_run_executing_loop creates stdout.log under the sessions dir."""
        import io
        from agenticcli.commands.orchestrate import _run_executing_loop, _store

        # Redirect the sessions dir to tmp_path
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        monkeypatch.setattr(_store, "get_dir", lambda override=None: sessions_dir)

        # Set a fixed loop_id via env var so we know the path
        loop_id = "exec-test-loop-001"
        monkeypatch.setenv("AGENTIC_EXEC_LOOP_ID", loop_id)

        # Mock the runner so it completes instantly
        mock_runner = MagicMock()
        mock_runner.run.return_value = True
        mock_runner.state = {
            "plans_processed": [],
            "plans_failed": [],
            "phases_completed": [],
            "phases_failed": [],
            "errors": [],
            "iteration": 1,
        }

        args = MagicMock()
        args.max_iterations = 1
        args.background = False
        args.completion_promise = None
        args.project = None
        args.plan = "some_epic"
        args.directory = str(tmp_path)
        args.dangerously_skip_permissions = False
        args.budget_usd = 50.0

        # ExecutionRunner and OrchestrationWorkflow are imported inside the function
        # so we patch them via their home modules.
        with patch("agenticcli.workflows.orchestration.ExecutionRunner", return_value=mock_runner):
            with patch("agenticcli.workflows.orchestration.OrchestrationWorkflow"):
                with patch("sys.exit"):
                    with patch("agenticcli.console.is_json_output", return_value=False):
                        with patch("agenticcli.console.print_success"):
                            _run_executing_loop(args)

        log_file = sessions_dir / loop_id / "stdout.log"
        assert log_file.exists(), (
            f"stdout.log must exist at {log_file} after foreground _run_executing_loop"
        )

    def test_run_planning_loop_creates_stdout_log(self, tmp_path, monkeypatch):
        """_run_planning_loop creates stdout.log under the sessions dir."""
        from agenticcli.commands.orchestrate import _run_planning_loop, _store

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        monkeypatch.setattr(_store, "get_dir", lambda override=None: sessions_dir)

        loop_id = "orch-test-loop-001"
        monkeypatch.setenv("AGENTIC_ORCH_LOOP_ID", loop_id)

        mock_runner = MagicMock()
        mock_runner.run.return_value = True
        mock_runner.state = {
            "plans_processed": [],
            "plans_failed": [],
            "errors": [],
            "iteration": 1,
        }

        args = MagicMock()
        args.max_iterations = 1
        args.background = False
        args.completion_promise = None
        args.project = None
        args.plan = "some_epic"
        args.directory = str(tmp_path)
        args.prompt = None
        args.budget_usd = 50.0
        args.dangerously_skip_permissions = False

        # PlanningRunner and PlannerLoopWorkflow are imported inside the function
        with patch("agenticcli.workflows.orchestration.PlanningRunner", return_value=mock_runner):
            with patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow"):
                with patch("sys.exit"):
                    with patch("agenticcli.console.is_json_output", return_value=False):
                        with patch("agenticcli.console.print_success"):
                            _run_planning_loop(args)

        log_file = sessions_dir / loop_id / "stdout.log"
        assert log_file.exists(), (
            f"stdout.log must exist at {log_file} after foreground _run_planning_loop"
        )
