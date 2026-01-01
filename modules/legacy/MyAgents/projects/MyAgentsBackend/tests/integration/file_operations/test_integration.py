"""Integration and end-to-end tests for file operations workflow.

Consolidates workflow integration and e2e tests using parametrization.
Tests complete workflows from agent request to domain execution.
"""

import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Skip if dependencies not available
try:
    from myagents.backend.services.agents.workflows.builder_agent import create_builder_agent, run_builder_agent
    from myagents.backend.services.agents.workflows.secrets_workflow import get_secret
    from myagents.backend.services.agents.tools.file_tools import get_all_tools
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    _import_error = None
except ImportError as e:
    _import_error = e


def get_worktree_root() -> Path:
    """Get the root directory of the current git worktree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        # Fallback for Docker environment
        current_dir = Path.cwd()
        if (current_dir / "pyproject.toml").exists():
            return current_dir
        raise


def setup_api_key():
    """Ensure API key is in environment for Gemini."""
    if _import_error:
        raise _import_error
    try:
        gemini_key = get_secret("GEMINI_API_KEY")
    except ValueError:
        gemini_key = get_secret("GOOGLE_API_KEY")
    os.environ["GEMINI_API_KEY"] = gemini_key


@pytest.mark.integration
@pytest.mark.skipif(_import_error is not None, reason="Dependencies not available")
class TestWorkflowToolBinding:
    """Test that workflow can bind and use tools."""

    @patch('myagents.backend.services.agents.workflows.builder_agent.get_secret')
    @patch('myagents.backend.services.agents.workflows.builder_agent.ChatGoogleGenerativeAI')
    def test_workflow_binds_tools_to_llm(self, mock_llm_class, mock_get_secret):
        """Test that workflow correctly binds tools to LLM."""
        mock_get_secret.return_value = "fake-api-key"
        mock_llm = Mock()
        mock_llm_with_tools = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm_with_tools)
        mock_llm_class.return_value = mock_llm

        create_builder_agent()

        mock_llm_class.assert_called_once()
        call_kwargs = mock_llm_class.call_args[1]
        assert call_kwargs['google_api_key'] == "fake-api-key"

        mock_llm.bind_tools.assert_called_once()
        bound_tools = mock_llm.bind_tools.call_args[0][0]
        assert len(bound_tools) == 11  # 6 file + 1 shell + 4 git tools

    @patch('myagents.backend.services.agents.workflows.builder_agent.get_secret')
    @patch('myagents.backend.services.agents.workflows.builder_agent.ChatGoogleGenerativeAI')
    @pytest.mark.parametrize("tool_name,setup_file,file_content", [
        ("read_file", "test.txt", "Hello World"),
        ("list_files", None, None),
    ])
    def test_workflow_executes_tool_calls(self, mock_llm_class, mock_get_secret, temp_dir, monkeypatch,
                                         tool_name, setup_file, file_content):
        """Test that workflow can execute tool calls from LLM response."""
        from myagents.backend.services.agents.domains.file_operations import FileOperations
        test_ops = FileOperations(allowed_dir=temp_dir)
        monkeypatch.setattr('myagents.backend.services.agents.tools.file_tools._file_ops', test_ops)

        if setup_file:
            test_file = temp_dir / setup_file
            test_file.write_text(file_content)

        mock_get_secret.return_value = "fake-api-key"
        mock_llm = Mock()
        mock_llm_with_tools = Mock()

        tool_args = {"path": setup_file} if tool_name == "read_file" else {"path": "."}
        tool_call_response = AIMessage(
            content="",
            tool_calls=[{
                "name": tool_name,
                "args": tool_args,
                "id": "call_123"
            }]
        )
        final_response = AIMessage(content="Task completed")

        mock_llm_with_tools.invoke = Mock(side_effect=[tool_call_response, final_response])
        mock_llm.bind_tools = Mock(return_value=mock_llm_with_tools)
        mock_llm_class.return_value = mock_llm

        workflow = create_builder_agent()
        result = workflow.invoke({
            "user_input": f"Execute {tool_name}",
            "messages": [],
            "response": "",
            "iteration_count": 0
        })

        assert "response" in result
        assert mock_llm_with_tools.invoke.call_count == 2


@pytest.mark.integration
@pytest.mark.skipif(_import_error is not None, reason="Dependencies not available")
class TestWorkflowErrorHandling:
    """Test that workflow properly handles tool execution errors."""

    @patch('myagents.backend.services.agents.workflows.builder_agent.get_secret')
    @patch('myagents.backend.services.agents.workflows.builder_agent.ChatGoogleGenerativeAI')
    @pytest.mark.parametrize("error_scenario,tool_args,error_keywords", [
        ("file_not_found", {"path": "nonexistent.txt"}, ["not found"]),
        ("invalid_path", {"path": "/etc/passwd"}, []),
    ])
    def test_workflow_handles_errors(self, mock_llm_class, mock_get_secret, temp_dir, monkeypatch,
                                     error_scenario, tool_args, error_keywords):
        """Test that workflow handles various error scenarios gracefully."""
        from myagents.backend.services.agents.domains.file_operations import FileOperations
        test_ops = FileOperations(allowed_dir=temp_dir)
        monkeypatch.setattr('myagents.backend.services.agents.tools.file_tools._file_ops', test_ops)

        mock_get_secret.return_value = "fake-api-key"
        mock_llm = Mock()
        mock_llm_with_tools = Mock()

        tool_call_response = AIMessage(
            content="",
            tool_calls=[{
                "name": "read_file",
                "args": tool_args,
                "id": "call_123"
            }]
        )
        final_response = AIMessage(content="Error handled")

        mock_llm_with_tools.invoke = Mock(side_effect=[tool_call_response, final_response])
        mock_llm.bind_tools = Mock(return_value=mock_llm_with_tools)
        mock_llm_class.return_value = mock_llm

        workflow = create_builder_agent()
        result = workflow.invoke({
            "user_input": "Read file",
            "messages": [],
            "response": "",
            "iteration_count": 0
        })

        assert "response" in result
        messages = result["messages"]
        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
        assert len(tool_messages) > 0
        if error_keywords:
            assert any(keyword in str(m.content).lower() for m in tool_messages for keyword in error_keywords)


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.costly
@pytest.mark.skipif(_import_error is not None, reason="Dependencies not available")
class TestE2EFileOperations:
    """End-to-end tests for file operations workflow."""

    @pytest.mark.parametrize("operation,file_content,expected_keywords", [
        ("read", "Hello from E2E test!", ["hello", "e2e"]),
        ("large_file", "x" * 50_000, []),  # Reduced from 200k to avoid OS arg limit
    ])
    def test_agent_file_operations(self, operation, file_content, expected_keywords):
        """Test complete workflow for file operations."""
        setup_api_key()

        test_file_rel = Path(f"test_data/{operation}_test.txt")
        test_file_abs = get_worktree_root() / test_file_rel
        test_file_abs.parent.mkdir(parents=True, exist_ok=True)

        if operation != "missing_file":
            test_file_abs.write_text(file_content)

        try:
            response, state = run_builder_agent(f"Read the file at {test_file_rel}")

            assert response is not None
            assert len(response) > 0
            assert "messages" in state
            assert len(state["messages"]) > 0

        finally:
            if test_file_abs.parent.exists():
                shutil.rmtree(test_file_abs.parent)

    def test_agent_handles_missing_file(self):
        """Test workflow handles missing file gracefully."""
        setup_api_key()

        test_file_rel = Path("test_data/nonexistent.txt")
        response, state = run_builder_agent(f"Read the file at {test_file_rel}")

        assert response is not None
        response_text = " ".join(str(r) for r in response) if isinstance(response, list) else str(response)
        response_lower = response_text.lower()
        assert any(word in response_lower for word in [
            "not found", "doesn't exist", "does not exist", "no such file",
            "error", "cannot", "unable", "missing", "couldn't find"
        ])

    @pytest.mark.parametrize("operation,setup_files", [
        ("list", ["file1.txt", "file2.txt"]),
        ("edit", ["edit_test.txt"]),
    ])
    def test_agent_directory_operations(self, operation, setup_files):
        """Test directory and editing operations."""
        setup_api_key()

        test_dir_rel = Path(f"test_data/{operation}_test")
        test_dir_abs = get_worktree_root() / test_dir_rel
        test_dir_abs.mkdir(parents=True, exist_ok=True)

        for filename in setup_files:
            (test_dir_abs / filename).write_text("Original content" if operation == "edit" else "content")

        try:
            if operation == "list":
                response, state = run_builder_agent(f"List the files in {test_dir_rel}")
            else:  # edit
                response, state = run_builder_agent(
                    f"In the file {test_dir_rel / setup_files[0]}, replace 'Original' with 'Modified'"
                )

            assert response is not None
            assert len(response) > 0

            if operation == "edit":
                updated_content = (test_dir_abs / setup_files[0]).read_text()
                assert "Modified" in updated_content

        finally:
            if test_dir_abs.exists():
                shutil.rmtree(test_dir_abs)


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.costly
@pytest.mark.skipif(_import_error is not None, reason="Dependencies not available")
class TestE2ESecurityAndMultiTool:
    """End-to-end tests for security validation and multi-tool workflows."""

    @pytest.mark.parametrize("invalid_path,expected_keywords", [
        ("/etc/passwd", [
            "error", "denied", "not allowed", "cannot", "unable", "rejected", "invalid", "forbidden", "absolute"
        ]),
        ("../../etc/passwd", [
            "error", "denied", "not allowed", "cannot", "unable", "rejected", "invalid", "forbidden", "traversal"
        ]),
    ])
    def test_agent_rejects_security_violations(self, invalid_path, expected_keywords):
        """Test that agent/domain rejects security violations."""
        setup_api_key()

        response, state = run_builder_agent(f"Read the file at {invalid_path}")

        assert response is not None
        response_text = " ".join(str(r) for r in response) if isinstance(response, list) else str(response)
        response_lower = response_text.lower()
        assert any(word in response_lower for word in expected_keywords)

    @pytest.mark.parametrize("workflow_type,instruction", [
        ("list_then_read", "First list the files in test_data/multi_tool, then read the target.txt file"),
        ("read_then_edit", "Read test_data/read_edit/test.txt, then replace 'Version 1' with 'Version 2'"),
    ])
    def test_multi_tool_workflows(self, workflow_type, instruction):
        """Test workflows using multiple tools in sequence."""
        setup_api_key()

        test_dir_rel = Path(f"test_data/{workflow_type.split('_')[0]}_{'_'.join(workflow_type.split('_')[1:])}")
        test_dir_abs = get_worktree_root() / test_dir_rel
        test_dir_abs.mkdir(parents=True, exist_ok=True)

        if workflow_type == "list_then_read":
            (test_dir_abs / "target.txt").write_text("Target file content")
        else:  # read_then_edit
            (test_dir_abs / "test.txt").write_text("Version 1")

        try:
            response, state = run_builder_agent(instruction)

            assert response is not None
            assert len(response) > 0
            assert "messages" in state

            if workflow_type == "read_then_edit":
                updated_content = (test_dir_abs / "test.txt").read_text()
                assert "Version 2" in updated_content

        finally:
            if test_dir_abs.exists():
                shutil.rmtree(test_dir_abs)
