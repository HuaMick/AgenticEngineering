"""UAT: CLI commands for priority and dependency management.

User Acceptance Tests for:
- US-PLN-004: epic list shows priority
- US-PLN-082: epic link/unlink works
- US-PLN-085: list sorted by priority
- set-priority changes priority
- epic status shows deps

Tests use subprocess.run with the real `agentic` binary, isolated via
a temporary HOME directory so TinyDB writes go to $TMPDIR/.agentic/epics.db
instead of the user's real database.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_env(tmp_path):
    """Create an isolated HOME environment for running agentic CLI.

    Returns env dict and seeds two test epics in the isolated TinyDB.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    agentic_dir = fake_home / ".agentic"
    agentic_dir.mkdir()
    db_path = agentic_dir / "epics.db"

    # Seed test data via Python
    from agenticguidance.services.epic_repository import EpicRepository

    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    for name, priority, deps in [
        ("260101AA_low_priority_epic", "low", []),
        ("260201BB_high_priority_epic", "high", []),
        ("260301CC_critical_epic", "critical", []),
        ("260101DD_medium_epic", "medium", []),
        ("260101EE_depends_on_cc", "medium", ["260301CC_critical_epic"]),
    ]:
        repo.create_epic({
            "epic_folder_name": name,
            "epic_folder": str(tmp_path / "epics" / name),
            "name": name,
            "status": "in_progress",
            "priority": priority,
            "objective": f"Objective for {name}",
            "depends_on": deps,
        })
    repo.close()

    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    return env, db_path, tmp_path


def _run_agentic(args, env, timeout=30):
    """Run agentic CLI with given args and isolated env."""
    result = subprocess.run(
        ["agentic"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return result


# ---------------------------------------------------------------------------
# US-PLN-004 / US-PLN-085: epic list shows priority, sorted by priority
# ---------------------------------------------------------------------------


class TestEpicListPriority:
    """Test that 'agentic epic list' shows and sorts by priority."""

    def test_epic_list_json_shows_priority(self, isolated_env):
        """Epic list JSON output includes priority field."""
        env, db_path, tmp_path = isolated_env

        result = _run_agentic(["-j", "epic", "list"], env)
        assert result.returncode == 0, f"stderr: {result.stderr}"

        data = json.loads(result.stdout)
        plans = data.get("plans", data.get("epics", []))
        assert len(plans) > 0

        # Check that priority field is present
        for plan in plans:
            assert "priority" in plan, f"Missing priority in: {plan}"

    def test_epic_list_sorted_by_priority(self, isolated_env):
        """Epic list is sorted by priority: critical first."""
        env, db_path, tmp_path = isolated_env

        result = _run_agentic(["-j", "epic", "list"], env)
        assert result.returncode == 0, f"stderr: {result.stderr}"

        data = json.loads(result.stdout)
        plans = data.get("plans", data.get("epics", []))
        names = [p.get("plan", p.get("epic_folder_name", "")) for p in plans]

        # Critical should come before high, high before medium, medium before low
        priority_weights = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        priorities = []
        for p in plans:
            prio = p.get("priority", "medium")
            priorities.append(priority_weights.get(prio, 3))
        # Verify sorted ascending (lower weight = higher priority)
        assert priorities == sorted(priorities), f"Not priority-sorted: {list(zip(names, priorities))}"


# ---------------------------------------------------------------------------
# US-PLN-082: epic link/unlink
# ---------------------------------------------------------------------------


class TestEpicLinkUnlink:
    """Test that 'agentic epic link' and 'unlink' work correctly."""

    def test_link_creates_dependency(self, isolated_env):
        """'agentic epic link' creates a dependency between two epics."""
        env, db_path, tmp_path = isolated_env

        result = _run_agentic(
            ["-j", "epic", "link",
             "--epic", "260101AA_low_priority_epic",
             "--depends-on", "260201BB_high_priority_epic"],
            env,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        data = json.loads(result.stdout)
        assert data.get("result") == "success"

        # Verify in DB
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        deps = repo.get_dependencies("260101AA_low_priority_epic")
        assert "260201BB_high_priority_epic" in deps
        repo.close()

    def test_unlink_removes_dependency(self, isolated_env):
        """'agentic epic unlink' removes an existing dependency."""
        env, db_path, tmp_path = isolated_env

        # 260101EE_depends_on_cc already has a dep on 260301CC_critical_epic
        result = _run_agentic(
            ["-j", "epic", "unlink",
             "--epic", "260101EE_depends_on_cc",
             "--depends-on", "260301CC_critical_epic"],
            env,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        data = json.loads(result.stdout)
        assert data.get("result") == "success"

        # Verify in DB
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        deps = repo.get_dependencies("260101EE_depends_on_cc")
        assert "260301CC_critical_epic" not in deps
        repo.close()

    def test_link_rejects_self_reference(self, isolated_env):
        """'agentic epic link' rejects self-dependency."""
        env, db_path, tmp_path = isolated_env

        result = _run_agentic(
            ["-j", "epic", "link",
             "--epic", "260101AA_low_priority_epic",
             "--depends-on", "260101AA_low_priority_epic"],
            env,
        )
        assert result.returncode != 0

    def test_link_rejects_cycle(self, isolated_env):
        """'agentic epic link' rejects a cycle-producing dependency."""
        env, db_path, tmp_path = isolated_env

        # First create A->B
        _run_agentic(
            ["-j", "epic", "link",
             "--epic", "260101AA_low_priority_epic",
             "--depends-on", "260201BB_high_priority_epic"],
            env,
        )
        # Now try B->A which would create a cycle
        result = _run_agentic(
            ["-j", "epic", "link",
             "--epic", "260201BB_high_priority_epic",
             "--depends-on", "260101AA_low_priority_epic"],
            env,
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# set-priority
# ---------------------------------------------------------------------------


class TestSetPriority:
    """Test that 'agentic epic set-priority' works."""

    def test_set_priority_changes_value(self, isolated_env):
        """'agentic epic set-priority' updates the priority."""
        env, db_path, tmp_path = isolated_env

        result = _run_agentic(
            ["-j", "epic", "set-priority",
             "--epic", "260101AA_low_priority_epic",
             "--priority", "critical"],
            env,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        data = json.loads(result.stdout)
        assert data.get("result") == "success"
        assert data.get("priority") == 1  # "critical" normalized to int

    def test_set_priority_rejects_invalid(self, isolated_env):
        """'agentic epic set-priority' rejects invalid priority values."""
        env, db_path, tmp_path = isolated_env

        result = _run_agentic(
            ["-j", "epic", "set-priority",
             "--epic", "260101AA_low_priority_epic",
             "--priority", "ultra-high"],
            env,
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# epic status shows deps
# ---------------------------------------------------------------------------


class TestEpicStatusDeps:
    """Test that 'agentic epic status' shows dependency information."""

    def test_status_json_shows_deps(self, isolated_env):
        """'agentic -j epic status' includes dependency info."""
        env, db_path, tmp_path = isolated_env

        result = _run_agentic(
            ["-j", "epic", "status",
             "--epic", "260101EE_depends_on_cc"],
            env,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        data = json.loads(result.stdout)
        # Check for depends_on or blocked_by fields
        depends_on = data.get("depends_on", [])
        blocked_by = data.get("blocked_by", [])
        # At least one should contain info about the dependency
        has_dep_info = (
            "260301CC_critical_epic" in depends_on
            or "260301CC_critical_epic" in blocked_by
            or data.get("dependency_blocked", False)
        )
        assert has_dep_info, f"Status should show dependency info: {data}"
