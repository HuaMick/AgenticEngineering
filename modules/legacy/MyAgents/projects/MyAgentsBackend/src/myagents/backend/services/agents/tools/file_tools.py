from langchain_core.tools import tool
from myagents.backend.services.agents.domains.file_operations import FileOperations

# Lazy initialization to respect MYAGENTS_ALLOWED_DIR set by conftest
_file_ops = None


def _get_file_ops():
    """Get FileOperations instance, initializing lazily."""
    global _file_ops
    if _file_ops is None:
        _file_ops = FileOperations()
    return _file_ops


@tool
def read_file(path: str) -> str:
    """Read file contents. Basic implementation."""
    return _get_file_ops().read_file(path)


@tool
def list_files(path: str) -> list:
    """List files in directory."""
    return _get_file_ops().list_files(path)


@tool
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit file by replacing old_text with new_text."""
    return _get_file_ops().edit_file(path, old_text, new_text)


@tool
def create_file(path: str, content: str) -> str:
    """Create a new file with specified content. Raises error if file already exists."""
    return _get_file_ops().create_file(path, content)


@tool
def search_in_files(pattern: str, directory: str = ".", file_pattern: str = "*") -> str:
    """Search for text pattern in files. Returns matches with file paths and line numbers."""
    results = _get_file_ops().search_in_files(pattern, directory, file_pattern)
    if not results:
        return f"No matches found for '{pattern}'"
    lines = []
    for match in results:
        lines.append(f"{match['file']}:{match['line_number']}: {match['line']}")
    return "\n".join(lines)


@tool
def find_files(name_pattern: str, directory: str = ".") -> str:
    """Find files matching name pattern (supports glob patterns like *.py)."""
    results = _get_file_ops().find_files(name_pattern, directory)
    if not results:
        return f"No files found matching '{name_pattern}'"
    return "\n".join(results)


# Tool Registry - single source of truth
ALL_TOOLS = [read_file, list_files, edit_file, create_file, search_in_files, find_files]
TOOLS_BY_NAME = {tool.name: tool for tool in ALL_TOOLS}


def get_all_tools():
    """Get all tools for LLM binding."""
    return ALL_TOOLS


def get_tool_by_name(tool_name: str):
    """Get a specific tool by name for execution."""
    if tool_name not in TOOLS_BY_NAME:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOLS_BY_NAME[tool_name]
