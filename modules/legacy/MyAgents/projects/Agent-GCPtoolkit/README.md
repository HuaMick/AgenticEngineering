# Agent-GCPtoolkit

Unified secret management for GCP-based agent worktrees. Provides a single source of truth for secrets via GCP Secret Manager with intelligent caching and fallback mechanisms.

**Note:** As of version 0.2.0, this package is library-only. The CLI entry point has been removed in favor of the unified `myagents` CLI. All functionality remains available via the myagents command.

## Why This Exists

When working with multiple agent worktrees, managing secrets becomes problematic:
- Duplicating .env files across worktrees creates inconsistency
- Hard-coding secrets is a security risk
- Environment variables don't scale across multiple processes

Agent-GCPtoolkit solves this by centralizing secrets in GCP Secret Manager while providing seamless local development support through environment variable fallback.

## Features

- **get_secret()** - Single function to fetch secrets from GCP Secret Manager
- **Memory caching** - Secrets fetched once per process, reducing API calls
- **Environment variable fallback** - Graceful degradation when GCP is unavailable
- **Config-based authentication** - Service account authentication via config file

## Quick Start (No GCP Required)

Test locally with environment variables:

```bash
# Build and install (installs via myagents CLI)
./scripts/build.sh && ./scripts/install-global.sh

# Set a test secret
export MY_SECRET="test_value"

# Retrieve it using the unified myagents CLI
myagents secrets get MY_SECRET
# Output: test_value
# Note: May show GCP warning on stderr (safe to ignore when using env vars)
```

For production setup with GCP Secret Manager, see [Prerequisites](#prerequisites).

## Configuration Management

agent-gcptoolkit uses the XDG Base Directory standard for configuration management, following modern CLI patterns (similar to git, docker, npm). This ensures reliable config discovery regardless of installation method (venv, system, editable).

### Configuration File Location

**Default location**: `~/.config/agent-gcptoolkit/config.yml`

**Preference-based override**: You can set a custom config path using the CLI:
```bash
myagents config set-path /path/to/your/config.yml
```

Preferences are stored in: `~/.config/agent-gcptoolkit/preferences.json`

### Discovery Order

The config file is discovered in the following order:

1. Check preference file (`~/.config/agent-gcptoolkit/preferences.json`) for custom `config_path`
2. If preference exists and file exists, use that path
3. Fall back to default location (`~/.config/agent-gcptoolkit/config.yml`)
4. If no config found, provide clear error with setup instructions

This approach ensures:
- **Explicit over implicit**: No brittle path traversal or assumptions about repository location
- **Works anywhere**: Config discovery works regardless of installation location (venv, system, editable)
- **User control**: Clear preference system for custom locations
- **Good defaults**: Follows XDG standard for modern CLI tools

### Setup Instructions

**Option 1: Use default location**
```bash
mkdir -p ~/.config/agent-gcptoolkit
cp /path/to/your/config.yml ~/.config/agent-gcptoolkit/config.yml
```

**Option 2: Point to existing config**
```bash
myagents config set-path /path/to/your/config.yml
```

**Option 3: Interactive setup**
```bash
myagents config init
```

**Verification**
```bash
myagents config show
```

### Configuration File Format

Your config file should follow this format:

```yaml
authentication:
  type: service_account
  service_account_path: /path/to/service-account-key.json

gcp:
  project_id: your-gcp-project-id
```

## Prerequisites

### 1. GCP Project Setup

```bash
gcloud services enable secretmanager.googleapis.com
```

### 2. Service Account Permissions

```bash
# Grant Secret Manager access to your service account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 3. Project ID Override (Optional)

Override config file project_id with environment variable:
```bash
export GCP_PROJECT="my-project-id"
```

## Installation

### Method 1: UV Tool (RECOMMENDED)

Globally accessible without venv activation. Installs via MyAgents CLI. Reference: https://docs.astral.sh/uv/concepts/tools/

```bash
./scripts/build.sh && ./scripts/install-global.sh
myagents --version
```

### Method 2: UV Pip (Requires venv activation)

```bash
./scripts/build.sh && ./scripts/install.sh
source .venv/bin/activate
myagents --version
```

### Development Scripts

- `./scripts/build.sh` - Build wheel
- `./scripts/install-global.sh` - Install globally (recommended)
- `./scripts/install.sh` - Install in venv
- `./scripts/clean.sh` - Clean build artifacts

## Usage

> **Note**: As of version 0.2.0, all CLI commands are accessed via the unified `myagents` CLI. The standalone `gcptoolkit` command has been removed. For cross-worktree usage (e.g., MyAgents accessing Agent-GCPtoolkit secrets), use the myagents CLI. Python imports only work within the Agent-GCPtoolkit codebase itself due to worktree isolation.

### CLI Commands

All commands are now accessed via `myagents`:

#### Configuration Management

```bash
# Set custom config file path
myagents config set-path /path/to/your/config.yml

# Show current config path and source
myagents config show

# Example output with config file present:
Config path: /home/code/myagents/config/config_agent_gcptoolkit.yml
Source: preference

# Example output when file not found:
Config path: ~/.config/agent-gcptoolkit/config.yml
Source: default (file not found)

# Clear config path preference (revert to default)
myagents config clear

# Example output:
Config path preference cleared. Will use default: ~/.config/agent-gcptoolkit/config.yml

# Interactive config setup wizard
myagents config init
```

**Notes on config commands**:
- `set-path`: Validates file exists before storing, stores absolute path
- `show`: Displays current config path and whether it's from preference or default
- `clear`: Removes custom path preference, reverts to `~/.config/agent-gcptoolkit/config.yml`
- `init`: Interactive wizard to copy existing config or point to custom location

#### Secret Management

```bash
# Get secret from GCP Secret Manager (with env var fallback)
myagents secrets get MY_SECRET

# Get secret in quiet mode (value only, for scripts)
myagents secrets get MY_SECRET -q

# Get secret with project ID override
myagents secrets get MY_SECRET --project-id my-project
```

#### Version and Updates

```bash
# Show version
myagents --version

# Update from latest build
./scripts/build.sh && myagents self-update
```

### Shell Script Integration

For using secrets in shell scripts, use the `-q` (quiet) flag for clean value capture:

```bash
#!/bin/bash
set -e

# Fetch secret with quiet mode (-q) and stderr suppression
API_TOKEN=$(myagents secrets get API_TOKEN -q 2>/dev/null)

# Verify value was retrieved
if [ -z "$API_TOKEN" ]; then
    echo "Error: Failed to fetch API_TOKEN" >&2
    exit 1
fi

# Use in API calls
curl -H "Authorization: Bearer $API_TOKEN" https://api.example.com/data
```

The `-q` flag ensures only the secret value is output to stdout, making it safe for variable assignment and piping to other commands.

See `/home/code/myagents/fetch_and_use_token.sh` for a complete working example.

### Secret Name Format

Must match: `[a-zA-Z0-9_-]+`

Valid: `MY_SECRET`, `api-key-prod`, `DATABASE_PASSWORD_123`
Invalid: `api.key`, `MY SECRET`, `test@prod`

Note: Invalid names rejected by GCP with "Secret not found" error. Empty values not allowed - use placeholder like `UNSET` or `TODO`.

### Exit Codes

- **0** - Success
- **1** - Runtime error (auth failed, secret not found, network error)
- **2** - Usage error (invalid arguments)

### Stderr Output

GCP failures fall back to environment variable. Warnings go to stderr, values to stdout. Suppress warnings:
```bash
SECRET_VALUE=$(myagents secrets get MY_SECRET 2>/dev/null)
```

## How It Works

1. **Config Discovery**: Uses XDG Base Directory standard for config file location:
   - Checks user preference (`~/.config/agent-gcptoolkit/preferences.json`)
   - Falls back to default location (`~/.config/agent-gcptoolkit/config.yml`)
   - Provides clear error with setup instructions if not found
   - Works regardless of installation method (venv, system, editable)

2. **Environment Variable Priority**: Checks environment variables FIRST for fast local development. Only initializes GCP client if env var not found. This provides:
   - Fast local development (< 1ms when using env vars)
   - No GCP authentication delay during development
   - Production still uses GCP Secret Manager when env vars not set

3. **Memory Caching**: Secrets are cached in-memory per-process. CLI invocations spawn new processes, so caching only benefits multiple `get_secret()` calls within the same Python script.

4. **Project ID Resolution**: Uses config file or GCP_PROJECT environment variable to determine the GCP project

## Environment Variables

- **GCP_PROJECT** - GCP project ID (optional, overrides config file)

## Troubleshooting

### First-Time Setup

**Issue**: Running commands shows "Configuration file not found"

**Solution**: You need to set up your configuration file. Choose one of these methods:

1. **Use default location** (recommended):
   ```bash
   mkdir -p ~/.config/agent-gcptoolkit
   cp /path/to/your/config.yml ~/.config/agent-gcptoolkit/config.yml
   ```

2. **Point to existing config**:
   ```bash
   myagents config set-path /path/to/your/config.yml
   ```

3. **Interactive setup**:
   ```bash
   myagents config init
   ```

After setup, verify:
```bash
myagents config show
```

### Configuration file not found

If you see an error about configuration file not found:

```bash
# Check current config path and source
myagents config show

# Option 1: Create config at default location
mkdir -p ~/.config/agent-gcptoolkit
cp /path/to/your/config.yml ~/.config/agent-gcptoolkit/config.yml

# Option 2: Point to existing config
myagents config set-path /path/to/your/config.yml

# Option 3: Use interactive setup
myagents config init

# Verify setup
myagents config show
```

### Config path not updating

If your config path preference doesn't seem to be working:

```bash
# Check preference file contents
cat ~/.config/agent-gcptoolkit/preferences.json

# Verify the config file exists at the path
ls -la $(myagents config show | grep "Config path:" | cut -d' ' -f3)

# Clear preference and try again
myagents config clear
myagents config set-path /path/to/your/config.yml

# Verify
myagents config show
```

### Secret not found

```bash
# Check if secret exists in GCP
gcloud secrets list | grep MY_SECRET

# Verify project ID in your config
myagents config show  # Check which config is being used
cat ~/.config/agent-gcptoolkit/config.yml  # Check project_id value

# Override project ID if needed
export GCP_PROJECT="my-correct-project"

# Use env var fallback for local testing
export MY_SECRET="fallback-value"
```

### GCP fetch failed warning

Command succeeded using env var fallback. Verify authentication is configured correctly in your config file or suppress stderr:

```bash
myagents secrets get MY_SECRET 2>/dev/null
```

To check your authentication configuration:

```bash
# Show which config file is being used
myagents config show

# Check the authentication settings
cat $(myagents config show | grep "Config path:" | cut -d' ' -f3)
```

### Permission denied

Verify your service account has the required role in Prerequisites section 2, or use env var fallback.

### Command not found

UV pip installation requires venv activation:
```bash
source .venv/bin/activate
```

UV tool installation requires shell reload:
```bash
source ~/.bashrc  # or ~/.zshrc
```

Recommended: Use UV tool installation for global access.

## Architecture

```
Agent-GCPtoolkit/
├── backend/services/secrets/src/
│   ├── domains/              # Models and GCP client
│   └── workflows/            # get_secret() with caching & fallback
├── frontend/cli/             # CLI entrypoint and validators
├── agent_gcptoolkit/         # Backward compatibility (DEPRECATED)
├── build-artifacts/          # Build outputs (git-ignored)
└── scripts/                  # Build and install scripts
```

### Design Principles

1. **Separation of Concerns**: Domains (models, clients) separate from workflows (business logic)
2. **Backward Compatibility**: Old imports work with deprecation warnings
3. **Build Artifacts Isolation**: All generated files in `build-artifacts/`
4. **UV Package Manager**: Build and install with UV, not pip
5. **Input Validation**: CLI validates before calling backend
6. **Standardized Exit Codes**: 0=success, 1=runtime, 2=usage

### Migration Path

> **Note**: Python imports are only for code within Agent-GCPtoolkit itself. For cross-worktree usage, use the CLI.

```python
# Old (works with deprecation warning, Agent-GCPtoolkit internal use only)
from agent_gcptoolkit.secrets import get_secret

# New (Agent-GCPtoolkit internal use only)
from backend.services.secrets.src.workflows.secret_operations import get_secret
```

## Development

Package built with UV and setuptools. Requires Python >= 3.10.

```bash
# Install dependencies
pip install google-cloud-secret-manager

# Test from source (within Agent-GCPtoolkit codebase)
python -c "from agent_gcptoolkit.secrets import get_secret; print(get_secret('TEST_SECRET'))"

# For cross-worktree usage, use CLI instead
myagents secrets get TEST_SECRET
```

## Version

Current version: 0.2.0
