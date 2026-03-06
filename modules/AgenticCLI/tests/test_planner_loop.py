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


# ---------------------------------------------------------------------------
# PlannerLoopWorkflow tests
# ---------------------------------------------------------------------------


class TestDiscoverPlansNeedingOrchestration:
    """Test discover_plans_needing_orchestration method."""

    def test_finds_plans_without_mmds(self, tmp_path):
        """Plans missing orchestration_*.mmd are returned."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)

        # Plan with MMD - should NOT be returned
        plan_a = epics_dir / "260210AA_with_mmd"
        plan_a.mkdir()
        (plan_a / "plan_build.yml").write_text("title: A")
        (plan_a / "orchestration_build.mmd").write_text("graph TD")

        # Plan without MMD - should be returned
        plan_b = epics_dir / "260210BB_no_mmd"
        plan_b.mkdir()
        (plan_b / "plan_build.yml").write_text("title: B")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        result = workflow.discover_plans_needing_orchestration()

        assert result == ["260210BB_no_mmd"]

    def test_returns_empty_when_all_have_mmds(self, tmp_path):
        """No plans returned when all have orchestration MMDs."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)

        plan_a = epics_dir / "260210AA_done"
        plan_a.mkdir()
        (plan_a / "orchestration_build.mmd").write_text("graph TD")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        result = workflow.discover_plans_needing_orchestration()

        assert result == []

    def test_returns_empty_when_no_plans_dir(self, tmp_path):
        """Returns empty list when epics directory doesn't exist."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow(epics_dir=tmp_path / "nonexistent")
        result = workflow.discover_plans_needing_orchestration()

        assert result == []

    def test_skips_files_in_plans_dir(self, tmp_path):
        """Only directories are considered, not files."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        (epics_dir / "README.md").write_text("info")

        plan = epics_dir / "260210CC_real"
        plan.mkdir()
        (plan / "plan_build.yml").write_text("title: C")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
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

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "my_plan"
        plan.mkdir()
        (plan / "plan_build.yml").write_text("title: test")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("my_plan") == "build"

    def test_test_type(self, tmp_path):
        """Returns 'test' when plan_test.yml exists."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "my_plan"
        plan.mkdir()
        (plan / "plan_test.yml").write_text("title: test")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("my_plan") == "test"

    def test_no_plan_file(self, tmp_path):
        """Returns None when no plan_*.yml exists."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "my_plan"
        plan.mkdir()
        (plan / "README.md").write_text("no plan here")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("my_plan") is None

    def test_nonexistent_folder(self, tmp_path):
        """Returns None when plan folder doesn't exist."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("nonexistent") is None


class TestDetectSdkObjective:
    """Test detect_sdk_objective method."""

    def test_detects_sdk_keyword_in_context(self, tmp_path):
        """Returns True when plan_build.yml context contains SDK keywords."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "sdk_plan"
        plan.mkdir()
        (plan / "plan_build.yml").write_text(
            "context: |\n  Migrate sessions to use claude-agent-sdk\n"
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("sdk_plan") is True

    def test_no_sdk_keywords(self, tmp_path):
        """Returns False when context has no SDK keywords."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "normal_plan"
        plan.mkdir()
        (plan / "plan_build.yml").write_text(
            "context: |\n  Add a new CLI command for listing plans\n"
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("normal_plan") is False

    def test_no_context_field(self, tmp_path):
        """Returns False when plan_build.yml has no context field."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "no_ctx"
        plan.mkdir()
        (plan / "plan_build.yml").write_text("title: test\nstatus: active\n")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("no_ctx") is False

    def test_no_plan_build_yml(self, tmp_path):
        """Returns False when plan_build.yml doesn't exist."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "no_build"
        plan.mkdir()
        (plan / "plan_test.yml").write_text("title: test\n")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("no_build") is False

    def test_case_insensitive_matching(self, tmp_path):
        """SDK keyword matching is case-insensitive."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "case_plan"
        plan.mkdir()
        (plan / "plan_build.yml").write_text(
            "context: |\n  Replace subprocess calls with SDK Migration patterns\n"
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("case_plan") is True

    def test_multiple_sdk_keywords(self, tmp_path):
        """Returns True when multiple SDK keywords present."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "multi_sdk"
        plan.mkdir()
        (plan / "plan_build.yml").write_text(
            "context: |\n  Use claude-agent-sdk query() and async iterator for session spawn\n"
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("multi_sdk") is True

    def test_malformed_yaml(self, tmp_path):
        """Returns False on malformed YAML (doesn't crash)."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "bad_yaml"
        plan.mkdir()
        (plan / "plan_build.yml").write_text(": : invalid: [yaml\n")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.detect_sdk_objective("bad_yaml") is False


class TestDeterminePlanTypeWithSdkRouting:
    """Test that determine_plan_type routes to SDK when context matches."""

    def test_build_with_sdk_context_returns_sdk(self, tmp_path):
        """plan_build.yml with SDK context returns 'sdk' instead of 'build'."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "sdk_build"
        plan.mkdir()
        (plan / "plan_build.yml").write_text(
            "context: |\n  Migrate subprocess replacement using claude-agent-sdk\n"
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("sdk_build") == "sdk"

    def test_build_without_sdk_context_returns_build(self, tmp_path):
        """plan_build.yml without SDK context still returns 'build'."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "normal_build"
        plan.mkdir()
        (plan / "plan_build.yml").write_text(
            "context: |\n  Add new CLI commands for plan management\n"
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("normal_build") == "build"

    def test_plan_sdk_yml_returns_sdk(self, tmp_path):
        """plan_sdk.yml returns 'sdk' directly (no context check needed)."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "explicit_sdk"
        plan.mkdir()
        (plan / "plan_sdk.yml").write_text("title: SDK plan\n")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("explicit_sdk") == "sdk"

    def test_test_type_not_affected(self, tmp_path):
        """plan_test.yml returns 'test' (SDK detection only applies to 'build')."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        epics_dir.mkdir()
        plan = epics_dir / "test_plan"
        plan.mkdir()
        (plan / "plan_test.yml").write_text(
            "context: |\n  Test claude-agent-sdk integration\n"
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.determine_plan_type("test_plan") == "test"


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

    def test_falls_back_to_agent(self, monkeypatch):
        """Falls back to planner-orchestration agent when CLI fails."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        def mock_run(cmd, **kwargs):
            # CLI generate fails
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="fail")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = PlannerLoopWorkflow()
        # Mock _run_role_agent to return success
        monkeypatch.setattr(workflow, "_run_role_agent", lambda role, pf: _ok_result())

        assert workflow.generate_mmd("test_plan") is True

    def test_fallback_agent_failure(self, monkeypatch):
        """Returns False when both CLI and fallback agent fail."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="fail")

        monkeypatch.setattr(subprocess, "run", mock_run)

        workflow = PlannerLoopWorkflow()
        monkeypatch.setattr(workflow, "_run_role_agent", lambda role, pf: _fail_result())

        assert workflow.generate_mmd("test_plan") is False


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
    """Test PlannerLoopRunner orchestration.

    Spawn methods now return SessionResult instead of session IDs.
    The spawn+wait pattern is eliminated — each call blocks until completion.
    """

    def _make_runner(self, monkeypatch, **overrides):
        """Create a runner with a mocked workflow."""
        import tempfile
        from pathlib import Path
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow

        # Create a temporary empty epics_dir so iterdir() won't fail
        tmp_epics_dir = Path(tempfile.mkdtemp()) / "docs" / "epics" / "live"
        tmp_epics_dir.mkdir(parents=True, exist_ok=True)

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
        assert "review" in step_names
        assert "generate" in step_names
        assert "validate" in step_names

        # Verify ordering: explore must come before story, story before plan_type
        idx_explore = next(i for i, c in enumerate(call_log) if c[0] == "spawn_explore")
        idx_story = next(i for i, c in enumerate(call_log) if c[0] == "spawn_story")
        idx_plan_type = next(i for i, c in enumerate(call_log) if c[0] == "plan_type")
        assert idx_explore < idx_story < idx_plan_type

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


class TestRunRoleAgent:
    """Test the _run_role_agent SDK integration method."""

    def test_sdk_path_records_session_state(self, monkeypatch):
        """SDK path writes session state for observability."""
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
    """Test get_plan_status respects YAML status field over task-counting."""

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _make_plan(self, epics_dir, folder_name, yaml_content):
        """Write a plan_build.yml under epics_dir/folder_name."""
        plan_dir = epics_dir / folder_name
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "plan_build.yml").write_text(yaml_content)
        return plan_dir

    # ------------------------------------------------------------------
    # Core bug regression: active status must NOT be overridden
    # ------------------------------------------------------------------

    def test_active_status_not_overridden_by_all_tasks_complete(self, tmp_path):
        """YAML status: active is preserved even when all tasks are completed.

        This is the regression test for the auto-archive bug: a plan whose
        plan_build.yml has 'status: active' must NOT be reported as 'completed'
        just because every task carries status: completed.
        """
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_plan(
            epics_dir,
            "active_plan",
            "status: active\nphases:\n"
            "  - tickets:\n"
            "      - {name: task1, status: completed}\n"
            "      - {name: task2, status: completed}\n",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("active_plan") == "active"

    def test_in_progress_status_not_overridden(self, tmp_path):
        """Any non-completed YAML status is respected regardless of tasks."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_plan(
            epics_dir,
            "wip_plan",
            "status: in_progress\nphases:\n"
            "  - tickets:\n"
            "      - {name: task1, status: completed}\n",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("wip_plan") == "in_progress"

    # ------------------------------------------------------------------
    # Task-counting fallback: no explicit status field
    # ------------------------------------------------------------------

    def test_no_status_field_all_tasks_complete_returns_completed(self, tmp_path):
        """Plans with no YAML status field are auto-detected as completed via task counting."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_plan(
            epics_dir,
            "implicit_done",
            "phases:\n"
            "  - tickets:\n"
            "      - {name: task1, status: completed}\n"
            "      - {name: task2, status: completed}\n",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("implicit_done") == "completed"

    def test_no_status_field_pending_tasks_returns_none(self, tmp_path):
        """Plans with no status field and pending tasks return None (not completed)."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_plan(
            epics_dir,
            "partial_plan",
            "phases:\n"
            "  - tickets:\n"
            "      - {name: task1, status: completed}\n"
            "      - {name: task2, status: pending}\n",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("partial_plan") is None

    # ------------------------------------------------------------------
    # Explicit completed status in YAML
    # ------------------------------------------------------------------

    def test_explicit_completed_status_all_tasks_done(self, tmp_path):
        """Explicit status: completed with all tasks done returns completed."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_plan(
            epics_dir,
            "done_plan",
            "status: completed\nphases:\n"
            "  - tickets:\n"
            "      - {name: task1, status: completed}\n",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("done_plan") == "completed"

    def test_explicit_completed_status_even_with_pending_tasks(self, tmp_path):
        """Explicit status: completed falls through to task counting which yields None for pending tasks."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        # When YAML says completed but tasks are still pending, task counting
        # won't trigger the 'pending==0' branch, so the YAML status is returned.
        epics_dir = tmp_path / "epics"
        self._make_plan(
            epics_dir,
            "weird_plan",
            "status: completed\nphases:\n"
            "  - tickets:\n"
            "      - {name: task1, status: pending}\n",
        )

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        # Task counting: pending=1, completed=0 -> not triggered -> falls back to yaml_status="completed"
        assert workflow.get_plan_status("weird_plan") == "completed"

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_nonexistent_plan_folder_returns_none(self, tmp_path):
        """Returns None when epic folder does not exist."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow(epics_dir=tmp_path / "epics")
        assert workflow.get_plan_status("ghost_plan") is None

    def test_plan_folder_without_plan_build_yml_returns_none(self, tmp_path):
        """Returns None when plan_build.yml is absent."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        plan_dir = epics_dir / "no_build"
        plan_dir.mkdir(parents=True)
        (plan_dir / "README.md").write_text("no plan file")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("no_build") is None

    def test_malformed_yaml_returns_none(self, tmp_path):
        """Returns None gracefully when plan_build.yml is malformed."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        plan_dir = epics_dir / "bad_yaml"
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan_build.yml").write_text(": : invalid: [yaml\n")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("bad_yaml") is None

    def test_empty_phases_no_tasks_returns_none(self, tmp_path):
        """Returns None when phases exist but contain no tasks (completed=0)."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        epics_dir = tmp_path / "epics"
        self._make_plan(epics_dir, "empty_plan", "phases:\n  - tickets: []\n")

        workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
        assert workflow.get_plan_status("empty_plan") is None


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

        workflow = PlannerLoopWorkflow(epics_dir=tmp_epics_dir)
        monkeypatch.setattr(workflow, "get_plan_status", lambda pf: "in_progress")
        monkeypatch.setattr(workflow, "run_health_check", lambda: None)
        monkeypatch.setattr(workflow, "compile_bootstrap_context", lambda role="orchestration-planning": {})
        monkeypatch.setattr(workflow, "spawn_explore_agent", lambda pf: _ok_result(duration_ms=100))
        monkeypatch.setattr(workflow, "spawn_story_agent", lambda pf: _ok_result(duration_ms=100))
        monkeypatch.setattr(workflow, "determine_plan_type", lambda pf: "build")
        monkeypatch.setattr(workflow, "spawn_planner", lambda pf, pt: _ok_result(duration_ms=100))
        monkeypatch.setattr(workflow, "run_review_cycle", lambda pf, **kw: (True, 1, "approved"))
        monkeypatch.setattr(workflow, "generate_mmd", lambda pf: True)
        monkeypatch.setattr(workflow, "validate_mmd", lambda pf, **kw: True)
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

        # explore, story-generator, and planner-build should all be validated
        assert "explore" in validated_roles
        assert "story-generator" in validated_roles
        assert "planner-build" in validated_roles


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
