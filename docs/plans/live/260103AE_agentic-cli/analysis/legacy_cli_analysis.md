# Legacy CLI Analysis

## Source Location
`modules/legacy/MyAgents/projects/MyAgentsBackend/src/myagents/frontend/cli`

## File Structure
```
cli/
├── __init__.py      # Empty package init
├── entry.py         # Entry point (121 lines)
└── myagents_cli.py  # Main CLI (1989 lines)
```

## Key Architecture Patterns

### 1. Entry Point Pattern
- Separate `entry.py` for project detection and routing
- Fast help handling: --help/-h and --version before any imports
- Lazy imports for startup performance

### 2. Command Structure
```
myagents
├── Agent Commands
│   ├── chat [--agent AGENT]
│   ├── agents
│   ├── clean --identify|--execute
│   ├── test --run|--audit|--simulate
│   └── explore --arch|--feature|--dep|--test|--synth
│
├── Service Management
│   ├── studio start|stop|restart|status
│   ├── relay start|stop|status
│   └── remote start|stop|status
│
├── Configuration
│   ├── config set-path|show|clear|init|verify|list
│   ├── preferences get|set|delete|list|clear
│   └── secrets get
│
└── Package Management
    ├── update
    ├── rebuild
    ├── setup
    └── gcptoolkit build|update|rebuild
```

### 3. Workflow Integration
All complex operations delegate to backend workflows:
- `HealthCheckWorkflow`: Context detection
- `StudioWorkflow`: Studio management
- `SetupWorkflow`: Initial setup
- `PreferencesWorkflow`: User preferences

### 4. Home Directory as Source of Truth
All CLI operations use centralized home configuration (`~/.config/myagents/`).
No project detection required for most commands.

## Patterns to Adopt for AgenticCLI

1. **Lazy imports** - Only import what's needed
2. **Separate entry.py** - Keep routing logic separate
3. **Argparse subparsers** - For command groups
4. **Workflow delegation** - Complex ops in separate modules
5. **Consistent error handling** - stderr output, exit codes
6. **Home directory config** - Central preferences storage

## Commands to Exclude (Non-Core)

- GCP toolkit commands
- LangSmith integration
- LangGraph Studio commands
- Relay/Remote service commands
- Agent execution (chat) - deferred
