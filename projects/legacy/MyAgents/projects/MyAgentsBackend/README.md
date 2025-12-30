# MyAgents

A LangGraph-based agentic framework for building AI agents with observability and tool-calling capabilities.

## Status: Alpha / Experimental

This project is in **early alpha stage**. The **Builder Agent** is currently available:
- **Builder Agent**: File manipulation agent with tool-calling support (formerly Coding Agent)

Use for learning and experimentation only.

## TL;DR - Get Started in 5 Minutes

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install
git clone https://github.com/HuaMick/MyAgents.git
cd MyAgents
uv sync

# 3. Run commands
uv run myagents setup
uv run myagents chat
```

For global CLI access: `uv tool install .` then use `myagents` from anywhere.

For detailed GCP setup, see [SETUP.md](SETUP.md).

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://astral.sh/uv) package manager
- GCP project with Secret Manager API enabled
- Gemini API key stored in GCP Secret Manager

### Installation

#### Global Installation (Recommended)

For global CLI access that works from any directory, use `uv tool install`:

```bash
# Prerequisites: uv must be installed (https://astral.sh/uv)
# agent-gcptoolkit must be available (installed globally or from registry)

# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/HuaMick/MyAgents.git
cd MyAgents

# Build and install globally
./scripts/install-global.sh

# Verify installation (works from any directory)
cd /tmp && myagents --version
```

**Note**: This method builds a wheel and installs it globally using `uv tool install`, making `myagents` available system-wide without needing to activate a virtual environment.

#### Developer Installation

For development with local dependencies and modifications:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/HuaMick/MyAgents.git
cd MyAgents
uv sync

# Set GCP project
export GCP_PROJECT_ID="your-gcp-project-id"

# Run initial setup
uv run myagents setup
```

**Running commands:**
- From project directory: `uv run myagents <command>`
- After global install: `myagents <command>` from anywhere

The `myagents setup` command creates `~/.config/myagents/config.yml` with default settings for:
- Server configuration (host, port)
- Runtime paths (logs, checkpoints, PID file)
- LangGraph configuration

This setup is idempotent and will not overwrite existing configuration. The `langgraph.json` file is created automatically on first use of agent commands.

For detailed setup, see [SETUP.md](SETUP.md).

### Updating MyAgents

After initial installation, use CLI commands to update the package:

```bash
# Quick update (reinstall from current source)
myagents update

# Full rebuild (clean build + reinstall)
myagents rebuild
```

These commands work from any directory regardless of your current location.

## Entrypoints

### CLI Binary

MyAgents provides a single unified binary: **`myagents`**

### Default Behavior

Running `myagents` with no arguments displays help:

```bash
myagents          # Shows help menu
```

### Command Structure

All MyAgents commands are **global** - they work from any directory without needing to be in the project folder.

**Command-Line Flags:**
- `myagents --version`, `myagents -v` - Show version information
- `myagents --help`, `myagents -h` - Show help message

**Setup & Package Management (Global):**
```bash
myagents setup       # Run initial setup to create configuration
myagents update      # Update MyAgents package from current source
myagents rebuild     # Clean rebuild with dependency reinstallation
```

**Preferences (Global):**

Works from any directory - stores preferences in `~/.myagents/preferences.json`:
```bash
myagents preferences set <key> <value>    # Set preference
myagents preferences get <key>            # Get preference
myagents preferences list                 # List all preferences (alias: ls)
myagents prefs list                       # Alias for 'preferences'
myagents pref list                        # Shorter alias for 'preferences'
myagents preferences delete <key>         # Delete preference (aliases: del, rm)
myagents preferences clear                # Clear all preferences
```

**Agent and Service Commands (Home Directory Only):**

These commands use home directory configuration:
- **All directories**: Uses `~/.config/myagents/langgraph.json` (auto-created)
- **No local discovery**: Local project `langgraph.json` files are ignored

```bash
# Chat agents
myagents chat                    # Run builder agent (default)
myagents chat --agent builder    # Run builder agent explicitly
myagents chat --agent coding     # Run builder agent (alias for backward compatibility)
myagents c                       # Alias for 'chat' command

# Studio management
myagents studio start            # Start LangGraph Studio
myagents studio start -f         # Start in foreground (alias: --foreground)
myagents studio status           # Check Studio status
myagents studio stop             # Stop Studio
myagents studio stop --force     # Force kill Studio process
myagents studio restart          # Restart Studio

# Configuration management (from agent-gcptoolkit)
myagents config set-path <path>  # Set custom config file path
myagents config show             # Show current config path
myagents config clear            # Clear config path preference
myagents config init             # Interactive config setup

# Secrets management (from agent-gcptoolkit)
myagents secrets get <name>      # Get secret from GCP Secret Manager
myagents secrets get <name> -q   # Get secret (quiet mode, alias: --quiet)

# GCPToolkit package management
myagents gcptoolkit build        # Build agent-gcptoolkit package
myagents gcptoolkit update       # Update agent-gcptoolkit package
myagents gcptoolkit rebuild      # Rebuild agent-gcptoolkit package
```

## Remote Services

MyAgents provides remote terminal and relay services to enable controlling Claude Code terminal sessions from a web browser.

### Architecture

```
Browser (Flutter Web)
    |
    | WSS (E2E encrypted)
    v
Relay Server (FastAPI)
    |
    | WSS (E2E encrypted)
    v
Desktop CLI (PTY wrapper around Claude Code)
```

### Services Overview

**Relay Service**: WebSocket relay server that routes encrypted messages between desktop and web clients
- Manages session lifecycle and pairing codes
- Handles WebSocket connections for desktop and client endpoints
- Provides health monitoring and active session tracking

**Remote Terminal Service**: PTY wrapper that provides terminal access via WebSocket
- Wraps Claude Code CLI in a pseudo-terminal (PTY)
- Connects to relay server for remote access
- Manages terminal I/O and session state

### Quick Start: Remote Services

Follow these steps to enable remote terminal access:

#### 1. Start Relay Server

```bash
# Start relay server (default: 0.0.0.0:8080)
myagents relay start

# Or with custom settings
myagents relay start --host localhost --port 9000

# Run in foreground for debugging
myagents relay start --foreground
```

**Expected output:**
```
Relay server started successfully!
PID: 12345
WebSocket URL: ws://0.0.0.0:8080
Desktop endpoint: ws://0.0.0.0:8080/ws/desktop/{session_id}
Client endpoint: ws://0.0.0.0:8080/ws/client/{pairing_code}
Active sessions: 0
```

#### 2. Start Remote Terminal Service

```bash
# Start remote terminal service (default: port 8080)
myagents remote start

# Or with custom settings
myagents remote start --port 8080 --relay-url ws://localhost:8080

# Run in foreground for debugging
myagents remote start --foreground
```

**Expected output:**
```
Remote Terminal service started successfully!
PID: 12346
WebSocket URL: ws://0.0.0.0:8080
Session ID: (connect to create session)
```

#### 3. Check Service Status

```bash
# Check relay server status
myagents relay status

# Check remote terminal status
myagents remote status
```

**Example relay status output:**
```
============================================================
Relay Service Status
============================================================
Status: RUNNING
PID: 12345
Host: 0.0.0.0
Port: 8080

WebSocket URL: ws://0.0.0.0:8080
Desktop endpoint: /ws/desktop/{session_id}
Client endpoint: /ws/client/{pairing_code}

Active sessions: 0
Health: HEALTHY
============================================================
```

#### 4. Connect from Web Client

1. Relay server creates a pairing code when desktop connects
2. Desktop displays the pairing code (e.g., "ABC-123")
3. Enter pairing code in web client to establish connection
4. All terminal I/O is encrypted end-to-end using NaCl

### CLI Reference: Remote and Relay Commands

#### Relay Commands

**Start Relay Server:**
```bash
myagents relay start [OPTIONS]

Options:
  --host HOST         Host to bind to (default: 0.0.0.0)
  --port PORT, -p     Port to listen on (default: 8080)
  --foreground, -f    Run in foreground instead of background
```

**Stop Relay Server:**
```bash
myagents relay stop [OPTIONS]

Options:
  --force             Force kill if graceful shutdown fails
```

**Check Relay Status:**
```bash
myagents relay status
```

#### Remote Terminal Commands

**Start Remote Terminal:**
```bash
myagents remote start [OPTIONS]

Options:
  --port PORT, -p         Port for terminal service (default: 8080)
  --relay-url URL         WebSocket relay URL (default: ws://localhost:8080)
  --foreground, -f        Run in foreground instead of background
```

**Stop Remote Terminal:**
```bash
myagents remote stop [OPTIONS]

Options:
  --force                 Force kill if graceful shutdown fails
```

**Check Remote Terminal Status:**
```bash
myagents remote status
```

### Connection Flow

The complete connection flow from desktop to web client:

1. **Start Relay Server**
   ```bash
   myagents relay start
   ```

2. **Start Remote Terminal**
   ```bash
   myagents remote start
   ```

3. **Desktop Connects to Relay**
   - Remote terminal connects to relay's desktop endpoint
   - Relay creates session and generates pairing code
   - Desktop displays pairing code (e.g., "ABC-123")

4. **Web Client Pairs**
   - User enters pairing code in web interface
   - Web client connects to relay's client endpoint
   - Relay validates code and establishes bidirectional tunnel

5. **Terminal Access Enabled**
   - All messages are E2E encrypted using NaCl
   - Web client can send terminal input
   - Desktop receives input and executes commands
   - Desktop sends terminal output back to web client

### Troubleshooting Remote Services

#### Common Issues

**Port Already in Use:**
```bash
# Error: Port 8080 is already in use by another process

# Solution 1: Stop the service using that port
myagents relay stop
myagents remote stop

# Solution 2: Use a different port
myagents relay start --port 9000
myagents remote start --port 9001
```

**Service Not Responding:**
```bash
# Check if service is running
myagents relay status
myagents remote status

# Check recent logs
cat ~/.config/myagents/logs/relay_stderr.log
cat ~/.config/myagents/logs/remote_stderr.log

# Force restart
myagents relay stop --force
myagents relay start
```

**Connection Timeout:**
- Verify relay server is running: `myagents relay status`
- Check firewall settings allow WebSocket connections
- Verify correct relay URL in remote terminal configuration
- Check logs for connection errors

**Stale Processes:**
```bash
# Clean up stale state files
rm ~/.config/myagents/relay.state
rm ~/.config/myagents/remote.state

# Force stop and restart
myagents relay stop --force
myagents remote stop --force

myagents relay start
myagents remote start
```

#### Log Files

Service logs are stored in `~/.config/myagents/logs/`:

**Relay Server Logs:**
- `relay_stdout.log` - Standard output
- `relay_stderr.log` - Error messages and warnings
- `relay_stdout.YYYYMMDD_HHMMSS.log` - Rotated logs

**Remote Terminal Logs:**
- `remote_stdout.log` - Standard output
- `remote_stderr.log` - Error messages and warnings
- `remote_stdout.YYYYMMDD_HHMMSS.log` - Rotated logs

**Viewing logs:**
```bash
# View recent relay errors
tail -f ~/.config/myagents/logs/relay_stderr.log

# View recent remote terminal errors
tail -f ~/.config/myagents/logs/remote_stderr.log

# View all rotated logs
ls -lh ~/.config/myagents/logs/
```

#### Health Checks

Both services provide health endpoints:

**Relay Server Health:**
```bash
# HTTP health check
curl http://localhost:8080/health

# Response: {"status": "healthy", "repository": "InMemorySessionRepository(total=0, active=0)"}
```

**Process Verification:**
```bash
# Check if relay process is running
ps aux | grep "uvicorn.*relay"

# Check if remote terminal is running
ps aux | grep "agent_remote.services.terminal"
```

### Command Aliases

The CLI provides several command aliases for convenience:

| Full Command | Aliases |
|-------------|---------|
| `myagents chat` | `myagents c` |
| `myagents preferences` | `myagents prefs`, `myagents pref` |
| `myagents preferences list` | `myagents preferences ls` |
| `myagents preferences delete` | `myagents preferences del`, `myagents preferences rm` |

### Flag Shortcuts

Most flags have short forms:

| Long Form | Short Form | Context |
|-----------|-----------|---------|
| `--version` | `-v` | Global flag |
| `--help` | `-h` | Global flag |
| `--agent` | `-a` | chat command |
| `--foreground` | `-f` | studio start command |
| `--quiet` | `-q` | secrets get command |

### Usage Examples

```bash
# Using aliases
myagents c                        # Same as: myagents chat
myagents c -a builder             # Same as: myagents chat --agent builder
myagents prefs list               # Same as: myagents preferences list
myagents pref get agent.default   # Same as: myagents preferences get agent.default

# Using flag shortcuts
myagents -v                       # Same as: myagents --version
myagents studio start -f          # Same as: myagents studio start --foreground
myagents secrets get API_KEY -q   # Same as: myagents secrets get API_KEY --quiet

# Default behavior
myagents                          # Shows help menu (no command required)
```

### LangGraph Studio

Start Studio for visual debugging:
```bash
uv run langgraph dev
# Open: http://localhost:2024
```

Select agent from Studio UI:
- `builder` - File operations agent (tool-calling with file, git, and shell operations)

## Configuration

MyAgents uses a centralized home directory configuration system:

### Configuration Files

**Home Directory (`~/.config/myagents/`):**
- `langgraph.json` - Agent workflow definitions with absolute paths
- `config.yml` - Runtime configuration (server, ports, etc.)

**User Preferences (`~/.myagents/`):**
- `preferences.json` - User preferences (separate from config)

All configuration is stored in the home directory. Local project `langgraph.json` files are ignored.

### Home Directory Setup

Run `myagents setup` to create `~/.config/myagents/config.yml` with:
- Default server settings (host, port)
- Runtime paths (logs, checkpoints, PID file)
- LangGraph configuration

On first use of agent commands, `langgraph.json` is created automatically with:
- Self-contained agent workflow definitions
- Required dependencies

User preferences are stored in `preferences.json` (created on first preference operation).

This enables all commands to work immediately from any directory.

## Work from Anywhere

MyAgents commands work from any directory using home directory configuration:

### Home Directory Only Configuration

The home directory configuration is the **single source of truth** - it contains agent workflow definitions with absolute paths to your project files.

**Setup:**
```bash
# Run setup to create configuration
myagents setup

# On first agent command, ~/.config/myagents/langgraph.json is created
myagents chat
# Home config auto-created with complete agent definitions
```

**Usage:**
```bash
# Works from any directory via home config
cd /tmp
myagents chat              # Works! Uses ~/.config/myagents/langgraph.json
myagents studio start      # Works! Uses ~/.config/myagents/langgraph.json

cd ~/Documents
myagents chat --agent builder # Works! Uses ~/.config/myagents/langgraph.json

cd /home/code/myagents/MyAgents
myagents chat              # Works! Uses ~/.config/myagents/langgraph.json
```

### Benefits

This home directory only approach ensures:
- **Minimal configuration needed** - Run `myagents setup` once after installation
- **Work from anywhere** - All commands use home config regardless of current directory
- **Self-contained** - Home config uses absolute paths, no dependencies on current location
- **No routing complexity** - Single configuration file, no discovery mechanism needed
- **Consistent behavior** - Same configuration used everywhere

**Note:** Local project `langgraph.json` files are ignored. All agent workflow paths must be absolute and specified in `~/.config/myagents/langgraph.json`.

### langgraph.json Configuration

MyAgents requires a `langgraph.json` file in your home directory that defines your agent workflows.

**Home Directory Structure (`~/.config/myagents/langgraph.json`):**
```json
{
  "dependencies": [
    "langgraph>=0.2.0",
    "langchain-core",
    "langchain-google-genai>=2.0.5",
    "google-generativeai>=0.8.5",
    "langsmith>=0.1.0"
  ],
  "graphs": {
    "builder": "/home/code/myagents/MyAgents/src/myagents/backend/services/agents/workflows/builder_agent.py:create_builder_agent",
    "coding": "/home/code/myagents/MyAgents/src/myagents/backend/services/agents/workflows/builder_agent.py:create_builder_agent"
  },
  "env": "/home/code/myagents/MyAgents/.env"
}
```

**Important:**
- All paths in `langgraph.json` must be **absolute paths**
- Local project `langgraph.json` files are ignored
- The home directory config is the single source of truth
- Update paths in home config when moving project directories

## Preferences

MyAgents supports user preferences for customization.

### Managing Preferences

```bash
# Set a preference
myagents preferences set <key> <value>

# Get a preference value
myagents preferences get <key>

# List all preferences
myagents preferences list

# Delete a preference
myagents preferences delete <key>

# Clear all preferences
myagents preferences clear
```

### Common Preferences

**agent.default** - Set default agent for chat command:
```bash
# Set default agent
myagents preferences set agent.default coding

# View current default
myagents preferences get agent.default

# Remove default (reverts to system default)
myagents preferences delete agent.default
```

### Preference Storage

Preferences are stored in `~/.myagents/preferences.json` as JSON. The file supports:
- Flat key-value pairs (e.g., `agent.default`)
- Dot notation for nested keys (e.g., `studio.port`)
- Automatic file creation on first use

### Best Practices

1. **Use preferences for user settings** - Default agent, port numbers, etc.
2. **Use absolute paths in home config** - Ensures workflows work from any directory
3. **Update home config when moving projects** - Paths must remain valid
4. **Preferences are portable** - Travel with your user account

### Troubleshooting Configuration

**Verify configuration:**
```bash
# Check home directory file exists
ls -la ~/.config/myagents/langgraph.json

# View home directory configuration (verify absolute paths)
cat ~/.config/myagents/langgraph.json

# View all preferences
myagents preferences list
```

**Reset to defaults:**
```bash
# Remove home directory configuration (will be recreated)
rm ~/.config/myagents/langgraph.json

# Next command will auto-create default configuration
myagents chat
```

## Features

### Builder Agent
- Tool-calling architecture with conditional routing
- File operations: read, list, edit, search, and find files
- Search capabilities: content search with regex, file finding with glob patterns
- Shell execution: run shell commands within allowed directories
- Git operations: status, diff, branch, and repository info
- Multi-turn conversations with state persistence
- Interactive CLI sessions
- LangGraph Studio visual debugging

### Shared Infrastructure
- GCP Secret Manager integration for API keys
- LangSmith tracing support (basic)
- Python + uv dependency management
- pytest test suite

## Limitations

**Builder Agent:**
- Cannot create new files (only edit existing)
- No undo functionality
- Text files only (no binary)

**General:**
- Requires GCP project and Secret Manager setup
- No .env file support (must use Secret Manager)
- Hardcoded model settings (no runtime configuration)
- No streaming responses
- LangSmith integration unverified
- Silent failures in tracing

## Documentation

Essential guides for getting started and understanding MyAgents:

**Getting Started:**
- **[Setup Guide](SETUP.md)** - Complete installation and GCP configuration
- **[Usage Guide](docs/guides/usage.md)** - How to use the Builder agent
- **[Configuration Guide](docs/guides/configuration.md)** - Configuration files and their purpose

**Technical Documentation:**
- **[Architecture Overview](docs/architecture/architecture.md)** - System design and implementation
- **[Workflows Guide](docs/architecture/workflows.md)** - Detailed workflow documentation
- **[Testing Guide](docs/testing/README.md)** - Testing procedures and structure

For more documentation, see [docs/README.md](docs/README.md)

## Testing

Tests are organized by workflow with health reporting to track overall system status.

**Note**: The full test suite contains 680+ tests and takes approximately 5 minutes to complete.

### Test Structure

```
tests/
├── workflows/              # Workflow-specific tests
│   ├── agent_chat/        # Builder agent tests
│   ├── secrets_workflow/  # Secrets workflow tests
│   └── infrastructure/    # Infrastructure tests (53 tests)
│       └── test_cli_integration.py
├── integration/           # Integration tests
└── utils/
    └── health_reporter.py  # Workflow health monitoring
```

### Running Tests

```bash
# Run all tests with health report (full suite, ~5 minutes)
make test-all

# Quick smoke test for faster feedback (~30 seconds)
uv run pytest tests/workflows/infrastructure/test_cli_integration.py -v

# Run specific workflow tests
make test-workflow-builder-agent
make test-infrastructure

# Standard pytest commands also work
uv run pytest                    # All tests
uv run pytest -v                 # With verbose output (shows progress)
uv run pytest --workflow-health  # With health report
uv run pytest -m infrastructure  # By marker
```

### Workflow Health Report

Running tests with `--workflow-health` shows system-level status:

```bash
$ make test-all
================= Workflow Health Report ==================
✓ builder_agent: HEALTHY (tests passed)
✓ infrastructure: HEALTHY (53/53 tests passed)

Overall: 2/2 workflows healthy
```

**Status Levels:**
- HEALTHY: All tests passing
- DEGRADED: Some tests passing, some failing
- UNHEALTHY: All tests failing

For detailed testing documentation, see [tests/README.md](tests/README.md)

## Troubleshooting

### Studio Issues

**Protobuf Version Mismatch:**
If Studio fails to start with protobuf errors:
```bash
# Error: protobuf version mismatch
# Solution: Rebuild with correct dependencies
myagents rebuild
```

**Studio Process Management:**
If Studio appears to hang or doesn't stop properly:
```bash
# Check if Studio is running
myagents studio status

# Force stop if needed
myagents studio stop

# Clean restart
myagents studio restart
```

**Common Studio Errors:**
- Port already in use: Stop Studio with `myagents studio stop` before restarting
- Stale process: Use `myagents studio restart` to clean up and restart
- Module import errors: Run `myagents rebuild` to reinstall dependencies

### Configuration Issues

All commands work from any directory. If you experience issues:

**Configuration location:**
- All commands use `~/.config/myagents/langgraph.json`
- Local project `langgraph.json` files are ignored
- Home config is auto-created on first run with absolute paths

**Verify configuration:**
```bash
# View all preferences
myagents preferences list

# Check home directory setup
ls -la ~/.config/myagents/

# View home configuration
cat ~/.config/myagents/langgraph.json
```

## Architecture

### Global Command Architecture

MyAgents commands work from any directory using home directory configuration.

**How Commands Find Your Configuration:**

1. **Entry Point** (`frontend/cli/entry.py`)
   - Intercepts all CLI commands
   - Delegates to `HealthCheckWorkflow.detect_context()`
   - Passes home directory context to command handlers

2. **Home Directory Only** (`HealthCheckWorkflow`)
   - Detects CLI installation location via `__file__` (for update/rebuild commands)
   - Uses home directory for all agent/service commands:
     - Always loads `~/.config/myagents/langgraph.json`
     - Auto-created if missing with absolute paths
     - Local project `langgraph.json` files are ignored
   - Returns unified context with CLI and home directory locations

3. **Command Execution**
   - Package management commands (update/rebuild) use CLI installation location
   - Agent/service commands use home directory configuration
   - All commands guaranteed to work from any directory

**Configuration Flow Example:**

```
User runs: myagents chat (from any directory)
    ↓
Entry point calls: HealthCheckWorkflow.detect_context()
    ↓
Context detection:
    1. Use home directory: ~/.config/myagents/langgraph.json
    2. Return context with config_root = ~/.config/myagents
    ↓
CLI loads agents from: ~/.config/myagents/langgraph.json
    ↓
Chat agent starts successfully
```

**Benefits:**
- **Zero configuration required** - Auto-creates home directory config on first run
- **Works from anywhere** - No need to cd into specific directory
- **Single source of truth** - Home directory only, no discovery mechanism needed
- **Consistent behavior** - Same configuration used regardless of current directory
- **Absolute paths** - Home config uses absolute paths to project files

**Practical Examples:**

```bash
# Example 1: Fresh install (no configuration)
$ myagents chat
# Auto-creates ~/.config/myagents/langgraph.json with absolute paths
# Works immediately from any directory

# Example 2: Work from anywhere via home config
$ cd /tmp
$ myagents chat
# Uses ~/.config/myagents/langgraph.json

$ cd /home/user/my-project
$ myagents chat
# Uses ~/.config/myagents/langgraph.json (same config everywhere)

# Example 3: Package management (always uses CLI location)
$ cd /tmp
$ myagents rebuild
# Rebuilds CLI installation regardless of current directory
```

### Workflow-Based CLI

MyAgents uses a three-layer architecture: **Domain → Workflow → Entrypoint**

**The Four Core Workflows:**

1. **HealthCheckWorkflow** - CLI infrastructure validation and root detection
2. **PreferencesWorkflow** - User preference management
3. **StudioWorkflow** - LangGraph Studio lifecycle management
4. **HelpWorkflow** - CLI help and documentation

Each CLI command delegates to a workflow, which orchestrates domain logic:

```
CLI Command → Workflow → Domain → Result
```

**Example:**
```python
# CLI: myagents preferences set agent.default coding
# ↓
# Workflow: PreferencesWorkflow.set_preference("agent.default", "coding")
# ↓
# Domain: PreferencesManager.set("agent.default", "coding")
# ↓
# Result: (True, "Preference 'agent.default' set to 'coding'")
```

**Benefits:**
- **Separation of Concerns** - Clear boundaries between layers
- **Testability** - 56 workflow tests at each layer
- **Reusability** - Workflows used by CLI, tests, and future APIs
- **Maintainability** - Single responsibility for each workflow

### Agent Workflows

**Builder Agent:** Tool-calling graph with conditional routing (agent ↔ tools loop)

### Technology Stack
- LangGraph 0.2.60
- Gemini 2.5-flash via LangChain
- GCP Secret Manager
- LangSmith tracing
- pytest

See [Architecture](docs/architecture.md) for complete details and [Workflows](docs/workflows.md) for workflow documentation.

## Contributing

Contributions welcome! This is an experimental project. Please:

1. Run tests before submitting: `uv run pytest`
2. Add tests for new functionality
3. Follow existing code patterns

### Adding New Workflows

To add a new workflow to the MyAgents CLI, follow this pattern:

**1. Create workflow class:**
```python
# src/myagents/backend/services/<service>/workflows/my_workflow.py
class MyWorkflow:
    """Workflow for <purpose>."""

    def __init__(self, some_param: Path):
        self.some_param = some_param

    def my_operation(self, arg: str) -> Tuple[bool, str]:
        """Perform operation.

        Returns:
            Tuple of (success: bool, message: str)
        """
        from myagents.backend.services.<service>.domains.<domain> import DomainClass

        domain = DomainClass(...)
        return domain.operation(arg)
```

**2. Add CLI entrypoint:**
```python
# src/myagents/frontend/cli/myagents_cli.py
def cmd_my_command(args):
    """CLI command handler."""
    from myagents.backend.services.<service>.workflows.my_workflow import MyWorkflow

    workflow = MyWorkflow(some_param=Path(...))
    success, message = workflow.my_operation(args.arg)

    if success:
        print(message)
    else:
        print(f"Error: {message}", file=sys.stderr)
        sys.exit(1)
```

**3. Add tests:**
```python
# tests/workflows/infrastructure/test_my_workflow.py
from myagents.backend.services.<service>.workflows.my_workflow import MyWorkflow

@pytest.mark.infrastructure
def test_my_workflow_basic():
    workflow = MyWorkflow(some_param=Path("/tmp"))
    success, message = workflow.my_operation("test")
    assert success is True
```

**4. Update documentation:**
- Add workflow to `docs/workflows.md`
- Add CLI command to `README.md`
- Update help text in `HelpWorkflow`

See [Workflows Documentation](docs/workflows.md) for complete details.

**High Priority Help Wanted:**
- LangSmith integration verification
- External configuration implementation

## CI/CD Pipeline

This repository uses Google Cloud Build for Continuous Integration and Deployment.

- **Status**: Active
- **Documentation**: [docs/cicd.md](docs/cicd.md)
- **Triggers**:
  - **PRs**: Runs fast checks (Linting + Unit Tests).
  - **Main Branch**: Runs full test suite (Integration + End-to-End).

## License

[License information to be determined]

## Contact

[Contact information to be determined]

---

**Generated with Claude Code** 🤖
