"""UAT: Agent roster consistency after 28->20 restructure.

Validates that all agent-name registries (fallback types, known agents,
tool allowlists, timeout dicts, planning roles) are consistent with
the filesystem and contain no deleted agents.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.story("US-PLN-046")

# The 9 deleted agents from the restructure
DELETED_AGENTS = frozenset({
    "test-runner", "test-cleaner", "test-final-output",
    "test-guidance-simulator", "test-service",
    "planner-cleaning", "planner-guidance",
    "planner-guidance-testing", "planner-sdk",
})


class TestFallbackAgentTypes:
    """Verify _FALLBACK_AGENT_TYPES matches filesystem."""

    def test_fallback_agent_types_matches_filesystem(self):
        """_FALLBACK_AGENT_TYPES must match actual agents/ directories."""
        from agenticcli.commands.epic import _FALLBACK_AGENT_TYPES

        agents_dir = Path(__file__).resolve().parents[2] / "AgenticGuidance" / "agents"
        if not agents_dir.exists():
            pytest.skip("AgenticGuidance/agents/ not found")

        fs_agents = set()
        for category_dir in agents_dir.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith("."):
                continue
            # Underscore-prefixed categories (e.g. `_mock/`) are UAT-only
            # harnesses and excluded from the production roster.
            if category_dir.name.startswith("_"):
                continue
            for agent_dir in category_dir.iterdir():
                if agent_dir.is_dir() and (agent_dir / "manifest.yml").exists():
                    fs_agents.add(agent_dir.name)

        assert _FALLBACK_AGENT_TYPES == fs_agents, (
            f"Mismatch:\n"
            f"  In fallback but not on disk: {_FALLBACK_AGENT_TYPES - fs_agents}\n"
            f"  On disk but not in fallback: {fs_agents - _FALLBACK_AGENT_TYPES}"
        )

    def test_get_valid_agent_types_matches_fallback(self):
        """Dynamic filesystem scan must match hardcoded fallback."""
        from agenticcli.commands.epic import _FALLBACK_AGENT_TYPES, get_valid_agent_types

        agents_dir = Path(__file__).resolve().parents[2] / "AgenticGuidance" / "agents"
        if not agents_dir.exists():
            pytest.skip("AgenticGuidance/agents/ not found")

        result = get_valid_agent_types(agents_dir=agents_dir)
        assert result == _FALLBACK_AGENT_TYPES, (
            f"Mismatch:\n"
            f"  get_valid_agent_types extra: {result - _FALLBACK_AGENT_TYPES}\n"
            f"  get_valid_agent_types missing: {_FALLBACK_AGENT_TYPES - result}"
        )


class TestKnownAgents:
    """Verify KNOWN_AGENTS list matches filesystem."""

    def test_known_agents_matches_filesystem(self):
        """KNOWN_AGENTS must match actual agent directories."""
        from agenticcli.commands.agent_help import KNOWN_AGENTS
        from agenticcli.commands.epic import _FALLBACK_AGENT_TYPES

        assert set(KNOWN_AGENTS) == _FALLBACK_AGENT_TYPES, (
            f"Mismatch:\n"
            f"  In KNOWN_AGENTS but not fallback: {set(KNOWN_AGENTS) - _FALLBACK_AGENT_TYPES}\n"
            f"  In fallback but not KNOWN_AGENTS: {_FALLBACK_AGENT_TYPES - set(KNOWN_AGENTS)}"
        )


class TestToolAndTimeoutConsistency:
    """Verify tool allowlist and timeout dict are consistent."""

    def test_tool_allowlist_has_no_deleted_agents(self):
        """ROLE_TOOL_ALLOWLIST must not reference deleted agents."""
        from agenticcli.utils.sdk_runner import ROLE_TOOL_ALLOWLIST

        overlap = DELETED_AGENTS & set(ROLE_TOOL_ALLOWLIST.keys())
        assert overlap == set(), f"Deleted agents in ROLE_TOOL_ALLOWLIST: {overlap}"

    def test_timeout_dict_covers_all_agents_in_allowlist(self):
        """Every agent in ROLE_TOOL_ALLOWLIST should have a ROLE_TIMEOUT_SECONDS entry."""
        from agenticcli.utils.sdk_runner import ROLE_TOOL_ALLOWLIST, ROLE_TIMEOUT_SECONDS

        allowlist_keys = set(ROLE_TOOL_ALLOWLIST.keys())
        timeout_keys = set(ROLE_TIMEOUT_SECONDS.keys())

        # 'explore' is a legacy shorthand alias, allowed to be in allowlist without timeout
        missing = (allowlist_keys - {"explore"}) - timeout_keys
        assert missing == set(), (
            f"Agents in ROLE_TOOL_ALLOWLIST missing from ROLE_TIMEOUT_SECONDS: {missing}"
        )

    def test_no_deleted_agents_in_any_registry(self):
        """Comprehensive sweep: no deleted agents in any of the 5 registries."""
        from agenticcli.commands.epic import _FALLBACK_AGENT_TYPES
        from agenticcli.commands.agent_help import KNOWN_AGENTS
        from agenticcli.utils.sdk_runner import ROLE_TOOL_ALLOWLIST, ROLE_TIMEOUT_SECONDS
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES

        registries = {
            "_FALLBACK_AGENT_TYPES": _FALLBACK_AGENT_TYPES,
            "KNOWN_AGENTS": set(KNOWN_AGENTS),
            "ROLE_TOOL_ALLOWLIST": set(ROLE_TOOL_ALLOWLIST.keys()),
            "ROLE_TIMEOUT_SECONDS": set(ROLE_TIMEOUT_SECONDS.keys()),
            "_PLANNING_PHASE_ROLES": _PLANNING_PHASE_ROLES,
        }

        for name, registry in registries.items():
            overlap = DELETED_AGENTS & registry
            assert overlap == set(), (
                f"Deleted agents found in {name}: {overlap}"
            )
