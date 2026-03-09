"""Integration tests for sequential SDK-in-tmux agent spawning.

Validates that the spawn orchestration logic handles 5 sequential planning
roles correctly without real SDK or tmux calls.

Context: The SDK zombie bug means query() cannot be called >1x per process.
The fix spawns each agent in its own tmux pane via sdk_pane_runner.py,
which calls query() exactly once per OS process. These tests verify the
spawn orchestration logic (command construction, session ID uniqueness,
state read-back) using mocks only.

Run with: pytest tests/integration/test_sdk_tmux_sequential.py -x -q
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticcli.utils.session_id import (
    generate_loop_id,
    generate_session_id,
    short_id,
    tmux_session_name,
)
from agenticcli.utils.session_state import (
    make_session_data,
    mark_completed,
    mark_failed,
    mark_running,
    read_sdk_metrics,
)
from agenticcli.utils.spawn_command import build_spawn_command


# The five planning roles executed sequentially by PlannerLoopRunner
PLANNING_ROLES = [
    "explore",
    "story-generator",
    "planner-build",
    "planner-reviewer",
    "planner-orchestration",
]

TEST_EPIC = "260309TM_sdk_in_tmux_spawn_unification"


@pytest.mark.integration
class TestSequentialSDKTmuxSpawns:
    """Validate that sequential agent spawns via SDK-in-tmux work correctly."""

    # ── Command construction ──────────────────────────────────────────────

    def test_five_sequential_spawns_build_correct_commands(self):
        """Each planning role produces a valid spawn command with --tmux flag."""
        for role in PLANNING_ROLES:
            cmd = build_spawn_command(role=role, epic_folder=TEST_EPIC)
            assert "--tmux" in cmd, f"--tmux missing for role {role}"
            assert "--role" in cmd, f"--role flag missing for role {role}"
            assert role in cmd, f"role name {role!r} not in command"
            assert "-b" in cmd, f"-b (background) missing for role {role}"

    def test_spawn_command_includes_epic_flag(self):
        """build_spawn_command always includes --epic <epic_folder>."""
        cmd = build_spawn_command(role="explore", epic_folder=TEST_EPIC)
        assert "--epic" in cmd
        epic_idx = cmd.index("--epic")
        assert cmd[epic_idx + 1] == TEST_EPIC

    def test_spawn_command_skip_permissions_flag(self):
        """skip_permissions=True appends --dangerously-skip-permissions."""
        cmd = build_spawn_command(
            role="planner-build",
            epic_folder=TEST_EPIC,
            skip_permissions=True,
        )
        assert "--dangerously-skip-permissions" in cmd

    def test_spawn_command_no_skip_permissions_by_default(self):
        """skip_permissions defaults to False — flag absent unless requested."""
        cmd = build_spawn_command(role="planner-build", epic_folder=TEST_EPIC)
        assert "--dangerously-skip-permissions" not in cmd

    def test_spawn_command_json_flag_present_by_default(self):
        """build_spawn_command includes -j for machine-readable output."""
        cmd = build_spawn_command(role="explore", epic_folder=TEST_EPIC)
        assert "-j" in cmd

    def test_planner_loop_sequential_spawn_flow(self):
        """All 5 planning roles produce valid spawn commands (skip_permissions=True)."""
        results = []
        for role in PLANNING_ROLES:
            cmd = build_spawn_command(
                role=role,
                epic_folder=TEST_EPIC,
                skip_permissions=True,
            )
            results.append(cmd)

        assert len(results) == 5
        for cmd in results:
            assert "--dangerously-skip-permissions" in cmd
            assert "--tmux" in cmd
            assert "-b" in cmd

    def test_spawn_command_max_turns_flag(self):
        """max_turns parameter is reflected in the built command."""
        cmd = build_spawn_command(
            role="explore", epic_folder=TEST_EPIC, max_turns=50
        )
        assert "--max-turns" in cmd
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "50"

    def test_spawn_command_no_max_turns_by_default(self):
        """max_turns not set by default — --max-turns absent."""
        cmd = build_spawn_command(role="explore", epic_folder=TEST_EPIC)
        assert "--max-turns" not in cmd

    def test_spawn_command_no_tmux_when_disabled(self):
        """use_tmux=False omits the --tmux flag."""
        cmd = build_spawn_command(
            role="explore", epic_folder=TEST_EPIC, use_tmux=False
        )
        assert "--tmux" not in cmd

    # ── Session ID uniqueness ─────────────────────────────────────────────

    def test_sequential_spawns_get_unique_session_ids(self):
        """Each spawn in a planning sequence gets a unique session ID."""
        ids = [generate_session_id() for _ in PLANNING_ROLES]
        assert len(set(ids)) == len(ids), "Duplicate session IDs generated"

    def test_no_session_id_reuse_across_retries(self):
        """Retry attempts generate fresh session IDs — never reuse existing ones."""
        ids: set[str] = set()
        for _ in range(3):  # 3 retry cycles
            for role in PLANNING_ROLES:
                sid = generate_session_id()
                assert sid not in ids, f"Session ID reused: {sid}"
                ids.add(sid)
        # 15 unique IDs total (5 roles × 3 retries)
        assert len(ids) == 15

    def test_session_id_is_valid_uuid_format(self):
        """generate_session_id() returns a well-formed UUID string."""
        import uuid

        for _ in range(5):
            sid = generate_session_id()
            # Should not raise ValueError
            parsed = uuid.UUID(sid)
            assert str(parsed) == sid

    def test_short_id_is_eight_chars(self):
        """short_id() returns the first 8 characters of the session ID."""
        sid = generate_session_id()
        assert len(short_id(sid)) == 8
        assert short_id(sid) == sid[:8]

    def test_loop_id_has_prefix(self):
        """generate_loop_id() respects the supplied prefix."""
        lid = generate_loop_id("planner")
        assert lid.startswith("planner-")
        # Suffix is 12 hex chars
        suffix = lid[len("planner-"):]
        assert len(suffix) == 12
        assert all(c in "0123456789abcdef" for c in suffix)

    # ── Tmux session naming ───────────────────────────────────────────────

    def test_tmux_session_name_includes_role(self):
        """tmux_session_name embeds role when provided."""
        sid = generate_session_id()
        name = tmux_session_name(sid, epic_folder=Path(TEST_EPIC), role="explore")
        assert "explore" in name

    def test_tmux_session_names_differ_per_role(self):
        """Different roles produce different tmux session names."""
        sid = generate_session_id()
        names = {
            tmux_session_name(sid, epic_folder=Path(TEST_EPIC), role=role)
            for role in PLANNING_ROLES
        }
        assert len(names) == len(PLANNING_ROLES), "Role names must be distinct"

    def test_tmux_session_name_sanitised(self):
        """tmux_session_name contains only alphanumerics and hyphens."""
        import re

        sid = generate_session_id()
        name = tmux_session_name(sid, epic_folder=Path(TEST_EPIC), role="planner-build")
        assert re.fullmatch(r"[a-zA-Z0-9_-]+", name), f"Invalid chars in: {name}"
        assert "--" not in name, "Consecutive hyphens in tmux session name"

    # ── SDK metrics read-back ─────────────────────────────────────────────

    def test_sdk_metrics_available_after_spawn(self, tmp_path):
        """After spawn completes, SDK metrics are readable from session state."""
        mock_metrics = {
            "cost_usd": 0.05,
            "duration_ms": 30_000,
            "num_turns": 10,
            "usage": {"input_tokens": 5_000, "output_tokens": 2_000},
            "sdk_session_id": "test-session-abc",
            "transport": "sdk-tmux",
        }

        with patch(
            "agenticcli.utils.state_store.StateStore"
        ) as MockStore:
            instance = MockStore.return_value
            instance.load.return_value = mock_metrics

            for role in PLANNING_ROLES:
                session_id = generate_session_id()
                metrics = read_sdk_metrics(session_id)

                assert metrics["cost_usd"] == 0.05, f"cost_usd wrong for {role}"
                assert metrics["transport"] == "sdk-tmux", f"transport wrong for {role}"
                assert metrics["num_turns"] == 10, f"num_turns wrong for {role}"
                assert metrics["usage"]["input_tokens"] == 5_000

    def test_sdk_metrics_defaults_when_store_empty(self, tmp_path):
        """read_sdk_metrics() returns safe defaults when no state exists."""
        with patch(
            "agenticcli.utils.state_store.StateStore"
        ) as MockStore:
            instance = MockStore.return_value
            instance.load.return_value = None

            metrics = read_sdk_metrics(generate_session_id())

        assert metrics["cost_usd"] == 0.0
        assert metrics["duration_ms"] == 0
        assert metrics["num_turns"] == 0
        assert metrics["usage"] == {}
        assert metrics["sdk_session_id"] == ""
        assert metrics["transport"] == "unknown"

    def test_sdk_metrics_all_five_roles_readable(self, tmp_path):
        """SDK metrics can be read back for all 5 planning roles independently."""
        role_states = {}
        for i, role in enumerate(PLANNING_ROLES):
            sid = generate_session_id()
            role_states[sid] = {
                "cost_usd": 0.01 * (i + 1),
                "duration_ms": 10_000 * (i + 1),
                "num_turns": i + 1,
                "usage": {},
                "sdk_session_id": f"sdk-{role}",
                "transport": "sdk-tmux",
            }

        for sid, expected in role_states.items():
            with patch(
                "agenticcli.utils.state_store.StateStore"
            ) as MockStore:
                instance = MockStore.return_value
                instance.load.return_value = expected

                metrics = read_sdk_metrics(sid)
                assert metrics["transport"] == "sdk-tmux"
                assert metrics["sdk_session_id"] == expected["sdk_session_id"]
                assert metrics["cost_usd"] == expected["cost_usd"]

    # ── Session state helpers ─────────────────────────────────────────────

    def test_make_session_data_transport_field(self):
        """make_session_data records transport=sdk-tmux for tmux-based spawns."""
        sid = generate_session_id()
        data = make_session_data(
            sid,
            role="explore",
            epic_folder=TEST_EPIC,
            transport="sdk-tmux",
            working_dir="/home/code",
        )
        assert data["transport"] == "sdk-tmux"
        assert data["status"] == "starting"
        assert data["role"] == "explore"
        assert data["epic_folder"] == TEST_EPIC

    def test_mark_running_sets_status(self):
        """mark_running() transitions status to 'running'."""
        sid = generate_session_id()
        data = make_session_data(sid, role="planner-build", epic_folder=TEST_EPIC)
        mark_running(data, pid=12345, transport="sdk-tmux", tmux_session="agentic-test")
        assert data["status"] == "running"
        assert data["pid"] == 12345
        assert data["transport"] == "sdk-tmux"
        assert data["tmux_session"] == "agentic-test"

    def test_mark_completed_sets_status(self):
        """mark_completed() transitions status to 'completed' with metrics."""
        sid = generate_session_id()
        data = make_session_data(sid, role="planner-reviewer", epic_folder=TEST_EPIC)
        mark_completed(
            data,
            exit_code=0,
            cost_usd=0.042,
            duration_ms=25_000,
            num_turns=8,
            sdk_session_id="sdk-abc",
        )
        assert data["status"] == "completed"
        assert data["exit_code"] == 0
        assert data["cost_usd"] == 0.042
        assert data["num_turns"] == 8
        assert data["sdk_session_id"] == "sdk-abc"

    def test_mark_failed_sets_structured_error(self):
        """mark_failed() populates failure_reason with structured error info."""
        sid = generate_session_id()
        data = make_session_data(sid, role="explore", epic_folder=TEST_EPIC)
        mark_failed(
            data,
            error_code="sdk_pane_failure",
            error_type="sdk_error",
            detail="SDK query timed out",
            retryable=True,
        )
        assert data["status"] == "failed"
        assert data["error_code"] == "sdk_pane_failure"
        assert data["failure_reason"]["retryable"] is True
        assert data["failure_reason"]["suggested_action"] == "retry"
        assert "sdk_error" == data["failure_reason"]["error_type"]

    def test_session_state_lifecycle_for_all_roles(self):
        """Full starting -> running -> completed lifecycle for each planning role."""
        for role in PLANNING_ROLES:
            sid = generate_session_id()
            data = make_session_data(
                sid, role=role, epic_folder=TEST_EPIC, transport="sdk-tmux"
            )
            assert data["status"] == "starting"

            mark_running(data, pid=99999)
            assert data["status"] == "running"

            mark_completed(data, cost_usd=0.02, num_turns=5)
            assert data["status"] == "completed"
            assert data["exit_code"] == 0

    # ── State file persistence (real tmp_path, no mock) ───────────────────

    def test_state_store_round_trip(self, tmp_path):
        """Session state written to disk is read back intact."""
        from agenticcli.utils.state_store import StateStore

        store = StateStore("sessions", id_key="session_id")
        sid = generate_session_id()
        state = make_session_data(
            sid,
            role="planner-orchestration",
            epic_folder=TEST_EPIC,
            transport="sdk-tmux",
        )
        mark_completed(state, cost_usd=0.07, num_turns=12)

        store.save(state, state_dir=tmp_path)

        loaded = store.load(sid, state_dir=tmp_path)
        assert loaded is not None
        assert loaded["session_id"] == sid
        assert loaded["status"] == "completed"
        assert loaded["cost_usd"] == 0.07
        assert loaded["transport"] == "sdk-tmux"

    def test_state_store_five_sessions_independent(self, tmp_path):
        """Five sessions written to the same store are independent."""
        from agenticcli.utils.state_store import StateStore

        store = StateStore("sessions", id_key="session_id")
        written: dict[str, dict] = {}

        for i, role in enumerate(PLANNING_ROLES):
            sid = generate_session_id()
            state = make_session_data(sid, role=role, epic_folder=TEST_EPIC)
            mark_completed(state, cost_usd=0.01 * (i + 1), num_turns=i + 2)
            store.save(state, state_dir=tmp_path)
            written[sid] = state

        # Read each back and verify no cross-contamination
        for sid, original in written.items():
            loaded = store.load(sid, state_dir=tmp_path)
            assert loaded is not None
            assert loaded["role"] == original["role"]
            assert loaded["cost_usd"] == original["cost_usd"]
            assert loaded["num_turns"] == original["num_turns"]

    def test_state_store_list_all_five_sessions(self, tmp_path):
        """StateStore.list_all() returns all five saved sessions."""
        from agenticcli.utils.state_store import StateStore

        store = StateStore("sessions", id_key="session_id")
        sids = []

        for role in PLANNING_ROLES:
            sid = generate_session_id()
            state = make_session_data(sid, role=role, epic_folder=TEST_EPIC)
            store.save(state, state_dir=tmp_path)
            sids.append(sid)

        all_records = store.list_all(state_dir=tmp_path)
        recovered_ids = {r["session_id"] for r in all_records}
        assert set(sids) == recovered_ids
