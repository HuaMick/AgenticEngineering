from langchain_core.tools import tool
from myagents.backend.services.agents.domains.shell_operations import ShellOperations

# Lazy initialization to respect MYAGENTS_ALLOWED_DIR set by conftest
_shell_ops = None


def _get_shell_ops():
    """Get ShellOperations instance, initializing lazily."""
    global _shell_ops
    if _shell_ops is None:
        _shell_ops = ShellOperations()
    return _shell_ops


@tool
def execute_shell(command: str, working_dir: str | None = None) -> str:
    """Execute a shell command and return the output. Returns stdout, stderr, and return code."""
    result = _get_shell_ops().execute_shell(command, working_dir)

    # Format result as readable string
    output_parts = []
    if result["stdout"]:
        output_parts.append(f"stdout:\n{result['stdout']}")
    if result["stderr"]:
        output_parts.append(f"stderr:\n{result['stderr']}")
    output_parts.append(f"return_code: {result['returncode']}")

    return "\n".join(output_parts)


# Tool Registry - single source of truth
ALL_TOOLS = [execute_shell]
TOOLS_BY_NAME = {tool.name: tool for tool in ALL_TOOLS}


def get_all_tools():
    """Get all tools for LLM binding."""
    return ALL_TOOLS


def get_tool_by_name(tool_name: str):
    """Get a specific tool by name for execution."""
    if tool_name not in TOOLS_BY_NAME:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOLS_BY_NAME[tool_name]
