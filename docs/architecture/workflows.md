# MyAgents Workflow Documentation

This document provides detailed documentation for all workflows in the MyAgents CLI architecture.

## Overview

MyAgents uses a three-layer architecture: **Domain → Workflow → Entrypoint**

- **Domains:** Pure business logic (e.g., preferences storage, studio process management)
- **Workflows:** Orchestration and coordination (e.g., multiple domain calls, error handling)
- **Entrypoints:** User interaction (e.g., CLI argument parsing, output formatting)

The CLI has four core workflows that handle different aspects of functionality:

1. **HealthCheckWorkflow** - CLI infrastructure and root detection
2. **PreferencesWorkflow** - User preference management
3. **StudioWorkflow** - LangGraph Studio lifecycle management
4. **HelpWorkflow** - CLI help and documentation

## HealthCheckWorkflow

### Purpose

Provides health checking and context detection for the MyAgents CLI. This workflow is used internally by the CLI routing system to determine command context and validate the environment.

### Location

`src/myagents/backend/services/agents/workflows/health_check_workflow.py`

### Class Interface

```python
from myagents.backend.services.agents.workflows.health_check_workflow import HealthCheckWorkflow

workflow = HealthCheckWorkflow()
```

### Entrypoints

#### check_cli_health()

Verify CLI installation and return health status.

**Returns:**
- `Dict[str, Any]` with keys:
  - `installed`: bool - Whether CLI is properly installed
  - `source_root`: Path - CLI installation location
  - `version`: str - CLI version (if available)
  - `python_version`: str - Python version being used

**Example:**
```python
workflow = HealthCheckWorkflow()
health = workflow.check_cli_health()

if health["installed"]:
    print(f"CLI {health['version']} installed at {health['source_root']}")
else:
    print(f"CLI not installed: {health['error']}")
```

#### check_project_health(project_root=None)

Verify project context and return health status.

**Args:**
- `project_root`: Optional[Path] - Project root path. If None, attempts detection.

**Returns:**
- `Dict[str, Any]` with keys:
  - `valid`: bool - Whether project context is valid
  - `project_root`: Path - Project root location (if found)
  - `has_langgraph_json`: bool - Whether langgraph.json exists
  - `config_path`: Path - Configuration file path (if found)
  - `error`: str - Error message (if validation failed)

**Example:**
```python
workflow = HealthCheckWorkflow()
health = workflow.check_project_health()

if health["valid"]:
    print(f"Project root: {health['project_root']}")
    print(f"Config: {health['config_path']}")
else:
    print(f"Invalid project: {health['error']}")
```

#### detect_context(command=None)

Combined detection for routing commands to appropriate context. This is the main entrypoint for CLI routing logic.

**Args:**
- `command`: Optional[str] - Command name to determine context requirements

**Returns:**
- `Dict[str, Any]` with keys:
  - `context_type`: str - "global" or "project"
  - `source_root`: Path - CLI installation location (for global commands)
  - `project_root`: Path - Project root location (for project commands)
  - `config_path`: Path - Configuration file path (for project commands)
  - `is_global_command`: bool - Whether this is a global command

**Global commands:** `update`, `rebuild`

**Example:**
```python
workflow = HealthCheckWorkflow()

# Global command context
context = workflow.detect_context(command="update")
# Returns: {"context_type": "global", "source_root": Path(...), ...}

# Project command context
context = workflow.detect_context(command="chat")
# Returns: {"context_type": "project", "project_root": Path(...), "config_path": Path(...), ...}
```

#### validate_environment()

Check prerequisites and environment setup.

**Returns:**
- `Dict[str, Any]` with keys:
  - `valid`: bool - Whether environment is valid
  - `python_version_ok`: bool - Whether Python version is acceptable (3.11+)
  - `venv_active`: bool - Whether virtual environment is active
  - `issues`: List[str] - List of any issues found
  - `warnings`: List[str] - List of non-critical warnings

**Example:**
```python
workflow = HealthCheckWorkflow()
env = workflow.validate_environment()

if not env["valid"]:
    print("Environment issues:")
    for issue in env["issues"]:
        print(f"  - {issue}")

if env["warnings"]:
    print("Warnings:")
    for warning in env["warnings"]:
        print(f"  - {warning}")
```

### Internal Methods

The following methods are used internally by the workflow but can also be called directly:

#### detect_cli_source_root()

Detect CLI installation location via `__file__`.

**Returns:** `Path` - Absolute path to CLI source root

#### detect_project_root(required=True)

Detect project root by looking for langgraph.json.

**Args:**
- `required`: bool - If True, raise error when not found. If False, return None.

**Returns:** `Optional[Path]` - Absolute path to project root, or None if not found and not required

**Raises:** `RuntimeError` - If langgraph.json cannot be found and `required=True`

#### detect_config_path(project_root)

Multi-level fallback for config path detection.

**Priority order:**
1. `project_root/config.yml` (local override)
2. `project_root/.myagents/config.yml` (local override)
3. `~/.config/myagents/config.yml` with `config_path` routing
4. `~/.config/myagents/config.yml` (default home directory)
5. Fallback: Create `~/.config/myagents/config.yml`

**Args:**
- `project_root`: Path - Path to project root directory

**Returns:** `Path` - Absolute path to config file

### Use Cases

1. **Command Routing** - Determine if command is global or project-scoped
2. **Environment Validation** - Verify Python version and virtual environment
3. **Configuration Detection** - Locate config files with multi-level fallback
4. **Root Detection** - Find CLI installation and project directories

## PreferencesWorkflow

### Purpose

Manages user preferences with support for nested keys (dot notation), JSON values, and persistent storage.

### Location

`src/myagents/backend/services/agents/workflows/preferences_workflow.py`

### Class Interface

```python
from myagents.backend.services.agents.workflows.preferences_workflow import PreferencesWorkflow

workflow = PreferencesWorkflow(preferences_file=Path("~/.config/myagents/prefs.json"))
```

### Constructor

```python
def __init__(self, preferences_file: Optional[Path] = None)
```

**Args:**
- `preferences_file`: Optional[Path] - Path to preferences file. If None, uses default location.

### Entrypoints

#### get_preference(key)

Retrieve a preference value.

**Args:**
- `key`: str - Preference key (supports dot notation like 'agent.default')

**Returns:**
- `Tuple[bool, str, Any]`:
  - `success`: bool - Whether operation succeeded
  - `message`: str - Human-readable message
  - `value`: Any - Preference value (None if not found)

**Example:**
```python
workflow = PreferencesWorkflow()
success, msg, value = workflow.get_preference("agent.default")

if success:
    print(f"Agent default: {value}")
else:
    print(f"Error: {msg}")
```

#### set_preference(key, value)

Set a preference value.

**Args:**
- `key`: str - Preference key (supports dot notation like 'agent.default')
- `value`: Any - Preference value (must be JSON serializable)

**Returns:**
- `Tuple[bool, str]`:
  - `success`: bool - Whether operation succeeded
  - `message`: str - Human-readable message

**Example:**
```python
workflow = PreferencesWorkflow()
success, msg = workflow.set_preference("agent.default", "coding")

if success:
    print(msg)  # "Preference 'agent.default' set to 'coding'"
else:
    print(f"Error: {msg}")

# Nested values with JSON
success, msg = workflow.set_preference("studio.config", {"port": 3000, "host": "localhost"})
```

#### delete_preference(key)

Delete a preference.

**Args:**
- `key`: str - Preference key (supports dot notation like 'agent.default')

**Returns:**
- `Tuple[bool, str]`:
  - `success`: bool - Whether operation succeeded
  - `message`: str - Human-readable message

**Example:**
```python
workflow = PreferencesWorkflow()
success, msg = workflow.delete_preference("agent.default")

if success:
    print(msg)  # "Preference 'agent.default' deleted"
else:
    print(f"Error: {msg}")  # "Preference 'agent.default' not found"
```

#### list_preferences()

List all preferences.

**Returns:**
- `Tuple[bool, str, dict]`:
  - `success`: bool - Whether operation succeeded
  - `message`: str - Human-readable message
  - `preferences`: dict - All preferences

**Example:**
```python
workflow = PreferencesWorkflow()
success, msg, prefs = workflow.list_preferences()

if success:
    print(msg)  # "Found 3 preference(s)"
    for key, value in prefs.items():
        print(f"  {key}: {value}")
else:
    print(f"Error: {msg}")
```

#### clear_preferences()

Clear all preferences.

**Returns:**
- `Tuple[bool, str]`:
  - `success`: bool - Whether operation succeeded
  - `message`: str - Human-readable message

**Example:**
```python
workflow = PreferencesWorkflow()
success, msg = workflow.clear_preferences()

if success:
    print(msg)  # "All preferences cleared"
else:
    print(f"Error: {msg}")
```

### Backward-Compatible Functions

The workflow also provides function-based API for backward compatibility:

```python
from myagents.backend.services.agents.workflows.preferences_workflow import (
    get_preference,
    set_preference,
    delete_preference,
    list_preferences,
    clear_preferences
)

# These wrap the workflow class methods
success, msg, value = get_preference(key="agent.default", preferences_file=Path(...))
success, msg = set_preference(key="agent.default", value="coding", preferences_file=Path(...))
```

### Use Cases

1. **User Configuration** - Store user-specific settings
2. **Default Agent Selection** - Remember preferred agent type
3. **Studio Configuration** - Store Studio port and host preferences
4. **Custom Settings** - Store arbitrary JSON-serializable data

### Supported Value Types

- Strings: `"coding"`
- Numbers: `42`, `3.14`
- Booleans: `true`, `false`
- Objects: `{"port": 3000, "host": "localhost"}`
- Arrays: `["coding", "echo"]`
- Nested: `{"agent": {"default": "coding", "history": ["echo", "coding"]}}`

## StudioWorkflow

### Purpose

Manages the LangGraph Studio lifecycle including starting, stopping, restarting, status checking, health verification, and state recovery.

### Location

`src/myagents/backend/services/agents/workflows/studio_workflow.py`

### Class Interface

```python
from myagents.backend.services.agents.workflows.studio_workflow import StudioWorkflow

workflow = StudioWorkflow(
    home_config_dir=Path("~/.config/myagents"),
    config_path=Path("~/.config/myagents/config.yml")
)
```

### Constructor

```python
def __init__(self, home_config_dir: Optional[Path] = None, config_path: Optional[Path] = None)
```

**Args:**
- `home_config_dir`: Path - Path to home config directory where langgraph.json is (defaults to ~/.config/myagents/)
- `config_path`: Optional[Path] - Path to config.yml (defaults to ~/.config/myagents/config.yml)

### Entrypoints

#### start_studio(config=None, background=True)

Start Studio service.

**Args:**
- `config`: Optional[Dict[str, Any]] - Configuration overrides (currently unused, for future extensibility)
- `background`: bool - Run in background (default: True)

**Returns:**
- `Tuple[bool, str]`:
  - `success`: bool - Whether operation succeeded
  - `message`: str - Human-readable message

**Example:**
```python
workflow = StudioWorkflow(worktree_root=Path("/path/to/project"))
success, msg = workflow.start_studio(background=True)

if success:
    print(msg)  # "Studio started on port 2024"
else:
    print(f"Error: {msg}")  # "Studio is already running"
```

#### stop_studio(force=False)

Stop Studio gracefully or forcefully.

**Args:**
- `force`: bool - Force kill if graceful shutdown fails (default: False)

**Returns:**
- `Tuple[bool, str]`:
  - `success`: bool - Whether operation succeeded
  - `message`: str - Human-readable message

**Example:**
```python
workflow = StudioWorkflow(worktree_root=Path("/path/to/project"))

# Graceful stop
success, msg = workflow.stop_studio()

# Force stop if needed
success, msg = workflow.stop_studio(force=True)
```

#### restart_studio(config=None)

Restart Studio service.

**Args:**
- `config`: Optional[Dict[str, Any]] - Configuration overrides (currently unused)

**Returns:**
- `Tuple[bool, str]`:
  - `success`: bool - Whether operation succeeded
  - `message`: str - Human-readable message

**Example:**
```python
workflow = StudioWorkflow(worktree_root=Path("/path/to/project"))
success, msg = workflow.restart_studio()

if success:
    print(msg)  # "Studio restarted successfully"
else:
    print(f"Error: {msg}")
```

#### get_studio_status()

Get current Studio status.

**Returns:**
- `Dict[str, Any]` with keys:
  - `running`: bool - Whether Studio is running
  - `port`: int - Port Studio is running on (or configured port)
  - `host`: str - Host Studio is bound to
  - `url`: str - WebUI URL (e.g., "http://localhost:2024")
  - `api_url`: str - API base URL
  - `pid`: int - Process ID (if available)

**Example:**
```python
workflow = StudioWorkflow(worktree_root=Path("/path/to/project"))
status = workflow.get_studio_status()

if status["running"]:
    print(f"Studio is running on port {status['port']}")
    print(f"WebUI: {status['url']}")
    print(f"PID: {status['pid']}")
else:
    print("Studio is not running")
```

#### check_studio_health()

Verify Studio is responding and healthy.

**Returns:**
- `Dict[str, Any]` with keys:
  - `healthy`: bool - Whether Studio is healthy
  - `running`: bool - Whether Studio is running
  - `responding`: bool - Whether Studio is responding (currently same as running)
  - `port`: int - Port Studio is running on
  - `error`: str - Error message (if not healthy)

**Example:**
```python
workflow = StudioWorkflow(worktree_root=Path("/path/to/project"))
health = workflow.check_studio_health()

if health["healthy"]:
    print(f"Studio is healthy on port {health['port']}")
else:
    print(f"Studio is not healthy: {health.get('error', 'Unknown')}")
```

#### recover_studio_state()

Recover from inconsistent state.

Handles scenarios like:
- PID file exists but process is dead
- Port is in use but PID file is missing
- Stale processes need cleanup

**Returns:**
- `Tuple[bool, str]`:
  - `success`: bool - Whether operation succeeded
  - `message`: str - Human-readable message

**Example:**
```python
workflow = StudioWorkflow(worktree_root=Path("/path/to/project"))
success, msg = workflow.recover_studio_state()

print(msg)
# "Studio state recovered successfully. Running on port 2024 (PID: 12345)"
# or "Studio not running. State is clean."
```

#### get_recent_errors(num_lines=20)

Get recent error messages from Studio logs.

**Args:**
- `num_lines`: int - Number of recent lines to retrieve (default: 20)

**Returns:**
- `Optional[str]` - String containing recent error lines, or None if log doesn't exist

**Example:**
```python
workflow = StudioWorkflow(worktree_root=Path("/path/to/project"))
errors = workflow.get_recent_errors(num_lines=10)

if errors:
    print("Recent errors:")
    print(errors)
else:
    print("No error log found")
```

### Backward-Compatible Functions

The workflow also provides function-based API for backward compatibility:

```python
from myagents.backend.services.agents.workflows.studio_workflow import (
    start_studio,
    stop_studio,
    restart_studio,
    get_studio_status,
    get_studio_recent_errors
)

# These wrap the workflow class methods
success, msg = start_studio(worktree_root=Path(...), config_path=Path(...))
status = get_studio_status(worktree_root=Path(...))
```

### Use Cases

1. **Visual Debugging** - Start Studio to visualize agent execution
2. **Status Monitoring** - Check if Studio is running and on which port
3. **Error Diagnostics** - Retrieve recent error messages for troubleshooting
4. **Process Management** - Clean up stale processes and recover state
5. **Development Workflow** - Restart Studio after code changes

### Studio Configuration

Studio can be configured via:
- Config file: `~/.config/myagents/config.yml` (created by `myagents config init`)
- Preferences: `studio.port`, `studio.host` (via PreferencesWorkflow)
- Defaults: Port 2024, host 127.0.0.1

## HelpWorkflow

### Purpose

Provides help, version, and documentation display functionality for the MyAgents CLI.

### Location

`src/myagents/backend/services/agents/workflows/help_workflow.py`

### Class Interface

```python
from myagents.backend.services.agents.workflows.help_workflow import HelpWorkflow

workflow = HelpWorkflow()
```

### Entrypoints

#### show_version()

Display version information.

**Returns:**
- `str` - Version string in format "myagents X.Y.Z" or "myagents (development version)"

**Example:**
```python
workflow = HelpWorkflow()
version = workflow.show_version()
print(version)  # "myagents 0.1.0"
```

#### show_main_help()

Display main CLI help text.

**Returns:**
- `str` - Main help text with command overview

**Example:**
```python
workflow = HelpWorkflow()
help_text = workflow.show_main_help()
print(help_text)
# Outputs:
# MyAgents - LangGraph agent framework with Studio integration
#
# Usage:
#   myagents [command] [options]
# ...
```

#### show_command_help(command)

Show help for a specific command.

**Args:**
- `command`: str - Command name to show help for

**Returns:**
- `str` - Help text for the specified command

**Supported commands:**
- `chat` - Agent chat command
- `studio` - Studio management command
- `preferences` - Preferences management command
- `config` - Configuration management command
- `secrets` - Secrets management command
- `update` - Update command
- `rebuild` - Rebuild command

**Example:**
```python
workflow = HelpWorkflow()
help_text = workflow.show_command_help("studio")
print(help_text)
# Outputs:
# Studio Command - Manage LangGraph Studio
#
# Usage:
#   myagents studio <subcommand> [options]
# ...
```

#### show_workflow_docs(workflow)

Show documentation for a specific workflow.

**Args:**
- `workflow`: str - Workflow name (e.g., "health_check", "studio", "preferences", "help")

**Returns:**
- `str` - Documentation for the specified workflow

**Supported workflows:**
- `health_check` - HealthCheckWorkflow documentation
- `studio` - StudioWorkflow documentation
- `preferences` - PreferencesWorkflow documentation
- `help` - HelpWorkflow documentation

**Example:**
```python
workflow = HelpWorkflow()
docs = workflow.show_workflow_docs("studio")
print(docs)
# Outputs:
# Studio Workflow
# ===============
#
# Purpose:
#   Manages the LangGraph Studio lifecycle...
```

#### generate_usage_examples(command=None)

Generate usage examples for commands.

**Args:**
- `command`: Optional[str] - Command name to generate examples for. If None, returns all examples.

**Returns:**
- `List[str]` - List of usage example strings

**Example:**
```python
workflow = HelpWorkflow()

# Get examples for specific command
examples = workflow.generate_usage_examples("studio")
for example in examples:
    print(example)
# Outputs:
# myagents studio start
# myagents studio start --port 3000
# myagents studio start --foreground
# ...

# Get all examples
all_examples = workflow.generate_usage_examples()
for example in all_examples:
    print(example)
```

### Use Cases

1. **Help Text Display** - Show help for CLI commands
2. **Version Reporting** - Display package version
3. **Documentation Generation** - Generate workflow documentation
4. **Usage Examples** - Provide command examples for users
5. **Self-Documentation** - CLI can document itself programmatically

## CLI Command to Workflow Mapping

This table shows how CLI commands map to workflow methods:

| CLI Command | Workflow | Method |
|-------------|----------|--------|
| `myagents --help` | HelpWorkflow | `show_main_help()` |
| `myagents --version` | HelpWorkflow | `show_version()` |
| `myagents preferences list` | PreferencesWorkflow | `list_preferences()` |
| `myagents preferences get KEY` | PreferencesWorkflow | `get_preference(key)` |
| `myagents preferences set KEY VAL` | PreferencesWorkflow | `set_preference(key, value)` |
| `myagents preferences delete KEY` | PreferencesWorkflow | `delete_preference(key)` |
| `myagents preferences clear` | PreferencesWorkflow | `clear_preferences()` |
| `myagents studio start` | StudioWorkflow | `start_studio()` |
| `myagents studio stop` | StudioWorkflow | `stop_studio()` |
| `myagents studio restart` | StudioWorkflow | `restart_studio()` |
| `myagents studio status` | StudioWorkflow | `get_studio_status()` |
| Command routing | HealthCheckWorkflow | `detect_context(command)` |
| Root detection | HealthCheckWorkflow | `detect_project_root()` |

## Testing Workflows

Workflows have comprehensive test coverage organized by category:

### Test Organization

```
tests/
├── workflows/
│   ├── infrastructure/          # Infrastructure workflow tests
│   │   ├── test_health_check_workflow.py
│   │   ├── test_preferences_workflow.py
│   │   ├── test_studio_workflow.py
│   │   └── test_help_workflow.py
│   ├── packaging/               # Packaging and E2E tests
│   └── coding_agent/            # Agent workflow tests
```

### Running Workflow Tests

```bash
# Run all infrastructure workflow tests
pytest tests/workflows/infrastructure/ -v

# Run specific workflow tests
pytest tests/workflows/infrastructure/test_health_check_workflow.py -v
pytest tests/workflows/infrastructure/test_preferences_workflow.py -v
pytest tests/workflows/infrastructure/test_studio_workflow.py -v
pytest tests/workflows/infrastructure/test_help_workflow.py -v

# Run with markers
pytest -m infrastructure -v
```

### Writing Workflow Tests

When testing workflows, follow these patterns:

**Example: Testing HealthCheckWorkflow**
```python
import pytest
from myagents.backend.services.agents.workflows.health_check_workflow import HealthCheckWorkflow

@pytest.mark.infrastructure
def test_health_check_cli_health():
    """Test CLI health check."""
    workflow = HealthCheckWorkflow()
    health = workflow.check_cli_health()

    assert health["installed"] is True
    assert "source_root" in health
    assert "version" in health

@pytest.mark.infrastructure
def test_health_check_environment_validation():
    """Test environment validation."""
    workflow = HealthCheckWorkflow()
    env = workflow.validate_environment()

    assert "valid" in env
    assert "python_version_ok" in env
    assert env["python_version_ok"] is True  # Assuming Python 3.11+
```

**Example: Testing PreferencesWorkflow**
```python
import pytest
from pathlib import Path
from myagents.backend.services.agents.workflows.preferences_workflow import PreferencesWorkflow

@pytest.fixture
def temp_prefs_file(tmp_path):
    """Create temporary preferences file."""
    return tmp_path / "prefs.json"

@pytest.mark.infrastructure
def test_preferences_set_get(temp_prefs_file):
    """Test setting and getting preferences."""
    workflow = PreferencesWorkflow(preferences_file=temp_prefs_file)

    # Set preference
    success, msg = workflow.set_preference("test.key", "test_value")
    assert success is True

    # Get preference
    success, msg, value = workflow.get_preference("test.key")
    assert success is True
    assert value == "test_value"
```

## Adding New Workflows

To add a new workflow to the MyAgents CLI:

### 1. Create Workflow Class

```python
# src/myagents/backend/services/<service>/workflows/my_workflow.py
from typing import Tuple
from pathlib import Path

class MyWorkflow:
    """Workflow for <purpose>.

    This workflow provides multiple entrypoints for:
    - Operation 1
    - Operation 2
    - Operation 3
    """

    def __init__(self, some_param: Path):
        """Initialize the workflow.

        Args:
            some_param: Description of parameter
        """
        self.some_param = some_param

    def my_operation(self, arg: str) -> Tuple[bool, str]:
        """Perform operation.

        Args:
            arg: Description of argument

        Returns:
            Tuple of (success: bool, message: str)
        """
        from myagents.backend.services.<service>.domains.<domain> import DomainClass

        try:
            domain = DomainClass(...)
            result = domain.operation(arg)
            return True, f"Operation successful: {result}"
        except Exception as e:
            return False, f"Operation failed: {e}"
```

### 2. Add CLI Entrypoint

```python
# src/myagents/frontend/cli/myagents_cli.py
def cmd_my_command(args):
    """CLI command handler for my_command.

    Args:
        args: Parsed command-line arguments
    """
    from myagents.backend.services.<service>.workflows.my_workflow import MyWorkflow

    workflow = MyWorkflow(some_param=Path(...))
    success, message = workflow.my_operation(args.arg)

    if success:
        print(message)
    else:
        print(f"Error: {message}", file=sys.stderr)
        sys.exit(1)
```

### 3. Add Tests

```python
# tests/workflows/infrastructure/test_my_workflow.py
import pytest
from myagents.backend.services.<service>.workflows.my_workflow import MyWorkflow

@pytest.mark.infrastructure
def test_my_workflow_basic():
    """Test basic workflow functionality."""
    workflow = MyWorkflow(some_param=Path("/tmp"))
    success, message = workflow.my_operation("test")
    assert success is True
    assert "successful" in message

@pytest.mark.infrastructure
def test_my_workflow_error_handling():
    """Test workflow error handling."""
    workflow = MyWorkflow(some_param=Path("/tmp"))
    success, message = workflow.my_operation("invalid")
    assert success is False
    assert "failed" in message
```

### 4. Update Documentation

- Add workflow to this file (architecture/workflows.md)
- Add CLI command to README.md
- Update help text in HelpWorkflow
- Update CLI command to workflow mapping table

## Best Practices

### Workflow Design

1. **Single Responsibility** - Each workflow should have a clear, focused purpose
2. **Return Tuples** - Use `(success: bool, message: str)` for operations
3. **Error Handling** - Catch exceptions and return error messages, don't let them propagate
4. **Documentation** - Provide comprehensive docstrings with examples
5. **Testability** - Design workflows to be easily testable without external dependencies

### Workflow Methods

1. **Descriptive Names** - Use clear, descriptive method names (e.g., `get_preference`, not `get`)
2. **Consistent Returns** - Use consistent return types across similar methods
3. **Optional Parameters** - Use optional parameters with sensible defaults
4. **Type Hints** - Always include type hints for parameters and return values

### CLI Integration

1. **Lazy Imports** - Import workflows only when needed to speed up CLI startup
2. **Error Handling** - Handle workflow errors gracefully with user-friendly messages
3. **Exit Codes** - Use appropriate exit codes (0 for success, 1 for error)
4. **Output Formatting** - Format workflow output for user consumption

### Testing

1. **Test All Entrypoints** - Every workflow method should have tests
2. **Test Error Cases** - Test both success and error scenarios
3. **Use Fixtures** - Use pytest fixtures for common setup
4. **Markers** - Use `@pytest.mark.infrastructure` for workflow tests

## See Also

- [Architecture Documentation](architecture.md) - Overall architecture and design decisions
- [Testing Guide](../tests/README.md) - Comprehensive testing documentation
- [README](../README.md) - Main project documentation
