"""Tool-level tests for execute_shell tool.

Tests that the execute_shell tool correctly:
1. Can be retrieved via get_tool_by_name
2. Executes commands and returns formatted string with stdout, stderr, return_code
3. Handles errors and returns readable error messages
"""

import pytest
from myagents.backend.services.agents.tools import get_tool_by_name


@pytest.mark.integration
class TestExecuteShellToolRetrieval:
    """Test execute_shell tool can be retrieved and has correct properties."""

    def test_tool_retrieval(self):
        """Test tool can be retrieved via get_tool_by_name('execute_shell')."""
        tool = get_tool_by_name('execute_shell')
        assert tool is not None
        assert tool.name == 'execute_shell'

    def test_tool_has_description(self):
        """Test that execute_shell has a description for LLM binding."""
        tool = get_tool_by_name('execute_shell')
        assert hasattr(tool, "description")
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0

    def test_tool_has_invoke_method(self):
        """Test that execute_shell has invoke method."""
        tool = get_tool_by_name('execute_shell')
        assert hasattr(tool, "invoke")
        assert callable(tool.invoke)


@pytest.mark.integration
class TestExecuteShellToolInvocation:
    """Test execute_shell tool invocation and output formatting."""

    def test_tool_invocation_basic(self):
        """Test tool invocation executes commands and returns formatted string."""
        tool = get_tool_by_name('execute_shell')
        result = tool.invoke({"command": "echo hello"})
        assert "hello" in result
        assert "return_code: 0" in result

    def test_tool_invocation_stdout_format(self):
        """Test that stdout is properly formatted in output."""
        tool = get_tool_by_name('execute_shell')
        result = tool.invoke({"command": "echo test output"})
        assert "stdout:" in result
        assert "test output" in result

    def test_tool_invocation_multiple_lines(self):
        """Test output with multiple lines."""
        tool = get_tool_by_name('execute_shell')
        result = tool.invoke({"command": "printf 'line1\\nline2\\nline3'"})
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result
        assert "return_code: 0" in result

    def test_tool_invocation_with_working_dir(self):
        """Test tool invocation with working_dir parameter."""
        tool = get_tool_by_name('execute_shell')
        # Use tests directory which is within the allowed directory (worktree root)
        result = tool.invoke({"command": "pwd", "working_dir": "tests"})
        assert "tests" in result
        assert "return_code: 0" in result


@pytest.mark.integration
class TestExecuteShellToolErrorHandling:
    """Test execute_shell tool error handling."""

    def test_tool_error_handling_nonexistent_command(self):
        """Test tool error handling returns readable error messages."""
        tool = get_tool_by_name('execute_shell')
        result = tool.invoke({"command": "nonexistent_command_xyz123"})
        # Should have non-zero return code
        assert "return_code:" in result
        # Return code should not be 0
        assert "return_code: 0" not in result

    def test_tool_error_handling_stderr_format(self):
        """Test that stderr is properly formatted in output."""
        tool = get_tool_by_name('execute_shell')
        # Command that writes to stderr
        result = tool.invoke({"command": "ls /nonexistent_directory_xyz123"})
        assert "stderr:" in result
        assert "return_code:" in result
        assert "return_code: 0" not in result

    def test_tool_error_handling_exit_code(self):
        """Test that exit codes are captured."""
        tool = get_tool_by_name('execute_shell')
        result = tool.invoke({"command": "exit 42"})
        assert "return_code: 42" in result

    def test_tool_error_handling_failed_command(self):
        """Test handling of command that returns failure status."""
        tool = get_tool_by_name('execute_shell')
        result = tool.invoke({"command": "false"})
        assert "return_code: 1" in result


@pytest.mark.integration
class TestExecuteShellToolLLMBinding:
    """Test that execute_shell tool is properly configured for LLM binding."""

    def test_tool_can_be_imported_from_tools_module(self):
        """Test that execute_shell can be imported from tools module."""
        from myagents.backend.services.agents.tools import get_tool_by_name
        tool = get_tool_by_name('execute_shell')
        assert tool is not None

    def test_tool_in_all_tools(self):
        """Test that execute_shell is included in ALL_TOOLS."""
        from myagents.backend.services.agents.tools import ALL_TOOLS
        tool_names = [tool.name for tool in ALL_TOOLS]
        assert 'execute_shell' in tool_names

    def test_tool_in_tools_by_name(self):
        """Test that execute_shell is in TOOLS_BY_NAME mapping."""
        from myagents.backend.services.agents.tools import TOOLS_BY_NAME
        assert 'execute_shell' in TOOLS_BY_NAME
        assert TOOLS_BY_NAME['execute_shell'].name == 'execute_shell'
