from myagents.backend.services.agents.tools.file_tools import (
    read_file,
    list_files,
    edit_file,
    ALL_TOOLS as FILE_TOOLS,
    TOOLS_BY_NAME as FILE_TOOLS_BY_NAME,
)
from myagents.backend.services.agents.tools.shell_tools import (
    execute_shell,
    ALL_TOOLS as SHELL_TOOLS,
    TOOLS_BY_NAME as SHELL_TOOLS_BY_NAME,
)
from myagents.backend.services.agents.tools.git_tools import (
    git_repo_root,
    git_status,
    git_diff,
    git_current_branch,
    ALL_TOOLS as GIT_TOOLS,
    TOOLS_BY_NAME as GIT_TOOLS_BY_NAME,
)

# Combine tools from all modules
ALL_TOOLS = FILE_TOOLS + SHELL_TOOLS + GIT_TOOLS
TOOLS_BY_NAME = {**FILE_TOOLS_BY_NAME, **SHELL_TOOLS_BY_NAME, **GIT_TOOLS_BY_NAME}


def get_all_tools():
    """Get all tools for LLM binding."""
    return ALL_TOOLS


def get_tool_by_name(tool_name: str):
    """Get a specific tool by name for execution."""
    if tool_name not in TOOLS_BY_NAME:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOLS_BY_NAME[tool_name]
