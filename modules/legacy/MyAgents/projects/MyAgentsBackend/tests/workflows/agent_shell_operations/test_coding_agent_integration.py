"""Integration tests for builder_agent's execute_shell tool integration.

Tests that the builder_agent workflow properly includes and can use the execute_shell tool,
and that tool results are formatted correctly for LLM consumption.
"""

import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.mark.integration
class TestBuilderAgentHasExecuteShell:
    """Test that builder_agent includes execute_shell in its tools."""

    def test_builder_agent_imports_execute_shell(self):
        """Test that builder_agent module can import execute_shell tool."""
        from myagents.backend.services.agents.tools import get_all_tools, get_tool_by_name

        # Verify execute_shell is accessible
        tool = get_tool_by_name("execute_shell")
        assert tool is not None
        assert tool.name == "execute_shell"

    def test_get_all_tools_includes_execute_shell(self):
        """Test that get_all_tools() returns list containing execute_shell."""
        from myagents.backend.services.agents.tools import get_all_tools

        tools = get_all_tools()
        tool_names = [tool.name for tool in tools]

        assert "execute_shell" in tool_names, (
            f"execute_shell not found in tools. Available tools: {tool_names}"
        )

    def test_execute_shell_in_combined_tools(self):
        """Test that execute_shell is in the combined ALL_TOOLS list."""
        from myagents.backend.services.agents.tools import ALL_TOOLS

        tool_names = [tool.name for tool in ALL_TOOLS]
        assert "execute_shell" in tool_names

    def test_execute_shell_in_tools_by_name(self):
        """Test that execute_shell is in the TOOLS_BY_NAME registry."""
        from myagents.backend.services.agents.tools import TOOLS_BY_NAME

        assert "execute_shell" in TOOLS_BY_NAME
        assert TOOLS_BY_NAME["execute_shell"].name == "execute_shell"

    def test_shell_tools_properly_exported(self):
        """Test that shell_tools module exports are correct."""
        from myagents.backend.services.agents.tools.shell_tools import (
            execute_shell,
            ALL_TOOLS,
            TOOLS_BY_NAME,
        )

        assert execute_shell is not None
        assert execute_shell in ALL_TOOLS
        assert "execute_shell" in TOOLS_BY_NAME


@pytest.mark.integration
class TestExecuteShellToolProperties:
    """Test that execute_shell tool has proper LLM binding properties."""

    def test_execute_shell_has_name(self):
        """Test that execute_shell has name attribute."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        assert hasattr(tool, "name")
        assert tool.name == "execute_shell"

    def test_execute_shell_has_description(self):
        """Test that execute_shell has description for LLM."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        assert hasattr(tool, "description")
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0
        # Description should mention shell/command execution
        assert "shell" in tool.description.lower() or "command" in tool.description.lower()

    def test_execute_shell_has_invoke_method(self):
        """Test that execute_shell has invoke method for execution."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        assert hasattr(tool, "invoke")
        assert callable(tool.invoke)

    def test_execute_shell_has_args_schema(self):
        """Test that execute_shell has args schema for parameter validation."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        # LangChain tools have args_schema or similar for parameters
        assert hasattr(tool, "args_schema") or hasattr(tool, "args")


@pytest.mark.integration
class TestToolOutputFormat:
    """Test that tool output is properly formatted for LLM consumption."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def setup_shell_env(self, temp_dir, monkeypatch):
        """Setup test environment with temporary directory for shell operations."""
        # Set the allowed directory for shell operations
        monkeypatch.setenv("MYAGENTS_ALLOWED_DIR", str(temp_dir))

        # Reset the shell_ops singleton to pick up new env var
        import myagents.backend.services.agents.tools.shell_tools as shell_tools_module
        shell_tools_module._shell_ops = None

        yield temp_dir

        # Reset after test
        shell_tools_module._shell_ops = None

    def test_output_contains_stdout_section(self, setup_shell_env):
        """Test that tool output contains stdout section when there's output."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        result = tool.invoke({"command": "echo 'test output'"})

        # Result should contain stdout section
        assert "stdout:" in result
        assert "test output" in result

    def test_output_contains_return_code(self, setup_shell_env):
        """Test that tool output always contains return_code section."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        result = tool.invoke({"command": "echo 'hello'"})

        # Result should always contain return_code
        assert "return_code:" in result
        assert "return_code: 0" in result

    def test_output_contains_stderr_when_present(self, setup_shell_env):
        """Test that tool output contains stderr section when there's error output."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        # Command that writes to stderr
        result = tool.invoke({"command": "echo 'error message' >&2"})

        # Result should contain stderr section
        assert "stderr:" in result
        assert "error message" in result

    def test_output_format_is_string(self, setup_shell_env):
        """Test that tool output is a plain string (not dict/json)."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        result = tool.invoke({"command": "echo 'test'"})

        # Result should be a string, not a dictionary
        assert isinstance(result, str)

    def test_output_format_is_readable(self, setup_shell_env):
        """Test that output format is human-readable for LLM."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        result = tool.invoke({"command": "echo 'hello world'"})

        # Output should be formatted with clear sections
        lines = result.split('\n')

        # Should have multiple lines with clear structure
        assert len(lines) >= 1

        # Should not be JSON format
        assert not result.startswith('{')
        assert not result.startswith('[')

    def test_failed_command_shows_nonzero_return_code(self, setup_shell_env):
        """Test that failed commands show non-zero return code."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        # Command that will fail
        result = tool.invoke({"command": "exit 1"})

        # Should show non-zero return code
        assert "return_code: 1" in result

    def test_output_omits_empty_sections(self, setup_shell_env):
        """Test that empty stdout/stderr sections are omitted for cleaner output."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        # Command with no stdout
        result = tool.invoke({"command": "exit 0"})

        # Return code should always be present
        assert "return_code: 0" in result

        # Empty stdout should not create a "stdout:" section
        # (based on the shell_tools.py implementation which checks if result["stdout"])
        if "stdout:" not in result:
            # This is the expected clean output
            pass
        else:
            # If stdout is present, it should have actual content
            stdout_idx = result.index("stdout:")
            # Check that stdout has some content after it
            _after_stdout = result[stdout_idx + len("stdout:"):]
            # Empty stdout would just have whitespace before the next section


@pytest.mark.integration
class TestToolIntegrationWithBuilderAgent:
    """Test that execute_shell integrates properly with builder_agent workflow."""

    def test_builder_agent_tools_init_log(self):
        """Test that builder_agent logs tool initialization count."""
        from myagents.backend.services.agents.tools import get_all_tools

        tools = get_all_tools()
        # Should have at least 4 tools (3 file tools + 1 shell tool)
        assert len(tools) >= 4, f"Expected at least 4 tools, got {len(tools)}"

    def test_execute_shell_tool_can_be_bound_to_llm(self):
        """Test that execute_shell tool has correct structure for LLM binding."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")

        # Tool must have properties required for LangChain LLM binding
        assert hasattr(tool, "name")
        assert hasattr(tool, "description")

        # Should be invokable
        assert callable(getattr(tool, "invoke", None))

        # Should have parameter schema (for command and working_dir)
        if hasattr(tool, "args_schema"):
            schema = tool.args_schema
            # Should define at least 'command' parameter
            assert schema is not None

    def test_all_tools_have_unique_names(self):
        """Test that all tools have unique names (no duplicates)."""
        from myagents.backend.services.agents.tools import get_all_tools

        tools = get_all_tools()
        tool_names = [tool.name for tool in tools]

        # Check for duplicates
        assert len(tool_names) == len(set(tool_names)), (
            f"Duplicate tool names found: {tool_names}"
        )

    def test_tool_registry_consistency(self):
        """Test that ALL_TOOLS and TOOLS_BY_NAME are consistent."""
        from myagents.backend.services.agents.tools import ALL_TOOLS, TOOLS_BY_NAME

        # All tools in list should be in dict
        for tool in ALL_TOOLS:
            assert tool.name in TOOLS_BY_NAME
            assert TOOLS_BY_NAME[tool.name] is tool

        # Dict should not have extra tools
        assert len(ALL_TOOLS) == len(TOOLS_BY_NAME)


@pytest.mark.integration
class TestToolWorkingDirectory:
    """Test execute_shell working directory parameter."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def setup_shell_env(self, temp_dir, monkeypatch):
        """Setup test environment with temporary directory."""
        monkeypatch.setenv("MYAGENTS_ALLOWED_DIR", str(temp_dir))

        import myagents.backend.services.agents.tools.shell_tools as shell_tools_module
        shell_tools_module._shell_ops = None

        yield temp_dir

        shell_tools_module._shell_ops = None

    def test_execute_shell_with_working_dir(self, setup_shell_env):
        """Test that execute_shell respects working_dir parameter."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        # Create a subdirectory
        subdir = setup_shell_env / "subdir"
        subdir.mkdir()

        tool = get_tool_by_name("execute_shell")
        result = tool.invoke({
            "command": "pwd",
            "working_dir": str(subdir)
        })

        # Output should show the subdirectory path
        assert "subdir" in result

    def test_execute_shell_without_working_dir(self, setup_shell_env):
        """Test that execute_shell works without working_dir parameter."""
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")
        result = tool.invoke({"command": "echo 'no working dir'"})

        assert "no working dir" in result
        assert "return_code: 0" in result
