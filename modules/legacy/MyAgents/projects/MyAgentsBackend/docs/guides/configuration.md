# Configuration Guide

This guide covers configuration files and their purpose in MyAgents.

## Configuration Files

### config.yml

Location: `~/.config/myagents/config.yml`

Purpose: Runtime configuration for MyAgents CLI and agents.

#### Config Location

MyAgents uses home directory configuration exclusively:

- **~/.config/myagents/config.yml** - Single source of truth for all configuration
- **Auto-creation** - Created automatically if missing

Local project config files are ignored.

#### Home Directory Config

MyAgents stores global configuration in your home directory:

- **Location**: `~/.config/myagents/config.yml`
- **Standard**: Follows XDG Base Directory specification
- **Auto-creation**: Created automatically on first use
- **Purpose**: Global defaults for all MyAgents installations

#### Home Directory Only

All configuration is stored in the home directory:

- **Single source of truth**: `~/.config/myagents/config.yml`
- **No local overrides**: Local project config files are ignored
- **Works from anywhere**: Same configuration used regardless of current directory

#### Examples

```yaml
# Example: Home directory config
# Location: ~/.config/myagents/config.yml
project: my-project
environment: production
```

### langgraph.json

Purpose: Defines LangGraph Studio configuration and graph definitions.

#### Home Directory Only

MyAgents uses home directory configuration exclusively:

- **Location**: `~/.config/myagents/langgraph.json` (single source of truth)
- **Auto-creation**: Created automatically on first agent command
- **Absolute paths**: All workflow paths must be absolute
- **No local discovery**: Local project `langgraph.json` files are ignored

#### Structure

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
    "echo": "/home/code/myagents/MyAgents/src/myagents/backend/services/agents/workflows/echo_agent.py:create_echo_agent",
    "coding": "/home/code/myagents/MyAgents/src/myagents/backend/services/agents/workflows/coding_agent.py:create_coding_agent"
  },
  "env": "/home/code/myagents/MyAgents/.env"
}
```

**Important**: All paths must be absolute. Update paths in home config when moving project directories.

## Migration Guide: Local to Home Directory

If you previously used local project `langgraph.json` files, follow this guide to migrate to the home directory architecture.

### Understanding the Change

**Old Architecture (No Longer Supported):**
- Local project `langgraph.json` files in each project directory
- Configuration discovered by walking up directory tree
- Different configs for different projects

**New Architecture:**
- Single `~/.config/myagents/langgraph.json` in home directory
- Works from any directory
- Same configuration everywhere
- Local project files are ignored

### Migration Steps

**Step 1: Backup your local configuration (optional)**
```bash
# If you have a local langgraph.json you want to preserve
cp langgraph.json langgraph.json.backup
```

**Step 2: Run setup to create home directory configuration**
```bash
# This creates ~/.config/myagents/langgraph.json with default settings
myagents setup
```

**Step 3: Customize home configuration if needed**

If you had custom settings in your local `langgraph.json`, transfer them to the home directory config:
```bash
# View your backup (if you created one)
cat langgraph.json.backup

# Edit home directory configuration
vim ~/.config/myagents/langgraph.json

# Important: Use absolute paths, not relative paths
```

**Step 4: Convert relative paths to absolute paths**

The home directory config requires absolute paths. Convert any relative paths:
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
    "echo": "/home/code/myagents/MyAgents/src/myagents/backend/services/agents/workflows/echo_agent.py:create_echo_agent",
    "coding": "/home/code/myagents/MyAgents/src/myagents/backend/services/agents/workflows/coding_agent.py:create_coding_agent"
  },
  "env": "/home/code/myagents/MyAgents/.env"
}
```

**Step 5: Test from multiple directories**
```bash
# Test from home directory
cd ~/
myagents chat

# Test from arbitrary directory
cd /tmp
myagents chat

# Test from project directory
cd /home/code/myagents/MyAgents
myagents chat

# All should work identically using home directory config
```

**Step 6: Remove local langgraph.json files (optional)**

Local files are ignored but you can remove them to avoid confusion:
```bash
# Remove local config from project directories
rm langgraph.json

# Local files will be ignored even if present
```

### Common Migration Issues

**Issue: Commands can't find agents after migration**

Solution: Verify absolute paths in home directory configuration:
```bash
# Check configuration
cat ~/.config/myagents/langgraph.json

# Ensure paths point to actual file locations
ls -la /home/code/myagents/MyAgents/src/myagents/backend/services/agents/workflows/
```

**Issue: Different behavior in different directories**

Solution: This should not happen with home directory architecture. If it does:
1. Verify you're using the latest version of MyAgents
2. Check that local `langgraph.json` files are not being picked up (they should be ignored)
3. Run `myagents setup` to regenerate home directory configuration

**Issue: Want different configs for different projects**

The new architecture uses a single configuration. If you need project-specific settings:
1. Use environment variables for project-specific values
2. Edit `~/.config/myagents/langgraph.json` when switching projects
3. Consider using separate user accounts for completely isolated configs

#### Home Directory Configuration

MyAgents uses home directory as single source of truth:

- **Location**: `~/.config/myagents/langgraph.json`
- **Standard**: Follows XDG Base Directory specification
- **Auto-creation**: Automatically created on first agent command with absolute paths
- **Works from anywhere**: Same configuration used regardless of current directory

#### Usage Examples

**Example 1: Work from any directory**
```bash
# Commands work from any directory
cd /tmp
myagents studio start  # Uses ~/.config/myagents/langgraph.json

cd ~/Documents
myagents chat          # Uses ~/.config/myagents/langgraph.json

cd /home/code/myagents/MyAgents
myagents chat          # Uses ~/.config/myagents/langgraph.json
```

**Example 2: Update paths when moving project**
```bash
# If you move your project directory, update the home config
vim ~/.config/myagents/langgraph.json
# Update all absolute paths to new project location

# Verify updated paths
myagents studio start
```

### config.yml

Location: `~/.config/myagents/config.yml`

Purpose: Configuration for LangGraph Studio service management. Created by `myagents config init`.

Sections:
- **server**: Host, port, and server settings
- **runtime**: PID file location, checkpoint directory, log directory
- **langgraph**: Project name for LangSmith tracing

### pyproject.toml

Location: Root of project

Purpose: Python project configuration including dependencies, build settings, and CLI entrypoints.

Key sections:
- `[project]`: Project metadata and dependencies
- `[project.scripts]`: CLI command definitions (`myagents` command)
- `[build-system]`: Build backend configuration

## Configuration Limitations

Current limitations:

- **No .env file support** - Must use environment variables or Secret Manager
- **Hardcoded model name** - Cannot change model without code edits
- **Hardcoded temperature** - No runtime configuration
- **Hardcoded max_tokens** - Fixed in code
- **No runtime configuration files** - All settings in code or environment variables

## Troubleshooting Configuration

### Common Issues

**Commands not finding configuration:**
```bash
# Verify home directory configuration exists
ls -la ~/.config/myagents/langgraph.json

# If missing, create it with setup
myagents setup

# View configuration to verify absolute paths
cat ~/.config/myagents/langgraph.json
```

**Local project langgraph.json being ignored:**

This is expected behavior. The home directory configuration is the single source of truth:
- Local project `langgraph.json` files are intentionally ignored
- All commands use `~/.config/myagents/langgraph.json` regardless of current directory
- To update configuration, edit `~/.config/myagents/langgraph.json` directly

**Commands work in some directories but not others:**

All commands should work from any directory. If you experience directory-specific issues:
1. Verify paths in `~/.config/myagents/langgraph.json` are absolute (not relative)
2. Check that workflow files exist at the specified absolute paths
3. Run `myagents setup` to regenerate configuration with correct paths

**Moving project directory:**

If you move your MyAgents project directory, update the absolute paths in home configuration:
```bash
# Edit home directory configuration
vim ~/.config/myagents/langgraph.json

# Update all paths to new project location
# Example: Change /old/path/MyAgents to /new/path/MyAgents
```

**Permission errors:**

Ensure you have write permissions for the home directory configuration:
```bash
# Check permissions
ls -la ~/.config/myagents/

# Fix permissions if needed
chmod 755 ~/.config/myagents/
chmod 644 ~/.config/myagents/langgraph.json
```

## Configuration Management

For managing secrets and environment variables, see [Setup Guide](../SETUP.md).
