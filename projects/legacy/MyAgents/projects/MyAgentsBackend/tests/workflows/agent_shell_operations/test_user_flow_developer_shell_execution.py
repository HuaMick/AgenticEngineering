"""User flow tests for US-001: Developer using shell execution.

This test simulates the user journey of a developer trying to execute shell
commands through the coding agent. It tests the complete flow following
documentation only (agent-blind-test strategy).

Test Journey:
1. Read documentation to understand how to use the coding agent
2. Start coding agent conversation (or simulate tool usage)
3. Ask agent to "run pwd to check current directory"
4. Ask agent to "run git status to see repository state"
5. Ask agent to "list files in current directory"

User Story:
- Starting State: Coding agent deployed with execute_shell tool available
- User Goal: Execute shell commands like pwd, ls, git status through the coding agent
- Expected Outcome: Commands execute successfully with output returned to user
"""

import pytest
import os
from pathlib import Path


class TestDeveloperShellExecutionUserFlow:
    """Test user flow for developer executing shell commands through coding agent."""

    @pytest.fixture
    def worktree_root(self):
        """Get worktree root for shell operations.

        Uses MYAGENTS_ALLOWED_DIR set by conftest.py which determines
        the worktree root dynamically from the test file location.
        """
        return Path(os.environ.get("MYAGENTS_ALLOWED_DIR", Path(__file__).parent.parent.parent.parent))

    def test_step1_documentation_provides_shell_execution_guidance(self, worktree_root):
        """Step 1: User reads documentation to understand shell execution.

        Agent-blind-test: Check if documentation tells user about execute_shell capability.
        The README and usage.md should mention shell execution is available.
        """
        readme_path = worktree_root / "README.md"
        usage_path = worktree_root / "docs" / "guides" / "usage.md"

        # Check README for shell execution documentation
        readme_content = readme_path.read_text()
        usage_content = usage_path.read_text()

        # The documentation should NOT say "No bash/shell execution" if the feature exists
        readme_has_limitation = "No bash/shell execution" in readme_content
        usage_has_limitation = "No bash/shell execution" in usage_content

        # Check if documentation mentions execute_shell or shell execution as a capability
        readme_mentions_shell = any(term in readme_content.lower() for term in
                                     ["execute_shell", "shell command", "shell execution", "run command"])
        usage_mentions_shell = any(term in usage_content.lower() for term in
                                    ["execute_shell", "shell command", "shell execution", "run command"])

        # Documentation gap: if limitation exists but feature is available
        if readme_has_limitation or usage_has_limitation:
            pytest.fail(
                "DOCUMENTATION GAP: README and/or usage.md state 'No bash/shell execution' as a limitation, "
                "but execute_shell tool exists. User following docs would not know this capability exists.\n"
                f"README has limitation: {readme_has_limitation}\n"
                f"Usage.md has limitation: {usage_has_limitation}\n"
                "Expected: Documentation should mention execute_shell as an available tool.\n"
                "Recommendation: Remove shell execution from limitations and add to features."
            )

        # Documentation should also mention the capability positively
        if not (readme_mentions_shell or usage_mentions_shell):
            pytest.fail(
                "DOCUMENTATION GAP: Neither README nor usage.md mention shell execution capability.\n"
                "User following docs would not know execute_shell tool is available.\n"
                f"README mentions shell: {readme_mentions_shell}\n"
                f"Usage.md mentions shell: {usage_mentions_shell}\n"
                "Expected: Documentation should describe how to use shell execution.\n"
                "Recommendation: Add examples like 'run pwd' or 'run git status'."
            )

    def test_step2_execute_shell_tool_is_available(self):
        """Step 2: Verify execute_shell tool is available in coding agent.

        User starts coding agent and the execute_shell tool should be accessible.
        """
        from myagents.backend.services.agents.tools import get_all_tools, get_tool_by_name

        # Get all tools
        all_tools = get_all_tools()
        tool_names = [tool.name for tool in all_tools]

        # execute_shell should be in the tools list
        assert "execute_shell" in tool_names, (
            f"UNEXPECTED BEHAVIOR: execute_shell tool not found in available tools.\n"
            f"Available tools: {tool_names}\n"
            f"Expected: execute_shell should be available for coding agent.\n"
            f"User would not be able to execute shell commands."
        )

        # Verify tool can be retrieved by name
        tool = get_tool_by_name("execute_shell")
        assert tool is not None, "execute_shell tool cannot be retrieved by name"
        assert tool.name == "execute_shell", f"Tool name mismatch: {tool.name}"

    def test_step3_run_pwd_to_check_current_directory(self, worktree_root):
        """Step 3: User asks agent to run pwd to check current directory.

        Simulates: "run pwd to check current directory"
        """
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")

        # Execute pwd command
        result = tool.invoke({"command": "pwd", "working_dir": str(worktree_root)})

        # Verify result is useful
        assert result is not None, "COMMAND FAILURE: pwd returned None"
        assert isinstance(result, str), f"UNEXPECTED BEHAVIOR: Result should be string, got {type(result)}"

        # Result should contain stdout with the directory path
        assert "stdout:" in result, (
            f"UNEXPECTED BEHAVIOR: Result format doesn't include 'stdout:'\n"
            f"Actual result: {result}\n"
            f"Expected: Output should show stdout: with directory path"
        )

        # The working directory should be in the output
        assert str(worktree_root) in result or "MyAgents-staging" in result, (
            f"UNEXPECTED BEHAVIOR: pwd output doesn't show expected directory\n"
            f"Actual result: {result}\n"
            f"Expected: Should contain '{worktree_root}' or 'MyAgents-staging'"
        )

        # Return code should be 0 (success)
        assert "return_code: 0" in result, (
            f"COMMAND FAILURE: pwd command did not succeed\n"
            f"Actual result: {result}\n"
            f"Expected: return_code: 0"
        )

    def test_step4_run_git_status_to_see_repository_state(self, worktree_root):
        """Step 4: User asks agent to run git status to see repository state.

        Simulates: "run git status to see repository state"
        """
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")

        # Execute git status command
        result = tool.invoke({"command": "git status", "working_dir": str(worktree_root)})

        # Verify result is useful
        assert result is not None, "COMMAND FAILURE: git status returned None"
        assert isinstance(result, str), f"UNEXPECTED BEHAVIOR: Result should be string, got {type(result)}"

        # Result should contain meaningful git output
        # Could be clean branch, changes, or "not a git repository" - all are valid
        has_git_output = any(term in result.lower() for term in [
            "branch", "commit", "modified", "untracked", "clean",
            "changes", "git repository", "on branch"
        ])

        # If it's a git repo, we should see some git-specific output
        # If not a git repo, we should see an error about that
        is_meaningful = has_git_output or "return_code:" in result

        assert is_meaningful, (
            f"UNEXPECTED BEHAVIOR: git status output is not meaningful\n"
            f"Actual result: {result}\n"
            f"Expected: Git branch info, changes, or 'not a git repository' message"
        )

    def test_step5_list_files_in_current_directory(self, worktree_root):
        """Step 5: User asks agent to list files in current directory.

        Simulates: "list files in current directory"
        Note: This tests the execute_shell tool with ls command.
        The coding agent also has a list_files tool, but user asking to
        "list files" might expect shell ls to work too.
        """
        from myagents.backend.services.agents.tools import get_tool_by_name

        tool = get_tool_by_name("execute_shell")

        # Execute ls command
        result = tool.invoke({"command": "ls -la", "working_dir": str(worktree_root)})

        # Verify result is useful
        assert result is not None, "COMMAND FAILURE: ls returned None"
        assert isinstance(result, str), f"UNEXPECTED BEHAVIOR: Result should be string, got {type(result)}"

        # Result should contain stdout with file listing
        assert "stdout:" in result, (
            f"UNEXPECTED BEHAVIOR: Result format doesn't include 'stdout:'\n"
            f"Actual result: {result}"
        )

        # Should show common project files
        expected_files = ["README.md", "pyproject.toml", "backend", "tests", "src"]
        files_found = [f for f in expected_files if f in result]

        assert len(files_found) >= 3, (
            f"UNEXPECTED BEHAVIOR: ls output doesn't show expected project files\n"
            f"Actual result: {result}\n"
            f"Expected some of: {expected_files}\n"
            f"Found: {files_found}"
        )

        # Return code should be 0 (success)
        assert "return_code: 0" in result, (
            f"COMMAND FAILURE: ls command did not succeed\n"
            f"Actual result: {result}"
        )


class TestDeveloperShellExecutionEndToEnd:
    """End-to-end test simulating complete user journey."""

    def test_complete_user_journey(self):
        """Complete user journey from reading docs to executing commands.

        This test validates the entire flow a developer would follow.
        """
        from pathlib import Path
        from myagents.backend.services.agents.tools import get_tool_by_name, get_all_tools

        # Use environment variable set by conftest.py for worktree root
        worktree_root = Path(os.environ.get("MYAGENTS_ALLOWED_DIR", Path(__file__).parent.parent.parent.parent))
        failures = []

        # Step 1: Check documentation (this will fail if docs haven't been updated)
        readme_path = worktree_root / "README.md"
        readme_content = readme_path.read_text()
        if "No bash/shell execution" in readme_content:
            failures.append({
                "step": "Step 1: Documentation",
                "failure_type": "documentation_gap",
                "description": "README states shell execution is not available",
                "expected": "Documentation should mention execute_shell tool",
                "actual": "Documentation says 'No bash/shell execution'"
            })

        # Step 2: Verify tool availability
        try:
            tool = get_tool_by_name("execute_shell")
            if tool is None:
                failures.append({
                    "step": "Step 2: Tool availability",
                    "failure_type": "command_failure",
                    "description": "execute_shell tool not found",
                    "expected": "Tool should be available",
                    "actual": "get_tool_by_name returned None"
                })
        except Exception as e:
            failures.append({
                "step": "Step 2: Tool availability",
                "failure_type": "command_failure",
                "description": f"Error getting execute_shell tool: {e}",
                "expected": "Tool should be retrievable",
                "actual": str(e)
            })

        # Step 3: Run pwd
        if not any(f["step"].startswith("Step 2") for f in failures):
            try:
                result = tool.invoke({"command": "pwd", "working_dir": str(worktree_root)})
                if "return_code: 0" not in result:
                    failures.append({
                        "step": "Step 3: Run pwd",
                        "failure_type": "command_failure",
                        "description": "pwd command failed",
                        "expected": "return_code: 0",
                        "actual": result
                    })
            except Exception as e:
                failures.append({
                    "step": "Step 3: Run pwd",
                    "failure_type": "command_failure",
                    "description": f"Exception running pwd: {e}",
                    "expected": "Command should execute successfully",
                    "actual": str(e)
                })

        # Step 4: Run git status
        if not any(f["step"].startswith("Step 2") for f in failures):
            try:
                result = tool.invoke({"command": "git status", "working_dir": str(worktree_root)})
                # Git status might fail if not a repo, but should still execute
                if result is None:
                    failures.append({
                        "step": "Step 4: Run git status",
                        "failure_type": "command_failure",
                        "description": "git status returned None",
                        "expected": "Command output even if not a git repo",
                        "actual": "None"
                    })
            except Exception as e:
                failures.append({
                    "step": "Step 4: Run git status",
                    "failure_type": "command_failure",
                    "description": f"Exception running git status: {e}",
                    "expected": "Command should execute",
                    "actual": str(e)
                })

        # Step 5: List files
        if not any(f["step"].startswith("Step 2") for f in failures):
            try:
                result = tool.invoke({"command": "ls", "working_dir": str(worktree_root)})
                if "return_code: 0" not in result:
                    failures.append({
                        "step": "Step 5: List files",
                        "failure_type": "command_failure",
                        "description": "ls command failed",
                        "expected": "return_code: 0",
                        "actual": result
                    })
            except Exception as e:
                failures.append({
                    "step": "Step 5: List files",
                    "failure_type": "command_failure",
                    "description": f"Exception running ls: {e}",
                    "expected": "Command should execute successfully",
                    "actual": str(e)
                })

        # Report results
        if failures:
            failure_report = "\n\n".join([
                f"FAILURE at {f['step']}\n"
                f"  Type: {f['failure_type']}\n"
                f"  Description: {f['description']}\n"
                f"  Expected: {f['expected']}\n"
                f"  Actual: {f['actual']}"
                for f in failures
            ])
            pytest.fail(f"User flow failures:\n\n{failure_report}")
