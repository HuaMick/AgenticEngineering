"""UAT: Restructure regression tests for agent tool/timeout configs.

Validates that new/renamed/merged agents have correct tool allowlists
and timeout budgets after the 28->20 restructure.
"""

import pytest

pytestmark = pytest.mark.story("US-PLN-046")


class TestToolAllowlists:
    """Verify tool access for new/renamed agents."""

    def test_build_story_writer_gets_write_tool(self):
        """build-story-writer must have Write and Bash tools."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        tools = get_allowed_tools_for_role("build-story-writer")
        assert tools is not None
        assert "Write" in tools
        assert "Bash" in tools

    def test_test_uat_gets_full_tool_access(self):
        """test-uat must have Edit, Write, and Bash tools."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        tools = get_allowed_tools_for_role("test-uat")
        assert tools is not None
        assert "Edit" in tools
        assert "Write" in tools
        assert "Bash" in tools

    def test_planner_audit_tools_are_read_only(self):
        """planner-audit must have Read, Glob, Grep, Bash only (no Edit/Write)."""
        from agenticcli.utils.sdk_runner import get_allowed_tools_for_role

        tools = get_allowed_tools_for_role("planner-audit")
        assert tools == ["Read", "Glob", "Grep", "Bash"]


class TestTimeouts:
    """Verify timeout budgets for new/renamed agents."""

    def test_build_story_writer_timeout_is_1200(self):
        from agenticcli.utils.sdk_runner import get_timeout_for_role
        assert get_timeout_for_role("build-story-writer") == 1200

    def test_test_uat_timeout_is_3600(self):
        from agenticcli.utils.sdk_runner import get_timeout_for_role
        assert get_timeout_for_role("test-uat") == 3600

    def test_trace_explorer_timeout_is_3600(self):
        from agenticcli.utils.sdk_runner import get_timeout_for_role
        assert get_timeout_for_role("trace-explorer") == 3600

    def test_build_docs_writer_timeout_is_3600(self):
        from agenticcli.utils.sdk_runner import get_timeout_for_role
        assert get_timeout_for_role("build-docs-writer") == 3600


class TestRegistryPresence:
    """Verify new/renamed agents appear in all registries."""

    def test_trace_explorer_in_all_registries(self):
        """trace-explorer must be in all 4 agent-name constants."""
        from agenticcli.commands.epic import _FALLBACK_AGENT_TYPES
        from agenticcli.commands.agent_help import KNOWN_AGENTS
        from agenticcli.utils.sdk_runner import ROLE_TOOL_ALLOWLIST, ROLE_TIMEOUT_SECONDS

        assert "trace-explorer" in _FALLBACK_AGENT_TYPES
        assert "trace-explorer" in KNOWN_AGENTS
        assert "trace-explorer" in ROLE_TOOL_ALLOWLIST
        assert "trace-explorer" in ROLE_TIMEOUT_SECONDS

    def test_planner_audit_replaces_planner_cleaning(self):
        """planner-audit in all registries, planner-cleaning in none."""
        from agenticcli.commands.epic import _FALLBACK_AGENT_TYPES
        from agenticcli.commands.agent_help import KNOWN_AGENTS
        from agenticcli.utils.sdk_runner import ROLE_TOOL_ALLOWLIST, ROLE_TIMEOUT_SECONDS
        from agenticcli.workflows.planner_loop import _PLANNING_PHASE_ROLES

        for registry_name, registry in [
            ("_FALLBACK_AGENT_TYPES", _FALLBACK_AGENT_TYPES),
            ("KNOWN_AGENTS", set(KNOWN_AGENTS)),
            ("ROLE_TOOL_ALLOWLIST", set(ROLE_TOOL_ALLOWLIST.keys())),
            ("ROLE_TIMEOUT_SECONDS", set(ROLE_TIMEOUT_SECONDS.keys())),
            ("_PLANNING_PHASE_ROLES", _PLANNING_PHASE_ROLES),
        ]:
            assert "planner-audit" in registry, f"planner-audit missing from {registry_name}"
            assert "planner-cleaning" not in registry, f"planner-cleaning still in {registry_name}"

    def test_test_builder_replaces_test_runner(self):
        """test-builder in all non-planning registries, test-runner in none."""
        from agenticcli.commands.epic import _FALLBACK_AGENT_TYPES
        from agenticcli.commands.agent_help import KNOWN_AGENTS
        from agenticcli.utils.sdk_runner import ROLE_TOOL_ALLOWLIST, ROLE_TIMEOUT_SECONDS

        for registry_name, registry in [
            ("_FALLBACK_AGENT_TYPES", _FALLBACK_AGENT_TYPES),
            ("KNOWN_AGENTS", set(KNOWN_AGENTS)),
            ("ROLE_TOOL_ALLOWLIST", set(ROLE_TOOL_ALLOWLIST.keys())),
            ("ROLE_TIMEOUT_SECONDS", set(ROLE_TIMEOUT_SECONDS.keys())),
        ]:
            assert "test-builder" in registry, f"test-builder missing from {registry_name}"
            assert "test-runner" not in registry, f"test-runner still in {registry_name}"
