"""Tests for the planner loop workflow."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# PlannerLoopWorkflow tests
# ---------------------------------------------------------------------------


class TestDiscoverPlansNeedingOrchestration:
    """Test discover_plans_needing_orchestration method."""

    def test_finds_plans_without_mmds(self, tmp_path):
        """Plans missing orchestration_*.mmd are returned."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        plans_dir = tmp_path / "docs" / "plans" / "live"
        plans_dir.mkdir(parents=True)

        # Plan with MMD - should NOT be returned
        plan_a = plans_dir / "260210AA_with_mmd"
        plan_a.mkdir()
        (plan_a / "plan_build.yml").write_text("title: A")
        (plan_a / "orchestration_build.mmd").write_text("graph TD")

        # Plan without MMD - should be returned
        plan_b = plans_dir / "260210BB_no_mmd"
        plan_b.mkdir()
        (plan_b / "plan_build.yml").write_text("title: B")

        workflow = PlannerLoopWorkflow(plans_dir=plans_dir)
        result = workflow.discover_plans_needing_orchestration()

        assert result == ["260210BB_no_mmd"]

    def test_returns_empty_when_all_have_mmds(self, tmp_path):
        """No plans returned when all have orchestration MMDs."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        plans_dir = tmp_path / "docs" / "plans" / "live"
        plans_dir.mkdir(parents=True)

        plan_a = plans_dir / "260210AA_done"
        plan_a.mkdir()
        (plan_a / "orchestration_build.mmd").write_text("graph TD")

        workflow = PlannerLoopWorkflow(plans_dir=plans_dir)
        result = workflow.discover_plans_needing_orchestration()

        assert result == []

    def test_returns_empty_when_no_plans_dir(self, tmp_path):
        """Returns empty list when plans directory doesn't exist."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow(plans_dir=tmp_path / "nonexistent")
        result = workflow.discover_plans_needing_orchestration()

        assert result == []

    def test_skips_files_in_plans_dir(self, tmp_path):
        """Only directories are considered, not files."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        plans_dir = tmp_path / "docs" / "plans" / "live"
        plans_dir.mkdir(parents=True)
        (plans_dir / "README.md").write_text("info")

        plan = plans_dir / "260210CC_real"
        plan.mkdir()
        (plan / "plan_build.yml").write_text("title: C")

        workflow = PlannerLoopWorkflow(plans_dir=plans_dir)
        result = workflow.discover_plans_needing_orchestration()

        assert result == ["260210CC_real"]


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
        """Health check raises when agentic plan list fails."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        def mock_run(cmd, **kwargs):
            if "list" in cmd:
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = PlannerLoopWorkflow()
        with pytest.raises(RuntimeError, match="agentic plan list"):
            workflow.run_health_check()


class TestDeterminePlanType:
    """Test determine_plan_type method."""

    def test_build_type(self, tmp_path):
        """Returns 'build' when plan_build.yml exists."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan = plans_dir / "my_plan"
        plan.mkdir()
        (plan / "plan_build.yml").write_text("title: test")

        workflow = PlannerLoopWorkflow(plans_dir=plans_dir)
        assert workflow.determine_plan_type("my_plan") == "build"

    def test_test_type(self, tmp_path):
        """Returns 'test' when plan_test.yml exists."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan = plans_dir / "my_plan"
        plan.mkdir()
        (plan / "plan_test.yml").write_text("title: test")

        workflow = PlannerLoopWorkflow(plans_dir=plans_dir)
        assert workflow.determine_plan_type("my_plan") == "test"

    def test_no_plan_file(self, tmp_path):
        """Returns None when no plan_*.yml exists."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan = plans_dir / "my_plan"
        plan.mkdir()
        (plan / "README.md").write_text("no plan here")

        workflow = PlannerLoopWorkflow(plans_dir=plans_dir)
        assert workflow.determine_plan_type("my_plan") is None

    def test_nonexistent_folder(self, tmp_path):
        """Returns None when plan folder doesn't exist."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()

        workflow = PlannerLoopWorkflow(plans_dir=plans_dir)
        assert workflow.determine_plan_type("nonexistent") is None


class TestGenerateMmd:
    """Test generate_mmd method."""

    def test_success_via_cli(self, monkeypatch):
        """Returns True when CLI generation succeeds."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = PlannerLoopWorkflow()
        assert workflow.generate_mmd("test_plan") is True

    def test_falls_back_to_spawn(self, monkeypatch):
        """Falls back to planner-orchestration spawn when CLI fails."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        call_count = {"n": 0}

        def mock_run(cmd, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # CLI generate fails
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="fail")
            if "spawn" in cmd:
                # Spawn succeeds
                return subprocess.CompletedProcess(cmd, 0, stdout='{"session_id": "abc"}', stderr="")
            # Session status check - completed
            return subprocess.CompletedProcess(cmd, 0, stdout='{"status": "completed"}', stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = PlannerLoopWorkflow()
        # Mock wait_for_session to return completed
        monkeypatch.setattr(workflow, "wait_for_session", lambda sid, **kw: "completed")

        assert workflow.generate_mmd("test_plan") is True


class TestValidateMmd:
    """Test validate_mmd method."""

    def test_success_first_attempt(self, monkeypatch):
        """Returns True on first successful validation."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout="valid", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = PlannerLoopWorkflow()
        assert workflow.validate_mmd("test_plan") is True

    def test_failure_then_success(self, monkeypatch):
        """Retries and succeeds on second attempt."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        attempts = {"n": 0}

        def mock_run(cmd, **kwargs):
            attempts["n"] += 1
            if attempts["n"] <= 2:
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="invalid")
            return subprocess.CompletedProcess(cmd, 0, stdout="valid", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        # Speed up test by not sleeping
        monkeypatch.setattr("time.sleep", lambda _: None)

        workflow = PlannerLoopWorkflow()
        assert workflow.validate_mmd("test_plan") is True
        assert attempts["n"] == 3

    def test_all_retries_fail(self, monkeypatch):
        """Returns False after max retries exhausted."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="invalid")

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr("time.sleep", lambda _: None)

        workflow = PlannerLoopWorkflow()
        assert workflow.validate_mmd("test_plan", max_retries=3) is False


# ---------------------------------------------------------------------------
# PlannerLoopRunner tests
# ---------------------------------------------------------------------------


class TestPlannerLoopRunner:
    """Test PlannerLoopRunner orchestration."""

    def _make_runner(self, monkeypatch, **overrides):
        """Create a runner with a mocked workflow."""
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow()
        # Default mocks for all workflow methods
        monkeypatch.setattr(workflow, "run_health_check", overrides.get("health_check", lambda: None))
        monkeypatch.setattr(workflow, "compile_bootstrap_context", overrides.get("bootstrap", lambda role="orchestration-planning": {}))
        monkeypatch.setattr(workflow, "discover_plans_needing_orchestration",
                            overrides.get("discover", lambda: []))
        monkeypatch.setattr(workflow, "spawn_explore_agent",
                            overrides.get("spawn_explore", lambda pf: "explore-session-123"))
        monkeypatch.setattr(workflow, "spawn_story_agent",
                            overrides.get("spawn_story", lambda pf: "story-session-123"))
        monkeypatch.setattr(workflow, "discover_stories",
                            overrides.get("stories", lambda pf, project=None: []))
        monkeypatch.setattr(workflow, "determine_plan_type",
                            overrides.get("plan_type", lambda pf: "build"))
        monkeypatch.setattr(workflow, "spawn_planner",
                            overrides.get("spawn_planner", lambda pf, pt: "session-123"))
        monkeypatch.setattr(workflow, "wait_for_session",
                            overrides.get("wait_session", lambda sid, **kw: "completed"))
        monkeypatch.setattr(workflow, "run_review_cycle",
                            overrides.get("review", lambda pf, **kw: (True, 1, "approved")))
        monkeypatch.setattr(workflow, "generate_mmd",
                            overrides.get("generate", lambda pf: True))
        monkeypatch.setattr(workflow, "validate_mmd",
                            overrides.get("validate", lambda pf, **kw: True))

        return PlannerLoopRunner(workflow=workflow)

    def test_completes_when_no_plans(self, monkeypatch, capsys):
        """Runner exits successfully when no plans need work."""
        runner = self._make_runner(monkeypatch)
        result = runner.run(max_iterations=5)

        assert result is True
        assert "Planning complete" in capsys.readouterr().out

    def test_processes_single_plan(self, monkeypatch, capsys):
        """Runner processes a single plan through full workflow including explore and story steps."""
        call_log = []

        def tracking_discover():
            if not call_log or "discover" not in [c[0] for c in call_log]:
                call_log.append(("discover",))
                return ["test_plan"]
            return []

        def tracking_spawn_explore(pf):
            call_log.append(("spawn_explore", pf))
            return "explore-session-abc"

        def tracking_spawn_story(pf):
            call_log.append(("spawn_story", pf))
            return "story-session-abc"

        def tracking_plan_type(pf):
            call_log.append(("plan_type", pf))
            return "build"

        def tracking_spawn(pf, pt):
            call_log.append(("spawn", pf, pt))
            return "session-abc"

        def tracking_wait(sid, **kw):
            call_log.append(("wait", sid))
            return "completed"

        def tracking_review(pf, **kw):
            call_log.append(("review", pf))
            return (True, 1, "approved")

        def tracking_generate(pf):
            call_log.append(("generate", pf))
            return True

        def tracking_validate(pf, **kw):
            call_log.append(("validate", pf))
            return True

        runner = self._make_runner(
            monkeypatch,
            discover=tracking_discover,
            spawn_explore=tracking_spawn_explore,
            spawn_story=tracking_spawn_story,
            plan_type=tracking_plan_type,
            spawn_planner=tracking_spawn,
            wait_session=tracking_wait,
            review=tracking_review,
            generate=tracking_generate,
            validate=tracking_validate,
        )
        result = runner.run(max_iterations=5)

        assert result is True
        # Verify call sequence includes explore and story steps
        step_names = [c[0] for c in call_log]
        assert "discover" in step_names
        assert "spawn_explore" in step_names
        assert "spawn_story" in step_names
        assert "plan_type" in step_names
        assert "spawn" in step_names
        assert "wait" in step_names
        assert "review" in step_names
        assert "generate" in step_names
        assert "validate" in step_names

        # Verify ordering: explore must come before story, story before plan_type
        idx_explore = next(i for i, c in enumerate(call_log) if c[0] == "spawn_explore")
        idx_story = next(i for i, c in enumerate(call_log) if c[0] == "spawn_story")
        idx_plan_type = next(i for i, c in enumerate(call_log) if c[0] == "plan_type")
        assert idx_explore < idx_story < idx_plan_type

    def test_explore_agent_failure_skips_plan(self, monkeypatch):
        """Plan is skipped when explore agent fails to spawn."""
        call_count = {"discover": 0}

        def discover():
            call_count["discover"] += 1
            if call_count["discover"] <= 1:
                return ["bad_explore_plan"]
            return []

        runner = self._make_runner(
            monkeypatch,
            discover=discover,
            spawn_explore=lambda pf: None,  # Explore spawn fails
        )
        result = runner.run(max_iterations=5)

        assert "bad_explore_plan" in runner.state["plans_skipped"]

    def test_story_agent_failure_skips_plan(self, monkeypatch):
        """Plan is skipped when story agent fails to spawn."""
        call_count = {"discover": 0}

        def discover():
            call_count["discover"] += 1
            if call_count["discover"] <= 1:
                return ["bad_story_plan"]
            return []

        runner = self._make_runner(
            monkeypatch,
            discover=discover,
            spawn_story=lambda pf: None,  # Story spawn fails
        )
        result = runner.run(max_iterations=5)

        assert "bad_story_plan" in runner.state["plans_skipped"]

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
        """Runner stops after max_iterations even if plans remain."""
        runner = self._make_runner(
            monkeypatch,
            discover=lambda: ["always_plan"],
        )
        result = runner.run(max_iterations=2)

        assert result is False
        assert runner.state["iteration"] == 2

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
            discover=discover,
            plan_type=lambda pf: None,
        )
        result = runner.run(max_iterations=5)

        assert "no_type_plan" in runner.state["plans_skipped"]
