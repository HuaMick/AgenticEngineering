"""Tests for the planner loop workflow."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agenticcli.utils.sdk_runner import SessionResult


def _ok_result(**kwargs) -> SessionResult:
    """Create a successful SessionResult for testing."""
    return SessionResult(status="completed", result="ok", **kwargs)


def _fail_result(**kwargs) -> SessionResult:
    """Create a failed SessionResult for testing."""
    return SessionResult(status="failed", result="failed", is_error=True, **kwargs)


_UNSET = object()  # Sentinel for "not provided" vs explicit None


def _setup_tinydb_for_workflow(tmp_path, epic_folder_name, *, agent_type=None,
                                context=None, status=_UNSET, tickets=None):
    """Set up TinyDB for PlannerLoopWorkflow tests.

    Creates a .git marker so the workflow can find the repo root,
    then populates TinyDB with the given epic data.

    Args:
        tmp_path: pytest tmp_path fixture value.
        epic_folder_name: Name of the epic folder (e.g. "my_plan").
        agent_type: Agent type string for the mock ticket (e.g. "build-python").
        context: Epic context string (used by detect_sdk_objective).
        status: Epic status string (used by get_plan_status). Pass None to
                omit the status field entirely; omit the arg to default "active".
        tickets: List of ticket dicts [{id, name, status, agent_type, ...}].
                 If None and agent_type is given, one ticket is created.

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
    repo.add_phase(epic_folder_name, {"name": phase_name})

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


class TestDiscoverPlansNeedingOrchestration:
    """Test discover_plans_needing_orchestration method.

    The primary path checks TinyDB for live epics with no phases.
    The legacy fallback checks for missing orchestration_*.mmd files on disk.
    """

    def test_finds_plans_without_phases_in_tinydb(self, tmp_path):
        """Live epics with no phases in TinyDB are returned."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        # Epic with routed phases - should NOT be returned (uses "active" which maps to "live")
        repo.create_epic({"epic_folder_name": "260210AA_with_phases", "status": "active"})
        repo.add_phase("260210AA_with_phases", {"name": "Phase 1", "agent": "build-python"})
        # Epic without phases - should be returned (uses "active" which maps to "live")
        repo.create_epic({"epic_folder_name": "260210BB_no_phases", "status": "active"})
        repo.close()

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        result = workflow.discover_plans_needing_orchestration()

        assert result == ["260210BB_no_phases"]

    def test_returns_empty_when_all_have_phases(self, tmp_path):
        """No plans returned when all live epics have phases in TinyDB."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        # "active" maps to "live" via STATUS_DIR_MAP
        repo.create_epic({"epic_folder_name": "260210AA_done", "status": "active"})
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


class TestDeterminePlanType:
    """Test determine_plan_type method."""

    def test_build_type(self, tmp_path):
        """Returns 'build' when TinyDB has a ticket with build agent type."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "my_plan"
        plan.mkdir()
        # Populate TinyDB with a build-type agent ticket
        _setup_tinydb_for_workflow(tmp_path, "my_plan", agent_type="build-python")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("my_plan") == "build"

    def test_test_type(self, tmp_path):
        """Returns 'test' when TinyDB has a ticket with test agent type."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "my_plan"
        plan.mkdir()
        # Populate TinyDB with a test-type agent ticket
        _setup_tinydb_for_workflow(tmp_path, "my_plan", agent_type="test-runner")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("my_plan") == "test"

    def test_no_tickets_defaults_to_build(self, tmp_path):
        """Defaults to 'build' when no tickets in TinyDB (first-time planning)."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "my_plan"
        plan.mkdir()
        # Only create .git so workflow can initialize, but no tickets in TinyDB
        (tmp_path / ".git").mkdir(exist_ok=True)
        (tmp_path / ".agentic").mkdir(exist_ok=True)

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("my_plan") == "build"

    def test_nonexistent_folder_defaults_to_build(self, tmp_path):
        """Defaults to 'build' for nonexistent folder (no tickets = first-time planning)."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        # Create .git so workflow initializes, but no epic in TinyDB
        (tmp_path / ".git").mkdir(exist_ok=True)
        (tmp_path / ".agentic").mkdir(exist_ok=True)

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        # _process_plan guards against nonexistent epics before calling this,
        # so in isolation, no tickets defaults to "build"
        assert workflow.determine_plan_type("nonexistent") == "build"


class TestDetectSdkObjective:
    """Test detect_sdk_objective method (reads epic context from TinyDB)."""

    def test_detects_sdk_keyword_in_context(self, tmp_path):
        """Returns True when TinyDB epic context contains SDK keywords."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        (epics_dir / "sdk_plan").mkdir()
        _setup_tinydb_for_workflow(
            tmp_path, "sdk_plan",
            context="Migrate sessions to use claude-agent-sdk",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("sdk_plan") is True

    def test_no_sdk_keywords(self, tmp_path):
        """Returns False when TinyDB context has no SDK keywords."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        (epics_dir / "normal_plan").mkdir()
        _setup_tinydb_for_workflow(
            tmp_path, "normal_plan",
            context="Add a new CLI command for listing plans",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("normal_plan") is False

    def test_no_context_field(self, tmp_path):
        """Returns False when TinyDB epic has no context field."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        (epics_dir / "no_ctx").mkdir()
        _setup_tinydb_for_workflow(tmp_path, "no_ctx", context=None)

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("no_ctx") is False

    def test_no_plan_build_yml(self, tmp_path):
        """Returns False when epic not in TinyDB."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        (epics_dir / "no_build").mkdir()
        # Create .git but don't add epic to TinyDB
        (tmp_path / ".git").mkdir(exist_ok=True)
        (tmp_path / ".agentic").mkdir(exist_ok=True)

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("no_build") is False

    def test_case_insensitive_matching(self, tmp_path):
        """SDK keyword matching is case-insensitive."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        (epics_dir / "case_plan").mkdir()
        _setup_tinydb_for_workflow(
            tmp_path, "case_plan",
            context="Replace subprocess calls with SDK Migration patterns",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("case_plan") is True

    def test_multiple_sdk_keywords(self, tmp_path):
        """Returns True when multiple SDK keywords present."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        (epics_dir / "multi_sdk").mkdir()
        _setup_tinydb_for_workflow(
            tmp_path, "multi_sdk",
            context="Use claude-agent-sdk query() and async iterator for session spawn",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("multi_sdk") is True

    def test_malformed_yaml(self, tmp_path):
        """Returns False when epic is not in TinyDB (doesn't crash)."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "bad_yaml"
        plan.mkdir()
        # No TinyDB entry - detect_sdk_objective reads from TinyDB, returns False

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("bad_yaml") is False


class TestDeterminePlanTypeWithSdkRouting:
    """Test that determine_plan_type routes to SDK when context matches."""

    def test_build_with_sdk_context_returns_sdk(self, tmp_path):
        """Build agent ticket with SDK context returns 'sdk' instead of 'build'."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        (epics_dir / "sdk_build").mkdir()
        _setup_tinydb_for_workflow(
            tmp_path, "sdk_build",
            agent_type="build-python",
            context="Migrate subprocess replacement using claude-agent-sdk",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("sdk_build") == "sdk"

    def test_build_without_sdk_context_returns_build(self, tmp_path):
        """Build agent ticket without SDK context still returns 'build'."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        (epics_dir / "normal_build").mkdir()
        _setup_tinydb_for_workflow(
            tmp_path, "normal_build",
            agent_type="build-python",
            context="Add new CLI commands for plan management",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("normal_build") == "build"

    def test_build_with_sdk_context_in_tinydb_returns_sdk(self, tmp_path):
        """TinyDB epic with SDK context and build agent ticket returns 'sdk'."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        (epics_dir / "explicit_sdk").mkdir()
        _setup_tinydb_for_workflow(
            tmp_path, "explicit_sdk",
            agent_type="build-python",
            context="Use claude-agent-sdk for session spawning",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("explicit_sdk") == "sdk"

    def test_test_type_not_affected(self, tmp_path):
        """Test agent ticket returns 'test' even when epic has SDK context."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        (epics_dir / "test_plan").mkdir()
        _setup_tinydb_for_workflow(
            tmp_path, "test_plan",
            agent_type="test-runner",
            context="Test claude-agent-sdk integration",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("test_plan") == "test"


# ---------------------------------------------------------------------------
# PlannerLoopRunner tests
# ---------------------------------------------------------------------------


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
        from pathlib import Path
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow

        # Create a temporary empty epics_dir so iterdir() won't fail
        tmp_epics_dir = Path(tempfile.mkdtemp()) / "docs" / "epics" / "live"
        tmp_epics_dir.mkdir(parents=True, exist_ok=True)
        # Create stub epic folders so the folder-existence guard doesn't reject them
        for folder in (epic_folders or ["test_plan"]):
            (tmp_epics_dir / folder).mkdir(exist_ok=True)

        workflow = PlannerLoopWorkflow(epics_dir=tmp_epics_dir)
        # Also mock get_plan_status so archive loop doesn't fail on missing plans
        monkeypatch.setattr(workflow, "get_plan_status", lambda pf: "in_progress")
        # Default mocks: all spawn methods return successful SessionResult
        monkeypatch.setattr(workflow, "run_health_check", overrides.get("health_check", lambda: None))
        monkeypatch.setattr(workflow, "compile_bootstrap_context", overrides.get("bootstrap", lambda role="orchestration-planning": {}))
        monkeypatch.setattr(workflow, "discover_plans_needing_orchestration",
                            overrides.get("discover", lambda: []))
        monkeypatch.setattr(workflow, "spawn_explore_agent",
                            overrides.get("spawn_explore", lambda pf: _ok_result()))
        monkeypatch.setattr(workflow, "spawn_story_agent",
                            overrides.get("spawn_story", lambda pf: _ok_result()))
        monkeypatch.setattr(workflow, "discover_stories",
                            overrides.get("stories", lambda pf, project=None: []))
        monkeypatch.setattr(workflow, "determine_plan_type",
                            overrides.get("plan_type", lambda pf: "build"))
        monkeypatch.setattr(workflow, "spawn_planner",
                            overrides.get("spawn_planner", lambda pf, pt: _ok_result()))
        monkeypatch.setattr(workflow, "spawn_reviewer",
                            overrides.get("spawn_reviewer", lambda pf: _ok_result()))
        monkeypatch.setattr(workflow, "run_review_cycle",
                            overrides.get("review", lambda pf, **kw: (True, 1, "approved")))
        monkeypatch.setattr(workflow, "spawn_orchestration_agent",
                            overrides.get("spawn_orchestration", lambda pf: _ok_result()))

        return PlannerLoopRunner(workflow=workflow)

    def test_completes_when_no_plans(self, monkeypatch, capsys):
        """Runner exits successfully when no plans need work."""
        runner = self._make_runner(monkeypatch)
        result = runner.run(max_iterations=5)

        assert result is True
        assert "Planning complete" in capsys.readouterr().out

    def test_processes_single_plan(self, monkeypatch, capsys):
        """Runner processes a plan through the 6-step workflow (includes orchestration)."""
        call_log = []

        def tracking_discover():
            if not call_log or "discover" not in [c[0] for c in call_log]:
                call_log.append(("discover",))
                return ["test_plan"]
            return []

        def tracking_spawn_explore(pf):
            call_log.append(("spawn_explore", pf))
            return _ok_result(session_id="explore-session-abc")

        def tracking_spawn_story(pf):
            call_log.append(("spawn_story", pf))
            return _ok_result(session_id="story-session-abc")

        def tracking_plan_type(pf):
            call_log.append(("plan_type", pf))
            return "build"

        def tracking_spawn(pf, pt):
            call_log.append(("spawn", pf, pt))
            return _ok_result(session_id="planner-session-abc")

        def tracking_review(pf, **kw):
            call_log.append(("review", pf))
            return (True, 1, "approved")

        def tracking_orchestration(pf):
            call_log.append(("orchestration", pf))
            return _ok_result(session_id="orchestration-session-abc")

        runner = self._make_runner(
            monkeypatch,
            discover=tracking_discover,
            spawn_explore=tracking_spawn_explore,
            spawn_story=tracking_spawn_story,
            plan_type=tracking_plan_type,
            spawn_planner=tracking_spawn,
            review=tracking_review,
            spawn_orchestration=tracking_orchestration,
        )
        result = runner.run(max_iterations=5)

        assert result is True
        # Verify call sequence includes all 6 steps
        step_names = [c[0] for c in call_log]
        assert "discover" in step_names
        assert "spawn_explore" in step_names
        assert "spawn_story" in step_names
        assert "plan_type" in step_names
        assert "spawn" in step_names
        assert "review" in step_names
        assert "orchestration" in step_names

        # Verify ordering: explore -> story -> plan_type -> spawn -> review -> orchestration
        idx_explore = next(i for i, c in enumerate(call_log) if c[0] == "spawn_explore")
        idx_story = next(i for i, c in enumerate(call_log) if c[0] == "spawn_story")
        idx_plan_type = next(i for i, c in enumerate(call_log) if c[0] == "plan_type")
        idx_review = next(i for i, c in enumerate(call_log) if c[0] == "review")
        idx_orch = next(i for i, c in enumerate(call_log) if c[0] == "orchestration")
        assert idx_explore < idx_story < idx_plan_type
        assert idx_review < idx_orch

    def test_explore_agent_failure_skips_plan(self, monkeypatch):
        """Plan is skipped when explore agent fails."""
        call_count = {"discover": 0}

        def discover():
            call_count["discover"] += 1
            if call_count["discover"] <= 1:
                return ["bad_explore_plan"]
            return []

        runner = self._make_runner(
            monkeypatch,
            discover=discover,
            spawn_explore=lambda pf: _fail_result(),
        )
        result = runner.run(max_iterations=5)

        assert "bad_explore_plan" in runner.state["plans_skipped"]

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

    def test_planner_failure_skips_plan(self, monkeypatch):
        """Plan is skipped when planner agent fails."""
        call_count = {"discover": 0}

        def discover():
            call_count["discover"] += 1
            if call_count["discover"] <= 1:
                return ["bad_planner_plan"]
            return []

        runner = self._make_runner(
            monkeypatch,
            discover=discover,
            spawn_planner=lambda pf, pt: _fail_result(),
        )
        result = runner.run(max_iterations=5)

        assert "bad_planner_plan" in runner.state["plans_skipped"]

    def test_review_loop_max_rejections(self, monkeypatch):
        """Plan is skipped after max review rejections."""
        call_count = {"discover": 0}

        def discover():
            call_count["discover"] += 1
            if call_count["discover"] <= 1:
                return ["rejected_plan"]
            return []

        runner = self._make_runner(
            monkeypatch,
            discover=discover,
            review=lambda pf, **kw: (False, 3, "Max review iterations reached"),
        )
        result = runner.run(max_iterations=5)

        assert "rejected_plan" in runner.state["plans_skipped"]

    def test_respects_max_iterations(self, monkeypatch):
        """Runner stops early when all discovered epics fail planning."""
        runner = self._make_runner(
            monkeypatch,
            epic_folders=["always_plan"],
            discover=lambda: ["always_plan"],
            # Make explore fail so the epic is marked as failed
            spawn_explore=lambda pf: _fail_result(),
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

    def test_skips_plan_without_type(self, monkeypatch):
        """Plans without plan YAML are skipped."""
        call_count = {"discover": 0}

        def discover():
            call_count["discover"] += 1
            if call_count["discover"] <= 1:
                return ["no_type_plan"]
            return []

        runner = self._make_runner(
            monkeypatch,
            epic_folders=["no_type_plan"],
            discover=discover,
            plan_type=lambda pf: None,
        )
        result = runner.run(max_iterations=5)

        assert "no_type_plan" in runner.state["plans_skipped"]


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
        result = workflow._run_role_agent("explore", "test_plan")

        assert result.status == "completed"
        assert saved_data["status"] == "completed"
        assert saved_data["transport"] == "sdk"
        assert saved_data["role"] == "explore"
        assert saved_data["cost_usd"] == 0.03

    def test_subprocess_fallback_when_sdk_unavailable(self, monkeypatch):
        """Falls back to subprocess when SDK is not available."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        monkeypatch.setattr("agenticcli.workflows.planner_loop.SDK_AVAILABLE", False)

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                cmd, 0,
                stdout='{"session_id": "subprocess-session-123"}',
                stderr="",
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = PlannerLoopWorkflow()
        monkeypatch.setattr(workflow, "wait_for_session", lambda sid, **kw: "completed")

        result = workflow._run_role_agent("explore", "test_plan")
        assert result.status == "completed"
        assert result.session_id == "subprocess-session-123"


class TestReviewCycleWithSessionResult:
    """Test run_review_cycle with SessionResult-based spawn_reviewer."""

    def test_approved_on_successful_review(self, monkeypatch):
        """Review cycle approves when reviewer completes successfully."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow()
        monkeypatch.setattr(workflow, "spawn_reviewer", lambda pf: _ok_result())

        approved, iters, feedback = workflow.run_review_cycle("test_plan")
        assert approved is True
        assert iters == 1
        assert feedback == "approved"

    def test_rejected_on_failed_review(self, monkeypatch):
        """Review cycle rejects when reviewer fails."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow()
        monkeypatch.setattr(workflow, "spawn_reviewer", lambda pf: _fail_result())

        approved, iters, feedback = workflow.run_review_cycle("test_plan")
        assert approved is False
        assert "failed" in feedback


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

    def test_active_status_not_overridden_by_all_tasks_complete(self, tmp_path):
        """TinyDB status: active is preserved even when all tickets are completed.

        This is the regression test for the auto-archive bug: an epic whose
        TinyDB record has status='active' must NOT be reported as 'completed'
        just because every ticket carries status='completed'.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_tinydb_plan(
            tmp_path, epics_dir, "active_plan",
            status="active",
            tickets=[
                {"task_id": "t1", "name": "task1", "status": "completed"},
                {"task_id": "t2", "name": "task2", "status": "completed"},
            ],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("active_plan") == "active"

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

    def test_pending_status_with_all_tasks_complete_returns_pending(self, tmp_path):
        """Epic with status=pending is returned as-is even when all tickets are done.

        TinyDB always stores a status (defaulting to 'pending'), so task counting
        is only triggered when the status field is missing. Since TinyDB always
        has a status, 'pending' is honoured like any non-completed status.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_tinydb_plan(
            tmp_path, epics_dir, "pending_done",
            status="pending",
            tickets=[
                {"task_id": "t1", "name": "task1", "status": "completed"},
                {"task_id": "t2", "name": "task2", "status": "completed"},
            ],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        # "pending" != "completed" and is not None → returned directly
        assert workflow.get_plan_status("pending_done") == "pending"

    def test_pending_status_with_mixed_tasks_returns_pending(self, tmp_path):
        """Epic with status=pending and mixed ticket statuses returns 'pending'."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_tinydb_plan(
            tmp_path, epics_dir, "partial_plan",
            status="pending",
            tickets=[
                {"task_id": "t1", "name": "task1", "status": "completed"},
                {"task_id": "t2", "name": "task2", "status": "pending"},
            ],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("partial_plan") == "pending"

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
        # Create epic with no tickets - TinyDB defaults status to "pending"
        self._make_tinydb_plan(
            tmp_path, epics_dir, "empty_plan",
            status="pending",
            tickets=[],
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        # "pending" is not None and not "completed" → returned as-is
        assert workflow.get_plan_status("empty_plan") == "pending"


# ---------------------------------------------------------------------------
# SDK Resilience tests (SDK_010, SDK_011)
# ---------------------------------------------------------------------------


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

        # Explore role
        workflow._run_via_sdk("s1", "explore", "p", "prompt")
        assert captured_timeouts["last"] == ROLE_TIMEOUT_SECONDS["explore"]  # 600

        # Orchestration role
        workflow._run_via_sdk("s2", "planner-orchestration", "p", "prompt")
        assert captured_timeouts["last"] == ROLE_TIMEOUT_SECONDS["planner-orchestration"]  # 3600


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
            workflow._validate_result(result, "story-generator")

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
        monkeypatch.setattr(workflow, "get_plan_status", lambda pf: "in_progress")
        monkeypatch.setattr(workflow, "run_health_check", lambda: None)
        monkeypatch.setattr(workflow, "compile_bootstrap_context", lambda role="orchestration-planning": {})
        monkeypatch.setattr(workflow, "spawn_explore_agent", lambda pf: _ok_result(duration_ms=100))
        monkeypatch.setattr(workflow, "spawn_story_agent", lambda pf: _ok_result(duration_ms=100))
        monkeypatch.setattr(workflow, "determine_plan_type", lambda pf: "build")
        monkeypatch.setattr(workflow, "spawn_planner", lambda pf, pt: _ok_result(duration_ms=100))
        monkeypatch.setattr(workflow, "run_review_cycle", lambda pf, **kw: (True, 1, "approved"))
        monkeypatch.setattr(workflow, "spawn_orchestration_agent", lambda pf: _ok_result(duration_ms=100))
        monkeypatch.setattr(workflow, "_validate_result", tracking_validate_result)

        runner = PlannerLoopRunner(workflow=workflow)
        monkeypatch.setattr(
            runner.workflow, "discover_plans_needing_orchestration",
            lambda: ["my_test_plan"] if not validated_roles else [],
        )
        # Need to override discover on the runner's workflow
        call_count = {"n": 0}

        def one_shot_discover():
            call_count["n"] += 1
            return ["my_test_plan"] if call_count["n"] == 1 else []

        monkeypatch.setattr(workflow, "discover_plans_needing_orchestration", one_shot_discover)

        runner.run(max_iterations=5)

        # explore, story-generator, planner-build, and planner-orchestration should all be validated
        assert "explore" in validated_roles
        assert "story-generator" in validated_roles
        assert "planner-build" in validated_roles
        assert "planner-orchestration" in validated_roles


# ---------------------------------------------------------------------------
# Phase 6 tests (SDK_016): Role-based tool allow-lists in planner_loop
# ---------------------------------------------------------------------------


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
        expected = get_allowed_tools_for_role("explore")
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

        result = _build_sdk_options("/some/dir", role="explore")
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


class TestWaitForSessionTmux:
    """TT_005: Tests for tmux-aware completion detection in wait_for_session."""

    def _make_workflow(self, monkeypatch):
        """Create a PlannerLoopWorkflow with controlled defaults."""
        import tempfile
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        tmp_epics_dir = Path(tempfile.mkdtemp()) / "docs" / "epics" / "live"
        tmp_epics_dir.mkdir(parents=True, exist_ok=True)
        return PlannerLoopWorkflow(epics_dir=tmp_epics_dir)

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
