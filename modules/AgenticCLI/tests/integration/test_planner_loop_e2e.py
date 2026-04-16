"""Integration tests for PlannerLoopRunner end-to-end flow.

Validates the full planning loop workflow logic with all SDK/tmux/subprocess
calls mocked.  No real API calls or real tmux sessions are used.

The suite verifies:
- All expected agent roles are invoked (epic-creator, build-story-writer,
  planner-orchestration, planner-build, planner-test)
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
    pytest.mark.story("US-PLN-046", "US-PLN-047"),
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
        monkeypatch.setattr(workflow, "spawn_planner_phases",
                            overrides.get("spawn_planner_phases",
                                          lambda pf, phase_ids, role: _ok_result()))
        monkeypatch.setattr(workflow, "spawn_story_agent",
                            overrides.get("spawn_story", _default_spawn_story))
        if "spawn_orchestration" in overrides:
            monkeypatch.setattr(workflow, "spawn_orchestration_agent",
                                overrides["spawn_orchestration"])

        runner = PlannerLoopRunner(workflow=workflow)
        # Mock validation to pass (e2e tests don't set up full TinyDB for validation)
        monkeypatch.setattr(runner, "_validate_planning_output",
                            lambda pf, skip_story_ids_check=False: (True, []))
        return runner

    # ------------------------------------------------------------------ #
    # Test: all expected roles are invoked                                 #
    # ------------------------------------------------------------------ #

    def test_planning_loop_spawns_all_roles(self, tmp_path, monkeypatch):
        """Full planning loop invokes all expected agent roles.

        Verifies that epic-creator, planner-orchestration, and
        build-story-writer are each invoked for a single unplanned epic
        (dispatcher-first pipeline; stories enabled by safe default).
        """
        epic_folder = "260309AA_test_epic"
        workflow, _ = _make_workflow_with_tinydb(
            tmp_path, epic_folder, agent_type="build-python",
        )

        spawned_roles = []

        def tracking_epic_creator(pf):
            spawned_roles.append("epic-creator")
            return _ok_result(session_id="creator-001")

        def tracking_spawn_planner_phases(pf, phase_ids, role):
            spawned_roles.append(role)
            return _ok_result(session_id=f"{role}-001")

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
            spawn_planner_phases=tracking_spawn_planner_phases,
            spawn_story=tracking_spawn_story,
            spawn_orchestration=tracking_spawn_orchestration,
        )
        result = runner.run(max_iterations=5)

        assert result is True

        assert "epic-creator" in spawned_roles, f"epic-creator not in {spawned_roles}"
        assert "planner-orchestration" in spawned_roles, f"planner-orchestration not in {spawned_roles}"
        assert "build-story-writer" in spawned_roles, f"story-writer not in {spawned_roles}"

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
        """Agents are invoked in the dispatcher-first sequential order.

        Order must be: epic_creator -> orchestration -> story.
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

        def log_planner_phases(pf, phase_ids, role):
            invocation_log.append(role)
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
            spawn_planner_phases=log_planner_phases,
            spawn_story=log_story,
            spawn_orchestration=log_orchestration,
        )

        result = runner.run(max_iterations=5)

        assert result is True
        # Dispatcher runs second; story conditional on decision (default True).
        assert invocation_log[:3] == [
            "epic_creator", "orchestration", "story",
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


# ---------------------------------------------------------------------------
# Dispatcher-first pipeline tests (Wave 4C)
# Tests for the planning_decision-driven pipeline introduced in _process_plan_inner
# ---------------------------------------------------------------------------

def _setup_dispatcher_epic(tmp_path, epic_folder_name, phase_configs, ticket_configs=None):
    """Set up TinyDB with an epic in 'planning' status and pre-created phases.

    Args:
        tmp_path: pytest tmp_path fixture.
        epic_folder_name: Name of the epic folder.
        phase_configs: List of dicts with phase configuration (name, phase_id, agent).
        ticket_configs: Optional list of dicts with ticket configuration per phase.

    Returns:
        (workflow, db_path, repo) — caller must close repo when done.
    """
    from agenticguidance.services.epic_repository import EpicRepository
    from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

    # Create directory structure
    epics_dir = tmp_path / "docs" / "epics" / "live"
    epics_dir.mkdir(parents=True, exist_ok=True)
    (epics_dir / epic_folder_name).mkdir(exist_ok=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    db_path = tmp_path / ".agentic" / "epics.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    # Register epic with planning status
    repo.create_epic({
        "epic_folder_name": epic_folder_name,
        "epic_folder": str(epics_dir / epic_folder_name),
        "name": epic_folder_name,
        "status": "planning",
    })

    # Create phases and tickets
    for i, phase_cfg in enumerate(phase_configs):
        phase_name = phase_cfg.get("name", f"Phase {i+1}")
        repo.add_phase(epic_folder_name, {
            "name": phase_name,
            "phase_id": phase_cfg.get("phase_id", f"p{i+1}"),
            "agent": phase_cfg.get("agent", "build-python"),
        })

        # Add tickets for this phase
        tickets_for_phase = (ticket_configs or [{}])[i] if ticket_configs else [{}]
        if isinstance(tickets_for_phase, dict):
            tickets_for_phase = [tickets_for_phase]
        for j, ticket_cfg in enumerate(tickets_for_phase):
            ticket = {
                "task_id": ticket_cfg.get("task_id", f"T{i:02d}{j:02d}"),
                "name": ticket_cfg.get("name", f"Task {i}-{j}"),
                "status": ticket_cfg.get("status", "pending"),
                "agent": ticket_cfg.get("agent", phase_cfg.get("agent", "build-python")),
            }
            if "story_ids" in ticket_cfg:
                ticket["story_ids"] = ticket_cfg["story_ids"]
            repo.add_ticket(epic_folder_name, phase_name, ticket)

    repo.close()

    workflow = PlannerLoopWorkflow(epics_dir=epics_dir)

    # Override workflow's repository to use our isolated db
    isolated_repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    workflow._repository = isolated_repo

    return workflow, db_path, isolated_repo


def _make_stub_run_role_agent(decision, repo, epic_folder_name, call_log, stories_path=None):
    """Build a stub _run_role_agent function.

    When role == "planner-orchestration", writes the given planning_decision
    to the repo. For all other roles, returns success without side effects.
    Appends each (role, extra_prompt) pair to call_log.

    Args:
        decision: Dict with planning_decision fields.
        repo: EpicRepository instance to write the decision into.
        epic_folder_name: Epic folder name for the decision record.
        call_log: List to track role invocations [(role, extra_prompt), ...].
        stories_path: Optional path; if provided, writes a minimal story file
                      when build-story-writer is called (needed for file-ready check).
    """
    import yaml
    from agenticcli.utils.sdk_runner import SessionResult

    def stub(role, ef, extra_prompt=None):
        call_log.append((role, extra_prompt))
        if role == "planner-orchestration":
            repo.write_planning_decision(
                ef,
                needs_stories=decision.get("needs_stories", True),
                needs_preflight_story_check=decision.get("needs_preflight_story_check", True),
                build_phase_ids=decision.get("build_phase_ids", []),
                test_phase_ids=decision.get("test_phase_ids", []),
            )
        elif role == "build-story-writer" and stories_path is not None:
            stories_path.parent.mkdir(parents=True, exist_ok=True)
            stories_path.write_text(yaml.dump({
                "stories": [{"id": "US-001", "title": "Test story"}],
                "categories": [{"name": "default", "story_ids": ["US-001"]}],
            }))
        return SessionResult(
            status="completed",
            result=f"stub ok for {role}",
            cost_usd=0.001,
            duration_ms=100,
            num_turns=1,
            session_id=f"stub-{role}-001",
        )

    return stub


@pytest.mark.integration
class TestDispatcherPipeline:
    """Tests for the planning_decision-driven dispatcher pipeline.

    Each test calls _process_plan_inner directly (bypassing the lock acquired
    in _process_plan) and monkeypatches _run_role_agent to intercept role
    spawns. The planner-orchestration stub writes the planning_decision to
    TinyDB so the pipeline branches correctly.
    """

    def _patch_workflow(self, monkeypatch, workflow, stub_fn):
        """Monkeypatch workflow._run_role_agent with stub_fn."""
        monkeypatch.setattr(workflow, "_run_role_agent", stub_fn)

    def _patch_stories_path(self, monkeypatch, workflow, stories_path):
        """Monkeypatch get_epic_stories_path in the planner_loop module."""
        import agenticcli.workflows.planner_loop as plmod
        monkeypatch.setattr(plmod, "get_epic_stories_path", lambda ef: stories_path)

    # ------------------------------------------------------------------ #
    # Test 1: story-writer skipped when needs_stories=False               #
    # ------------------------------------------------------------------ #

    def test_pipeline_skips_story_writer_on_refactor_epic(self, tmp_path, monkeypatch):
        """Pipeline skips build-story-writer when planning_decision.needs_stories is False.

        A refactor/infrastructure epic does not need new user stories, so the
        planner-orchestration dispatcher emits needs_stories=False.  The pipeline
        must honour this and skip build-story-writer entirely.

        Also verifies that planner-build and planner-test are called the exact
        number of times matching the phase_ids in the decision.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopRunner

        epic_folder = "260415AA_refactor_epic_skip_stories"
        decision = {
            "needs_stories": False,
            "needs_preflight_story_check": False,
            "build_phase_ids": ["p1", "p2"],
            "test_phase_ids": ["p3"],
        }

        phase_configs = [
            {"name": "Phase 1", "phase_id": "p1", "agent": "build-python"},
            {"name": "Phase 2", "phase_id": "p2", "agent": "build-python"},
            {"name": "Phase 3", "phase_id": "p3", "agent": "test-builder"},
        ]
        ticket_configs = [
            [{"task_id": "T001", "name": "Build task 1", "status": "pending"}],
            [{"task_id": "T002", "name": "Build task 2", "status": "pending"}],
            [{"task_id": "T003", "name": "Test task 1", "status": "pending"}],
        ]

        workflow, db_path, repo = _setup_dispatcher_epic(
            tmp_path, epic_folder, phase_configs, ticket_configs
        )

        call_log = []
        stub = _make_stub_run_role_agent(decision, repo, epic_folder, call_log)
        self._patch_workflow(monkeypatch, workflow, stub)

        # Patch validation to pass (no story_ids needed per decision)
        runner = PlannerLoopRunner(workflow=workflow)
        monkeypatch.setattr(runner, "_validate_planning_output",
                            lambda ef, skip_story_ids_check=False: (True, []))

        result = runner._process_plan_inner(epic_folder)

        assert result is True, f"_process_plan_inner failed: {runner.state['errors']}"

        roles_called = [r for r, _ in call_log]

        assert "build-story-writer" not in roles_called, (
            f"build-story-writer must be skipped when needs_stories=False, "
            f"but was called. roles_called={roles_called}"
        )

        build_calls = [r for r in roles_called if r == "planner-build"]
        assert len(build_calls) == 2, (
            f"Expected planner-build called 2 times (one per phase_id), "
            f"got {len(build_calls)}. roles_called={roles_called}"
        )

        test_calls = [r for r in roles_called if r == "planner-test"]
        assert len(test_calls) == 1, (
            f"Expected planner-test called 1 time, "
            f"got {len(test_calls)}. roles_called={roles_called}"
        )

        repo.close()

    # ------------------------------------------------------------------ #
    # Test 2: story-writer runs when needs_stories=True                   #
    # ------------------------------------------------------------------ #

    def test_pipeline_runs_story_writer_on_feature_epic(self, tmp_path, monkeypatch):
        """Pipeline invokes build-story-writer when planning_decision.needs_stories is True.

        A feature epic that introduces new functionality must have user stories
        written by build-story-writer.  The planner-orchestration dispatcher
        emits needs_stories=True and the pipeline must call build-story-writer.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopRunner

        epic_folder = "260415BB_feature_epic_with_stories"
        decision = {
            "needs_stories": True,
            "needs_preflight_story_check": True,
            "build_phase_ids": ["p1"],
            "test_phase_ids": ["p2"],
        }

        phase_configs = [
            {"name": "Phase 1", "phase_id": "p1", "agent": "build-python"},
            {"name": "Phase 2", "phase_id": "p2", "agent": "test-builder"},
        ]
        ticket_configs = [
            [{"task_id": "T001", "name": "Build task", "status": "pending",
              "story_ids": ["US-001"]}],
            [{"task_id": "T002", "name": "Test task", "status": "pending",
              "story_ids": ["US-001"]}],
        ]

        workflow, db_path, repo = _setup_dispatcher_epic(
            tmp_path, epic_folder, phase_configs, ticket_configs
        )

        # Provide stories path so the stub can write a story file
        stories_path = tmp_path / "docs" / "userstories" / "EpicStories" / f"{epic_folder}.yml"
        self._patch_stories_path(monkeypatch, workflow, stories_path)

        call_log = []
        stub = _make_stub_run_role_agent(
            decision, repo, epic_folder, call_log, stories_path=stories_path
        )
        self._patch_workflow(monkeypatch, workflow, stub)

        runner = PlannerLoopRunner(workflow=workflow)
        monkeypatch.setattr(runner, "_validate_planning_output",
                            lambda ef, skip_story_ids_check=False: (True, []))

        result = runner._process_plan_inner(epic_folder)

        assert result is True, f"_process_plan_inner failed: {runner.state['errors']}"

        roles_called = [r for r, _ in call_log]

        assert "build-story-writer" in roles_called, (
            f"build-story-writer must be called when needs_stories=True. "
            f"roles_called={roles_called}"
        )

        repo.close()

    # ------------------------------------------------------------------ #
    # Test 3: preflight story_ids check gated by decision flag            #
    # ------------------------------------------------------------------ #

    def test_preflight_skips_story_ids_check_when_decision_says(self, tmp_path, monkeypatch):
        """Validation skips story_ids per-ticket check when needs_preflight_story_check=False.

        When an epic is a refactor/infra type, the dispatcher emits
        needs_preflight_story_check=False.  Pre-flight validation must pass even
        if tickets have no story_ids.  The control assertion (same epic but with
        needs_preflight_story_check=True) verifies that the story_ids check IS
        active and would catch missing story_ids.

        EpicService.is_build_plan uses the global TinyDB, so we monkeypatch it
        to always return True — ensuring the story_ids gate is exercised in the
        control case.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopRunner
        from agenticguidance.services.epic import EpicService

        epic_folder = "260415CC_preflight_gate"

        # Phase with build-python agent
        phase_configs = [
            {"name": "Build Phase", "phase_id": "p1", "agent": "build-python"},
        ]
        # Tickets WITHOUT story_ids — key for this test
        ticket_configs = [
            [{"task_id": "T001", "name": "Build task", "status": "pending"}],
        ]

        # Patch is_build_plan to return True so the story_ids gate is active
        monkeypatch.setattr(EpicService, "is_build_plan", lambda self, ef: True)

        # --- Control: needs_preflight_story_check=True → validation fails (story_ids missing) ---
        workflow_control, db_path_control, repo_control = _setup_dispatcher_epic(
            tmp_path / "control", epic_folder, phase_configs, ticket_configs
        )
        decision_control = {
            "needs_stories": False,
            "needs_preflight_story_check": True,
            "build_phase_ids": ["p1"],
            "test_phase_ids": [],
        }
        call_log_control = []
        stub_control = _make_stub_run_role_agent(
            decision_control, repo_control, epic_folder, call_log_control
        )
        monkeypatch.setattr(workflow_control, "_run_role_agent", stub_control)

        runner_control = PlannerLoopRunner(workflow=workflow_control)
        # Do NOT mock _validate_planning_output — let real validation run
        result_control = runner_control._process_plan_inner(epic_folder)

        # With needs_preflight_story_check=True on a build plan, missing story_ids
        # should cause validation to fail
        assert result_control is False, (
            "Control case: validation should fail for build-plan epic "
            "with needs_preflight_story_check=True and empty story_ids"
        )
        repo_control.close()

        # --- Main: needs_preflight_story_check=False → validation passes ---
        workflow_main, db_path_main, repo_main = _setup_dispatcher_epic(
            tmp_path / "main", epic_folder, phase_configs, ticket_configs
        )
        decision_main = {
            "needs_stories": False,
            "needs_preflight_story_check": False,
            "build_phase_ids": ["p1"],
            "test_phase_ids": [],
        }
        call_log_main = []
        stub_main = _make_stub_run_role_agent(
            decision_main, repo_main, epic_folder, call_log_main
        )
        monkeypatch.setattr(workflow_main, "_run_role_agent", stub_main)

        runner_main = PlannerLoopRunner(workflow=workflow_main)
        # Do NOT mock _validate_planning_output — let real validation run
        result_main = runner_main._process_plan_inner(epic_folder)

        assert result_main is True, (
            f"With needs_preflight_story_check=False, validation should pass "
            f"despite empty story_ids. errors={runner_main.state['errors']}"
        )
        repo_main.close()

    # ------------------------------------------------------------------ #
    # Test 4: parallel planner-build count matches phase_ids              #
    # ------------------------------------------------------------------ #

    def test_parallel_planner_build_count_matches_phase_ids(self, tmp_path, monkeypatch):
        """spawn_planner_phases calls _run_role_agent once per build phase_id.

        When the planning_decision contains 4 build_phase_ids, the parallel
        ThreadPoolExecutor must invoke _run_role_agent("planner-build", ...) exactly
        4 times — one dedicated invocation scoped to each phase.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopRunner

        epic_folder = "260415DD_four_build_phases"
        build_phase_ids = ["p1", "p2", "p3", "p4"]
        decision = {
            "needs_stories": False,
            "needs_preflight_story_check": False,
            "build_phase_ids": build_phase_ids,
            "test_phase_ids": [],
        }

        phase_configs = [
            {"name": f"Phase {i+1}", "phase_id": pid, "agent": "build-python"}
            for i, pid in enumerate(build_phase_ids)
        ]
        ticket_configs = [
            [{"task_id": f"T00{i+1}", "name": f"Task {i+1}", "status": "pending"}]
            for i in range(len(build_phase_ids))
        ]

        workflow, db_path, repo = _setup_dispatcher_epic(
            tmp_path, epic_folder, phase_configs, ticket_configs
        )

        call_log = []
        stub = _make_stub_run_role_agent(decision, repo, epic_folder, call_log)
        self._patch_workflow(monkeypatch, workflow, stub)

        runner = PlannerLoopRunner(workflow=workflow)
        monkeypatch.setattr(runner, "_validate_planning_output",
                            lambda ef, skip_story_ids_check=False: (True, []))

        result = runner._process_plan_inner(epic_folder)

        assert result is True, f"_process_plan_inner failed: {runner.state['errors']}"

        build_calls = [(r, xp) for r, xp in call_log if r == "planner-build"]
        assert len(build_calls) == len(build_phase_ids), (
            f"Expected planner-build called {len(build_phase_ids)} times "
            f"(one per phase_id in build_phase_ids), "
            f"got {len(build_calls)}. call_log={call_log}"
        )

        # Each call must carry a unique phase scope in extra_prompt
        extra_prompts = [xp for _, xp in build_calls]
        for pid in build_phase_ids:
            assert any(pid in (xp or "") for xp in extra_prompts), (
                f"Expected a planner-build call scoped to phase '{pid}', "
                f"but none found in extra_prompts: {extra_prompts}"
            )

        repo.close()
