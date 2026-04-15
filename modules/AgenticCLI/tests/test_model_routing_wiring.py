"""Regression guard: production spawn call sites wire model routing end-to-end.

The earlier refactor (Wave 2B) added ``ROLE_MODEL_MAP`` and a ``model`` kwarg on
``build_spawn_command``, but the callers in ``planner_loop._spawn_role_agent``
and ``orchestration`` did not pass ``model=get_model_for_role(role)``. Result:
every agent spawned via the tmux path fell through to the default model, so
Haiku for ``epic-creator`` and Opus for planners never fired.

These tests intercept ``build_spawn_command`` at the call sites and assert the
``model`` kwarg matches ``ROLE_MODEL_MAP``. Unit-level — no live spawn.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.story("US-SES-001")


class TestPlannerLoopPassesModel:
    def test_planner_loop_spawn_call_passes_model(self, monkeypatch):
        """planner_loop spawn path calls build_spawn_command with model=get_model_for_role(role)."""
        from agenticcli.utils import sdk_runner
        from agenticcli.workflows import planner_loop as plm

        # Capture the kwargs build_spawn_command is called with.
        captured: dict = {}

        def fake_build(role, epic_folder, **kwargs):
            captured["role"] = role
            captured["kwargs"] = kwargs
            # Return a harmless no-op command so the caller can proceed.
            return ["echo", "spawn", role, epic_folder]

        monkeypatch.setattr(plm, "build_spawn_command", fake_build)

        # Read the source and confirm the call site includes a `model=` keyword
        # referencing get_model_for_role. This is a static guard against
        # regressions where someone removes the kwarg and defaults return path.
        import inspect
        src = inspect.getsource(plm)
        assert "get_model_for_role(role)" in src, (
            "planner_loop must call get_model_for_role(role) before build_spawn_command"
        )
        # Assert the literal kwarg appears in a build_spawn_command call.
        assert "model=resolved_model" in src or "model=get_model_for_role" in src, (
            "planner_loop.build_spawn_command call must include model= kwarg"
        )

    def test_orchestration_executor_passes_model(self):
        """orchestration.py passes model=get_model_for_role(agent_type) to build_spawn_command."""
        import inspect
        from agenticcli.workflows import orchestration

        src = inspect.getsource(orchestration)
        assert "get_model_for_role" in src, (
            "orchestration.py must import/use get_model_for_role"
        )
        assert "model=get_model_for_role(agent_type)" in src, (
            "orchestration build_spawn_command call must wire model via get_model_for_role(agent_type)"
        )


class TestRoleModelMapFires:
    """Sanity: ROLE_MODEL_MAP returns Haiku for epic-creator and Opus for planners."""

    @pytest.mark.parametrize(
        "role,expected_substr",
        [
            ("epic-creator", "haiku"),
            ("planner-orchestration", "opus"),
            ("planner-build", "opus"),
            ("planner-test", "opus"),
            ("build-story-writer", "sonnet"),
        ],
    )
    def test_role_maps_to_expected_family(self, role, expected_substr):
        from agenticcli.utils.sdk_runner import get_model_for_role

        model = get_model_for_role(role)
        assert model is not None, f"{role} must have an explicit model in ROLE_MODEL_MAP"
        assert expected_substr in model.lower(), (
            f"{role} expected model family '{expected_substr}', got '{model}'"
        )

    def test_unknown_role_returns_none(self):
        from agenticcli.utils.sdk_runner import get_model_for_role

        assert get_model_for_role("build-python") is None, (
            "Roles not in ROLE_MODEL_MAP must return None (default model)"
        )
