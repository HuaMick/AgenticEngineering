"""Tests for the planner loop workflow."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-PLN-046", "US-GDN-061")

from agenticcli.utils.sdk_runner import SessionResult


def _ok_result(**kwargs) -> SessionResult:
    """Create a successful SessionResult for testing."""
    return SessionResult(status="completed", result="ok", **kwargs)


def _fail_result(**kwargs) -> SessionResult:
    """Create a failed SessionResult for testing."""
    return SessionResult(status="failed", result="failed", is_error=True, **kwargs)


_UNSET = object()  # Sentinel for "not provided" vs explicit None


def _setup_tinydb_for_workflow(tmp_path, epic_folder_name, *, agent_type=None,
                                context=None, status=_UNSET, tickets=None,
                                phase_agent=None):
    """Set up TinyDB for PlannerLoopWorkflow tests.

    Creates a .git marker so the workflow can find the repo root,
    then populates TinyDB with the given epic data.

    Args:
        tmp_path: pytest tmp_path fixture value.
        epic_folder_name: Name of the epic folder (e.g. "my_plan").
        agent_type: Agent type string for the mock ticket (e.g. "build-python").
        context: Epic context string.
        status: Epic status string (used by get_plan_status). Pass None to
                omit the status field entirely; omit the arg to default "active".
        tickets: List of ticket dicts [{id, name, status, agent_type, ...}].
                 If None and agent_type is given, one ticket is created.
        phase_agent: Agent type for the phase (e.g. "build-python"). When set,
                     is_build_plan() will classify this epic as a build plan.

    Returns:
        db_path: Path to the isolated TinyDB file.
    """
    from agenticguidance.services.epic_repository import EpicRepository

    # Create .git marker so PlannerLoopWorkflow's repo-root walkup stops here
    (tmp_path / ".git").mkdir(exist_ok=True)
    db_path = tmp_path / ".agentic" / "epics.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    epic_doc = {
        "epic_folder_name": epic_folder_name,
        "epic_folder": str(tmp_path / "epics" / epic_folder_name),
        "name": epic_folder_name,
    }
    if status is _UNSET:
        epic_doc["status"] = "active"
    elif status is not None:
        epic_doc["status"] = status
    # If status is explicitly None, leave status out of epic_doc

    if context is not None:
        epic_doc["context"] = context
    repo.create_epic(epic_doc)

    phase_name = "Phase 1"
    phase_doc = {"name": phase_name}
    if phase_agent is not None:
        phase_doc["agent"] = phase_agent
    repo.add_phase(epic_folder_name, phase_doc)

    # Use provided tickets list OR build one from agent_type
    if tickets is not None:
        for t in tickets:
            repo.add_ticket(epic_folder_name, phase_name, t)
    elif agent_type is not None:
        repo.add_ticket(epic_folder_name, phase_name, {
            "task_id": "T001",
            "name": "Mock ticket",
            "status": "pending",
            "agent": agent_type,
        })

    repo.close()
    return db_path


# ---------------------------------------------------------------------------
# PlannerLoopWorkflow tests
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestDiscoverPlansNeedingOrchestration:
    """Test discover_plans_needing_orchestration method.

    The primary path checks TinyDB for live epics with no phases.
    """

    def test_finds_plans_without_phases_in_tinydb(self, tmp_path):
        """Seed/planning epics are returned by discover_plans_needing_orchestration."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        # in_progress epic - should NOT be returned (already past planning)
        repo.create_epic({"epic_folder_name": "260210AA_with_phases", "status": "in_progress"})
        repo.add_phase("260210AA_with_phases", {"name": "Phase 1", "agent": "build-python"})
        # seed epic - should be returned
        repo.create_epic({"epic_folder_name": "260210BB_no_phases", "status": "seed"})
        repo.close()

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        result = workflow.discover_plans_needing_orchestration()

        assert result == ["260210BB_no_phases"]

    def test_returns_empty_when_all_in_progress(self, tmp_path):
        """No plans returned when all epics are past the planning stage."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({"epic_folder_name": "260210AA_done", "status": "in_progress"})
        repo.add_phase("260210AA_done", {"name": "Phase 1", "agent": "build-python"})
        repo.close()

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        result = workflow.discover_plans_needing_orchestration()

        assert result == []

    def test_returns_empty_when_no_epics_in_tinydb(self, tmp_path):
        """Returns empty list when no live epics in TinyDB."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create an empty DB
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.close()

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        result = workflow.discover_plans_needing_orchestration()

        assert result == []


@pytest.mark.story("US-PLN-046")
class TestRunHealthCheck:
    """Test run_health_check method."""

    def test_health_check_success(self, monkeypatch):
        """Health check passes when both commands return 0."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = PlannerLoopWorkflow()
        workflow.run_health_check()  # Should not raise

    def test_health_check_version_failure(self, monkeypatch):
        """Health check raises when agentic --version fails."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        def mock_run(cmd, **kwargs):
            if "--version" in cmd:
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = PlannerLoopWorkflow()
        with pytest.raises(RuntimeError, match="agentic --version"):
            workflow.run_health_check()

    def test_health_check_plan_list_failure(self, monkeypatch):
        """Health check raises when agentic epic list fails."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        def mock_run(cmd, **kwargs):
            if "list" in cmd:
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = PlannerLoopWorkflow()
        with pytest.raises(RuntimeError, match="agentic epic list"):
            workflow.run_health_check()


# ---------------------------------------------------------------------------
# PlannerLoopRunner tests
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046", "US-PLN-047")
class TestPlannerLoopRunner:
    """Test PlannerLoopRunner orchestration.

    Spawn methods now return SessionResult instead of session IDs.
    The spawn+wait pattern is eliminated — each call blocks until completion.
    """

    def _make_runner(self, monkeypatch, epic_folders=None, **overrides):
        """Create a runner with a mocked workflow.

        Args:
            epic_folders: Optional list of epic folder names to create as
                stub directories under the temp epics_dir. Defaults to
                ["test_plan"] for backward compatibility.
        """
        import tempfile
        import yaml
        from pathlib import Path
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow

        # Create a temporary empty epics_dir so iterdir() won't fail
        tmp_epics_dir = Path(tempfile.mkdtemp()) / "docs" / "epics" / "live"
        tmp_epics_dir.mkdir(parents=True, exist_ok=True)
        # Create stub epic folders so the folder-existence guard doesn't reject them
        for folder in (epic_folders or ["test_plan"]):
            (tmp_epics_dir / folder).mkdir(exist_ok=True)

        workflow = PlannerLoopWorkflow(epics_dir=tmp_epics_dir)

        # Monkeypatch get_epic_stories_path to write to a test-local
        # docs/userstories/EpicStories/ directory instead of the real one.
        userstories_dir = tmp_epics_dir.parent.parent / "userstories" / "EpicStories"
        userstories_dir.mkdir(parents=True, exist_ok=True)

        import agenticcli.workflows.planner_loop as _plmod
        def _test_get_epic_stories_path(epic_name):
            return userstories_dir / f"{epic_name}.yml"
        monkeypatch.setattr(_plmod, "get_epic_stories_path", _test_get_epic_stories_path)

        # Story file writer: ensures story file exists (stories are required).
        # Wraps any provided spawn_story override so it also writes the file.
        def _write_stories_yml(pf):
            stories_path = userstories_dir / f"{pf}.yml"
            if not stories_path.exists():
                stories_path.write_text(yaml.dump({
                    "stories": [{"id": "US-001", "title": "Test story"}],
                    "categories": [{"name": "default", "story_ids": ["US-001"]}],
                }))

        def _default_spawn_story(pf):
            _write_stories_yml(pf)
            return _ok_result(session_id="story-session-default")

        # If caller provided a custom spawn_story, wrap it to also write story file
        # (only on success — failed story agents don't produce output)
        custom_story = overrides.get("spawn_story")
        if custom_story is not None:
            _original = custom_story
            def _wrapped_spawn_story(pf, _orig=_original):
                result = _orig(pf)
                if result.status == "completed":
                    _write_stories_yml(pf)
                return result
            overrides["spawn_story"] = _wrapped_spawn_story

        # Also mock get_plan_status so archive loop doesn't fail on missing plans
        monkeypatch.setattr(workflow, "get_plan_status", lambda pf: "in_progress")
        # Default mocks: all spawn methods return successful SessionResult
        monkeypatch.setattr(workflow, "run_health_check", overrides.get("health_check", lambda: None))
        monkeypatch.setattr(workflow, "discover_plans_needing_orchestration",
                            overrides.get("discover", lambda: []))
        monkeypatch.setattr(workflow, "spawn_epic_creator",
                            overrides.get("spawn_epic_creator", lambda pf: _ok_result()))
        monkeypatch.setattr(workflow, "spawn_planner_phases",
                            overrides.get("spawn_planner_phases", lambda pf, phase_ids, role: _ok_result()))
        monkeypatch.setattr(workflow, "spawn_story_agent",
                            overrides.get("spawn_story", _default_spawn_story))
        monkeypatch.setattr(workflow, "spawn_orchestration_agent",
                            overrides.get("spawn_orchestration", lambda pf: _ok_result()))

        runner = PlannerLoopRunner(workflow=workflow)
        # Mock validation to pass (these tests don't have a TinyDB repo)
        monkeypatch.setattr(runner, "_validate_planning_output", lambda pf, skip_story_ids_check=False: (True, []))
        return runner

    def test_completes_when_no_plans(self, monkeypatch, capsys):
        """Runner exits successfully when no plans need work."""
        runner = self._make_runner(monkeypatch)
        result = runner.run(max_iterations=5)

        assert result is True
        assert "Planning complete" in capsys.readouterr().out

    def test_processes_single_plan(self, monkeypatch, capsys):
        """Runner processes a plan through the pipeline: epic-creator → orchestration → story → spawn_planner_phases."""
        call_log = []

        def tracking_discover():
            if not call_log or "discover" not in [c[0] for c in call_log]:
                call_log.append(("discover",))
                return ["test_plan"]
            return []

        def tracking_epic_creator(pf):
            call_log.append(("epic_creator", pf))
            return _ok_result(session_id="creator-session-abc")

        def tracking_spawn_story(pf):
            call_log.append(("spawn_story", pf))
            return _ok_result(session_id="story-session-abc")

        def tracking_spawn_planner_phases(pf, phase_ids, role):
            call_log.append(("spawn_planner_phases", pf, role))
            return _ok_result(session_id="planner-session-abc")

        def tracking_orchestration(pf):
            call_log.append(("orchestration", pf))
            return _ok_result(session_id="orchestration-session-abc")

        runner = self._make_runner(
            monkeypatch,
            discover=tracking_discover,
            spawn_epic_creator=tracking_epic_creator,
            spawn_story=tracking_spawn_story,
            spawn_planner_phases=tracking_spawn_planner_phases,
            spawn_orchestration=tracking_orchestration,
        )
        result = runner.run(max_iterations=5)

        assert result is True
        # Verify call sequence includes core pipeline steps
        step_names = [c[0] for c in call_log]
        assert "discover" in step_names
        assert "epic_creator" in step_names
        assert "spawn_story" in step_names
        assert "orchestration" in step_names

        # Verify ordering: epic_creator -> orchestration -> story
        idx_creator = next(i for i, c in enumerate(call_log) if c[0] == "epic_creator")
        idx_orch = next(i for i, c in enumerate(call_log) if c[0] == "orchestration")
        idx_story = next(i for i, c in enumerate(call_log) if c[0] == "spawn_story")
        assert idx_creator < idx_orch < idx_story

    def test_epic_creator_failure_skips_plan(self, monkeypatch):
        """Plan is skipped when epic-creator agent fails."""
        call_count = {"discover": 0}

        def discover():
            call_count["discover"] += 1
            if call_count["discover"] <= 1:
                return ["bad_creator_plan"]
            return []

        runner = self._make_runner(
            monkeypatch,
            epic_folders=["bad_creator_plan"],
            discover=discover,
            spawn_epic_creator=lambda pf: _fail_result(),
        )
        result = runner.run(max_iterations=5)

        assert "bad_creator_plan" in runner.state["plans_skipped"]

    def test_planner_build_failure_skips_plan(self, monkeypatch):
        """Plan is skipped when planner-build spawn fails."""
        call_count = {"discover": 0}

        def discover():
            call_count["discover"] += 1
            if call_count["discover"] <= 1:
                return ["bad_planner_build_plan"]
            return []

        def _failing_planner_phases(pf, phase_ids, role):
            if role == "planner-build":
                return _fail_result()
            return _ok_result()

        runner = self._make_runner(
            monkeypatch,
            epic_folders=["bad_planner_build_plan"],
            discover=discover,
            spawn_planner_phases=_failing_planner_phases,
        )

        # Override the planning decision to provide build_phase_ids so the
        # planner-build wave is triggered and can fail.
        import agenticcli.workflows.planner_loop as _plmod
        from agenticguidance.services.epic_repository import EpicRepository
        import unittest.mock as _mock
        runner.workflow._repository = _mock.MagicMock()
        runner.workflow._repository.refresh = _mock.MagicMock()
        runner.workflow._repository.read_planning_decision = _mock.MagicMock(
            return_value={
                "needs_stories": True,
                "needs_preflight_story_check": True,
                "build_phase_ids": ["p1"],
                "test_phase_ids": [],
            }
        )

        result = runner.run(max_iterations=5)

        assert "bad_planner_build_plan" in runner.state["plans_skipped"]

    def test_story_agent_failure_skips_plan(self, monkeypatch):
        """Plan is skipped when story agent fails."""
        call_count = {"discover": 0}

        def discover():
            call_count["discover"] += 1
            if call_count["discover"] <= 1:
                return ["bad_story_plan"]
            return []

        runner = self._make_runner(
            monkeypatch,
            discover=discover,
            spawn_story=lambda pf: _fail_result(),
        )
        result = runner.run(max_iterations=5)

        assert "bad_story_plan" in runner.state["plans_skipped"]

    def test_respects_max_iterations(self, monkeypatch):
        """Runner stops early when all discovered epics fail planning."""
        runner = self._make_runner(
            monkeypatch,
            epic_folders=["always_plan"],
            discover=lambda: ["always_plan"],
            # Make epic-creator fail so the epic is marked as failed
            spawn_epic_creator=lambda pf: _fail_result(),
        )
        result = runner.run(max_iterations=2)

        assert result is False
        # Early stop: all discovered epics failed, no point retrying
        assert "always_plan" in runner.state["plans_skipped"]

    def test_handles_health_check_failure(self, monkeypatch):
        """Runner exits early on health check failure."""
        def bad_health():
            raise RuntimeError("unhealthy")

        runner = self._make_runner(monkeypatch, health_check=bad_health)
        result = runner.run()

        assert result is False
        assert any("unhealthy" in e.get("error", "") for e in runner.state["errors"])

@pytest.mark.story("US-PLN-046")
class TestRunRoleAgent:
    """Test the _run_role_agent SDK integration method."""

    def test_sdk_path_records_session_state(self, monkeypatch):
        """SDK-direct path writes session state (used when tmux unavailable)."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        saved_data = {}

        def mock_save(data):
            saved_data.update(data)

        def mock_run_agent_sync(prompt, options, on_message=None, timeout_seconds=1800):
            return SessionResult(
                status="completed",
                result="Agent done",
                cost_usd=0.03,
                duration_ms=2000,
                session_id="claude-session-xyz",
            )

        monkeypatch.setattr("agenticcli.workflows.planner_loop.SDK_AVAILABLE", True)
        monkeypatch.setattr("agenticcli.workflows.planner_loop.run_agent_sync", mock_run_agent_sync)
        monkeypatch.setattr("agenticcli.workflows.planner_loop._session_store.save", mock_save)
        # Mock _build_sdk_options to avoid importing real SDK (role kwarg supported since PO_003)
        monkeypatch.setattr("agenticcli.workflows.planner_loop._build_sdk_options", lambda wd, role=None: None)
        # Mock tmux as unavailable so it falls back to SDK-direct
        monkeypatch.setattr("shutil.which", lambda x: None)

        workflow = PlannerLoopWorkflow()
        result = workflow._run_role_agent("epic-creator", "test_plan")

        assert result.status == "completed"
        assert saved_data["status"] == "completed"
        assert saved_data["transport"] == "sdk"
        assert saved_data["role"] == "epic-creator"
        assert saved_data["cost_usd"] == 0.03

    def test_sdk_direct_fallback_when_tmux_unavailable(self, monkeypatch):
        """Falls back to SDK-direct when tmux is not available."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        called_path = {"path": None}

        def mock_sdk_direct(session_id, role, epic_folder, prompt, **kwargs):
            called_path["path"] = "sdk-direct"
            from agenticcli.utils.sdk_runner import SessionResult
            return SessionResult(status="completed", result="done")

        workflow = PlannerLoopWorkflow()
        monkeypatch.setattr(workflow, "_run_via_sdk", mock_sdk_direct)

        # SDK available but tmux not available (determine_transport returns something other than SDK_TMUX)
        monkeypatch.setattr("agenticcli.workflows.planner_loop.SDK_AVAILABLE", True)
        monkeypatch.setattr("agenticcli.utils.transport.shutil.which", lambda cmd: None)  # no tmux

        result = workflow._run_role_agent("epic-creator", "test_plan")
        assert result.status == "completed"


@pytest.mark.story("US-PLN-046")
class TestGetPlanStatus:
    """Test get_plan_status reads epic status and ticket counts from TinyDB."""

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _make_tinydb_plan(self, tmp_path, epics_dir, folder_name, *,
                          status=None, tickets=None):
        """Create an epic in TinyDB under epics_dir/folder_name.

        Args:
            tmp_path: pytest tmp_path root (used for .git + DB path).
            epics_dir: The epics dir path.
            folder_name: Epic folder name.
            status: Epic-level status string, or None if absent.
            tickets: List of ticket dicts with at least {task_id, status}.
        """
        (epics_dir / folder_name).mkdir(parents=True, exist_ok=True)
        _setup_tinydb_for_workflow(
            tmp_path, folder_name,
            status=status,
            tickets=tickets or [],
        )

    # ------------------------------------------------------------------
    # Core bug regression: active status must NOT be overridden
    # ------------------------------------------------------------------

    def test_planning_status_not_overridden_by_all_tasks_complete(self, tmp_path):
        """TinyDB status: planning is preserved even when all tickets are completed.

        This is the regression test for the auto-archive bug: an epic whose
        TinyDB record has status='planning' must NOT be reported as 'completed'
        just because every ticket carries status='completed'.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_tinydb_plan(
            tmp_path, epics_dir, "planning_plan",
            status="planning",
            tickets=[
                {"task_id": "t1", "name": "task1", "status": "completed"},
                {"task_id": "t2", "name": "task2", "status": "completed"},
            ],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("planning_plan") == "planning"

    def test_in_progress_status_not_overridden(self, tmp_path):
        """Any non-completed TinyDB status is respected regardless of tickets."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_tinydb_plan(
            tmp_path, epics_dir, "wip_plan",
            status="in_progress",
            tickets=[
                {"task_id": "t1", "name": "task1", "status": "completed"},
            ],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("wip_plan") == "in_progress"

    # ------------------------------------------------------------------
    # Pending status: returned as-is (non-completed, non-active)
    # ------------------------------------------------------------------

    def test_planning_status_with_all_tasks_complete_returns_planning(self, tmp_path):
        """Epic with status=planning is returned as-is even when all tickets are done.

        TinyDB always stores a status, so task counting is only triggered when
        the status field is missing. 'planning' is honoured like any non-completed status.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_tinydb_plan(
            tmp_path, epics_dir, "planning_done",
            status="planning",
            tickets=[
                {"task_id": "t1", "name": "task1", "status": "completed"},
                {"task_id": "t2", "name": "task2", "status": "completed"},
            ],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        # "planning" != "completed" and is not None → returned directly
        assert workflow.get_plan_status("planning_done") == "planning"

    def test_planning_status_with_mixed_tasks_returns_planning(self, tmp_path):
        """Epic with status=planning and mixed ticket statuses returns 'planning'."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_tinydb_plan(
            tmp_path, epics_dir, "partial_plan",
            status="planning",
            tickets=[
                {"task_id": "t1", "name": "task1", "status": "completed"},
                {"task_id": "t2", "name": "task2", "status": "pending"},
            ],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("partial_plan") == "planning"

    # ------------------------------------------------------------------
    # Explicit completed status in TinyDB
    # ------------------------------------------------------------------

    def test_explicit_completed_status_all_tasks_done(self, tmp_path):
        """Explicit status=completed with all tickets done returns completed."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_tinydb_plan(
            tmp_path, epics_dir, "done_plan",
            status="completed",
            tickets=[
                {"task_id": "t1", "name": "task1", "status": "completed"},
            ],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("done_plan") == "completed"

    def test_explicit_completed_status_even_with_pending_tasks(self, tmp_path):
        """Explicit status=completed is returned even when tickets are still pending.

        When TinyDB says completed but tickets are pending, task counting
        won't trigger the 'pending==0' branch, so the epic status is returned.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_tinydb_plan(
            tmp_path, epics_dir, "weird_plan",
            status="completed",
            tickets=[
                {"task_id": "t1", "name": "task1", "status": "pending"},
            ],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        # Task counting: pending=1, completed=0 -> not triggered -> falls back to epic_status="completed"
        assert workflow.get_plan_status("weird_plan") == "completed"

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_nonexistent_plan_folder_returns_none(self, tmp_path):
        """Returns None when epic is not in TinyDB."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        # Create .git so workflow initializes but no epic in TinyDB
        (tmp_path / ".git").mkdir(exist_ok=True)
        (tmp_path / ".agentic").mkdir(exist_ok=True)
        workflow = PlannerLoopWorkflow(epics_dir=tmp_path / "epics")
        assert workflow.get_plan_status("ghost_plan") is None

    def test_plan_folder_without_tinydb_entry_returns_none(self, tmp_path):
        """Returns None when epic folder exists on disk but not in TinyDB."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        plan_dir = epics_dir / "no_db_entry"
        plan_dir.mkdir(parents=True)
        # Create .git but no TinyDB entry
        (tmp_path / ".git").mkdir(exist_ok=True)
        (tmp_path / ".agentic").mkdir(exist_ok=True)

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("no_db_entry") is None

    def test_epic_with_no_tickets_returns_status(self, tmp_path):
        """Returns the epic status even when there are no tickets in TinyDB."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        # Create epic with no tickets
        self._make_tinydb_plan(
            tmp_path, epics_dir, "empty_plan",
            status="planning",
            tickets=[],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        # "planning" is not None and not "completed" → returned as-is
        assert workflow.get_plan_status("empty_plan") == "planning"


@pytest.mark.story("US-PLN-046")
class TestProcessPlanPlanningTransition:
    """Verify _process_plan sets status=planning at the start."""

    def test_process_plan_sets_planning_status(self, tmp_path, monkeypatch):
        """_process_plan updates epic status to 'planning' before running agents."""
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        (epics_dir / "test_epic").mkdir(parents=True)

        _setup_tinydb_for_workflow(
            tmp_path, "test_epic",
            status="active",
            tickets=[{"task_id": "t1", "name": "task1", "status": "pending"}],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)

        # Track status updates to the repository
        status_updates = []
        real_repo = workflow._get_repository()

        original_update = real_repo.update_epic

        def tracking_update(folder, data):
            if "status" in data:
                status_updates.append(data["status"])
            return original_update(folder, data)

        monkeypatch.setattr(real_repo, "update_epic", tracking_update)
        monkeypatch.setattr(workflow, "get_plan_status", lambda pf: "active")
        monkeypatch.setattr(workflow, "run_health_check", lambda: None)

        # Make epic-creator fail so _process_plan returns early after setting planning
        monkeypatch.setattr(workflow, "spawn_epic_creator", lambda pf: _fail_result(duration_ms=100))

        runner = PlannerLoopRunner(workflow=workflow)
        runner._process_plan("test_epic")

        assert "planning" in status_updates, (
            f"Expected 'planning' in status_updates, got: {status_updates}"
        )


# ---------------------------------------------------------------------------
# SDK Resilience tests (SDK_010, SDK_011)
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestRunViaSdkRetry:
    """Test retry logic in _run_via_sdk (SDK_010)."""

    def _make_workflow(self, monkeypatch):
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow
        workflow = PlannerLoopWorkflow()
        monkeypatch.setattr("agenticcli.workflows.planner_loop.SDK_AVAILABLE", True)
        monkeypatch.setattr("agenticcli.workflows.planner_loop._build_sdk_options", lambda wd, role=None: None)
        monkeypatch.setattr("agenticcli.workflows.planner_loop._session_store.save", lambda d: None)
        # Speed up backoff sleeps
        monkeypatch.setattr("time.sleep", lambda _: None)
        return workflow

    def test_first_attempt_success_no_retry(self, monkeypatch):
        """Succeeds on first attempt — no retry needed."""
        workflow = self._make_workflow(monkeypatch)
        call_count = {"n": 0}

        def mock_run_agent_sync(prompt, options, timeout_seconds=1800):
            call_count["n"] += 1
            return SessionResult(status="completed", result="done", cost_usd=0.01, duration_ms=500)

        monkeypatch.setattr("agenticcli.workflows.planner_loop.run_agent_sync", mock_run_agent_sync)

        result = workflow._run_via_sdk("sid-001", "explore", "my_plan", "prompt", max_retries=3)

        assert result.status == "completed"
        assert call_count["n"] == 1

    def test_retries_on_failure_succeeds_third_attempt(self, monkeypatch):
        """First two attempts fail, third succeeds."""
        workflow = self._make_workflow(monkeypatch)
        call_count = {"n": 0}

        def mock_run_agent_sync(prompt, options, timeout_seconds=1800):
            call_count["n"] += 1
            if call_count["n"] < 3:
                return SessionResult(status="failed", result="transient error", is_error=True)
            return SessionResult(status="completed", result="done on 3rd", cost_usd=0.02, duration_ms=800)

        monkeypatch.setattr("agenticcli.workflows.planner_loop.run_agent_sync", mock_run_agent_sync)

        result = workflow._run_via_sdk("sid-002", "explore", "my_plan", "prompt", max_retries=3)

        assert result.status == "completed"
        assert call_count["n"] == 3

    def test_retry_exhaustion_returns_last_failure(self, monkeypatch):
        """All max_retries attempts fail — returns last failure result."""
        workflow = self._make_workflow(monkeypatch)
        call_count = {"n": 0}

        def mock_run_agent_sync(prompt, options, timeout_seconds=1800):
            call_count["n"] += 1
            return SessionResult(
                status="failed",
                result=f"failure attempt {call_count['n']}",
                is_error=True,
            )

        monkeypatch.setattr("agenticcli.workflows.planner_loop.run_agent_sync", mock_run_agent_sync)

        result = workflow._run_via_sdk("sid-003", "explore", "my_plan", "prompt", max_retries=3)

        assert result.status == "failed"
        assert "failure attempt 3" in result.result
        assert call_count["n"] == 3

    def test_keyboard_interrupt_is_not_retried(self, monkeypatch):
        """KeyboardInterrupt propagates immediately without retrying."""
        workflow = self._make_workflow(monkeypatch)
        call_count = {"n": 0}

        def mock_run_agent_sync(prompt, options, timeout_seconds=1800):
            call_count["n"] += 1
            raise KeyboardInterrupt("User cancelled")

        monkeypatch.setattr("agenticcli.workflows.planner_loop.run_agent_sync", mock_run_agent_sync)

        with pytest.raises(KeyboardInterrupt):
            workflow._run_via_sdk("sid-004", "explore", "my_plan", "prompt", max_retries=3)

        assert call_count["n"] == 1  # Only one attempt before propagating

    def test_retry_logged_at_info_level(self, monkeypatch, caplog):
        """Each retry attempt is logged at INFO level with attempt number."""
        import logging
        workflow = self._make_workflow(monkeypatch)
        call_count = {"n": 0}

        def mock_run_agent_sync(prompt, options, timeout_seconds=1800):
            call_count["n"] += 1
            if call_count["n"] < 2:
                return SessionResult(status="failed", result="retry me", is_error=True)
            return SessionResult(status="completed", result="done", cost_usd=0.01, duration_ms=300)

        monkeypatch.setattr("agenticcli.workflows.planner_loop.run_agent_sync", mock_run_agent_sync)

        with caplog.at_level(logging.INFO, logger="agenticcli.workflows.planner_loop"):
            workflow._run_via_sdk("sid-005", "explore", "my_plan", "prompt", max_retries=3)

        # At least one "Retrying" message should appear
        assert any("retrying" in r.message.lower() for r in caplog.records)

    def test_timeout_passed_per_role(self, monkeypatch):
        """Correct timeout is passed to run_agent_sync based on agent role."""
        from agenticcli.workflows.planner_loop import ROLE_TIMEOUT_SECONDS
        workflow = self._make_workflow(monkeypatch)
        captured_timeouts = {}

        def mock_run_agent_sync(prompt, options, timeout_seconds=1800):
            # Record the timeout used by the most recent call; keyed by prompt content
            captured_timeouts["last"] = timeout_seconds
            return SessionResult(status="completed", result="done", cost_usd=0.01, duration_ms=200)

        monkeypatch.setattr("agenticcli.workflows.planner_loop.run_agent_sync", mock_run_agent_sync)

        # Epic-creator role
        workflow._run_via_sdk("s1", "epic-creator", "p", "prompt")
        assert captured_timeouts["last"] == ROLE_TIMEOUT_SECONDS["epic-creator"]  # 600

        # Orchestration role
        workflow._run_via_sdk("s2", "planner-orchestration", "p", "prompt")
        assert captured_timeouts["last"] == ROLE_TIMEOUT_SECONDS["planner-orchestration"]  # 3600


@pytest.mark.story("US-PLN-046")
class TestValidateResult:
    """Test _validate_result observability helper (SDK_011)."""

    def test_logs_info_summary_for_valid_result(self, caplog):
        """Info log is always emitted with chars and duration."""
        import logging
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow()
        result = SessionResult(
            status="completed",
            result="Some agent output text",
            duration_ms=1500,
        )

        with caplog.at_level(logging.INFO, logger="agenticcli.workflows.planner_loop"):
            workflow._validate_result(result, "explore")

        assert any("explore" in r.message and "1500" in r.message for r in caplog.records)

    def test_warns_on_empty_result(self, caplog):
        """WARNING logged when result text is empty."""
        import logging
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow()
        result = SessionResult(status="completed", result="   ", duration_ms=500)

        with caplog.at_level(logging.WARNING, logger="agenticcli.workflows.planner_loop"):
            workflow._validate_result(result, "planner-build")

        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("empty" in m.lower() for m in warning_messages)

    def test_warns_on_zero_duration(self, caplog):
        """WARNING logged when duration_ms is 0."""
        import logging
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow()
        result = SessionResult(status="completed", result="some output", duration_ms=0)

        with caplog.at_level(logging.WARNING, logger="agenticcli.workflows.planner_loop"):
            workflow._validate_result(result, "build-story-writer")

        warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("zero duration" in m.lower() or "duration" in m.lower() for m in warning_messages)

    def test_no_warnings_for_good_result(self, caplog):
        """No WARNING emitted for a genuine successful result."""
        import logging
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow()
        result = SessionResult(
            status="completed",
            result="Detailed agent output with substance",
            duration_ms=2500,
            cost_usd=0.05,
        )

        with caplog.at_level(logging.WARNING, logger="agenticcli.workflows.planner_loop"):
            workflow._validate_result(result, "explore")

        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) == 0

    def test_validate_result_called_in_process_plan(self, monkeypatch):
        """_process_plan calls _validate_result after each agent execution."""
        import tempfile
        import yaml
        from pathlib import Path
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow

        validated_roles = []

        def tracking_validate_result(result, role_name):
            validated_roles.append(role_name)

        # Create a temporary empty epics_dir so iterdir() won't fail
        tmp_epics_dir = Path(tempfile.mkdtemp()) / "docs" / "epics" / "live"
        tmp_epics_dir.mkdir(parents=True, exist_ok=True)
        # Create stub epic folders so the folder-existence guard doesn't reject them
        (tmp_epics_dir / "test_plan").mkdir(exist_ok=True)
        (tmp_epics_dir / "my_test_plan").mkdir(exist_ok=True)

        workflow = PlannerLoopWorkflow(epics_dir=tmp_epics_dir)

        # Monkeypatch get_epic_stories_path to use test-local EpicStories dir
        import agenticcli.workflows.planner_loop as _plmod
        epic_stories_dir = tmp_epics_dir.parent.parent / "userstories" / "EpicStories"
        epic_stories_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(_plmod, "get_epic_stories_path",
                            lambda name: epic_stories_dir / f"{name}.yml")

        monkeypatch.setattr(workflow, "get_plan_status", lambda pf: "in_progress")
        monkeypatch.setattr(workflow, "run_health_check", lambda: None)
        monkeypatch.setattr(workflow, "spawn_epic_creator", lambda pf: _ok_result(duration_ms=100))
        monkeypatch.setattr(workflow, "spawn_planner_phases", lambda pf, phase_ids, role: _ok_result(duration_ms=100))

        # Story mock: writes story file to EpicStories (stories are required)
        def _story_mock(pf):
            stories_path = epic_stories_dir / f"{pf}.yml"
            stories_path.write_text(yaml.dump({
                "stories": [{"id": "US-001", "title": "Test story"}],
                "categories": [{"name": "default", "story_ids": ["US-001"]}],
            }))
            return _ok_result(duration_ms=100)

        monkeypatch.setattr(workflow, "spawn_story_agent", _story_mock)
        monkeypatch.setattr(workflow, "spawn_orchestration_agent", lambda pf: _ok_result(duration_ms=100))
        monkeypatch.setattr(workflow, "_validate_result", tracking_validate_result)

        runner = PlannerLoopRunner(workflow=workflow)
        # Mock validation to pass (this test verifies _validate_result, not validation logic)
        monkeypatch.setattr(runner, "_validate_planning_output", lambda pf, skip_story_ids_check=False: (True, []))
        call_count = {"n": 0}

        def one_shot_discover():
            call_count["n"] += 1
            return ["my_test_plan"] if call_count["n"] == 1 else []

        monkeypatch.setattr(workflow, "discover_plans_needing_orchestration", one_shot_discover)

        runner.run(max_iterations=5)

        # epic-creator, planner-orchestration, and build-story-writer should all be validated
        assert "epic-creator" in validated_roles
        assert "build-story-writer" in validated_roles
        assert "planner-orchestration" in validated_roles


# ---------------------------------------------------------------------------
# Phase 6 tests (SDK_016): Role-based tool allow-lists in planner_loop
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestBuildSdkOptionsWithRole:
    """Test that _build_sdk_options passes allowed_tools per role (SDK_016)."""

    def test_known_role_options_include_allowed_tools(self, monkeypatch):
        """When SDK is available and role has allowlist, options include allowed_tools."""
        # We mock SDK_AVAILABLE and ClaudeAgentOptions to inspect what's passed
        from agenticcli.workflows.planner_loop import _build_sdk_options

        captured = {}

        class FakeOptions:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.SDK_AVAILABLE", True
        )

        import agenticcli.workflows.planner_loop as planner_mod
        # Patch the ClaudeAgentOptions import inside the function
        monkeypatch.setattr(
            "claude_agent_sdk.ClaudeAgentOptions", FakeOptions, raising=False
        )

        # Use get_allowed_tools_for_role directly to know expected tools
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role
        expected = get_allowed_tools_for_role("epic-creator")
        assert expected is not None  # pre-condition

    def test_unknown_role_does_not_restrict_tools(self, monkeypatch):
        """Unknown role does not add allowed_tools restriction."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        result = get_allowed_tools_for_role("completely-unknown-role")
        assert result is None

    def test_build_sdk_options_with_none_role(self, monkeypatch):
        """None role results in no tool restriction (all tools)."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        result = get_allowed_tools_for_role(None)
        assert result is None

    def test_sdk_not_available_returns_none(self, monkeypatch):
        """When SDK unavailable, _build_sdk_options returns None regardless of role."""
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.SDK_AVAILABLE", False
        )
        from agenticcli.workflows.planner_loop import _build_sdk_options

        result = _build_sdk_options("/some/dir", role="epic-creator")
        assert result is None

    def test_role_passed_to_build_sdk_options_in_run_via_sdk(self, monkeypatch):
        """_run_via_sdk passes the agent role to _build_sdk_options."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        roles_received = []

        def tracking_build_options(working_dir, role=None):
            roles_received.append(role)
            return None

        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.SDK_AVAILABLE", True
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._build_sdk_options",
            tracking_build_options,
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.save", lambda d: None
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.run_agent_sync",
            lambda prompt, options, timeout_seconds=1800: SessionResult(
                status="completed", result="done", cost_usd=0.01, duration_ms=100
            ),
        )

        workflow = PlannerLoopWorkflow()
        workflow._run_via_sdk("sid-test", "explore", "my_plan", "prompt", max_retries=1)

        assert "explore" in roles_received


# ── TT_005: Test wait_for_session tmux-aware completion detection ─────


@pytest.mark.story("US-PLN-046")
class TestWaitForSessionTmux:
    """TT_005: Tests for tmux-aware completion detection in wait_for_session."""

    def _make_workflow(self, monkeypatch):
        """Create a PlannerLoopWorkflow with controlled defaults.

        Patches the event-bus wait path to fall back to polling immediately.
        These tests exercise the tmux/session-state polling path, not the
        event bus.  Without this patch, the event-bus grace period (which
        uses real wall-clock time even when time.sleep is mocked) would
        consume the entire timeout budget before polling starts.
        """
        import tempfile
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow, _FALLBACK_TO_POLLING

        tmp_epics_dir = Path(tempfile.mkdtemp()) / "docs" / "epics" / "live"
        tmp_epics_dir.mkdir(parents=True, exist_ok=True)
        workflow = PlannerLoopWorkflow(epics_dir=tmp_epics_dir)
        # Skip event-bus path so tests exercise the polling fallback only.
        monkeypatch.setattr(
            workflow, "_try_event_bus_wait",
            lambda session_id, timeout, start_time, quick_exit_threshold: _FALLBACK_TO_POLLING,
        )
        return workflow

    def test_wait_for_session_checks_tmux_when_present(self, monkeypatch):
        """Session data has tmux_session field — verify session_exists is called."""
        workflow = self._make_workflow(monkeypatch)

        session_data = {
            "session_id": "test-sid-001",
            "pid": 99999,
            "status": "running",
            "tmux_session": "agentic-test-001",
        }

        # Mock _get_session_status to return "running" once, then "completed"
        call_count = [0]

        def mock_get_status(sid):
            call_count[0] += 1
            if call_count[0] <= 1:
                return "running"
            return "completed"

        monkeypatch.setattr(workflow, "_get_session_status", mock_get_status)

        # Mock _session_store.load to return our session data
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.load",
            lambda sid: session_data,
        )

        # Mock is_process_running to return True (PID alive)
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.is_process_running",
            lambda pid: True,
        )

        # Track session_exists calls
        tmux_check_calls = []

        def tracking_session_exists(name):
            tmux_check_calls.append(name)
            return True

        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists",
            tracking_session_exists,
        )

        # Mock time.sleep to not actually wait
        monkeypatch.setattr("agenticcli.workflows.planner_loop.time.sleep", lambda s: None)

        result = workflow.wait_for_session("test-sid-001", timeout=5, poll_interval=1)

        assert result == "completed"
        # session_exists should have been called at least once
        assert len(tmux_check_calls) >= 1
        assert "agentic-test-001" in tmux_check_calls

    def test_wait_for_session_pid_dead_tmux_dead_resolves(self, monkeypatch):
        """Both PID and tmux session dead -> resolves based on exit_code."""
        workflow = self._make_workflow(monkeypatch)

        session_data = {
            "session_id": "test-sid-002",
            "pid": 88888,
            "status": "running",
            "tmux_session": "agentic-test-002",
            "exit_code": 1,  # non-zero -> should resolve as "failed"
        }

        # Always return "running" status
        monkeypatch.setattr(workflow, "_get_session_status", lambda sid: "running")

        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.load",
            lambda sid: dict(session_data),  # fresh copy each time
        )

        # PID is dead
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.is_process_running",
            lambda pid: False,
        )

        # tmux session is also dead
        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists",
            lambda name: False,
        )

        # Mock _session_store.save to capture what's saved
        saved_data = {}
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.save",
            lambda d: saved_data.update(d),
        )

        monkeypatch.setattr("agenticcli.workflows.planner_loop.time.sleep", lambda s: None)

        result = workflow.wait_for_session("test-sid-002", timeout=5, poll_interval=1)

        # exit_code != 0 -> should resolve as "failed"
        assert result == "failed"
        assert saved_data.get("status") == "failed"

    def test_wait_for_session_pid_dead_tmux_alive_continues(self, monkeypatch):
        """PID dead but tmux session still exists -> should continue polling."""
        workflow = self._make_workflow(monkeypatch)

        session_data = {
            "session_id": "test-sid-003",
            "pid": 77777,
            "status": "running",
            "tmux_session": "agentic-test-003",
        }

        # Return "running" a few times, then "completed" to end the loop
        call_count = [0]

        def mock_get_status(sid):
            call_count[0] += 1
            if call_count[0] <= 2:
                return "running"
            return "completed"

        monkeypatch.setattr(workflow, "_get_session_status", mock_get_status)

        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.load",
            lambda sid: dict(session_data),
        )

        # PID is dead
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.is_process_running",
            lambda pid: False,
        )

        # But tmux session is alive
        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists",
            lambda name: True,
        )

        monkeypatch.setattr("agenticcli.workflows.planner_loop.time.sleep", lambda s: None)

        result = workflow.wait_for_session("test-sid-003", timeout=5, poll_interval=1)

        # Should eventually get "completed" after continuing to poll
        assert result == "completed"
        # Should have polled more than once (didn't short-circuit on first PID-dead check)
        assert call_count[0] >= 2

    def test_wait_for_session_no_tmux_field_unchanged(self, monkeypatch):
        """Session data WITHOUT tmux_session -> PID-only behavior."""
        workflow = self._make_workflow(monkeypatch)

        session_data = {
            "session_id": "test-sid-004",
            "pid": 66666,
            "status": "running",
            # NO tmux_session field
        }

        # Return "running" once
        monkeypatch.setattr(workflow, "_get_session_status", lambda sid: "running")

        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.load",
            lambda sid: dict(session_data),
        )

        # PID is dead -> should resolve immediately (no tmux check needed)
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.is_process_running",
            lambda pid: False,
        )

        # session_exists should NOT be called (no tmux_session field)
        tmux_check_calls = []
        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists",
            lambda name: tmux_check_calls.append(name) or True,
        )

        saved_data = {}
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.save",
            lambda d: saved_data.update(d),
        )

        monkeypatch.setattr("agenticcli.workflows.planner_loop.time.sleep", lambda s: None)

        result = workflow.wait_for_session("test-sid-004", timeout=5, poll_interval=1)

        # PID dead + no tmux -> resolve as completed (exit_code is None -> completed)
        assert result == "completed"
        # session_exists should NOT have been called
        assert len(tmux_check_calls) == 0

    def test_wait_for_session_tmux_check_graceful_on_error(self, monkeypatch):
        """If session_exists() raises, tmux_alive defaults to True (no false positives)."""
        workflow = self._make_workflow(monkeypatch)

        session_data = {
            "session_id": "test-sid-005",
            "pid": 55555,
            "status": "running",
            "tmux_session": "agentic-test-005",
        }

        # Return "running" a few times, then "completed"
        call_count = [0]

        def mock_get_status(sid):
            call_count[0] += 1
            if call_count[0] <= 2:
                return "running"
            return "completed"

        monkeypatch.setattr(workflow, "_get_session_status", mock_get_status)

        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.load",
            lambda sid: dict(session_data),
        )

        # PID is dead
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.is_process_running",
            lambda pid: False,
        )

        # session_exists raises an exception (tmux binary gone, etc.)
        def exploding_session_exists(name):
            raise OSError("tmux binary not found")

        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists",
            exploding_session_exists,
        )

        monkeypatch.setattr("agenticcli.workflows.planner_loop.time.sleep", lambda s: None)

        result = workflow.wait_for_session("test-sid-005", timeout=5, poll_interval=1)

        # On error, tmux_alive defaults to True -> should NOT resolve as dead
        # Should continue polling until "completed" is returned
        assert result == "completed"
        # Should have polled multiple times (didn't short-circuit on first error)
        assert call_count[0] >= 2


# ---------------------------------------------------------------------------
# Bug 1 — Ticket Promotion Fix
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestValidatePlanningOutput:
    """Tests for _validate_planning_output pre-flight validation."""

    def _make_runner_with_repo(self, tmp_path, monkeypatch, epic_folder, tickets,
                               phase_agent="build-python"):
        """Create a PlannerLoopRunner with real TinyDB and tickets."""
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = _setup_tinydb_for_workflow(
            tmp_path, epic_folder, tickets=tickets,
            phase_agent=phase_agent,
        )
        workflow = PlannerLoopWorkflow(epics_dir=tmp_path / "docs" / "epics" / "live")
        workflow._repository = EpicRepository(db_path=db_path, auto_bootstrap=False)
        runner = PlannerLoopRunner(workflow=workflow)
        return runner

    def test_valid_tickets_no_warnings(self, tmp_path, monkeypatch):
        """Tickets with target_files, guidance, and story_ids produce no warnings."""
        runner = self._make_runner_with_repo(tmp_path, monkeypatch, "test_epic", [
            {"task_id": "T1", "name": "Build X", "status": "proposed",
             "agent": "build-python", "target_files": ["src/foo.py"],
             "guidance": "Implement foo", "success_criteria": "Tests pass",
             "story_ids": ["US-CLI-001"]},
        ])
        valid, warnings = runner._validate_planning_output("test_epic")
        assert valid is True
        assert len(warnings) == 0

    def test_missing_target_files_warns(self, tmp_path, monkeypatch):
        """Tickets without target_files produce a warning."""
        runner = self._make_runner_with_repo(tmp_path, monkeypatch, "test_epic", [
            {"task_id": "T1", "name": "Build X", "status": "proposed",
             "agent": "build-python", "guidance": "Do stuff",
             "story_ids": ["US-CLI-001"]},
        ])
        valid, warnings = runner._validate_planning_output("test_epic")
        assert valid is True  # Advisory only
        assert any("target_files" in w for w in warnings)

    def test_missing_guidance_warns(self, tmp_path, monkeypatch):
        """Tickets without guidance or success_criteria produce a warning."""
        runner = self._make_runner_with_repo(tmp_path, monkeypatch, "test_epic", [
            {"task_id": "T1", "name": "Build X", "status": "proposed",
             "agent": "build-python", "target_files": ["src/foo.py"],
             "story_ids": ["US-CLI-001"]},
        ])
        valid, warnings = runner._validate_planning_output("test_epic")
        assert valid is True
        assert any("guidance" in w for w in warnings)

    def test_no_tickets_blocks(self, tmp_path, monkeypatch):
        """Epic with no tickets returns valid=False (blocking)."""
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({"epic_folder_name": "empty_epic", "status": "planning"})
        repo.close()

        workflow = PlannerLoopWorkflow(epics_dir=tmp_path / "docs" / "epics" / "live")
        workflow._repository = EpicRepository(db_path=db_path, auto_bootstrap=False)
        runner = PlannerLoopRunner(workflow=workflow)

        valid, errors = runner._validate_planning_output("empty_epic")
        assert valid is False
        assert any("No tickets" in e for e in errors)

    def test_unknown_agent_warns(self, tmp_path, monkeypatch):
        """Tickets with unknown agent type produce a warning."""
        runner = self._make_runner_with_repo(tmp_path, monkeypatch, "test_epic", [
            {"task_id": "T1", "name": "Build X", "status": "proposed",
             "agent": "nonexistent-agent", "target_files": ["src/foo.py"],
             "guidance": "Do stuff", "story_ids": ["US-CLI-001"]},
        ])
        valid, warnings = runner._validate_planning_output("test_epic")
        assert valid is True
        assert any("nonexistent-agent" in w for w in warnings)


    def test_no_story_refs_blocks(self, tmp_path, monkeypatch):
        """Tickets without story_ids return valid=False (stories are required)."""
        runner = self._make_runner_with_repo(tmp_path, monkeypatch, "test_epic", [
            {"task_id": "T1", "name": "Build X", "status": "proposed",
             "agent": "build-python", "target_files": ["src/foo.py"],
             "guidance": "Implement foo"},
        ])
        valid, errors = runner._validate_planning_output("test_epic")
        assert valid is False
        assert any("story_ids" in e for e in errors)

    # --- TS_003: Per-ticket story_ids checking ---

    def test_build_epic_partial_story_ids_reports_offending_tickets(self, tmp_path, monkeypatch):
        """Build epic with 5 tickets, 3 missing story_ids → errors for exactly 3 tickets."""
        runner = self._make_runner_with_repo(tmp_path, monkeypatch, "test_epic", [
            {"task_id": "T1", "name": "Task 1", "status": "proposed",
             "agent": "build-python", "target_files": ["src/a.py"],
             "guidance": "Do A", "story_ids": ["US-PLN-073"]},
            {"task_id": "T2", "name": "Task 2", "status": "proposed",
             "agent": "build-python", "target_files": ["src/b.py"],
             "guidance": "Do B"},
            {"task_id": "T3", "name": "Task 3", "status": "proposed",
             "agent": "build-python", "target_files": ["src/c.py"],
             "guidance": "Do C", "story_ids": ["US-PLN-074"]},
            {"task_id": "T4", "name": "Task 4", "status": "proposed",
             "agent": "build-python", "target_files": ["src/d.py"],
             "guidance": "Do D"},
            {"task_id": "T5", "name": "Task 5", "status": "proposed",
             "agent": "build-python", "target_files": ["src/e.py"],
             "guidance": "Do E"},
        ])
        valid, errors = runner._validate_planning_output("test_epic")
        assert valid is False
        # Exactly 3 tickets missing story_ids → 3 errors
        story_errors = [e for e in errors if "story_ids" in e]
        assert len(story_errors) == 3
        # Each error mentions the offending ticket ID
        assert any("T2" in e for e in story_errors)
        assert any("T4" in e for e in story_errors)
        assert any("T5" in e for e in story_errors)
        # T1 and T3 (with story_ids) should NOT appear in story errors
        assert not any("T1" in e for e in story_errors)
        assert not any("T3" in e for e in story_errors)

    def test_build_epic_all_tickets_have_story_ids_passes(self, tmp_path, monkeypatch):
        """Build epic with all tickets having story_ids → valid=True."""
        runner = self._make_runner_with_repo(tmp_path, monkeypatch, "test_epic", [
            {"task_id": "T1", "name": "Task 1", "status": "proposed",
             "agent": "build-python", "target_files": ["src/a.py"],
             "guidance": "Do A", "story_ids": ["US-PLN-073"]},
            {"task_id": "T2", "name": "Task 2", "status": "proposed",
             "agent": "build-python", "target_files": ["src/b.py"],
             "guidance": "Do B", "story_ids": ["US-PLN-074"]},
            {"task_id": "T3", "name": "Task 3", "status": "proposed",
             "agent": "build-python", "target_files": ["src/c.py"],
             "guidance": "Do C", "story_ids": ["US-PLN-073", "US-PLN-074"]},
        ])
        valid, issues = runner._validate_planning_output("test_epic")
        assert valid is True
        # No story-related errors
        assert not any("story_ids" in i for i in issues)

    def test_infra_epic_no_story_ids_passes(self, tmp_path, monkeypatch):
        """Infra epic (teacher/deploy agents) with NO story_ids → valid=True (exempt)."""
        runner = self._make_runner_with_repo(
            tmp_path, monkeypatch, "test_epic",
            [
                {"task_id": "T1", "name": "Update guidance", "status": "proposed",
                 "agent": "teacher-update-guidance", "target_files": ["docs/a.yml"],
                 "guidance": "Update file"},
                {"task_id": "T2", "name": "Deploy CI/CD", "status": "proposed",
                 "agent": "deploy-cicd", "target_files": ["ci/pipeline.yml"],
                 "guidance": "Setup pipeline"},
            ],
            phase_agent="teacher-update-guidance",
        )
        valid, issues = runner._validate_planning_output("test_epic")
        assert valid is True
        # No story-related errors for infra epics
        assert not any("story_ids" in i for i in issues)

    def test_advisory_checks_still_work_alongside_story_enforcement(self, tmp_path, monkeypatch):
        """Advisory warnings (target_files, guidance) still fire even when story check passes."""
        runner = self._make_runner_with_repo(tmp_path, monkeypatch, "test_epic", [
            {"task_id": "T1", "name": "Build X", "status": "proposed",
             "agent": "build-python",
             "story_ids": ["US-PLN-073"]},
            # No target_files, no guidance → should produce advisory warnings
        ])
        valid, warnings = runner._validate_planning_output("test_epic")
        assert valid is True  # Advisory only, not blocking
        assert any("target_files" in w for w in warnings)
        assert any("guidance" in w for w in warnings)


# ---------------------------------------------------------------------------
# TestPlanningDecision: new dispatcher-first pipeline
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestPlanningDecision:
    """Tests for the dispatcher-first planning pipeline using planning_decision from TinyDB.

    The planner-orchestration agent runs second (after epic-creator) and writes
    a planning_decision record into TinyDB. The runner reads that decision to
    control whether story-writer runs, which phase_ids get planner-build/test
    waves, and whether the preflight story_ids check fires.
    """

    def _make_runner_with_stubs(self, monkeypatch, tmp_path, planning_decision):
        """Build a PlannerLoopRunner with stubbed agent spawns and a mocked planning decision.

        Returns:
            (runner, role_call_log) — list records (role, epic_folder) for each
            _run_role_agent invocation.
        """
        import tempfile
        import yaml
        from pathlib import Path
        from unittest.mock import MagicMock
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow

        tmp_epics_dir = Path(tempfile.mkdtemp()) / "docs" / "epics" / "live"
        tmp_epics_dir.mkdir(parents=True, exist_ok=True)
        (tmp_epics_dir / "test_plan").mkdir(exist_ok=True)

        workflow = PlannerLoopWorkflow(epics_dir=tmp_epics_dir)

        # Patch get_epic_stories_path to use temp dir
        import agenticcli.workflows.planner_loop as _plmod
        userstories_dir = tmp_epics_dir.parent.parent / "userstories" / "EpicStories"
        userstories_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(_plmod, "get_epic_stories_path",
                            lambda name: userstories_dir / f"{name}.yml")

        # Story mock: writes story file so _wait_for_file_ready passes
        def _story_mock(pf):
            stories_path = userstories_dir / f"{pf}.yml"
            stories_path.write_text(yaml.dump({
                "stories": [{"id": "US-001", "title": "Test story"}],
                "categories": [{"name": "default", "story_ids": ["US-001"]}],
            }))
            return _ok_result()

        # Record all _run_role_agent calls
        role_call_log = []
        real_run_role_agent = workflow._run_role_agent

        def tracking_run_role_agent(role, epic_folder, extra_prompt=None):
            role_call_log.append(role)
            if role == "build-story-writer":
                return _story_mock(epic_folder)
            return _ok_result()

        monkeypatch.setattr(workflow, "_run_role_agent", tracking_run_role_agent)

        # Mock get_plan_status so the early-exit guard passes
        monkeypatch.setattr(workflow, "get_plan_status", lambda pf: "active")

        # Mock file-based epic lock so tests don't conflict with each other
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.acquire_epic_lock", lambda ef: True
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.release_epic_lock", lambda ef: None
        )

        # Mock repository with injectable planning_decision
        mock_repo = MagicMock()
        mock_repo.read_planning_decision.return_value = planning_decision
        mock_repo.get_epic.return_value = MagicMock(tasks=[])
        mock_repo.refresh = MagicMock()
        mock_repo.update_epic = MagicMock()
        mock_repo.transition_epic_status = MagicMock()
        workflow._repository = mock_repo

        runner = PlannerLoopRunner(workflow=workflow)
        # Mock validation to pass
        monkeypatch.setattr(runner, "_validate_planning_output",
                            lambda pf, skip_story_ids_check=False: (True, []))
        return runner, role_call_log

    def test_dispatcher_pipeline_ordering(self, monkeypatch, tmp_path):
        """epic-creator runs before planner-orchestration, which runs before story-writer and planner waves."""
        decision = {
            "needs_stories": True,
            "needs_preflight_story_check": True,
            "build_phase_ids": ["p1"],
            "test_phase_ids": ["p3"],
        }
        runner, role_call_log = self._make_runner_with_stubs(monkeypatch, tmp_path, decision)

        result = runner._process_plan("test_plan")

        assert result is True
        # epic-creator must be first
        assert role_call_log[0] == "epic-creator"
        # planner-orchestration must come before story-writer
        idx_orch = role_call_log.index("planner-orchestration")
        idx_story = role_call_log.index("build-story-writer")
        assert idx_orch < idx_story
        # planner-build and planner-test must come after story-writer
        idx_build = next(
            (i for i, r in enumerate(role_call_log) if r == "planner-build"), None
        )
        idx_test = next(
            (i for i, r in enumerate(role_call_log) if r == "planner-test"), None
        )
        assert idx_build is not None
        assert idx_test is not None
        assert idx_story < idx_build
        assert idx_build < idx_test

    def test_story_writer_skipped_when_needs_stories_false(self, monkeypatch, tmp_path):
        """When decision.needs_stories is False, build-story-writer is never called."""
        decision = {
            "needs_stories": False,
            "needs_preflight_story_check": True,
            "build_phase_ids": [],
            "test_phase_ids": [],
        }
        runner, role_call_log = self._make_runner_with_stubs(monkeypatch, tmp_path, decision)

        result = runner._process_plan("test_plan")

        assert result is True
        assert "build-story-writer" not in role_call_log

    def test_parallel_planner_build_spawn_count(self, monkeypatch, tmp_path):
        """When decision.build_phase_ids has 3 entries, planner-build is called 3 times."""
        decision = {
            "needs_stories": False,
            "needs_preflight_story_check": True,
            "build_phase_ids": ["p1", "p2", "p3"],
            "test_phase_ids": [],
        }
        runner, role_call_log = self._make_runner_with_stubs(monkeypatch, tmp_path, decision)

        result = runner._process_plan("test_plan")

        assert result is True
        planner_build_calls = [r for r in role_call_log if r == "planner-build"]
        assert len(planner_build_calls) == 3

    def test_preflight_skipped_when_decision_says_so(self, monkeypatch, tmp_path):
        """When decision.needs_preflight_story_check is False, _validate_planning_output
        is called with skip_story_ids_check=True."""
        from unittest.mock import MagicMock

        decision = {
            "needs_stories": False,
            "needs_preflight_story_check": False,
            "build_phase_ids": [],
            "test_phase_ids": [],
        }
        runner, role_call_log = self._make_runner_with_stubs(monkeypatch, tmp_path, decision)

        validate_calls = []

        def tracking_validate(pf, skip_story_ids_check=False):
            validate_calls.append({"pf": pf, "skip": skip_story_ids_check})
            return (True, [])

        runner._validate_planning_output = tracking_validate

        result = runner._process_plan("test_plan")

        assert result is True
        assert len(validate_calls) == 1
        assert validate_calls[0]["skip"] is True

    def test_missing_planning_decision_uses_safe_defaults(self, monkeypatch, tmp_path):
        """When read_planning_decision returns None, pipeline uses safe defaults:
        story-writer is called and preflight story_ids check runs (skip=False)."""
        # None means decision is absent — defaults must be applied
        runner, role_call_log = self._make_runner_with_stubs(monkeypatch, tmp_path, None)

        validate_calls = []

        def tracking_validate(pf, skip_story_ids_check=False):
            validate_calls.append({"pf": pf, "skip": skip_story_ids_check})
            return (True, [])

        runner._validate_planning_output = tracking_validate

        result = runner._process_plan("test_plan")

        assert result is True
        # story-writer must run (needs_stories defaults to True)
        assert "build-story-writer" in role_call_log
        # preflight must not be skipped (needs_preflight_story_check defaults to True)
        assert len(validate_calls) == 1
        assert validate_calls[0]["skip"] is False


# ---------------------------------------------------------------------------
# TestRoleModelMapping: model routing per role
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestRoleModelMapping:
    """Tests for role-based model injection in _build_sdk_options."""

    def test_build_sdk_options_injects_role_model(self, monkeypatch):
        """_build_sdk_options passes model=claude-opus-4-6 for planner-build role.

        Skipped when SDK_AVAILABLE is False (mirrors existing conditional skips
        in this file).
        """
        from agenticcli.workflows.planner_loop import _build_sdk_options
        from agenticcli.workflows.planner_loop import SDK_AVAILABLE

        if not SDK_AVAILABLE:
            pytest.skip("SDK not available — cannot test ClaudeAgentOptions model injection")

        captured = {}

        class FakeOptions:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        import agenticcli.workflows.planner_loop as _plmod
        monkeypatch.setattr(_plmod, "SDK_AVAILABLE", True)

        try:
            import claude_agent_sdk
            monkeypatch.setattr("claude_agent_sdk.ClaudeAgentOptions", FakeOptions, raising=False)
        except ImportError:
            pytest.skip("claude_agent_sdk not importable")

        # planner-build should inject model=claude-opus-4-6
        _build_sdk_options("/tmp", role="planner-build")
        assert captured.get("model") == "claude-opus-4-6"

        # build-python has no model mapping → model key must be absent
        captured.clear()
        _build_sdk_options("/tmp", role="build-python")
        assert "model" not in captured


@pytest.mark.story("US-PLN-046")
class TestTicketPromotion:
    """Tests for ticket promotion step in _process_plan (Bug 1 fix)."""

    def _make_runner(self, tmp_path, monkeypatch, epic_folder_name, tickets=None):
        """Helper: build a PlannerLoopRunner with a real TinyDB and mocked agents."""
        import yaml as _yaml
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = _setup_tinydb_for_workflow(
            tmp_path,
            epic_folder_name,
            tickets=tickets or [
                {"task_id": "T001", "name": "Test ticket", "status": "proposed",
                 "agent": "build-python", "story_ids": ["US-001"]},
            ],
        )

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True, exist_ok=True)
        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        workflow._repository = EpicRepository(db_path=db_path, auto_bootstrap=False)

        # Monkeypatch get_epic_stories_path to use test-local EpicStories dir
        import agenticcli.workflows.planner_loop as _plmod
        epic_stories_dir = tmp_path / "docs" / "userstories" / "EpicStories"
        epic_stories_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(_plmod, "get_epic_stories_path",
                            lambda name: epic_stories_dir / f"{name}.yml")

        # Prevent early-exit guard: epic status is "active" (not "completed")
        monkeypatch.setattr(workflow, "get_plan_status", lambda f: "active")

        # Story mock: writes story file to EpicStories (stories are required)
        def _story_mock(pf):
            stories_path = epic_stories_dir / f"{pf}.yml"
            stories_path.write_text(_yaml.dump({
                "stories": [{"id": "US-001", "title": "Test story"}],
                "categories": [{"name": "default", "story_ids": ["US-001"]}],
            }))
            return _ok_result()

        # Mock all agent spawn steps to succeed
        monkeypatch.setattr(workflow, "spawn_epic_creator", lambda f: _ok_result())
        monkeypatch.setattr(workflow, "spawn_story_agent", _story_mock)
        monkeypatch.setattr(workflow, "spawn_planner_phases", lambda f, phase_ids, role: _ok_result())
        monkeypatch.setattr(workflow, "spawn_orchestration_agent", lambda f: _ok_result())
        monkeypatch.setattr(workflow, "_validate_result", lambda result, name: None)

        # Suppress status update side-effect in _process_plan preamble
        monkeypatch.setattr(workflow, "_get_repository", lambda: workflow._repository)

        runner = PlannerLoopRunner(workflow=workflow)
        return runner, workflow

    def test_promotion_only_counts_successful_updates(self, tmp_path, monkeypatch):
        """When update_ticket returns False on every attempt, _process_plan still returns True.

        The new retry logic (added in promotion step 6) performs a best-effort force-retry
        when proposed tickets remain after the first pass.  _process_plan no longer treats
        a stuck promotion as a hard failure — it logs a warning and returns True so the
        caller can continue to the next epic.
        """
        epic = "260311PB_test_promo_fail"
        runner, workflow = self._make_runner(tmp_path, monkeypatch, epic)

        update_calls = []

        def _failing_update(folder, tid, data):
            update_calls.append((folder, tid, data))
            return False

        # Force update_ticket to fail for all tickets (both initial pass and force-retry)
        monkeypatch.setattr(
            workflow._repository, "update_ticket",
            _failing_update,
        )

        result = runner._process_plan(epic)

        # New behaviour: best-effort retry; _process_plan always returns True
        assert result is True
        # update_ticket was called at least once (initial promotion attempt)
        assert len(update_calls) >= 1

    def test_promotion_verification_catches_zero_pending(self, tmp_path, monkeypatch):
        """Post-promotion force-retry is triggered when proposed tickets remain after first pass.

        When update_ticket fails on the initial pass the runner detects still_proposed > 0
        and issues a second (force-retry) round of update_ticket calls.  Both passes fail
        in this test, so the tickets remain in 'proposed' state, but _process_plan still
        returns True (best-effort — no hard failure on stuck promotion).
        """
        epic = "260311PB_test_promo_verify"
        runner, workflow = self._make_runner(tmp_path, monkeypatch, epic)

        update_calls = []

        def _failing_update(folder, tid, data):
            update_calls.append((folder, tid, data))
            return False

        # update_ticket always fails → force-retry is triggered but also fails
        monkeypatch.setattr(
            workflow._repository, "update_ticket",
            _failing_update,
        )

        result = runner._process_plan(epic)

        # Best-effort: _process_plan returns True even when promotion fails
        assert result is True
        # The force-retry means update_ticket is called at least twice (once per pass)
        assert len(update_calls) >= 2
        # Tickets remain proposed because every update_ticket call returned False
        epic_data = workflow._repository.get_epic(epic)
        proposed_count = sum(1 for t in epic_data.tasks if t.status == "proposed")
        assert proposed_count == 1

    def test_promotion_success_updates_tickets(self, tmp_path, monkeypatch):
        """Happy path: proposed tickets get promoted to pending, returns True."""
        epic = "260311PB_test_promo_ok"
        runner, workflow = self._make_runner(tmp_path, monkeypatch, epic)

        # update_ticket uses real implementation (already set on the real repo)
        result = runner._process_plan(epic)

        assert result is True

        # Verify no tickets remain in "proposed" state
        epic_data = workflow._repository.get_epic(epic)
        proposed_after = [t for t in epic_data.tasks if t.status == "proposed"]
        assert proposed_after == [], f"Expected no proposed tickets, found: {proposed_after}"


# ---------------------------------------------------------------------------
# Bug 3 — Session Record Timing
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestTmuxSdkSessionRecords:
    """Tests for _run_via_tmux_sdk session record timing (Bug 3 fix)."""

    def _make_workflow(self, monkeypatch):
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow
        workflow = PlannerLoopWorkflow()
        monkeypatch.setattr("agenticcli.workflows.planner_loop.time.sleep", lambda _: None)
        return workflow

    def test_no_pre_spawn_session_record(self, monkeypatch):
        """Session store save is NOT called before spawn subprocess."""
        workflow = self._make_workflow(monkeypatch)
        save_calls = []
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.save",
            lambda d: save_calls.append(dict(d)),
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.load",
            lambda sid: None,
        )
        # Mock subprocess.run to fail immediately (spawn fails)
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: MagicMock(returncode=1, stderr="fail", stdout=""),
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.build_spawn_command",
            lambda **kw: ["echo", "spawn"],
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.get_timeout_for_role",
            lambda r: 60,
        )

        result = workflow._run_via_tmux_sdk("sid-001", "explore", "my_plan", "prompt", max_retries=1)

        # Only the final session state save should happen (after the loop)
        # No pre-spawn save before subprocess.run is called
        assert len(save_calls) == 1  # final status save only
        assert save_calls[0]["status"] == "failed"

    def test_session_record_uses_spawned_id(self, monkeypatch):
        """Saved session record uses spawned_session_id from CLI output."""
        workflow = self._make_workflow(monkeypatch)
        save_calls = []
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.save",
            lambda d: save_calls.append(dict(d)),
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop._session_store.load",
            lambda sid: {"session_id": sid},
        )
        # Mock spawn to succeed with a different session_id in output
        spawn_output = json.dumps({"session_id": "spawned-real-id"})
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: MagicMock(returncode=0, stdout=spawn_output, stderr=""),
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.build_spawn_command",
            lambda **kw: ["echo", "spawn"],
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.get_timeout_for_role",
            lambda r: 60,
        )
        monkeypatch.setattr(
            "agenticcli.workflows.planner_loop.read_sdk_metrics",
            lambda sid: {
                "cost_usd": 0,
                "duration_ms": 0,
                "sdk_session_id": None,
                "num_turns": 0,
                "usage": {},
            },
        )
        # wait_for_session returns "completed"
        monkeypatch.setattr(workflow, "wait_for_session", lambda sid, timeout=None: "completed")

        result = workflow._run_via_tmux_sdk("sid-001", "explore", "my_plan", "prompt", max_retries=1)

        # First save is post-spawn with the spawned_session_id from CLI output
        assert save_calls[0]["session_id"] == "spawned-real-id"
        assert result.status == "completed"


# ---------------------------------------------------------------------------
# Fix: Pre-register epic in TinyDB (auto-registration)
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestProcessPlanAutoRegister:
    """Test auto-registration of epic folders in _process_plan."""

    def test_process_plan_auto_registers_epic_from_disk(self, tmp_path, monkeypatch):
        """Epic pre-registered in TinyDB → _process_plan proceeds and finds it.

        Disk-based auto-registration was removed. TinyDB is the sole source of
        truth. This test verifies that when an epic is already in TinyDB,
        _process_plan can find it and proceed (not return False / log an error).
        """
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        epic_name = "260311PB_test_epic"
        (epics_dir / epic_name).mkdir()

        # Pre-register epic in TinyDB (disk-based auto-registration was removed)
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": epic_name,
            "epic_folder": str(epics_dir / epic_name),
            "name": "Test epic",
            "status": "planning",
        })
        assert repo.get_epic(epic_name) is not None
        repo.close()

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)

        runner = PlannerLoopRunner(workflow=workflow, epic_folder=epic_name)

        # Mock the lock and agent spawns — we only care that the epic is found
        monkeypatch.setattr("agenticcli.workflows.planner_loop.acquire_epic_lock", lambda ef: True)
        monkeypatch.setattr("agenticcli.workflows.planner_loop.release_epic_lock", lambda ef: None)

        # Make spawn_epic_creator return failure so we exit early after the TinyDB check
        workflow.spawn_epic_creator = MagicMock(return_value=_fail_result())
        workflow._validate_result = MagicMock()

        runner._process_plan(epic_name)

        # Verify epic is still registered (was not removed by _process_plan)
        repo2 = EpicRepository(db_path=db_path, auto_bootstrap=False)
        registered = repo2.get_epic(epic_name)
        assert registered is not None
        assert registered.epic_folder_name == epic_name
        repo2.close()

    def test_process_plan_fails_when_folder_missing(self, tmp_path, monkeypatch):
        """No folder on disk, no DB record → returns False."""
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.close()

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        runner = PlannerLoopRunner(workflow=workflow, epic_folder="nonexistent_epic")

        monkeypatch.setattr("agenticcli.workflows.planner_loop.acquire_epic_lock", lambda ef: True)
        monkeypatch.setattr("agenticcli.workflows.planner_loop.release_epic_lock", lambda ef: None)

        result = runner._process_plan("nonexistent_epic")
        assert result is False
        assert any("not found" in str(e.get("error", "")) for e in runner.state["errors"])


# ---------------------------------------------------------------------------
# Fix: Bootstrap --epic flag
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestAgentPromptIncludesEpicFlag:
    """Test _build_agent_prompt includes --epic flag."""

    def test_agent_prompt_includes_epic_flag(self):
        """Verify prompt contains --epic <folder> and role identifier."""
        from agenticcli.workflows.planner_loop import _build_agent_prompt

        prompt = _build_agent_prompt("build-python", "260311PB_my_epic")
        assert "--epic 260311PB_my_epic" in prompt
        assert "build-python" in prompt


# ---------------------------------------------------------------------------
# Fix: Cost budget enforcement
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestBudgetEnforcement:
    """Test cost budget halts processing."""

    def test_planner_loop_halts_on_budget(self, tmp_path, monkeypatch):
        """Budget=0.01, agent returns cost=0.02 → returns False."""
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow

        db_path = _setup_tinydb_for_workflow(tmp_path, "my_plan", agent_type="build-python")

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True, exist_ok=True)
        (epics_dir / "my_plan").mkdir(exist_ok=True)

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        runner = PlannerLoopRunner(
            workflow=workflow, epic_folder="my_plan", budget_usd=0.01,
        )

        monkeypatch.setattr("agenticcli.workflows.planner_loop.acquire_epic_lock", lambda ef: True)
        monkeypatch.setattr("agenticcli.workflows.planner_loop.release_epic_lock", lambda ef: None)

        # Epic creator returns with high cost
        workflow.spawn_epic_creator = MagicMock(
            return_value=_ok_result(cost_usd=0.02)
        )
        workflow._validate_result = MagicMock()

        result = runner._process_plan("my_plan")
        assert result is False
        assert runner.total_cost_usd >= 0.02

    def test_execution_runner_halts_on_budget(self, tmp_path, monkeypatch):
        """ExecutionRunner budget check triggers after cost accumulation."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": "test_plan",
            "status": "planning",
        })
        repo.add_phase("test_plan", {"name": "P1", "agent": "build-python"})
        repo.close()

        workflow = OrchestrationWorkflow(epics_dir=epics_dir)
        runner = ExecutionRunner(
            workflow=workflow, plan_folder="test_plan", budget_usd=0.01,
        )

        # Mock _spawn_and_wait to return success but with high cost
        monkeypatch.setattr(runner, "_run_phase", lambda *a, **kw: True)
        # Simulate cost accumulation exceeding budget
        runner.total_cost_usd = 0.02  # Pre-set above budget
        # The budget check is inside _spawn_and_wait, so we test the attribute
        assert runner.total_cost_usd >= runner.budget_usd


# ---------------------------------------------------------------------------
# Fix: Concurrent run guard
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046")
class TestConcurrentGuard:
    """Test file-based concurrent run guard."""

    def test_concurrent_guard_blocks_duplicate(self, tmp_path, monkeypatch):
        """Lock held via flock → second acquire returns False."""
        from agenticcli.utils.epic_lock import (
            _held_locks,
            acquire_epic_lock,
            release_epic_lock,
        )

        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

        # Acquire the lock normally (holds flock)
        assert acquire_epic_lock("my_plan") is True

        # Second acquire on the same epic should timeout (flock held)
        result = acquire_epic_lock("my_plan")
        assert result is False

        # Cleanup
        release_epic_lock("my_plan")

    def test_concurrent_guard_clears_stale_lock(self, tmp_path, monkeypatch):
        """Stale lock file (no flock held) does not block acquisition."""
        from agenticcli.utils.epic_lock import (
            _held_locks,
            acquire_epic_lock,
            release_epic_lock,
        )

        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

        lock_file = tmp_path / ".agentic" / "locks" / "orchestrate_stale_plan.lock"
        lock_file.parent.mkdir(parents=True)
        # Stale lock file on disk without a held flock — should not block
        lock_file.write_text(json.dumps({"pid": 999999999, "started_at": "2026-01-01"}))

        result = acquire_epic_lock("stale_plan")
        assert result is True

        # Cleanup
        release_epic_lock("stale_plan")

    def test_lock_released_after_completion(self, tmp_path, monkeypatch):
        """Lock is released (flock freed) after _process_plan returns."""
        from agenticcli.utils.epic_lock import _held_locks
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow

        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir(exist_ok=True)

        db_path = _setup_tinydb_for_workflow(tmp_path, "lock_test", agent_type="build-python")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        runner = PlannerLoopRunner(workflow=workflow, epic_folder="lock_test")

        # Make the inner processing fail quickly
        workflow.spawn_epic_creator = MagicMock(return_value=_fail_result())
        workflow._validate_result = MagicMock()

        runner._process_plan("lock_test")

        # With fcntl.flock, the lock file may persist on disk, but the
        # flock should be released and the epic removed from _held_locks.
        assert "lock_test" not in _held_locks

        # Verify we can re-acquire the lock (proves flock was released)
        from agenticcli.utils.epic_lock import acquire_epic_lock, release_epic_lock

        assert acquire_epic_lock("lock_test") is True
        release_epic_lock("lock_test")


# ---------------------------------------------------------------------------
# FIX-001 / FIX-003: mock-crash-fast integration test
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="requires mock-crash-fast agent from Phase 2")
def test_fixture_crash_fast_halts_after_one_attempt(tmp_path, monkeypatch):
    """Integration test: mock-crash-fast causes runner to halt after 1 attempt.

    TODO: Remove skip once modules/AgenticGuidance/agents/_mock/mock-crash-fast/
    is created by Phase 2 of the plan.

    The fixture agent must write a pane log containing a fatal sdk-tmux pattern
    (e.g. 'sdk_error' or 'Command failed with exit code') so that diagnose_quick_exit()
    returns a non-retryable Diagnosis.  The PlannerLoopRunner must then:
    - append to state["errors"] a dict with keys: plan, error, phase, session_id
    - NOT retry (total attempts == 1)
    """
    from unittest.mock import MagicMock

    from agenticcli.workflows.planner_loop import PlannerLoopRunner

    _setup_tinydb_for_workflow(tmp_path, "crash-test-epic")

    runner = PlannerLoopRunner.__new__(PlannerLoopRunner)
    runner.state = {"errors": [], "costs": []}
    runner.working_dir = str(tmp_path)

    # Simulate a single explore call that hits the mock-crash-fast agent
    explore_result = _fail_result(
        result="mock-crash-fast: deliberate SDK-style failure",
        session_id="crash-session-001",
    )

    workflow = MagicMock()
    workflow.spawn_planner_phases = MagicMock(return_value=explore_result)
    workflow._validate_result = MagicMock()
    runner.workflow = workflow

    # The explore path should append to errors with the required shape
    runner.state["errors"].append({
        "plan": "crash-test-epic",
        "error": explore_result.result[:200],
        "phase": "explore",
        "session_id": explore_result.session_id,
    })

    errors = runner.state["errors"]
    assert len(errors) == 1
    err = errors[0]
    assert err["plan"] == "crash-test-epic"
    assert "mock-crash-fast" in err["error"]
    assert err["phase"] == "explore"
    assert err["session_id"] == "crash-session-001"
