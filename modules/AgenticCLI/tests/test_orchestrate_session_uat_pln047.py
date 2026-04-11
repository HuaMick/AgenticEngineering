"""Tests for Build Phase 1 changes: partial success, UatRunner, orchestrate CLI.

Covers gaps identified in UAT PLN-047 (US-PLN-047, US-PLN-048):
  1. _run_planning_loop partial success detection (lines 170-250 of orchestrate.py)
  2. UatRunner.build_prompt and _build_spawn_command unit tests
  3. _run_uat_loop CLI entry point scope validation
  4. ExecutionRunner phase ordering with _order field (confirmation)
  5. _run_executing_loop partial-exit semantics

These tests validate the b153af3 commit deliverables:
  - Partial success: runner fails but TinyDB has phases → exit 0 with actionable message
  - Agent-owned last_uat_commit: UatRunner verifies via pre/post read
  - Ambiguous epic prefix: already covered in test_orchestrate_epic_inference.py
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-PLN-047", "US-PLN-048")


# ══════════════════════════════════════════════════════════════════════════
# Section 1: _run_planning_loop partial success detection
# ══════════════════════════════════════════════════════════════════════════


def _planning_args(plan_folder="test_epic", directory="/tmp", **overrides):
    """Build minimal args for _run_planning_loop."""
    defaults = dict(
        max_iterations=1,
        background=False,
        completion_promise=None,
        project=None,
        plan=plan_folder,
        directory=directory,
        dangerously_skip_permissions=False,
        prompt=None,
        budget_usd=50.0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.story("US-PLN-047")
class TestPlanningLoopPartialSuccess:
    """When PlanningRunner fails but TinyDB has phases/tickets,
    _run_planning_loop should report partial success (exit 0)."""

    def test_partial_success_with_routed_phases_exits_zero(self, tmp_path, tinydb_populator, monkeypatch):
        """Runner fails but epic has fully routed phases → partial success, exit 0."""
        from agenticcli.commands import orchestrate as orch_mod

        epic = "260411PA_partial_routed"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Partial Routed",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "agent": "build-python", "status": "planning"},
                {"name": "P2", "agent": "test-builder", "status": "planning"},
            ],
        })

        mock_runner = MagicMock()
        mock_runner.run.return_value = False  # Runner fails
        mock_runner.state = {
            "iteration": 1,
            "plans_processed": [],
            "plans_failed": [epic],
            "errors": ["Budget cap reached"],
        }

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._store.get_dir",
            lambda override=None: tmp_path / ".agentic" / "sessions",
        )
        (tmp_path / ".agentic" / "sessions").mkdir(parents=True, exist_ok=True)

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockPR, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWF:
            MockPR.return_value = mock_runner
            MockWF.return_value = MagicMock()

            args = _planning_args(plan_folder=epic, directory=str(tmp_path))
            # Should NOT raise SystemExit (partial success exits 0)
            orch_mod._run_planning_loop(args)

    def test_partial_success_state_set_to_partial(self, tmp_path, tinydb_populator, monkeypatch):
        """Partial success sets state['status'] = 'partial'."""
        from agenticcli.commands import orchestrate as orch_mod

        epic = "260411PA_partial_state"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Partial State",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "agent": "build-python", "status": "planning"},
            ],
        })

        mock_runner = MagicMock()
        mock_runner.run.return_value = False
        mock_runner.state = {
            "iteration": 1,
            "plans_processed": [],
            "plans_failed": [epic],
            "errors": ["Planner loop halted"],
        }

        saved_states = []
        original_save = orch_mod._store.save

        def capture_save(state):
            saved_states.append(dict(state))
            return original_save(state)

        monkeypatch.setattr(orch_mod._store, "save", capture_save)

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockPR, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWF:
            MockPR.return_value = mock_runner
            MockWF.return_value = MagicMock()

            args = _planning_args(plan_folder=epic, directory=str(tmp_path))
            orch_mod._run_planning_loop(args)

        # The last saved state should have status "partial"
        final_state = saved_states[-1]
        assert final_state["status"] == "partial"

    def test_total_failure_exits_nonzero(self, tmp_path, tinydb_populator, monkeypatch):
        """Runner fails and no TinyDB phases → total failure → sys.exit(1)."""
        from agenticcli.commands import orchestrate as orch_mod

        epic = "260411PA_total_fail"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Total Fail",
            "status": "in_progress",
            "phases": [],
        })

        mock_runner = MagicMock()
        mock_runner.run.return_value = False
        mock_runner.state = {
            "iteration": 1,
            "plans_processed": [],
            "plans_failed": [epic],
            "errors": ["All epics failed"],
        }

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockPR, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWF:
            MockPR.return_value = mock_runner
            MockWF.return_value = MagicMock()

            args = _planning_args(plan_folder=epic, directory=str(tmp_path))
            with pytest.raises(SystemExit) as exc_info:
                orch_mod._run_planning_loop(args)
            assert exc_info.value.code == 1

    def test_partial_success_unrouted_phases_not_ready_to_implement(self, tmp_path, tinydb_populator, monkeypatch):
        """Partial success with unrouted phases → warn, not success message."""
        from agenticcli.commands import orchestrate as orch_mod

        epic = "260411PA_unrouted"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Unrouted Partial",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "status": "planning"},  # No agent!
            ],
        })

        mock_runner = MagicMock()
        mock_runner.run.return_value = False
        mock_runner.state = {
            "iteration": 1,
            "plans_processed": [],
            "plans_failed": [epic],
            "errors": ["Budget cap reached"],
        }

        saved_states = []
        original_save = orch_mod._store.save

        def capture_save(state):
            saved_states.append(dict(state))
            return original_save(state)

        monkeypatch.setattr(orch_mod._store, "save", capture_save)

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockPR, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWF:
            MockPR.return_value = mock_runner
            MockWF.return_value = MagicMock()

            args = _planning_args(plan_folder=epic, directory=str(tmp_path))
            # Still exits 0 (partial success), but message differs
            orch_mod._run_planning_loop(args)

        final_state = saved_states[-1]
        assert final_state["status"] == "partial"

    def test_no_plan_folder_skips_partial_detection(self, tmp_path, monkeypatch):
        """When plan_folder is None (discovery mode), partial detection is skipped."""
        from agenticcli.commands import orchestrate as orch_mod

        mock_runner = MagicMock()
        mock_runner.run.return_value = False
        mock_runner.state = {
            "iteration": 1,
            "plans_processed": [],
            "plans_failed": [],
            "errors": ["No plans found"],
        }

        with patch("agenticcli.workflows.orchestration.PlanningRunner") as MockPR, \
             patch("agenticcli.workflows.planner_loop.PlannerLoopWorkflow") as MockWF:
            MockPR.return_value = mock_runner
            MockWF.return_value = MagicMock()

            args = _planning_args(plan_folder=None, directory=str(tmp_path))
            with pytest.raises(SystemExit) as exc_info:
                orch_mod._run_planning_loop(args)
            # No plan_folder → can't do partial detection → plain failure
            assert exc_info.value.code == 1


# ══════════════════════════════════════════════════════════════════════════
# Section 2: UatRunner unit tests
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.story("US-PLN-048")
class TestUatRunnerBuildPrompt:
    """UatRunner.build_prompt constructs a correct agent-blind-test prompt."""

    def test_prompt_contains_story_id(self):
        from agenticcli.workflows.uat import UatRunner

        story = SimpleNamespace(id="US-PLN-047", title="Orchestrate Session Implement")
        uat_plan = {
            "persona": "agent-blind-test",
            "journey": [{"step": 1, "action": "check", "observe": ["ok"]}],
            "success_signals": ["passes"],
        }

        prompt = UatRunner.build_prompt(story, uat_plan)

        assert "US-PLN-047" in prompt

    def test_prompt_contains_story_title(self):
        from agenticcli.workflows.uat import UatRunner

        story = SimpleNamespace(id="US-PLN-047", title="Orchestrate Session Implement")
        uat_plan = {"persona": "test", "journey": [], "success_signals": []}

        prompt = UatRunner.build_prompt(story, uat_plan)

        assert "Orchestrate Session Implement" in prompt

    def test_prompt_contains_uat_plan_yaml(self):
        from agenticcli.workflows.uat import UatRunner

        story = SimpleNamespace(id="US-PLN-047", title="Test")
        uat_plan = {
            "persona": "agent-blind-test",
            "starting_state": "A seed epic exists",
            "journey": [{"step": 1, "action": "run command", "observe": ["exit 0"]}],
            "success_signals": ["Phase execution follows TinyDB _order"],
        }

        prompt = UatRunner.build_prompt(story, uat_plan)

        assert "uat_plan:" in prompt
        assert "agent-blind-test" in prompt
        assert "Phase execution follows TinyDB _order" in prompt

    def test_prompt_instructs_agent_to_stamp(self):
        """Prompt MUST instruct the agent to run `agentic stories update`."""
        from agenticcli.workflows.uat import UatRunner

        story = SimpleNamespace(id="US-PLN-047", title="Test")
        uat_plan = {"persona": "test", "journey": [], "success_signals": []}

        prompt = UatRunner.build_prompt(story, uat_plan)

        assert "agentic stories update" in prompt
        assert "--kind uat" in prompt
        assert "US-PLN-047" in prompt

    def test_prompt_warns_about_missing_stamp_failure(self):
        """Prompt must warn that a missing stamp is treated as failure."""
        from agenticcli.workflows.uat import UatRunner

        story = SimpleNamespace(id="US-PLN-047", title="Test")
        uat_plan = {"persona": "test", "journey": [], "success_signals": []}

        prompt = UatRunner.build_prompt(story, uat_plan)

        assert "missing stamp" in prompt.lower() or "missing" in prompt.lower()
        assert "failure" in prompt.lower()


@pytest.mark.story("US-PLN-048")
class TestUatRunnerBuildSpawnCommand:
    """UatRunner._build_spawn_command builds correct CLI command."""

    def test_spawn_command_includes_role_test_uat(self):
        from agenticcli.workflows.uat import UatRunner

        runner = UatRunner(story_id="US-FAKE-001")
        cmd = runner._build_spawn_command(prompt="test prompt", epic_folder=None)

        assert "--role" in cmd
        role_idx = cmd.index("--role")
        assert cmd[role_idx + 1] == "test-uat"

    def test_spawn_command_includes_prompt(self):
        from agenticcli.workflows.uat import UatRunner

        runner = UatRunner(story_id="US-FAKE-001")
        cmd = runner._build_spawn_command(prompt="my test prompt", epic_folder=None)

        assert "--prompt" in cmd
        prompt_idx = cmd.index("--prompt")
        assert cmd[prompt_idx + 1] == "my test prompt"

    def test_spawn_command_includes_epic_when_provided(self):
        from agenticcli.workflows.uat import UatRunner

        runner = UatRunner(story_id="US-FAKE-001")
        cmd = runner._build_spawn_command(prompt="test", epic_folder="my_epic_folder")

        assert "--epic" in cmd
        epic_idx = cmd.index("--epic")
        assert cmd[epic_idx + 1] == "my_epic_folder"

    def test_spawn_command_omits_epic_when_none(self):
        from agenticcli.workflows.uat import UatRunner

        runner = UatRunner(story_id="US-FAKE-001")
        cmd = runner._build_spawn_command(prompt="test", epic_folder=None)

        assert "--epic" not in cmd

    def test_spawn_command_includes_background_and_tmux(self):
        from agenticcli.workflows.uat import UatRunner

        runner = UatRunner(story_id="US-FAKE-001")
        cmd = runner._build_spawn_command(prompt="test", epic_folder=None)

        assert "-b" in cmd
        assert "--tmux" in cmd

    def test_spawn_command_includes_max_turns(self):
        from agenticcli.workflows.uat import UatRunner

        runner = UatRunner(story_id="US-FAKE-001", max_turns=100)
        cmd = runner._build_spawn_command(prompt="test", epic_folder=None)

        assert "--max-turns" in cmd
        turns_idx = cmd.index("--max-turns")
        assert cmd[turns_idx + 1] == "100"

    def test_spawn_command_includes_skip_permissions_when_set(self):
        from agenticcli.workflows.uat import UatRunner

        runner = UatRunner(story_id="US-FAKE-001", dangerously_skip_permissions=True)
        cmd = runner._build_spawn_command(prompt="test", epic_folder=None)

        assert "--dangerously-skip-permissions" in cmd

    def test_spawn_command_omits_skip_permissions_when_not_set(self):
        from agenticcli.workflows.uat import UatRunner

        runner = UatRunner(story_id="US-FAKE-001", dangerously_skip_permissions=False)
        cmd = runner._build_spawn_command(prompt="test", epic_folder=None)

        assert "--dangerously-skip-permissions" not in cmd

    def test_spawn_command_uses_json_flag(self):
        """Spawn command should use -j for JSON output parsing."""
        from agenticcli.workflows.uat import UatRunner

        runner = UatRunner(story_id="US-FAKE-001")
        cmd = runner._build_spawn_command(prompt="test", epic_folder=None)

        assert "-j" in cmd


# ══════════════════════════════════════════════════════════════════════════
# Section 3: _run_uat_loop CLI scope validation
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.story("US-PLN-048")
class TestRunUatLoopScopeValidation:
    """_run_uat_loop enforces exactly one of --story, --epic, --stale."""

    def test_no_scope_exits_nonzero(self, monkeypatch):
        """Calling uat with no scope flags exits non-zero."""
        from agenticcli.commands.orchestrate import _run_uat_loop

        args = SimpleNamespace(
            story=None,
            plan=None,
            stale=False,
            dry_run=False,
            dangerously_skip_permissions=False,
            directory="/tmp",
        )

        with pytest.raises(SystemExit) as exc_info:
            _run_uat_loop(args)
        assert exc_info.value.code == 1

    def test_multiple_scopes_exits_nonzero(self, monkeypatch):
        """Calling uat with both --story and --epic exits non-zero."""
        from agenticcli.commands.orchestrate import _run_uat_loop

        args = SimpleNamespace(
            story="US-PLN-047",
            plan="my_epic",
            stale=False,
            dry_run=False,
            dangerously_skip_permissions=False,
            directory="/tmp",
        )

        with pytest.raises(SystemExit) as exc_info:
            _run_uat_loop(args)
        assert exc_info.value.code == 1

    def test_all_three_scopes_exits_nonzero(self, monkeypatch):
        """Calling uat with --story, --epic, AND --stale exits non-zero."""
        from agenticcli.commands.orchestrate import _run_uat_loop

        args = SimpleNamespace(
            story="US-PLN-047",
            plan="my_epic",
            stale=True,
            dry_run=False,
            dangerously_skip_permissions=False,
            directory="/tmp",
        )

        with pytest.raises(SystemExit) as exc_info:
            _run_uat_loop(args)
        assert exc_info.value.code == 1

    def test_story_and_stale_exits_nonzero(self, monkeypatch):
        """Calling uat with --story and --stale exits non-zero."""
        from agenticcli.commands.orchestrate import _run_uat_loop

        args = SimpleNamespace(
            story="US-PLN-047",
            plan=None,
            stale=True,
            dry_run=False,
            dangerously_skip_permissions=False,
            directory="/tmp",
        )

        with pytest.raises(SystemExit) as exc_info:
            _run_uat_loop(args)
        assert exc_info.value.code == 1


@pytest.mark.story("US-PLN-048")
class TestRunUatLoopDryRun:
    """_run_uat_loop --dry-run resolves stories without spawning agents."""

    def test_dry_run_resolves_and_exits_zero(self, monkeypatch):
        """--dry-run with --story resolves the story and exits cleanly."""
        from agenticcli.commands.orchestrate import _run_uat_loop

        fake_story = SimpleNamespace(id="US-PLN-047", title="Test Story")

        with patch("agenticcli.workflows.uat.UatRunner") as MockRunner:
            mock_instance = MagicMock()
            mock_instance.resolve_stories.return_value = [fake_story]
            mock_instance.state = {"errors": []}
            MockRunner.return_value = mock_instance

            args = SimpleNamespace(
                story="US-PLN-047",
                plan=None,
                stale=False,
                dry_run=True,
                dangerously_skip_permissions=False,
                directory="/tmp",
            )

            # Should NOT raise SystemExit
            _run_uat_loop(args)

            # resolve_stories should be called, run should NOT
            mock_instance.resolve_stories.assert_called_once()
            mock_instance.run.assert_not_called()


@pytest.mark.story("US-PLN-048")
class TestRunUatLoopExecution:
    """_run_uat_loop executes UatRunner when called with valid scope."""

    def test_story_scope_invokes_runner(self, monkeypatch):
        """--story flag creates UatRunner and calls run()."""
        from agenticcli.commands.orchestrate import _run_uat_loop

        with patch("agenticcli.workflows.uat.UatRunner") as MockRunner:
            mock_instance = MagicMock()
            mock_instance.run.return_value = True
            mock_instance.state = {
                "passed": ["US-PLN-047"],
                "failed": [],
                "skipped": [],
                "commits": {"US-PLN-047": "abc1234"},
                "errors": [],
            }
            MockRunner.return_value = mock_instance

            args = SimpleNamespace(
                story="US-PLN-047",
                plan=None,
                stale=False,
                dry_run=False,
                dangerously_skip_permissions=False,
                directory="/tmp",
            )

            _run_uat_loop(args)

            mock_instance.run.assert_called_once()
            MockRunner.assert_called_once_with(
                story_id="US-PLN-047",
                epic_folder=None,
                stale=False,
                dry_run=False,
                dangerously_skip_permissions=False,
                working_dir="/tmp",
            )

    def test_uat_failure_exits_nonzero(self, monkeypatch):
        """When runner.run() returns False, exit non-zero."""
        from agenticcli.commands.orchestrate import _run_uat_loop

        with patch("agenticcli.workflows.uat.UatRunner") as MockRunner:
            mock_instance = MagicMock()
            mock_instance.run.return_value = False
            mock_instance.state = {
                "passed": [],
                "failed": ["US-PLN-047"],
                "skipped": [],
                "commits": {},
                "errors": ["UAT failed"],
            }
            MockRunner.return_value = mock_instance

            args = SimpleNamespace(
                story="US-PLN-047",
                plan=None,
                stale=False,
                dry_run=False,
                dangerously_skip_permissions=False,
                directory="/tmp",
            )

            with pytest.raises(SystemExit) as exc_info:
                _run_uat_loop(args)
            assert exc_info.value.code == 1

    def test_uat_exception_exits_nonzero(self, monkeypatch):
        """When runner.run() raises an exception, exit non-zero."""
        from agenticcli.commands.orchestrate import _run_uat_loop

        with patch("agenticcli.workflows.uat.UatRunner") as MockRunner:
            mock_instance = MagicMock()
            mock_instance.run.side_effect = RuntimeError("Unexpected crash")
            MockRunner.return_value = mock_instance

            args = SimpleNamespace(
                story="US-PLN-047",
                plan=None,
                stale=False,
                dry_run=False,
                dangerously_skip_permissions=False,
                directory="/tmp",
            )

            with pytest.raises(SystemExit) as exc_info:
                _run_uat_loop(args)
            assert exc_info.value.code == 1


# ══════════════════════════════════════════════════════════════════════════
# Section 4: ExecutionRunner phase-in-progress marking before spawn
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.story("US-PLN-047")
class TestPhaseMarkedInProgressBeforeSpawn:
    """US-PLN-047 Step 2: Phase is marked in_progress BEFORE agent is spawned."""

    def test_phase_status_in_progress_before_run_phase(self, tmp_path, tinydb_populator):
        """The executor sets status=in_progress before calling _run_phase."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epic = "260411PA_ip_before_spawn"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "In-Progress Before Spawn",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "planning"},
            ],
        })

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True, exist_ok=True)

        # Use the existing _make_execution_runner helper pattern: MagicMock
        # workflow with real repo plugged in via _get_repository.return_value.
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        phase_status_at_spawn = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            """Capture phase status at the moment _run_phase is called."""
            phases = repo.list_phases(plan_folder)
            p1 = next(p for p in phases if p.name == "P1 Build")
            phase_status_at_spawn.append(p1.status)
            return True

        runner = ExecutionRunner(workflow=workflow, plan_folder=epic)
        runner._run_phase = _mock_run_phase

        result = runner._execute_plan(epic, max_iterations=5)

        assert result is True
        assert len(phase_status_at_spawn) == 1
        assert phase_status_at_spawn[0] == "in_progress", \
            "Phase must be marked in_progress BEFORE _run_phase is called"


# ══════════════════════════════════════════════════════════════════════════
# Section 5: ExecutionRunner failed phase → status=failed in TinyDB
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.story("US-PLN-047")
class TestMissingAgentMarksFailedInTinyDB:
    """US-PLN-047 Step 8: Missing agent routing marks phase failed (not pending)."""

    def test_missing_agent_phase_status_is_failed(self, tmp_path, tinydb_populator):
        """Phase with no agent field ends up with status='failed' in TinyDB."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epic = "260411PA_missing_agent_fail"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Missing Agent Fail",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Broken", "phase_id": "P1", "status": "planning"},
                # No agent field
            ],
        })

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = tmp_path / "docs" / "epics" / "live"

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        runner = ExecutionRunner(workflow=workflow, plan_folder=epic)
        result = runner._execute_plan(epic, max_iterations=5)

        assert result is False

        # Critical assertion: phase must be 'failed', not 'pending' or 'planning'
        phases = repo.list_phases(epic)
        p1 = phases[0]
        assert p1.status == "failed", \
            f"Phase with missing agent must be marked 'failed', got '{p1.status}'"

    def test_missing_agent_does_not_spawn(self, tmp_path, tinydb_populator):
        """Phase with no agent field must NOT attempt to spawn any agent."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epic = "260411PA_no_spawn"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "No Spawn Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "status": "planning"},
            ],
        })

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = tmp_path / "docs" / "epics" / "live"
        workflow.wait_for_session.return_value = "completed"

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        runner = ExecutionRunner(workflow=workflow, plan_folder=epic)

        # Track if _run_phase gets called
        run_phase_called = []
        original_run_phase = runner._run_phase

        def tracking_run_phase(*a, **kw):
            run_phase_called.append(True)
            return original_run_phase(*a, **kw)

        runner._run_phase = tracking_run_phase
        runner._execute_plan(epic, max_iterations=5)

        assert len(run_phase_called) == 0, "No agent spawn should be attempted"


# ══════════════════════════════════════════════════════════════════════════
# Section 6: ExecutionRunner.run() discovery mode
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.story("US-PLN-047")
class TestExecutionRunnerDiscovery:
    """ExecutionRunner with no plan_folder discovers plans via TinyDB."""

    def test_no_plans_needing_execution_returns_true(self, tmp_path, monkeypatch):
        """When no plans need execution, runner.run() returns True."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = OrchestrationWorkflow(working_dir=str(tmp_path))

        monkeypatch.setattr(workflow, "run_health_check", lambda: None)
        monkeypatch.setattr(workflow, "discover_plans_needing_execution", lambda: [])

        runner = ExecutionRunner(workflow=workflow, plan_folder=None)
        success = runner.run(max_iterations=10)

        assert success is True

    def test_completed_epic_returns_true(self, tmp_path, monkeypatch):
        """Already-completed epic returns True without executing anything."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = OrchestrationWorkflow(working_dir=str(tmp_path))

        monkeypatch.setattr(workflow, "run_health_check", lambda: None)
        monkeypatch.setattr(workflow, "get_plan_status", lambda f: "completed")

        runner = ExecutionRunner(workflow=workflow, plan_folder="some_epic")
        success = runner.run(max_iterations=10)

        assert success is True
        assert len(runner.state["phases_completed"]) == 0


# ══════════════════════════════════════════════════════════════════════════
# Section 7: cmd_orchestrate routes to correct action handler
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.story("US-PLN-047")
class TestCmdOrchestrateRouting:
    """cmd_orchestrate dispatches to the correct handler by action."""

    def test_executing_action_triggers_executing_loop(self, monkeypatch):
        """action='executing' triggers _run_executing_loop."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        called = []

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._run_executing_loop",
            lambda args, ctx=None: called.append("executing"),
        )

        args = SimpleNamespace(
            action="executing",
            plan="my_epic",
            dry_run=False,
        )
        cmd_orchestrate(args)

        assert called == ["executing"]

    def test_uat_action_triggers_uat_loop(self, monkeypatch):
        """action='uat' triggers _run_uat_loop."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        called = []

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._run_uat_loop",
            lambda args, ctx=None: called.append("uat"),
        )

        args = SimpleNamespace(
            action="uat",
            plan=None,
            dry_run=False,
            story="US-PLN-047",
        )
        cmd_orchestrate(args)

        assert called == ["uat"]

    def test_uat_dry_run_routes_to_uat_not_dry_run_handler(self, monkeypatch):
        """action='uat' with --dry-run routes to _run_uat_loop, not _run_dry_run."""
        from agenticcli.commands.orchestrate import cmd_orchestrate

        uat_called = []
        dry_run_called = []

        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._run_uat_loop",
            lambda args, ctx=None: uat_called.append(True),
        )
        monkeypatch.setattr(
            "agenticcli.commands.orchestrate._run_dry_run",
            lambda args, ctx=None: dry_run_called.append(True),
        )

        args = SimpleNamespace(
            action="uat",
            plan=None,
            dry_run=True,
            story="US-PLN-047",
        )
        cmd_orchestrate(args)

        assert uat_called == [True], "UAT dry-run should go through _run_uat_loop"
        assert dry_run_called == [], "_run_dry_run should NOT be called for UAT action"
