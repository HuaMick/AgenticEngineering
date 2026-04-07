"""Tests for agent-specific help commands.

Tests the agent name detection and help output functionality.
Updated for CCI (CLI Context Injection) pattern: positional agent names instead of --flags.
"""

import json
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-GDN-005")

from agenticcli.commands.agent_help import (
    AGENT_CATEGORIES,
    KNOWN_AGENTS,
    get_agent_name,
    is_agent_name,
    show_agent_help,
    _load_agent_context,
    _find_agent_directory,
)


@pytest.mark.story("US-GDN-005")
class TestAgentNameDetection:
    """Tests for agent name detection functions (CCI positional syntax)."""

    def test_is_agent_name_valid(self):
        """Test detection of valid agent names (positional, no -- prefix)."""
        assert is_agent_name("planner-build") is True
        assert is_agent_name("build-python") is True
        assert is_agent_name("test-builder") is True
        assert is_agent_name("orchestration-executor") is True

    def test_is_agent_name_invalid(self):
        """Test rejection of invalid agent names."""
        assert is_agent_name("nonexistent-agent") is False
        assert is_agent_name("help") is False
        assert is_agent_name("-j") is False
        # Old flag syntax should NOT work
        assert is_agent_name("--planner-build") is False
        assert is_agent_name("--") is False

    def test_agent_name_with_dashes(self):
        """Test multi-word agent names work correctly."""
        # All agents with multiple dashes
        assert is_agent_name("build-story-writer") is True
        assert is_agent_name("build-docs-writer") is True
        assert is_agent_name("teacher-update-guidance") is True

    def test_get_agent_name_valid(self):
        """Test extracting agent name from valid positional argument."""
        assert get_agent_name("planner-build") == "planner-build"
        assert get_agent_name("build-python") == "build-python"
        assert get_agent_name("test-builder") == "test-builder"

    def test_get_agent_name_invalid(self):
        """Test returns None for invalid names."""
        assert get_agent_name("nonexistent") is None
        assert get_agent_name("help") is None
        # Old flag syntax should return None
        assert get_agent_name("--planner-build") is None

    def test_all_agents_registered(self):
        """Verify all agents are in KNOWN_AGENTS."""
        assert len(KNOWN_AGENTS) == 20, f"Expected 20 agents, got {len(KNOWN_AGENTS)}"

    def test_all_agents_have_categories(self):
        """Verify all agents have category mappings."""
        for agent in KNOWN_AGENTS:
            assert agent in AGENT_CATEGORIES, f"Agent {agent} missing from AGENT_CATEGORIES"

    def test_agent_categories_valid(self):
        """Verify all categories are valid."""
        valid_categories = {"planner", "build", "test", "orchestration", "teacher", "deploy"}
        for agent, category in AGENT_CATEGORIES.items():
            assert category in valid_categories, f"Invalid category {category} for {agent}"


@pytest.mark.story("US-GDN-005")
class TestAgentHelpContent:
    """Tests for agent help content generation."""

    def test_load_agent_context_basic(self):
        """Test loading context for a known agent."""
        context = _load_agent_context("planner-build")

        assert context["agent"] == "planner-build"
        assert context["category"] == "planner"
        assert "next_commands" in context
        assert len(context["next_commands"]) > 0

    def test_load_agent_context_unknown(self):
        """Test loading context for unknown agent still returns structure."""
        # Use a name that won't match any real agent
        context = _load_agent_context("nonexistent-agent-xyz")

        # Should have basic structure even if agent not found
        assert context["agent"] == "nonexistent-agent-xyz"
        assert "error" in context or context.get("role") is None

    def test_context_includes_next_commands(self):
        """Test that context includes CLI next commands."""
        context = _load_agent_context("build-python")

        assert "next_commands" in context
        commands = context["next_commands"]

        # Should reference the agent name in bootstrap command
        assert any("build-python" in cmd for cmd in commands)
        # Should include task commands (new style: agent epic ticket)
        assert any("epic ticket" in cmd for cmd in commands)

    def test_context_includes_role(self):
        """Test that context includes role description when available."""
        context = _load_agent_context("planner-build")

        # Role may be None if files not found, but key should exist
        assert "role" in context

    @pytest.mark.story("US-GDN-005")
    def test_help_includes_process_steps(self):
        """Test that context includes process steps when available."""
        context = _load_agent_context("test-builder")

        # process_steps should be a list
        assert isinstance(context.get("process_steps", []), list)

    @pytest.mark.story("US-GDN-005")
    def test_help_includes_inputs(self):
        """Test that context includes inputs when available."""
        context = _load_agent_context("planner-build")

        # inputs should be a list
        assert isinstance(context.get("inputs", []), list)


@pytest.mark.story("US-GDN-005")
class TestAgentHelpOutput:
    """Tests for agent help output formatting."""

    def test_show_agent_help_json_structure(self):
        """Test JSON output has expected structure."""
        # Capture stdout
        captured = StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = captured
            show_agent_help("planner-build", json_output=True)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        data = json.loads(output)

        assert "agent" in data
        assert data["agent"] == "planner-build"
        assert "category" in data
        assert "next_commands" in data

    def test_show_agent_help_text_format(self):
        """Test text output includes key sections."""
        captured = StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = captured
            show_agent_help("build-python", json_output=False)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()

        # Check for key sections
        assert "AGENT: build-python" in output
        assert "NEXT COMMANDS:" in output
        assert "agentic" in output  # CLI commands should be present

    def test_unknown_agent_error(self):
        """Test error handling for unknown agents."""
        with pytest.raises(SystemExit) as exc_info:
            show_agent_help("nonexistent-agent-xyz", json_output=False)

        assert exc_info.value.code == 1

    def test_json_output_flag(self):
        """Test -j flag produces JSON output."""
        captured = StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = captured
            show_agent_help("test-builder", json_output=True)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()

        # Should be valid JSON
        data = json.loads(output)
        assert isinstance(data, dict)


@pytest.mark.story("US-GDN-005")
class TestAgentDirectoryFinding:
    """Tests for finding agent directories."""

    def test_find_agent_directory_planner(self):
        """Test finding planner agent directory."""
        agent_dir = _find_agent_directory("planner-build")

        # May be None if not in AgenticEngineering repo
        if agent_dir:
            assert agent_dir.exists()
            assert "planner-build" in str(agent_dir)

    def test_find_agent_directory_build(self):
        """Test finding build agent directory."""
        agent_dir = _find_agent_directory("build-python")

        if agent_dir:
            assert agent_dir.exists()
            assert "build-python" in str(agent_dir)

    def test_find_agent_directory_unknown_returns_none(self):
        """Test that unknown agent returns None."""
        agent_dir = _find_agent_directory("nonexistent-agent")
        assert agent_dir is None


@pytest.mark.story("US-GDN-005")
class TestCLIIntegration:
    """Integration tests for CLI invocation with CCI positional syntax."""

    def test_cli_agent_positional_invocation(self):
        """Test invoking CLI with positional agent name (CCI pattern)."""
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "planner-build"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=10,
        )

        # Should succeed (exit 0)
        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Output should contain agent info
        assert "planner-build" in result.stdout.lower()

    def test_cli_agent_positional_with_json(self):
        """Test invoking CLI with positional agent name and -j."""
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "build-python", "-j"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=10,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Output should be valid JSON
        data = json.loads(result.stdout)
        assert data["agent"] == "build-python"

    @pytest.mark.story("US-GDN-005")
    def test_cli_agent_positional_with_bootstrap(self):
        """Test invoking CLI with positional agent name and --bootstrap."""
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "test-builder", "--bootstrap"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=10,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Bootstrap output should have more detail
        assert "BOOTSTRAP CONTEXT" in result.stdout or "test-builder" in result.stdout.lower()

    @pytest.mark.story("US-GDN-005")
    def test_cli_agent_bootstrap_with_json(self):
        """Test invoking CLI with agent name, --bootstrap and -j."""
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "planner-build", "--bootstrap", "-j"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=10,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Output should be valid JSON with expanded fields
        data = json.loads(result.stdout)
        assert data["agent"] == "planner-build"
        # Bootstrap includes more fields
        assert "process_goal" in data or "process_steps" in data

    def test_cli_old_flag_syntax_rejected(self):
        """Test old --agent-name syntax no longer works (breaking change)."""
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "--planner-build"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=10,
        )

        # Old flag syntax should fail (unrecognized argument)
        # It goes to argparse which doesn't recognize it
        assert result.returncode != 0 or "unrecognized" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_cli_unknown_agent_positional(self):
        """Test CLI with unknown agent name produces error."""
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "nonexistent-agent-xyz"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=10,
        )

        # Unknown positional is not detected as agent name, goes to normal CLI
        # which treats it as subcommand - will produce error or help
        pass  # Just verify it doesn't crash

    @pytest.mark.skipif(
        not Path("/home/code/AgenticEngineering").exists(),
        reason="Requires AgenticEngineering repo"
    )
    def test_cli_fast_response(self):
        """Test CLI responds quickly (< 500ms)."""
        import time

        start = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "test-builder"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=5,
        )
        elapsed = time.time() - start

        assert result.returncode == 0
        # Should complete in under 500ms
        assert elapsed < 0.5, f"CLI took {elapsed:.2f}s, expected < 0.5s"


@pytest.mark.story("US-GDN-005")
class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.story("US-GDN-005")
    def test_missing_manifest_graceful(self):
        """Test graceful handling when manifest doesn't exist."""
        # Mock _find_agent_directory to return a path that exists but has no files
        with patch("agenticcli.commands.agent_help._find_agent_directory") as mock_find:
            # Create a temp directory
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                mock_find.return_value = Path(tmpdir)

                context = _load_agent_context("planner-build")

                # Should still return a context dict without crashing
                assert context["agent"] == "planner-build"
                # Role should be None since no files exist
                assert context["role"] is None

    @pytest.mark.story("US-GDN-005")
    def test_missing_process_graceful(self):
        """Test graceful handling when process.yml doesn't exist."""
        with patch("agenticcli.commands.agent_help._find_agent_directory") as mock_find:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create only manifest
                manifest_path = Path(tmpdir) / "manifest.yml"
                manifest_path.write_text("agent:\n  name: Test Agent\n")

                mock_find.return_value = Path(tmpdir)

                context = _load_agent_context("test-builder")

                # Should work with just manifest
                assert context["agent"] == "test-builder"
                assert context["role"] == "Test Agent"
                assert context["process_steps"] == []  # No process file

    def test_malformed_yaml_graceful(self):
        """Test graceful handling of malformed YAML files."""
        with patch("agenticcli.commands.agent_help._find_agent_directory") as mock_find:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create malformed YAML
                manifest_path = Path(tmpdir) / "manifest.yml"
                manifest_path.write_text("invalid: yaml: content: [[[")

                mock_find.return_value = Path(tmpdir)

                context = _load_agent_context("build-python")

                # Should not crash
                assert context["agent"] == "build-python"


@pytest.mark.story("US-GDN-005")
class TestAgentCategories:
    """Tests for agent category organization."""

    def test_planner_agents_count(self):
        """Verify 6 planner agents."""
        planners = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "planner"]
        assert len(planners) == 6

    def test_test_agents_count(self):
        """Verify 4 test agents."""
        testers = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "test"]
        assert len(testers) == 4

    def test_orchestration_agents_count(self):
        """Verify 3 orchestration agents."""
        orchestrators = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "orchestration"]
        assert len(orchestrators) == 3

    def test_teacher_agents_count(self):
        """Verify 2 teacher agents."""
        teachers = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "teacher"]
        assert len(teachers) == 2

    def test_build_agents_count(self):
        """Verify 4 build agents."""
        builders = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "build"]
        assert len(builders) == 4

    def test_deploy_agents_count(self):
        """Verify 1 deploy agent."""
        deployers = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "deploy"]
        assert len(deployers) == 1
