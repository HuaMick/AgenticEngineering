"""Regression guard: sdk_pane_runner.main MUST finalize session state on every
exit path (normal return, unhandled exception, signals).

Context: in Phase 5 live UAT, test-uat session 1414344b ran 468s then the pane
terminated silently. The session json stayed in ``status: "running"`` forever
because run_pane exited without its normal state-write path completing. Blind
consumers (orchestrators, `agentic stories` listeners) had no way to observe
the terminal state.

These tests exercise main() under failure conditions with monkeypatched
run_pane and assert the session JSON lands in a terminal status.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.story("US-SES-001")


@pytest.fixture
def isolated_state_dir(tmp_path, monkeypatch):
    """Redirect pane-runner state files into tmp_path."""
    from agenticcli.utils import sdk_pane_runner

    state_dir = tmp_path / "sessions"
    state_dir.mkdir()

    def fake_get_state_file(sid):
        return state_dir / f"{sid}.json"

    monkeypatch.setattr(sdk_pane_runner, "_get_state_file", fake_get_state_file)
    return state_dir


def _invoke_main(session_id: str, context_file: Path):
    """Invoke pane runner main() with minimal required argv."""
    from agenticcli.utils import sdk_pane_runner

    argv = [
        "sdk_pane_runner",
        "--role", "test-uat",
        "--session-id", session_id,
        "--context-file", str(context_file),
        "--working-dir", str(context_file.parent),
    ]
    with patch("sys.argv", argv):
        try:
            sdk_pane_runner.main()
        except SystemExit as exc:
            return int(exc.code) if exc.code is not None else 0
    return 0


class TestMainFinalizesOnCrash:
    """main() writes a terminal state file even when run_pane crashes."""

    def test_run_pane_raises_is_caught_and_state_marked_failed(
        self, isolated_state_dir, tmp_path, monkeypatch
    ):
        """An uncaught exception from run_pane must produce a failed state file."""
        from agenticcli.utils import sdk_pane_runner

        sid = "11111111-1111-1111-1111-111111111111"
        ctx = tmp_path / "ctx.md"
        ctx.write_text("test prompt")

        # Simulate a crash deep inside run_pane (e.g. SDK internal error).
        def boom(*args, **kwargs):
            raise RuntimeError("simulated SDK crash")

        monkeypatch.setattr(sdk_pane_runner, "run_pane", boom)

        exit_code = _invoke_main(sid, ctx)
        assert exit_code == 1

        state_file = isolated_state_dir / f"{sid}.json"
        assert state_file.exists(), "pane runner must write state file on crash"
        state = json.loads(state_file.read_text())
        assert state["status"] not in ("running", None), (
            f"crash must transition status out of 'running', got {state}"
        )
        assert state["exit_code"] == 1
        assert "simulated SDK crash" in state.get("error", "")

    def test_run_pane_returns_but_state_still_running_gets_finalized(
        self, isolated_state_dir, tmp_path, monkeypatch
    ):
        """If run_pane returns but forgot to update state, main() closes the gap."""
        from agenticcli.utils import sdk_pane_runner

        sid = "22222222-2222-2222-2222-222222222222"
        ctx = tmp_path / "ctx.md"
        ctx.write_text("test prompt")

        # Pre-seed state file in 'running' status (as spawn does).
        state_file = isolated_state_dir / f"{sid}.json"
        state_file.write_text(json.dumps({
            "session_id": sid,
            "status": "running",
            "transport": "sdk-tmux",
        }))

        # run_pane returns 0 without touching state (simulates the Phase 5 bug).
        monkeypatch.setattr(sdk_pane_runner, "run_pane", lambda **kw: 0)

        _invoke_main(sid, ctx)

        state = json.loads(state_file.read_text())
        assert state["status"] != "running", (
            "main() must finalize a stuck 'running' state even when run_pane returns"
        )
        assert "ended_at" in state

    def test_keyboard_interrupt_still_writes_state(
        self, isolated_state_dir, tmp_path, monkeypatch
    ):
        """Ctrl+C / SIGINT must still persist a terminal state before re-raise."""
        from agenticcli.utils import sdk_pane_runner

        sid = "33333333-3333-3333-3333-333333333333"
        ctx = tmp_path / "ctx.md"
        ctx.write_text("test prompt")

        def interrupted(*a, **kw):
            raise KeyboardInterrupt()

        monkeypatch.setattr(sdk_pane_runner, "run_pane", interrupted)

        with pytest.raises(KeyboardInterrupt):
            _invoke_main(sid, ctx)

        state_file = isolated_state_dir / f"{sid}.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["status"] not in ("running", None)
        assert state["exit_code"] == 1
