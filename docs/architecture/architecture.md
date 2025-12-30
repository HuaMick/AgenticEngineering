# MyAgents Architecture

## Git Repository Structure

### Overview
This directory contains TWO separate Git repositories that work together:

1. **MyAgents** - Main project repository
2. **Agent-GCPtoolkit** - Shared GCP utilities toolkit

### Directory Structure

```
/home/code/myagents/
├── MyAgents.git/              # Bare repo for MyAgents
│   └── worktrees/
│       ├── main/              # Registered worktree
│       └── agent-test/        # Registered worktree
│
├── Agent-GCPtoolkit.git/      # Bare repo for GCP toolkit (SEPARATE)
│   └── worktrees/
│       └── Agent-GCPtoolkit/  # Registered worktree
│
├── MyAgents/                  # MyAgents worktree (main branch)
│   ├── .git → ../MyAgents.git/worktrees/main/
│   ├── frontend/
│   ├── backend/
│   └── pyproject.toml
│
├── agent-test/                # Another MyAgents worktree
│   └── .git → ../MyAgents.git/worktrees/agent-test/
│
├── Agent-GCPtoolkit/          # GCP toolkit worktree
│   ├── .git → ../Agent-GCPtoolkit.git/worktrees/Agent-GCPtoolkit/
│   ├── agent_gcptoolkit/
│   │   ├── secrets.py
│   │   └── cli.py
│   └── pyproject.toml
│
├── config/                    # Shared configuration
├── docs/                      # Project documentation
│   └── plans/                 # Planning and implementation documentation
└── architecture.md            # This file (source of truth)
```

### How It Works

#### MyAgents Repository
- **Remote**: `git@github.com:HuaMick/MyAgents.git`
- **Purpose**: Main application code
- **Worktrees**: `MyAgents/`, `agent-test/`, etc.
- **Commands from worktree**:
  ```bash
  cd /home/code/myagents/MyAgents
  git status          # Shows MyAgents repo status
  git commit -m "..."  # Commits to MyAgents.git
  git push            # Pushes to MyAgents remote
  ```

#### Agent-GCPtoolkit Repository
- **Remote**: TBD (separate GitHub repo)
- **Purpose**: Shared GCP utilities (secrets management, etc.)
- **Worktree**: `Agent-GCPtoolkit/`
- **Commands from worktree**:
  ```bash
  cd /home/code/myagents/Agent-GCPtoolkit
  git status          # Shows Agent-GCPtoolkit repo status
  git commit -m "..."  # Commits to Agent-GCPtoolkit.git
  git push            # Pushes to Agent-GCPtoolkit remote
  ```

#### Integration
From any MyAgents worktree, you can install the toolkit:
```bash
cd /home/code/myagents/MyAgents
uv pip install -e ../Agent-GCPtoolkit/
```

Or import it directly:
```python
import sys
sys.path.insert(0, '/home/code/myagents/Agent-GCPtoolkit')
from agent_gcptoolkit.secrets import get_secret
```

#### Benefits
1. **Separation of Concerns**: MyAgents and toolkit are independent
2. **Independent Versioning**: Each repo has its own commit history
3. **Shared Access**: All MyAgents worktrees can use ../Agent-GCPtoolkit/
4. **Reusability**: Toolkit can be used in other projects
5. **Clean Git History**: Toolkit changes don't clutter MyAgents history

#### Distinguishing Between Repos

**When you're in `/home/code/myagents/MyAgents/`:**
- `.git` points to `MyAgents.git/worktrees/main/`
- `git remote -v` shows `git@github.com:HuaMick/MyAgents.git`
- Changes go to MyAgents repository

**When you're in `/home/code/myagents/Agent-GCPtoolkit/`:**
- `.git` points to `Agent-GCPtoolkit.git/worktrees/Agent-GCPtoolkit/`
- `git remote -v` shows Agent-GCPtoolkit remote (if configured)
- Changes go to Agent-GCPtoolkit repository

#### Quick Commands

```bash
# List all MyAgents worktrees
cd /home/code/myagents
GIT_DIR=MyAgents.git git worktree list

# List all Agent-GCPtoolkit worktrees
GIT_DIR=Agent-GCPtoolkit.git git worktree list

# Check which repo a worktree belongs to
cd /home/code/myagents/MyAgents
git remote -v  # Shows MyAgents repo

cd /home/code/myagents/Agent-GCPtoolkit
git remote -v  # Shows Agent-GCPtoolkit repo
```

## Project Folder Structure

- `/home/code/myagents/docs/` - Project documentation directory
- `/home/code/myagents/docs/plans/` - Planning and implementation documentation
- `/home/code/myagents/config/` - Global configuration files
- `/home/code/myagents/MyAgents/backend/services/<service_name>/` - Backend services (independent and self-contained)
- `/home/code/myagents/MyAgents/backend/services/<service_name>/src/domains/` - Domain packages (source of truth for domain logic)
- `/home/code/myagents/MyAgents/backend/services/<service_name>/src/workflows/` - Workflow files (source of truth for workflow orchestration)
- `/home/code/myagents/MyAgents/backend/services/<service_name>/README.md` - Service-specific README files
- `/home/code/myagents/MyAgents/frontend/agents/` - Agent context documentation and definitions
- `/home/code/myagents/MyAgents/frontend/cli/` - CLI entrypoints (source of truth for user-facing commands)
- `/home/code/myagents/MyAgents/README.md` - Main project README file

### MyAgents Project Structure

#### Backend Services

```
src/myagents/backend/
└── services/
    └── agents/
        ├── tools/                      # Tool implementations for agents
        │   ├── __init__.py            # Tool registry
        │   └── file_tools.py          # File operation tools (86 lines)
        │       ├── read_file()        # Read file contents
        │       ├── write_file()       # Write/create files
        │       └── list_directory()   # List directory contents
        │
        └── workflows/                  # Agent workflow implementations
            ├── simple_agent.py         # Basic agent workflow
            └── coding_agent.py         # Tool-enabled coding agent (252 lines)
                └── run_coding_agent() # Multi-turn tool loop with state management
```

#### Frontend CLI

```
src/myagents/frontend/
├── cli/
│   ├── entry.py                          # Main CLI entrypoint
│   └── myagents_cli.py                   # Command-line interface
│       └── Routes commands to workflows
└── agents/                                # Agent definitions (YAML-based)
    ├── orchestration/                     # Orchestration agent definitions
    ├── planner/                          # Planning agent definitions
    ├── cleaner/                          # Code cleaning agent definitions
    ├── build/                            # Build agent definitions
    ├── test/                             # Testing agent definitions
    ├── deploy/                           # Deployment agent definitions
    ├── documentation/                    # Documentation agent definitions
    ├── teacher/                          # Teaching agent definitions
    ├── explore/                          # Exploration agent definitions
    └── diagnostics/                      # Diagnostics agent definitions
```

**Frontend Agents Structure:**
Each agent directory contains YAML files defining agent behavior:
- `manifest.yml` - Agent metadata and context
- `definitions.yml` - Domain-specific definitions and concepts
- `process.yml` - Process workflows and steps
- `processes/*.yml` - Sub-process definitions (when needed)

#### Tests

```
tests/
├── workflows/                             # Workflow-specific tests
│   ├── coding_agent/
│   │   ├── __init__.py
│   │   └── test_coding_agent.py          # Coding agent workflow tests
│   ├── echo_agent/
│   │   ├── __init__.py
│   │   └── test_echo_agent.py            # Echo agent workflow tests
│   └── secrets_workflow/
│       └── __init__.py
│
├── infrastructure/                        # Infrastructure tests
│   ├── __init__.py
│   ├── test_cli_integration.py           # CLI command tests (4 tests)
│   └── test_studio_service.py            # LangGraph Studio tests (10 tests)
│
├── utils/                                 # Test utilities
│   ├── __init__.py
│   └── health_reporter.py                # Workflow health monitoring plugin
│
├── conftest.py                            # Shared pytest fixtures
├── pytest.ini                             # Pytest configuration with markers
└── README.md                              # Testing guide
```

#### Key Components

**Tools System (`src/myagents/backend/services/agents/tools/`)**
- **Purpose**: Provides reusable tool definitions for AI agents
- **file_tools.py**: Implements 3 file operation tools with proper error handling
- **Architecture**: Tools return structured results with success/error states

**Coding Agent Workflow (`src/myagents/backend/services/agents/workflows/coding_agent.py`)**
- **Purpose**: Autonomous coding agent with file operation capabilities
- **Features**:
  - Multi-turn conversation loop
  - Tool execution with state management
  - Automatic function calling and result processing
  - Error handling and recovery
- **Length**: 252 lines

**Workflow Tests (`tests/workflows/`)**
- **Purpose**: End-to-end testing of agent workflows
- **Structure**: Organized by workflow (coding_agent, echo_agent, etc.)
- **Coverage**:
  - Coding agent: 1 test
  - Echo agent: 1 test
- **Documentation**: See `tests/README.md` for testing guide

**Infrastructure Tests (`tests/infrastructure/`)**
- **Purpose**: Cross-cutting infrastructure and service tests
- **Coverage**:
  - CLI integration: 4 tests
  - Studio service: 10 tests
- **Markers**: Tagged with `@pytest.mark.infrastructure`

**Workflow Health Reporter (`tests/utils/health_reporter.py`)**
- **Purpose**: System-level test status monitoring
- **Features**:
  - Groups tests by workflow
  - Reports HEALTHY/DEGRADED/UNHEALTHY status
  - Supports JSON output for CI/CD
- **Usage**: `pytest --workflow-health` or `make test-all`

## Technology Stack

- **LangGraph 0.2.60** - State graph orchestration
- **Gemini 2.5-flash via LangChain** - LLM integration
- **GCP Secret Manager** - API key storage
- **LangSmith** - Observability and tracing
- **Python 3.11+** - Runtime environment

## Architectural Patterns

**Echo Agent:** Simple linear graph (process_input → generate_response)

**Coding Agent:** Tool-calling graph with conditional routing (agent ↔ tools loop)

## Design Decisions

- **LangGraph:** Provides visual debugging, state management, and conditional routing
- **Gemini 2.5-flash:** Fast, cost-effective for development, integrates with GCP ecosystem
- **GCP Secret Manager:** Secure API key storage, no credentials in code
- **Service-based architecture:** Backend services are independent and self-contained

## CLI Command Routing Architecture

### Overview

The MyAgents CLI implements a home-directory-first architecture that distinguishes between global commands (update, rebuild, preferences) and agent/service commands (chat, studio). All commands work from any directory. Global commands use the CLI installation location, while agent/service commands use home directory configuration exclusively.

### Command Categories

**Command-Line Flags (handled before routing):**
- `--version`, `-v` - Show version information
- `--help`, `-h` - Show help message

These flags are handled via early exit in `entry.py` BEFORE command routing occurs. They bypass `detect_cli_source_root()` and the `GLOBAL_COMMANDS` set entirely.

**Global Commands (work from any directory):**
- `update` - Reinstall myagents from current source
- `rebuild` - Rebuild and reinstall myagents package
- `preferences` - Manage user preferences (get, set, delete, list, clear)

These commands use the routing mechanism. `update` and `rebuild` call `detect_cli_source_root()` to locate the CLI installation. `preferences` works globally and stores preferences in `~/.myagents/preferences.json`.

**Agent and Service Commands (use home directory only):**
- `chat` - Start interactive agent chat
- `studio` - Manage LangGraph Studio (start, stop, restart, status)

These commands use home directory configuration exclusively (`~/.config/myagents/langgraph.json`). Local project `langgraph.json` files are ignored.

### Configuration Detection Mechanism

The CLI uses home directory for all configuration:

#### CLI Source Root Detection
```python
def detect_cli_source_root() -> Path:
    """Detect CLI source root (installation location)."""
    # __file__ is frontend/cli/entry.py
    # Go up three levels: entry.py -> cli -> frontend -> MyAgents
    return Path(__file__).parent.parent.parent.resolve()
```

**Used for:** Global commands (update, rebuild)

**Purpose:** Locates the CLI installation directory using the `__file__` attribute of the entry.py module.

**Behavior:** Always succeeds, as it's based on the CLI's own file location.

#### Home Directory Configuration
```python
def get_home_config_path() -> Path:
    """Get home directory configuration path."""
    return Path.home() / ".config" / "myagents" / "langgraph.json"
```

**Used for:** All agent and service commands (chat, studio)

**Purpose:** Uses home directory as single source of truth for all configuration.

**Behavior:**
- Always uses `~/.config/myagents/langgraph.json`
- Auto-created if missing with absolute paths
- Local project `langgraph.json` files are ignored

### Command Routing Flow

The main entry point (`entry.py:main()`) implements command parsing and routing:

```
1. Parse command from sys.argv[1]
2. Check if command is in GLOBAL_COMMANDS set
3. Route to appropriate configuration:

   IF global command (update, rebuild):
     - Use detect_cli_source_root()
     - Config path = CLI source root / config.yml
     - Call run_cli(cli_source_root, config_path, is_global=True)

   ELSE (agent/service command):
     - Use home directory configuration only
     - Config path = ~/.config/myagents/langgraph.json
     - Auto-created if missing with absolute paths
     - Local project files ignored
     - Call run_cli(home_config_path, config_path, is_global=False)
```

### Configuration Path Detection

For agent and service commands, configuration is always loaded from home directory.

#### Implementation Location

**File:** `frontend/cli/entry.py`
**Functions:** `get_home_config_path()`

#### Configuration Flow

```
Home Directory Only Flow:
└── Use ~/.config/myagents/config.yml (auto-created if missing)
```

#### get_home_config_path() Function

**Purpose:** Get home directory configuration path

**Configuration:**
- **Home directory only (XDG standard):**
  - `~/.config/myagents/config.yml` - XDG Base Directory compliant
  - Single source of truth for all configuration
  - Auto-created if missing with parent directories
  - Populated with absolute paths

#### XDG Base Directory Standard Compliance

**Home config location:** `~/.config/myagents/config.yml`

**Standard compliance:**
- Follows XDG Base Directory specification
- User-specific application configs in `~/.config/`
- Consistent with modern CLI tool patterns (git, rg, bat, etc.)
- Separate from system-wide configs

#### Design Decisions

**1. Home directory only**
- Single source of truth for all configuration
- No local project overrides needed
- Consistent behavior everywhere

**2. Absolute paths required**
- Home config uses absolute paths to project files
- Works from any directory
- No dependency on current location

**3. Automatic directory/file creation**
- Reduces setup friction for new users
- Home config created on first run
- Parent directories created automatically

**4. Robust error handling**
- Malformed YAML doesn't break CLI
- Missing files trigger creation, not errors
- Simple home-only approach reduces complexity

**5. No local discovery**
- Local project `langgraph.json` files are ignored
- Eliminates discovery mechanism complexity
- Clear expectation: always uses home directory

### Usage Examples

**Command-line flags work from any directory (early exit):**
```bash
# Can run from anywhere on the system
cd /tmp
myagents --version      # Shows version (exits before routing)
myagents --help         # Shows help (exits before routing)
```

**Global commands work from any directory (via routing):**
```bash
# Can run from anywhere on the system
cd /tmp
myagents update                        # Updates CLI from its installation location
myagents rebuild                       # Rebuilds CLI from its installation location
myagents preferences set key value     # Sets preference globally (stored in ~/.myagents/preferences.json)
myagents preferences get key           # Gets preference from global store
myagents preferences list              # Lists all global preferences
```

**Agent and service commands work from any directory:**
```bash
# Works from any directory via home config
cd /tmp
myagents chat                          # Works - uses ~/.config/myagents/langgraph.json
myagents studio start                  # Works - uses ~/.config/myagents/langgraph.json

cd /home/code/myagents/MyAgents
myagents chat                          # Works - uses ~/.config/myagents/langgraph.json

cd ~/Documents
myagents studio start                  # Works - uses ~/.config/myagents/langgraph.json
```

### Design Rationale

**Why home directory only configuration?**

1. **Simplicity:** Single source of truth eliminates discovery complexity
2. **Consistency:** Same configuration used everywhere regardless of current directory
3. **Portability:** Absolute paths in home config work from any location
4. **Clarity:** No confusion about which configuration is being used

**Why absolute paths in langgraph.json?**

1. **Works from anywhere:** Commands can run from any directory
2. **No discovery needed:** Eliminates directory tree walking
3. **Explicit:** Clear which project files are being used
4. **Maintainable:** Easy to update paths when moving projects

**Why ignore local project files?**

1. **Consistency:** Prevents confusion from multiple configuration sources
2. **Simplicity:** No need to understand discovery priority
3. **Predictability:** Always uses same configuration
4. **Reliability:** No risk of accidentally using wrong config

## Workflow-Based CLI Architecture

### Overview

The MyAgents CLI follows a three-layer architecture pattern:
**Domain → Workflow → Entrypoint**

This design separates business logic (domains), orchestration (workflows), and user interaction (CLI entrypoints), creating a maintainable and testable codebase.

### The Core Workflows

#### 1. HealthCheckWorkflow
**Purpose:** CLI infrastructure validation and configuration detection

**Location:** `src/myagents/backend/services/agents/workflows/health_check_workflow.py`

**Entrypoints:**
- `check_cli_health()` - Verify CLI installation and return health status
- `detect_context(command)` - Detect configuration location for routing commands
- `detect_langgraph_path()` - Get home directory langgraph.json path
- `validate_environment()` - Check Python version and virtual environment

**Use Cases:**
- Command routing (global vs agent/service)
- Environment validation before execution
- Home directory configuration path detection
- CLI installation location detection

**Example:**
```python
from myagents.backend.services.agents.workflows.health_check_workflow import HealthCheckWorkflow

workflow = HealthCheckWorkflow()
context = workflow.detect_context(command="chat")
# Returns: {"context_type": "home", "config_path": Path("~/.config/myagents/langgraph.json")}
```

#### 2. SetupWorkflow
**Purpose:** System setup and user preference management with persistent storage

**Location:** `src/myagents/backend/services/agents/workflows/setup_workflow.py`

**Scope:** Global (works from any directory, stores preferences in `~/.myagents/preferences.json`)

**Note:** `PreferencesWorkflow` is a backward-compatibility alias for `SetupWorkflow`. Both can be imported and used interchangeably.

**Entrypoints:**
- `get_preference(key)` - Retrieve preference value
- `set_preference(key, value)` - Set preference value
- `delete_preference(key)` - Remove preference
- `list_preferences()` - List all preferences
- `clear_preferences()` - Remove all preferences
- `init_config()` - Initialize system configuration

**Features:**
- Dot notation for nested keys (e.g., 'agent.default')
- JSON value support (objects, arrays, numbers, booleans)
- File-based persistence in home directory
- Works from any directory (not project-scoped)
- Configuration initialization for home directory setup

**Use Cases:**
- User configuration management
- Default agent selection
- Studio port configuration
- Custom settings storage
- Initial system setup

**Example:**
```python
from myagents.backend.services.agents.workflows.setup_workflow import SetupWorkflow
# Or use backward-compatible alias:
# from myagents.backend.services.agents.workflows.setup_workflow import PreferencesWorkflow

workflow = SetupWorkflow(preferences_file=Path("~/.myagents/preferences.json"))
success, msg = workflow.set_preference("agent.default", "coding")
success, msg, value = workflow.get_preference("agent.default")
```

#### 3. StudioWorkflow
**Purpose:** LangGraph Studio lifecycle management

**Location:** `src/myagents/backend/services/agents/workflows/studio_workflow.py`

**Entrypoints:**
- `start_studio(background=True)` - Start Studio service
- `stop_studio(force=False)` - Stop Studio gracefully or forcefully
- `restart_studio()` - Restart Studio service
- `get_studio_status()` - Get current status (running, port, PID, URLs)
- `check_studio_health()` - Verify Studio is responding
- `recover_studio_state()` - Recover from inconsistent state
- `get_recent_errors(num_lines)` - Retrieve recent error messages

**Features:**
- Background process management
- PID file tracking
- Port configuration
- State recovery (handles stale PIDs, orphaned processes)

**Use Cases:**
- Starting/stopping Studio for visual debugging
- Status monitoring
- Error diagnostics
- Process cleanup

**Example:**
```python
from myagents.backend.services.agents.workflows.studio_workflow import StudioWorkflow

workflow = StudioWorkflow(
    home_config_dir=Path("~/.config/myagents"),
    config_path=Path("~/.config/myagents/config.yml")
)
success, msg = workflow.start_studio(background=True)
status = workflow.get_studio_status()
# Returns: {"running": True, "port": 2024, "url": "http://localhost:2024", ...}
```

#### 4. HelpWorkflow
**Purpose:** CLI help and metadata display

**Location:** `src/myagents/backend/services/agents/workflows/help_workflow.py`

**Entrypoints:**
- `show_main_help()` - Display main CLI help text
- `show_command_help(command)` - Show command-specific help
- `show_version()` - Display version information
- `show_workflow_docs(workflow)` - Show workflow documentation
- `generate_usage_examples(command)` - Generate usage examples

**Features:**
- Comprehensive command documentation
- Version detection (package or development)
- Usage examples for all commands
- Workflow documentation generation

**Use Cases:**
- Help text display
- Version reporting
- Documentation generation
- Usage examples

**Example:**
```python
from myagents.backend.services.agents.workflows.help_workflow import HelpWorkflow

workflow = HelpWorkflow()
print(workflow.show_version())  # "myagents 0.1.0"
print(workflow.show_main_help())  # Full CLI help text
examples = workflow.generate_usage_examples("studio")  # Studio command examples
```

#### 5. SecretsWorkflow (Function-based)
**Purpose:** Secret management via GCP Secret Manager with environment variable fallback

**Location:** `src/myagents/backend/services/agents/workflows/secrets_workflow.py`

**Architecture:** Wraps `agent_gcptoolkit.secrets.workflows.secret_operations` to maintain architectural boundaries

**Entrypoints:**
- `get_secret(secret_name, project_id=None, quiet=False)` - Retrieve secret from GCP or environment
- `clear_secret_cache()` - Clear cached secret values

**Features:**
- Environment variable checking first (fast path for development)
- GCP Secret Manager fallback (production path)
- In-memory caching (per-process)
- Auto-detection of project_id from GCP_PROJECT env var
- Fail-loud behavior (raises ValueError if secret not found)

**Use Cases:**
- API key retrieval
- Database credential management
- Secure configuration access
- Development/production secret handling

**Example:**
```python
from myagents.backend.services.agents.workflows.secrets_workflow import get_secret, clear_secret_cache

# Get secret (checks env vars first, then GCP)
api_key = get_secret("GEMINI_API_KEY")
db_password = get_secret("DB_PASSWORD", project_id="my-project")

# Clear cache for testing
clear_secret_cache()
```

### CLI Command to Workflow Mapping

The CLI entrypoints in `frontend/cli/myagents_cli.py` delegate to workflows:

| CLI Command | Workflow | Method |
|-------------|----------|--------|
| `myagents --help` | HelpWorkflow | `show_main_help()` |
| `myagents --version` | HelpWorkflow | `show_version()` |
| `myagents preferences list` | SetupWorkflow | `list_preferences()` |
| `myagents preferences get KEY` | SetupWorkflow | `get_preference(key)` |
| `myagents preferences set KEY VAL` | SetupWorkflow | `set_preference(key, value)` |
| `myagents preferences delete KEY` | SetupWorkflow | `delete_preference(key)` |
| `myagents preferences clear` | SetupWorkflow | `clear_preferences()` |
| `myagents studio start` | StudioWorkflow | `start_studio()` |
| `myagents studio stop` | StudioWorkflow | `stop_studio()` |
| `myagents studio restart` | StudioWorkflow | `restart_studio()` |
| `myagents studio status` | StudioWorkflow | `get_studio_status()` |
| Command routing | HealthCheckWorkflow | `detect_context(command)` |
| Config path detection | HealthCheckWorkflow | `detect_langgraph_path()` |
| Secret access (internal) | SecretsWorkflow | `get_secret(secret_name)` |

**Note:** `PreferencesWorkflow` is a backward-compatibility alias for `SetupWorkflow` and can be used interchangeably.

### Architecture Benefits

**1. Separation of Concerns**
- Domains: Pure business logic (preferences storage, studio process management)
- Workflows: Orchestration and coordination (multiple domain calls, error handling)
- Entrypoints: User interaction (argument parsing, output formatting)

**2. Testability**
- Workflows can be tested independently of CLI parsing
- Domain logic can be tested without workflow orchestration
- 56 workflow tests verify behavior at each layer

**3. Reusability**
- Workflows can be called from multiple entrypoints
- Same workflow used by CLI, tests, and future APIs
- Backward-compatible function wrappers for legacy code

**4. Maintainability**
- Clear boundaries between layers
- Single responsibility for each workflow
- Easy to locate and modify functionality

**5. Discoverability**
- Workflows are self-documenting with clear entrypoints
- Help workflow provides documentation for all workflows
- Consistent patterns across all workflows

### Adding New Workflows

To add a new workflow, follow this pattern:

**1. Create workflow class in appropriate service:**
```python
# src/myagents/backend/services/<service>/workflows/my_workflow.py
class MyWorkflow:
    """Workflow for <purpose>."""

    def __init__(self, ...):
        """Initialize workflow."""
        pass

    def my_operation(self, ...) -> Tuple[bool, str]:
        """Perform operation.

        Returns:
            Tuple of (success: bool, message: str)
        """
        from myagents.backend.services.<service>.domains.<domain> import DomainClass

        domain = DomainClass(...)
        return domain.operation(...)
```

**2. Add CLI entrypoint:**
```python
# src/myagents/frontend/cli/myagents_cli.py
def cmd_my_command(args):
    """CLI command handler."""
    from myagents.backend.services.<service>.workflows.my_workflow import MyWorkflow

    workflow = MyWorkflow(...)
    success, message = workflow.my_operation(...)

    if success:
        print(message)
    else:
        print(f"Error: {message}", file=sys.stderr)
        sys.exit(1)
```

**Note:** For function-based workflows (like SecretsWorkflow), import and call the function directly rather than instantiating a class.

**3. Add tests:**
```python
# tests/workflows/infrastructure/test_my_workflow.py
import pytest
from myagents.backend.services.<service>.workflows.my_workflow import MyWorkflow

@pytest.mark.infrastructure
def test_my_workflow_basic():
    """Test basic workflow functionality."""
    workflow = MyWorkflow(...)
    success, message = workflow.my_operation(...)
    assert success
    assert "expected" in message
```

**4. Update documentation:**
- Add workflow to architecture/workflows.md
- Add CLI command to README.md
- Update help text in HelpWorkflow

### Design Decisions

**Why workflows instead of direct domain calls?**
- Workflows provide orchestration layer for multi-domain operations
- Workflows handle cross-cutting concerns (error handling, logging)
- Workflows provide stable API for entrypoints

**Why class-based workflows with backward-compatible functions?**
- Classes enable state management and dependency injection
- Functions maintain backward compatibility with existing code
- Both interfaces coexist during transition period
- Some workflows (like SecretsWorkflow) are function-based by design for simplicity

**Why centralize workflows in agents service?**
- CLI-facing workflows belong with CLI infrastructure
- Reduces coupling between services
- Easier to maintain single workflow interface

**Why separate health check from other workflows?**
- Health checks needed before other workflows can run
- Root detection is prerequisite for routing
- Environment validation is cross-cutting concern

## Frontend Agents Architecture

### Overview

The MyAgents frontend uses a YAML-based agent definition system located in `src/myagents/frontend/agents/`. This system defines specialized agents that can be orchestrated to perform complex multi-agent workflows.

### Agent Definition Structure

Each agent directory follows a consistent structure:

```
src/myagents/frontend/agents/<agent_name>/
├── manifest.yml          # Agent metadata, context, and capabilities
├── definitions.yml       # Domain-specific definitions and concepts
├── process.yml           # Main process workflow
└── processes/            # Sub-process definitions (optional)
    ├── sub_process1.yml
    └── sub_process2.yml
```

### Core Agents

**1. Orchestration Agent** (`orchestration/`)
- **Purpose:** Coordinates multi-agent workflows (Explore → Plan → Execute → Audit)
- **Key Files:**
  - `plan_and_execute.yml` - Main orchestration process
  - `plan.yml` - Planning workflow with exploration loop
  - `execute.yml` - Execution workflow with agent spawning
  - `guidelines.yml` - Orchestration guidelines and best practices
- **Responsibilities:**
  - Reading and updating Live Plans (`docs/plans/live/`)
  - Spawning specialized agents (planner, builder, tester, etc.)
  - Coordinating agent hand-offs
  - Final output auditing

**2. Planner Agent** (`planner/`)
- **Purpose:** Creates and maintains implementation plans
- **Processes:** Research, cleaning, build planning
- **Output:** Updates to Live Plans

**3. Cleaner Agent** (`cleaner/`)
- **Purpose:** Code quality and refactoring
- **Processes:** Identify issues, execute cleaning

**4. Build Agent** (`build/`)
- **Purpose:** Build and compilation tasks
- **Processes:** Flutter builds, general builds

**5. Test Agent** (`test/`)
- **Purpose:** Testing and validation
- **Processes:** Test runner, test builder, audit, user simulator, service tests
- **Testing Types:** smoke_test, user_simulator, service_test, end2end, audit

**6. Deploy Agent** (`deploy/`)
- **Purpose:** Deployment and CI/CD
- **Processes:** Packaging, worktree management, CI/CD maintenance

**7. Documentation Agent** (`documentation/`)
- **Purpose:** Documentation generation and maintenance

**8. Teacher Agent** (`teacher/`)
- **Purpose:** Educational and teaching workflows

**9. Explore Agent** (`explore/`)
- **Purpose:** Codebase exploration and analysis
- **Processes:** Architecture, dependency, feature, test, synthesis exploration

**10. Diagnostics Agent** (`diagnostics/`)
- **Purpose:** System diagnostics and troubleshooting

### Agent Definition Files

**manifest.yml:**
- Worktree structure information
- Folder descriptions
- Agent capabilities and context

**definitions.yml:**
- Domain concepts (plans, guidance, friction, domains, workflows, entrypoints)
- Testing types and strategies
- Agent-specific definitions

**process.yml:**
- Step-by-step process workflows
- Input requirements
- Output specifications
- Agent spawning instructions

### Plan Management

Agents work with three types of plans:

1. **Live Plans** (`docs/plans/live/YYMMDD_<worktree>.yml`)
   - Current in-progress plans per worktree
   - Focused on active work items
   - Updated by orchestration and specialized agents

2. **Backlog Plans** (`docs/plans/backlog/backlog_*.yml`)
   - Future plans organized by category
   - Items moved from backlog to live plans when ready

3. **Completed Plans** (`docs/plans/completed/YYMMDD_<worktree>.yml`)
   - Historical record of completed work
   - Minimized to single-line summaries

### Guidance System

Guidance provides instructions for agents:
- Context about what needs to be done
- Specific instructions for work to be performed
- Important details or constraints
- Process file paths to specify which process to execute

Guidance is read from plans and used by the orchestration agent to construct prompts for spawned agents.

## RemoteAgents Integration

### Overview

MyAgents integrates with **RemoteAgents** (`agent_remote` package) to provide remote service capabilities including relay services and remote terminal access.

### RemoteAgents Package

**Location:** Separate package (`agent_remote`)
**Purpose:** Provides remote service infrastructure

**Services:**

1. **Relay Service** (`agent_remote.services.relay`)
   - WebSocket relay for desktop-client communication
   - Manages active sessions
   - Provides health check endpoints

2. **Terminal Service** (`agent_remote.services.terminal`)
   - Remote terminal PTY sessions (experimental)
   - WebSocket-based terminal access
   - Health check endpoints

### CLI Integration

The MyAgents CLI provides commands for managing RemoteAgents services:

**Relay Commands:**
- `myagents relay start` - Start relay service
- `myagents relay stop` - Stop relay service
- `myagents relay status` - Show relay service status

**Remote Terminal Commands:**
- `myagents remote start` - Start remote terminal service
- `myagents remote stop` - Stop remote terminal service
- `myagents remote status` - Show remote terminal service status

### Workflow Integration

RemoteAgents services are managed through workflow classes:

**RelayServiceWorkflow:**
```python
from agent_remote.services.relay.workflows.relay_service_workflow import RelayServiceWorkflow

workflow = RelayServiceWorkflow(home_config_dir=None)
success, msg = workflow.start_relay(host="localhost", port=8080, background=True)
status = workflow.get_status()
```

**RemoteWorkflow:**
```python
from agent_remote.services.terminal.workflows.remote_workflow import RemoteWorkflow

workflow = RemoteWorkflow(home_config_dir=None)
success, msg = workflow.start_service(port=8080, background=True)
status = workflow.get_status()
```

### Architecture Pattern

RemoteAgents follows the same Domain → Workflow → Entrypoint pattern:
- **Domains:** Core service logic (relay management, terminal PTY handling)
- **Workflows:** Service orchestration (start, stop, status, health checks)
- **Entrypoints:** CLI commands in MyAgents CLI

### Status

- **Relay Service:** Fully functional
- **Terminal Service:** Experimental (PTY functionality not yet implemented)

## Packaging Architecture

**Philosophy:** Scripts for initial installation only, CLI for all subsequent updates

### Why This Approach?

1. **Clarity:** Clear separation between one-time setup vs. ongoing management
2. **Agent-friendly:** Agents can easily discover and use CLI commands
3. **Self-managing:** Package can update itself without external scripts
4. **Discoverability:** CLI commands are self-documenting via help text

### Installation Workflow

**Initial Installation (One-Time):**
- Use `scripts/installation.sh` for first-time setup
- Installs uv package manager if needed
- Creates virtual environment
- Installs dependencies
- Sets up environment variables
- Script is idempotent and safe to re-run

**Subsequent Updates:**
- Use CLI commands (`myagents update`, `myagents rebuild`)
- Package manages its own updates
- No need to re-run installation script

### CLI Command Structure

**GCPToolkit Commands:**
- `gcptoolkit build` - Build package using uv build
- `gcptoolkit rebuild` - Build and reinstall package

**MyAgents Commands:**
- `myagents update` - Reinstall from current source
- `myagents rebuild` - Rebuild and reinstall package

**Makefile Targets:**
- `make rebuild-myagents` - Calls myagents rebuild
- `make test-myagents` - Run myagents tests
- `make update-test-myagents` - Update and test in one step

### Package Dependencies

**MyAgents depends on:**
- agent-gcptoolkit (editable install from ../Agent-GCPtoolkit)
- LangGraph and related packages
- Python 3.11+

**Update order:**
1. Update Agent-GCPtoolkit first if needed (gcptoolkit rebuild)
2. Then update MyAgents (myagents rebuild)
3. Or use Makefile targets for convenience
