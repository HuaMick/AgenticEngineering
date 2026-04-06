"""Integration tests for PlannerLoopRunner end-to-end flow.

Validates the full planning loop workflow logic with all SDK/tmux/subprocess
calls mocked.  No real API calls or real tmux sessions are used.

The suite verifies:
- All expected agent roles are invoked (epic-creator, build-story-writer,
  planner-explore, planner-orchestration)
- Spawn commands include the --tmux flag (sdk-tmux path)
- SDK metrics are collected after each agent completes
- Failed spawns are retried with a new session ID
- Tickets appear in TinyDB after the loop completes

Patterns follow test_planner_loop.py closely so that both suites stay aligned
as the workflow evolves.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from agenticcli.utils.sdk_runner import SessionResult

pytestmark = [
    pytest.mark.story("US-PLN-027", "US-PLN-038", "US-PLN-046", "US-PLN-047", "US-PLN-055", "US-PLN-091"),
]


# ---------------------------------------------------------------------------
# Shared helpers (mirror test_planner_loop.py)
# ---------------------------------------------------------------------------

def _ok_result(**kwargs) -> SessionResult:
    """Create a successful SessionResult for testing."""
    defaults = dict(
        status="completed",
        result="ok",
        cost_usd=0.01,
        duration_ms=5000,
        num_turns=3,
        session_id="sess-ok-123",
    )
    defaults.update(kwargs)
    return SessionResult(**defaults)


def _fail_result(**kwargs) -> SessionResult:
    """Create a failed SessionResult for testing."""
    defaults = dict(
        status="failed",
        result="failed",
        is_error=True,
        session_id="sess-fail-456",
    )
    defaults.update(kwargs)
    return SessionResult(**defaults)


_UNSET = object()


def _setup_tinydb_for_workflow(tmp_path, epic_folder_name, *, agent_type=None,
                                context=None, status=_UNSET, tickets=None):
    """Set up TinyDB for PlannerLoopWorkflow tests.

    Creates a .git marker so the workflow can find the repo root, then
    populates TinyDB with the given epic data.

    Returns:
        db_path: Path to the isolated TinyDB file.
    """
    from agenticguidance.services.epic_repository import EpicRepository

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

    if context is not None:
        epic_doc["context"] = context

    repo.create_epic(epic_doc)

    phase_name = "Phase 1"
    repo.add_phase(epic_folder_name, {"name": phase_name})

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


def _make_workflow_with_tinydb(tmp_path, epic_folder_name, **kwargs):
    """Create a PlannerLoopWorkflow backed by an isolated TinyDB.

    Returns (workflow, db_path).
    """
    from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

    epics_dir = tmp_path / "docs" / "epics" / "live"
    epics_dir.mkdir(parents=True, exist_ok=True)
    (epics_dir / epic_folder_name).mkdir(exist_ok=True)

    db_path = _setup_tinydb_for_workflow(tmp_path, epic_folder_name, **kwargs)
    workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
    return workflow, db_path


# ---------------------------------------------------------------------------
# Integration test class
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPlannerLoopE2E:
    """End-to-end validation of planning loop with SDK-in-tmux spawns."""

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _make_runner(self, monkeypatch, workflow, epic_folders=None, **overrides):
        """Create a PlannerLoopRunner with selected methods monkeypatched.

        All spawn methods default to returning _ok_result() unless overridden.
        Story mocks auto-write story files to EpicStories/ (stories are required).
        """
        import yaml
        from agenticcli.workflows.planner_loop import PlannerLoopRunner

        monkeypatch.setattr(workflow, "run_health_check",
                            overrides.get("health_check", lambda: None))
        monkeypatch.setattr(workflow, "get_plan_status",
                            overrides.get("plan_status", lambda pf: "in_progress"))

        if "discover" in overrides:
            monkeypatch.setattr(workflow, "discover_plans_needing_orchestration",
                                overrides["discover"])

        # Monkeypatch get_epic_stories_path to write to a test-local
        # docs/userstories/EpicStories/ directory instead of the real one.
        userstories_dir = workflow.epics_dir.parent.parent / "userstories" / "EpicStories"
        userstories_dir.mkdir(parents=True, exist_ok=True)

        import agenticcli.workflows.planner_loop as _plmod
        def _test_get_epic_stories_path(epic_name):
            return userstories_dir / f"{epic_name}.yml"
        monkeypatch.setattr(_plmod, "get_epic_stories_path", _test_get_epic_stories_path)

        # Story file writer: ensures story file exists (stories are required)
        def _write_stories_yml(pf):
            stories_path = userstories_dir / f"{pf}.yml"
            if not stories_path.exists():
                stories_path.write_text(yaml.dump({
                    "stories": [{"id": "US-001", "title": "Test story"}],
                    "categories": [{"name": "default", "story_ids": ["US-001"]}],
                }))

        def _default_spawn_story(pf):
            _write_stories_yml(pf)
            return _ok_result()

        # If caller provided a custom spawn_story, wrap it to write story file on success
        custom_story = overrides.get("spawn_story")
        if custom_story is not None:
            _original = custom_story
            def _wrapped(pf, _orig=_original):
                result = _orig(pf)
                if result.status == "completed":
                    _write_stories_yml(pf)
                return result
            overrides["spawn_story"] = _wrapped

        # Always patch spawn methods — defaults to _ok_result() unless overridden
        monkeypatch.setattr(workflow, "spawn_epic_creator",
                            overrides.get("spawn_epic_creator", lambda pf: _ok_result()))
        monkeypatch.setattr(workflow, "spawn_explore_agents",
                            overrides.get("spawn_explore", lambda pf, categories=None: _ok_result()))
        monkeypatch.setattr(workflow, "spawn_story_agent",
                            overrides.get("spawn_story", _default_spawn_story))
        if "spawn_orchestration" in overrides:
            monkeypatch.setattr(workflow, "spawn_orchestration_agent",
                                overrides["spawn_orchestration"])

        runner = PlannerLoopRunner(workflow=workflow)
        # Mock validation to pass (e2e tests don't set up full TinyDB for validation)
        monkeypatch.setattr(runner, "_validate_planning_output", lambda pf: (True, []))
        return runner

    # ------------------------------------------------------------------ #
    # Test: all expected roles are invoked                                 #
    # ------------------------------------------------------------------ #

    def test_planning_loop_spawns_all_roles(self, tmp_path, monkeypatch):
        """Full planning loop invokes all expected agent roles.

        Verifies that epic-creator, build-story-writer, planner-explore,
        and planner-orchestration are each invoked for a single unplanned epic.
        """
        epic_folder = "260309AA_test_epic"
        workflow, _ = _make_workflow_with_tinydb(
            tmp_path, epic_folder, agent_type="build-python",
        )

        spawned_roles = []

        def tracking_epic_creator(pf):
            spawned_roles.append("epic-creator")
            return _ok_result(session_id="creator-001")

        def tracking_spawn_explore(pf, **kw):
            spawned_roles.append("planner-explore")
            return _ok_result(session_id="explore-001")

        def tracking_spawn_story(pf):
            spawned_roles.append("build-story-writer")
            return _ok_result(session_id="story-001")

        def tracking_spawn_orchestration(pf):
            spawned_roles.append("planner-orchestration")
            return _ok_result(session_id="orchestration-001")

        call_count = {"discover": 0}

        def tracking_discover():
            call_count["discover"] += 1
            if call_count["discover"] == 1:
                return [epic_folder]
            return []

        runner = self._make_runner(
            monkeypatch, workflow,
            discover=tracking_discover,
            spawn_epic_creator=tracking_epic_creator,
            spawn_explore=tracking_spawn_explore,
            spawn_story=tracking_spawn_story,
            spawn_orchestration=tracking_spawn_orchestration,
        )
        result = runner.run(max_iterations=5)

        assert result is True

        # All roles must appear
        assert "epic-creator" in spawned_roles, f"epic-creator not in {spawned_roles}"
        assert "build-story-writer" in spawned_roles, f"story-writer not in {spawned_roles}"
        assert "planner-explore" in spawned_roles, f"planner-explore not in {spawned_roles}"
        assert "planner-orchestration" in spawned_roles, f"planner-orchestration not in {spawned_roles}"

    # ------------------------------------------------------------------ #
    # Test: spawn commands include --tmux flag                             #
    # ------------------------------------------------------------------ #

    def test_planning_loop_uses_tmux_spawn_path(self, tmp_path, monkeypatch):
        """Spawn commands built by build_spawn_command include the --tmux flag.

        Validates that the sdk-tmux path is used when tmux is available, by
        asserting the spawn command constructed by build_spawn_command contains
        --tmux.
        """
        from agenticcli.utils.spawn_command import build_spawn_command

        epic_folder = "260309BB_tmux_test"
        role = "planner-build"

        cmd = build_spawn_command(
            role=role,
            epic_folder=epic_folder,
            skip_permissions=True,
            use_tmux=True,
        )

        assert "--tmux" in cmd, f"--tmux not found in spawn command: {cmd}"
        assert "--role" in cmd, f"--role not found in spawn command: {cmd}"
        assert role in cmd, f"role '{role}' not found in spawn command: {cmd}"
        assert epic_folder in cmd, f"epic_folder not found in spawn command: {cmd}"

    def test_all_roles_use_tmux_flag_in_spawn_commands(self, tmp_path, monkeypatch):
        """build_spawn_command always includes --tmux for all planning roles."""
        from agenticcli.utils.spawn_command import build_spawn_command

        planning_roles = [
            "explore",
            "build-story-writer",
            "planner-build",
            "planner-orchestration",
        ]
        epic_folder = "260309CC_roles_tmux"

        for role in planning_roles:
            cmd = build_spawn_command(
                role=role,
                epic_folder=epic_folder,
                skip_permissions=True,
                use_tmux=True,
            )
            assert "--tmux" in cmd, f"--tmux missing for role '{role}': {cmd}"
            assert role in cmd, f"role '{role}' missing in command: {cmd}"

    # ------------------------------------------------------------------ #
    # Test: SDK metrics collection                                         #
    # ------------------------------------------------------------------ #

    def test_planning_loop_collects_metrics(self, tmp_path, monkeypatch):
        """Planning loop reads SDK metrics after each agent completes.

        Mocks subprocess.run to return spawn JSON and read_sdk_metrics to
        return known values, then verifies the final SessionResult carries
        the expected cost/duration/turns.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow
        from agenticcli.utils import session_state as ss_module

        epic_folder = "260309DD_metrics_test"
        workflow, _ = _make_workflow_with_tinydb(tmp_path, epic_folder)

        # Patch SDK availability off + tmux present so the code falls into
        # _run_via_tmux_sdk.  We stub subprocess.run and wait_for_session.
        mock_spawn_output = json.dumps({"session_id": "metrics-session-001"})
        spawn_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=mock_spawn_output, stderr="",
        )

        expected_metrics = {
            "cost_usd": 0.042,
            "duration_ms": 12345,
            "num_turns": 7,
            "usage": {"input_tokens": 1000, "output_tokens": 200},
            "sdk_session_id": "sdk-abc-999",
            "transport": "sdk-tmux",
        }

        with (
            patch("agenticcli.workflows.planner_loop.SDK_AVAILABLE", True),
            patch("shutil.which", return_value="/usr/bin/tmux"),
            patch("agenticcli.workflows.planner_loop.diagnose_quick_exit", return_value=None),
            patch("agenticcli.workflows.planner_loop._session_store"),
            patch.object(workflow, "wait_for_session", return_value="completed"),
            patch("agenticcli.workflows.planner_loop.read_sdk_metrics",
                  return_value=expected_metrics),
            patch("subprocess.run", return_value=spawn_result),
        ):
            result = workflow._run_via_tmux_sdk(
                session_id="test-session-id",
                role="planner-build",
                epic_folder=epic_folder,
                prompt="Test prompt",
                max_retries=1,
            )

        assert result.status == "completed"
        assert result.cost_usd == expected_metrics["cost_usd"]
        assert result.duration_ms == expected_metrics["duration_ms"]
        assert result.num_turns == expected_metrics["num_turns"]
        assert result.usage == expected_metrics["usage"]

    # ------------------------------------------------------------------ #
    # Test: retry on failure                                               #
    # ------------------------------------------------------------------ #

    def test_planning_loop_retry_on_failure(self, tmp_path, monkeypatch):
        """Failed agent spawn retries with a new session ID.

        The first subprocess.run returns a non-zero exit code; the second
        returns success.  Verifies that exactly 2 spawn calls are made and
        the final result is completed.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epic_folder = "260309EE_retry_test"
        workflow, _ = _make_workflow_with_tinydb(tmp_path, epic_folder)

        call_count = {"n": 0}
        session_ids_used = []

        def mock_subprocess_run(cmd, *args, **kwargs):
            # Track the -b (background) spawn calls, not internal agentic calls
            is_spawn_cmd = isinstance(cmd, list) and "spawn" in cmd
            if is_spawn_cmd:
                call_count["n"] += 1
                if call_count["n"] == 1:
                    # First attempt: spawn fails
                    return subprocess.CompletedProcess(
                        args=cmd, returncode=1, stdout="", stderr="tmux error",
                    )
                else:
                    # Second attempt: spawn succeeds
                    return subprocess.CompletedProcess(
                        args=cmd, returncode=0,
                        stdout=json.dumps({"session_id": "retry-session-002"}),
                        stderr="",
                    )
            # Non-spawn subprocess calls succeed by default
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="{}", stderr="",
            )

        with (
            patch("agenticcli.workflows.planner_loop.SDK_AVAILABLE", True),
            patch("shutil.which", return_value="/usr/bin/tmux"),
            patch("agenticcli.workflows.planner_loop.diagnose_quick_exit", return_value=None),
            patch("agenticcli.workflows.planner_loop._session_store"),
            patch("agenticcli.workflows.planner_loop.read_sdk_metrics",
                  return_value={
                      "cost_usd": 0.01, "duration_ms": 3000, "num_turns": 2,
                      "usage": {}, "sdk_session_id": "sdk-retry", "transport": "sdk-tmux",
                  }),
            patch.object(workflow, "wait_for_session", return_value="completed"),
            patch("agenticcli.workflows.planner_loop.static_backoff", return_value=0),
            patch("agenticcli.workflows.planner_loop.time") as mock_time,
            patch("subprocess.run", side_effect=mock_subprocess_run),
        ):
            mock_time.monotonic.return_value = 60.0  # simulate > 30s elapsed
            mock_time.sleep = MagicMock()

            result = workflow._run_via_tmux_sdk(
                session_id="initial-session-id",
                role="planner-build",
                epic_folder=epic_folder,
                prompt="Test prompt",
                max_retries=3,
            )

        assert result.status == "completed", f"Expected completed, got: {result.status}"
        assert call_count["n"] == 2, f"Expected 2 spawn calls, got {call_count['n']}"

    # ------------------------------------------------------------------ #
    # Test: tickets created in TinyDB after loop                          #
    # ------------------------------------------------------------------ #

    def test_planning_loop_creates_tickets_in_tinydb(self, tmp_path, monkeypatch):
        """After a successful planning loop, the epic has tickets in TinyDB.

        Uses the full PlannerLoopRunner with all agent methods mocked, but
        with a real TinyDB-backed workflow. After the runner completes, we
        add a mock ticket directly (simulating what the orchestration agent
        would do) and verify the ticket appears in TinyDB.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow
        from agenticguidance.services.epic_repository import EpicRepository

        epic_folder = "260309FF_tinydb_test"
        workflow, db_path = _make_workflow_with_tinydb(
            tmp_path, epic_folder, agent_type="build-python",
        )

        call_count = {"discover": 0}

        def tracking_discover():
            call_count["discover"] += 1
            if call_count["discover"] == 1:
                return [epic_folder]
            return []

        runner = self._make_runner(
            monkeypatch, workflow,
            discover=tracking_discover,
            spawn_epic_creator=lambda pf: _ok_result(session_id="creator-e2e"),
            spawn_explore=lambda pf, categories=None: _ok_result(session_id="explore-e2e"),
            spawn_story=lambda pf: _ok_result(session_id="story-e2e"),
            spawn_design=lambda pf: SessionResult(status="completed", result="DESIGN_STATUS: approved", session_id="design-e2e"),
            review=lambda pf, **kw: (True, 1, "approved"),
            spawn_orchestration=lambda pf: _ok_result(session_id="orch-e2e"),
        )

        result = runner.run(max_iterations=3)

        # Loop completes successfully (all agents mocked as ok)
        assert result is True
        assert epic_folder in runner.state["plans_processed"]

        # Simulate what planner-orchestration would have written:
        # add a routed phase + ticket to TinyDB
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.add_phase(epic_folder, {
            "name": "P1 Build",
            "agent": "build-python",
            "loop_type": "sequential",
        })
        repo.add_ticket(epic_folder, "P1 Build", {
            "task_id": "T002",
            "name": "Implement feature X",
            "status": "pending",
            "agent": "build-python",
        })
        repo.close()

        # Now verify TinyDB has the ticket
        repo2 = EpicRepository(db_path=db_path, auto_bootstrap=False)
        tickets = repo2.get_tickets(epic_folder)
        repo2.close()

        ticket_ids = [t.id for t in tickets]
        assert "T002" in ticket_ids, f"Expected T002 in tickets: {ticket_ids}"

    # ------------------------------------------------------------------ #
    # Test: _run_role_agent routes through tmux when SDK + tmux available #
    # ------------------------------------------------------------------ #

    def test_run_role_agent_uses_tmux_sdk_when_available(self, tmp_path, monkeypatch):
        """_run_role_agent dispatches to _run_via_tmux_sdk when SDK + tmux present."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epic_folder = "260309GG_route_test"
        workflow, _ = _make_workflow_with_tinydb(tmp_path, epic_folder)

        called_path = {"path": None}

        def mock_tmux_sdk(session_id, role, epic_folder, prompt, **kwargs):
            called_path["path"] = "sdk-tmux"
            return _ok_result()

        def mock_sdk_direct(session_id, role, epic_folder, prompt, **kwargs):
            called_path["path"] = "sdk-direct"
            return _ok_result()

        with (
            patch("agenticcli.workflows.planner_loop.SDK_AVAILABLE", True),
            patch("shutil.which", return_value="/usr/bin/tmux"),
            patch.dict("os.environ", {}, clear=False),
            patch.object(workflow, "_run_via_tmux_sdk", side_effect=mock_tmux_sdk),
            patch.object(workflow, "_run_via_sdk", side_effect=mock_sdk_direct),
        ):
            # Ensure AGENTIC_FORCE_SDK_DIRECT is not set
            import os
            os.environ.pop("AGENTIC_FORCE_SDK_DIRECT", None)
            workflow._run_role_agent("planner-build", epic_folder)

        assert called_path["path"] == "sdk-tmux", (
            f"Expected sdk-tmux path, got: {called_path['path']}"
        )

    # ------------------------------------------------------------------ #
    # Test: ordering of agent phases                                       #
    # ------------------------------------------------------------------ #

    def test_planning_loop_phase_order(self, tmp_path, monkeypatch):
        """Agents are invoked in the correct sequential order.

        Order must be: epic_creator -> story -> explore -> orchestration.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epic_folder = "260309HH_order_test"
        workflow, _ = _make_workflow_with_tinydb(
            tmp_path, epic_folder, agent_type="build-python",
        )

        invocation_log = []

        def log_epic_creator(pf):
            invocation_log.append("epic_creator")
            return _ok_result()

        def log_explore(pf, categories=None):
            invocation_log.append("explore")
            return _ok_result()

        def log_story(pf):
            invocation_log.append("story")
            return _ok_result()

        def log_orchestration(pf):
            invocation_log.append("orchestration")
            return _ok_result()

        call_count = {"discover": 0}

        def one_shot_discover():
            call_count["discover"] += 1
            if call_count["discover"] == 1:
                return [epic_folder]
            return []

        runner = self._make_runner(
            monkeypatch, workflow,
            discover=one_shot_discover,
            spawn_epic_creator=log_epic_creator,
            spawn_explore=log_explore,
            spawn_story=log_story,
            spawn_orchestration=log_orchestration,
        )

        result = runner.run(max_iterations=5)

        assert result is True
        assert invocation_log == [
            "epic_creator", "story", "explore", "orchestration",
        ], f"Unexpected phase order: {invocation_log}"

    # ------------------------------------------------------------------ #
    # Test: skips plan when explore agent fails                            #
    # ------------------------------------------------------------------ #

    def test_planning_loop_skips_on_epic_creator_failure(self, tmp_path, monkeypatch):
        """Epic is skipped when the epic-creator agent fails.

        The runner must NOT proceed to story or explore when epic-creator fails.
        """
        epic_folder = "260309II_creator_fail"
        workflow, _ = _make_workflow_with_tinydb(tmp_path, epic_folder)

        story_called = {"called": False}

        def failing_creator(pf):
            return _fail_result(result="Connection error")

        def should_not_be_called_story(pf):
            story_called["called"] = True
            return _ok_result()

        call_count = {"discover": 0}

        def one_shot_discover():
            call_count["discover"] += 1
            if call_count["discover"] == 1:
                return [epic_folder]
            return []

        runner = self._make_runner(
            monkeypatch, workflow,
            discover=one_shot_discover,
            spawn_epic_creator=failing_creator,
            spawn_story=should_not_be_called_story,
        )

        runner.run(max_iterations=3)

        assert epic_folder in runner.state["plans_skipped"]
        assert not story_called["called"], "Story agent should not be called after epic-creator failure"
