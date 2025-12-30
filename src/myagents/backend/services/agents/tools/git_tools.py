from langchain_core.tools import tool
from myagents.backend.services.agents.domains.git_operations import GitOperations

# Lazy initialization to respect MYAGENTS_ALLOWED_DIR set by conftest
_git_ops = None


def _get_git_ops():
    """Get GitOperations instance, initializing lazily."""
    global _git_ops
    if _git_ops is None:
        _git_ops = GitOperations()
    return _git_ops


@tool
def git_repo_root(path: str = ".") -> str:
    """Get the git repository root directory for a given path."""
    return _get_git_ops().get_repo_root(path)


@tool
def git_status(path: str = ".") -> str:
    """Get git status showing modified, added, deleted, and untracked files."""
    status = _get_git_ops().get_status(path)
    # Format as string
    lines = []
    if status["modified"]:
        lines.append(f"Modified: {', '.join(status['modified'])}")
    if status["added"]:
        lines.append(f"Added: {', '.join(status['added'])}")
    if status["deleted"]:
        lines.append(f"Deleted: {', '.join(status['deleted'])}")
    if status["untracked"]:
        lines.append(f"Untracked: {', '.join(status['untracked'])}")
    return "\n".join(lines) if lines else "No changes"


@tool
def git_diff(path: str = ".", file_path: str | None = None) -> str:
    """Get git diff for the repository or a specific file."""
    return _get_git_ops().get_diff(path, file_path)


@tool
def git_current_branch(path: str = ".") -> str:
    """Get the name of the current git branch."""
    return _get_git_ops().get_current_branch(path)


# Tool Registry - single source of truth
ALL_TOOLS = [git_repo_root, git_status, git_diff, git_current_branch]
TOOLS_BY_NAME = {tool.name: tool for tool in ALL_TOOLS}


def get_all_tools():
    """Get all tools for LLM binding."""
    return ALL_TOOLS


def get_tool_by_name(tool_name: str):
    """Get a specific tool by name for execution."""
    if tool_name not in TOOLS_BY_NAME:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOLS_BY_NAME[tool_name]
