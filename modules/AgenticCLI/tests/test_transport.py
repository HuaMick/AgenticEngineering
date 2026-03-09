"""Tests for agenticcli.utils.transport module.

Covers:
1. determine_transport() priority logic from transport.py
2. AGENTIC_FORCE_SDK_DIRECT env override in PlannerLoopWorkflow._run_role_agent
"""
import logging
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from agenticcli.utils.transport import (
    SDK_DIRECT,
    SDK_TMUX,
    SUBPROCESS,
    TMUX,
    determine_transport,
)


def test_transport_constants():
    assert SDK_TMUX == "sdk-tmux"
    assert TMUX == "tmux"
    assert SUBPROCESS == "subprocess"
    assert SDK_DIRECT == "sdk"


def test_determine_transport_sdk_tmux(monkeypatch):
    """SDK available + tmux exists + tmux_requested -> sdk-tmux."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/tmux" if name == "tmux" else None)
    result = determine_transport(sdk_available=True, tmux_requested=True)
    assert result == SDK_TMUX


def test_determine_transport_tmux_only(monkeypatch):
    """SDK not available + tmux exists + tmux_requested -> tmux."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/tmux" if name == "tmux" else None)
    result = determine_transport(sdk_available=False, tmux_requested=True)
    assert result == TMUX


def test_determine_transport_subprocess(monkeypatch):
    """SDK not available + no tmux -> subprocess."""
    monkeypatch.setattr(shutil, "which", lambda name: None)
    result = determine_transport(sdk_available=False, tmux_requested=True)
    assert result == SUBPROCESS


def test_determine_transport_sdk_no_tmux(monkeypatch):
    """SDK available + no tmux + tmux_requested -> subprocess."""
    monkeypatch.setattr(shutil, "which", lambda name: None)
    result = determine_transport(sdk_available=True, tmux_requested=True)
    assert result == SUBPROCESS


def test_determine_transport_not_requested(monkeypatch):
    """tmux_requested=False -> subprocess regardless of availability."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/tmux" if name == "tmux" else None)
    result = determine_transport(sdk_available=True, tmux_requested=False)
    assert result == SUBPROCESS


# ---------------------------------------------------------------------------
# AGENTIC_FORCE_SDK_DIRECT override tests (planner_loop._run_role_agent)
# ---------------------------------------------------------------------------

def _ok_result(**kwargs):
    """Create a successful SessionResult for testing."""
    from agenticcli.utils.sdk_runner import SessionResult

    defaults = dict(
        status="completed",
        result="ok",
        cost_usd=0.01,
        duration_ms=5000,
        num_turns=3,
        session_id="sess-transport-test",
    )
    defaults.update(kwargs)
    return SessionResult(**defaults)


def _make_workflow(tmp_path, epic_folder_name="260309XX_transport_test"):
    """Create a minimal PlannerLoopWorkflow for transport routing tests."""
    from agenticcli.workflows.planner_loop import PlannerLoopWorkflow
    from agenticguidance.services.epic_repository import EpicRepository

    epics_dir = tmp_path / "docs" / "epics" / "live"
    epics_dir.mkdir(parents=True, exist_ok=True)
    (epics_dir / epic_folder_name).mkdir(exist_ok=True)

    # Minimal TinyDB setup
    db_path = tmp_path / "test_db.json"
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    repo.create_epic({
        "name": epic_folder_name,
        "status": "active",
    })
    repo.add_phase(epic_folder_name, {"name": "Phase 1"})
    repo.close()

    workflow = PlannerLoopWorkflow(epics_dir=epics_dir)
    return workflow


class TestForceSDKDirectOverride:
    """Test AGENTIC_FORCE_SDK_DIRECT=1 env var forces SDK-direct path."""

    def test_force_sdk_direct_uses_sdk_direct_path(self, tmp_path, monkeypatch):
        """AGENTIC_FORCE_SDK_DIRECT=1 + SDK available -> SDK-direct path."""
        workflow = _make_workflow(tmp_path)
        epic_folder = "260309XX_transport_test"
        called_path = {"path": None}

        def mock_tmux_sdk(session_id, role, epic_folder, prompt, **kw):
            called_path["path"] = "sdk-tmux"
            return _ok_result()

        def mock_sdk_direct(session_id, role, epic_folder, prompt, **kw):
            called_path["path"] = "sdk-direct"
            return _ok_result()

        def mock_subprocess(session_id, role, epic_folder):
            called_path["path"] = "subprocess"
            return _ok_result()

        monkeypatch.setenv("AGENTIC_FORCE_SDK_DIRECT", "1")

        with (
            patch("agenticcli.workflows.planner_loop.SDK_AVAILABLE", True),
            patch("shutil.which", return_value="/usr/bin/tmux"),
            patch.object(workflow, "_run_via_tmux_sdk", side_effect=mock_tmux_sdk),
            patch.object(workflow, "_run_via_sdk", side_effect=mock_sdk_direct),
            patch.object(workflow, "_run_via_subprocess", side_effect=mock_subprocess),
        ):
            workflow._run_role_agent("planner-build", epic_folder)

        assert called_path["path"] == "sdk-direct", (
            f"AGENTIC_FORCE_SDK_DIRECT=1 should force sdk-direct, got: {called_path['path']}"
        )

    def test_force_sdk_direct_emits_warning_log(self, tmp_path, monkeypatch, caplog):
        """AGENTIC_FORCE_SDK_DIRECT=1 emits a warning about zombie bug risk."""
        workflow = _make_workflow(tmp_path)
        epic_folder = "260309XX_transport_test"

        monkeypatch.setenv("AGENTIC_FORCE_SDK_DIRECT", "1")

        with (
            patch("agenticcli.workflows.planner_loop.SDK_AVAILABLE", True),
            patch("shutil.which", return_value="/usr/bin/tmux"),
            patch.object(workflow, "_run_via_sdk", return_value=_ok_result()),
            patch.object(workflow, "_run_via_tmux_sdk", return_value=_ok_result()),
            caplog.at_level(logging.WARNING, logger="agenticcli.workflows.planner_loop"),
        ):
            workflow._run_role_agent("planner-build", epic_folder)

        assert any(
            "AGENTIC_FORCE_SDK_DIRECT=1" in record.message
            and "zombie" in record.message.lower()
            for record in caplog.records
        ), f"Expected zombie warning log, got: {[r.message for r in caplog.records]}"

    def test_unset_env_defaults_to_sdk_tmux(self, tmp_path, monkeypatch):
        """Without AGENTIC_FORCE_SDK_DIRECT, defaults to sdk-tmux when available."""
        workflow = _make_workflow(tmp_path)
        epic_folder = "260309XX_transport_test"
        called_path = {"path": None}

        def mock_tmux_sdk(session_id, role, epic_folder, prompt, **kw):
            called_path["path"] = "sdk-tmux"
            return _ok_result()

        def mock_sdk_direct(session_id, role, epic_folder, prompt, **kw):
            called_path["path"] = "sdk-direct"
            return _ok_result()

        def mock_subprocess(session_id, role, epic_folder):
            called_path["path"] = "subprocess"
            return _ok_result()

        # Explicitly ensure the env var is NOT set
        monkeypatch.delenv("AGENTIC_FORCE_SDK_DIRECT", raising=False)

        with (
            patch("agenticcli.workflows.planner_loop.SDK_AVAILABLE", True),
            patch("shutil.which", return_value="/usr/bin/tmux"),
            patch.object(workflow, "_run_via_tmux_sdk", side_effect=mock_tmux_sdk),
            patch.object(workflow, "_run_via_sdk", side_effect=mock_sdk_direct),
            patch.object(workflow, "_run_via_subprocess", side_effect=mock_subprocess),
        ):
            workflow._run_role_agent("planner-build", epic_folder)

        assert called_path["path"] == "sdk-tmux", (
            f"Default path should be sdk-tmux, got: {called_path['path']}"
        )

    def test_force_sdk_direct_value_zero_uses_default(self, tmp_path, monkeypatch):
        """AGENTIC_FORCE_SDK_DIRECT=0 should NOT force sdk-direct (only '1' triggers)."""
        workflow = _make_workflow(tmp_path)
        epic_folder = "260309XX_transport_test"
        called_path = {"path": None}

        def mock_tmux_sdk(session_id, role, epic_folder, prompt, **kw):
            called_path["path"] = "sdk-tmux"
            return _ok_result()

        def mock_sdk_direct(session_id, role, epic_folder, prompt, **kw):
            called_path["path"] = "sdk-direct"
            return _ok_result()

        monkeypatch.setenv("AGENTIC_FORCE_SDK_DIRECT", "0")

        with (
            patch("agenticcli.workflows.planner_loop.SDK_AVAILABLE", True),
            patch("shutil.which", return_value="/usr/bin/tmux"),
            patch.object(workflow, "_run_via_tmux_sdk", side_effect=mock_tmux_sdk),
            patch.object(workflow, "_run_via_sdk", side_effect=mock_sdk_direct),
        ):
            workflow._run_role_agent("planner-build", epic_folder)

        assert called_path["path"] == "sdk-tmux", (
            f"AGENTIC_FORCE_SDK_DIRECT=0 should use default sdk-tmux, got: {called_path['path']}"
        )
