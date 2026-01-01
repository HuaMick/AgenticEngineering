# MyAgents CLI Architecture

This document describes the CLI architecture, focusing on the separation between global and project-scoped commands.

## Overview

The MyAgents CLI supports two types of commands:

1. **Global commands**: Work from any directory, operate on CLI installation
2. **Project commands**: Require a MyAgents project (langgraph.json)

## Architecture Components

### Entry Point (`entry.py`)

The entry point handles command routing and context detection. It contains three key detection functions:

#### `detect_cli_source_root()`

Detects where the CLI itself is installed (not where a project is located).

```python
def detect_cli_source_root() -> Path:
    """Detect CLI installation location via __file__.

    Returns:
        Path: Absolute path to CLI source root (where pyproject.toml is)
    """
    # __file__ points to frontend/cli/entry.py
    # Navigate up: frontend/cli/entry.py -> frontend -> cli -> MyAgents
    cli_file = Path(__file__).resolve()
    return cli_file.parent.parent.parent
```

**Purpose**: Used for global commands (update, rebuild) that need to operate on the CLI installation itself, regardless of current directory.

**Example**: If CLI is installed at `/usr/local/lib/python3.x/site-packages/myagents/`, this function returns that location.

#### `detect_project_root()`

Walks up the directory tree from current working directory to find `langgraph.json`.

```python
def detect_project_root(required: bool = True) -> Path | None:
    """Detect project root by looking for langgraph.json.

    Args:
        required: If True, raise error when not found. If False, return None.

    Returns:
        Path: Absolute path to project root, or None if not found and not required

    Raises:
        RuntimeError: If langgraph.json cannot be found and required=True
    """
```

**Purpose**: Used for project-scoped commands (chat, studio, preferences) that need a MyAgents project context.

#### `detect_config_path()`

Multi-level fallback for config file detection:

1. `~/.config/myagents/config.yml` (home directory, single source of truth)
2. `project_root/config.yml` (legacy fallback)
3. `project_root/.myagents/config.yml` (legacy fallback)

**Purpose**: Uses home directory config as primary location, with legacy fallbacks for backwards compatibility.

## Command Routing Logic

The `main()` function in `entry.py` implements command routing:

```python
def main():
    """Entry point for CLI.

    Routes commands to appropriate detection logic:
    - Global commands (update, rebuild, version): Use CLI source root
    - Project commands (chat, studio, preferences): Use project root
    """
    # Handle --version flag (global command)
    if "--version" in sys.argv or "-v" in sys.argv:
        # ... print version and exit

    # Define global commands
    global_commands = {"update", "rebuild"}

    # Parse command from argv
    command = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            command = arg
            break

    # Route based on command type
    if command in global_commands:
        # Global: Use CLI source root, no config needed
        source_root = detect_cli_source_root()
        run_cli(source_root, config_path=None, is_global=True)
    else:
        # Project: Use project root and detect config
        project_root = detect_project_root(required=True)
        config_path = detect_config_path(project_root)
        run_cli(project_root, config_path, is_global=False)
```

## Command Categories

### Global Commands

Commands that work from any directory without requiring a project:

- `myagents --version` / `myagents -v`: Show CLI version
- `myagents update`: Reinstall CLI from source
- `myagents rebuild`: Rebuild and reinstall CLI package

**Behavior**:
- Use `detect_cli_source_root()` to find CLI installation
- Do not require `langgraph.json`
- Do not use config file (`config_path=None`)
- Can be run from any directory

### Project Commands

Commands that require a MyAgents project context:

- `myagents chat`: Interactive agent chat
- `myagents studio start/stop/restart/status`: Manage LangGraph Studio
- `myagents preferences get/set/delete/list/clear`: Manage preferences

**Behavior**:
- Use `detect_project_root()` to find project
- Require `langgraph.json` in project root
- Use `detect_config_path()` to find config
- Must be run from within a MyAgents project directory

## CLI Execution Flow

```
user runs `myagents <command>`
    ↓
entry.py:main()
    ↓
Parse command and flags
    ↓
Is command global?
    ├─ YES → detect_cli_source_root()
    │         ↓
    │         run_cli(source_root, None, is_global=True)
    │
    └─ NO  → detect_project_root()
              ↓
              detect_config_path()
              ↓
              run_cli(project_root, config_path, is_global=False)
    ↓
myagents_cli.py:run_cli()
    ↓
Set global variables (project_dir, config_path, is_global_mode)
    ↓
Execute command handler (cmd_*)
```

## Implementation Notes

### Why Separate Global and Project Commands?

1. **User Experience**: Global commands (update, rebuild) should work from anywhere
2. **Context Safety**: Project commands need project context to function correctly
3. **Error Messages**: Clear error when project command run outside project
4. **Installation Independence**: CLI can update itself without needing a project

### Key Design Decisions

1. **Early routing**: Command type determined in `entry.py` before main CLI logic
2. **Single entry point**: All commands go through `entry.py:main()`
3. **Explicit global list**: `global_commands` set makes behavior clear
4. **Path detection over hardcoding**: Uses `__file__` for portability

### Example Use Cases

**Global command from any directory**:
```bash
$ cd /tmp
$ myagents update
Updating myagents from source: /usr/local/lib/python3.x/site-packages/myagents
Successfully updated myagents
```

**Project command from project directory**:
```bash
$ cd /home/user/my-agent-project
$ myagents studio start
Starting LangGraph Studio...
Studio started on port 2024
```

**Project command from wrong directory**:
```bash
$ cd /tmp
$ myagents studio start
Error: Could not find langgraph.json. Please run this command from within the MyAgents project directory.
```

## Development Guidelines

### Adding a New Global Command

1. Add command name to `global_commands` set in `entry.py:main()`
2. Implement handler in `myagents_cli.py` (e.g., `cmd_mycommand`)
3. Use `project_dir` variable (will be CLI source root in global mode)
4. Do not assume `config_path` is available (will be None)

### Adding a New Project Command

1. Implement handler in `myagents_cli.py` (e.g., `cmd_mycommand`)
2. Use `project_dir` variable (will be project root)
3. Use `config_path` variable (will be config file path)
4. Command will automatically require project context

## Related Files

- `frontend/cli/entry.py`: Entry point and detection logic
- `frontend/cli/myagents_cli.py`: Command implementations
- `pyproject.toml`: CLI package configuration and entry point definition
