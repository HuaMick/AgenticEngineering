# Packaging & Installation Guide

This guide covers the complete packaging workflow for MyAgents, including installation, updates, and development workflows.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [CLI Commands](#cli-commands)
- [Makefile Targets](#makefile-targets)
- [Workflows](#workflows)
- [Artifact Registry Deployment](#artifact-registry-deployment)
- [For Agents](#for-agents)
- [Troubleshooting](#troubleshooting)

## Overview

### Architecture Decision

MyAgents uses a two-tier approach to package management:

1. **Scripts** - For initial installation only (one-time setup)
2. **CLI Commands** - For all subsequent updates and rebuilds

This design makes it easier for agents to discover, install, and manage the project.

### Recent Improvements

**Phase 1-2 Completed (2025-11-05):**
1. **DIAG-001: Protobuf Version Fix**
   - Updated pyproject.toml to require `protobuf>=6.32.1,<7.0.0`
   - Resolved import errors and API failures from version mismatches
   - Ensures compatibility between gRPC and Google Genai SDK

2. **DIAG-002: Studio Process Management**
   - Implemented port-based PID detection fallback
   - Automatic PID file recovery when process is running
   - Stale PID file cleanup for accurate status reporting

3. **CLI-001: Global Command Support**
   - Commands like update, rebuild, version work from any directory
   - CLI source root detection via `__file__` path traversal
   - Separate routing for global vs project commands

### When to Use Scripts

Use `scripts/installation.sh` ONLY for:
- First-time installation on a new system
- Setting up a fresh development environment
- Initial worktree setup

The script is idempotent and safe to re-run, but subsequent updates should use CLI commands.

### When to Use CLI

Use CLI commands for:
- Updating packages after code changes
- Rebuilding packages during development
- Testing package installations
- All ongoing package management

## Installation

### Prerequisites

Before installing, ensure you have:
- Python 3.11 or higher
- Git (for cloning the repository)
- GCP project with Secret Manager API enabled
- Gemini API key stored in GCP Secret Manager

### Dependency Requirements

MyAgents has specific version requirements for key dependencies:

**Protobuf Version:**
- Required: `protobuf>=6.32.1,<7.0.0`
- This version constraint ensures compatibility between gRPC and Google Genai SDK
- Earlier versions (e.g., 4.x, 5.x) cause import errors and API failures

### Initial Installation

Run the installation script from the project root:

```bash
cd /path/to/myagents
./scripts/installation.sh
```

The script will:
1. Check Python version (3.11+ required)
2. Install uv package manager if not present
3. Create virtual environment (.venv)
4. Install project dependencies
5. Install myagents package in editable mode
6. Verify installation
7. Display next steps

### Environment Setup

After installation, set required environment variables:

```bash
# Set your GCP project ID
export GCP_PROJECT_ID="your-gcp-project-id"

# Make it permanent
echo 'export GCP_PROJECT_ID="your-gcp-project-id"' >> ~/.bashrc
# OR for zsh:
echo 'export GCP_PROJECT_ID="your-gcp-project-id"' >> ~/.zshrc
```

### Verification

Verify the installation:

```bash
# Activate virtual environment
source .venv/bin/activate

# Check myagents CLI
myagents --help

# Check gcptoolkit CLI
gcptoolkit --help

# Test basic functionality
myagents chat --agent echo
```

### Installation Troubleshooting

**Problem: uv installation fails**
- Manually install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Ensure ~/.cargo/bin is in your PATH
- Restart your shell

**Problem: Python version too old**
- Install Python 3.11+: `pyenv install 3.11` or use system package manager
- Verify version: `python3 --version`

**Problem: GCP_PROJECT_ID not set**
- Export the variable in your current shell
- Add to shell profile for persistence
- Verify: `echo $GCP_PROJECT_ID`

**Problem: Virtual environment activation fails**
- Ensure .venv directory was created
- Try: `source .venv/bin/activate` or `. .venv/bin/activate`
- Check file permissions

## CLI Commands

### Global Command Architecture

MyAgents CLI supports global commands that work from any directory:

**Global Commands:**
- `myagents update` - Reinstall myagents from source
- `myagents rebuild` - Full rebuild and reinstall
- `myagents --version` - Show version information

**How Global Commands Work:**
- Detect CLI installation location via `__file__` path traversal
- Use CLI source root (where CLI is installed) instead of project root
- No project detection required - work from any directory
- Implementation in `/frontend/cli/entry.py` routes commands based on type

**Project Commands:**
- `myagents chat` - Requires project root (langgraph.json detection)
- `myagents studio` - Requires project root and config detection
- `myagents preferences` - Requires project root

This architecture allows package management from anywhere while project-specific commands enforce proper project context.

### GCPToolkit Commands

The agent-gcptoolkit package provides commands for building and managing itself.

#### gcptoolkit build

Build the agent-gcptoolkit package:

```bash
gcptoolkit build
```

**What it does:**
- Runs `uv build` from the Agent-GCPtoolkit directory
- Creates wheel and source distribution
- Outputs to `build-artifacts/dist/` directory

**When to use:**
- After making changes to agent-gcptoolkit code
- Before installing a new version
- When testing build configuration

**Example output:**
```
=== Building agent-gcptoolkit ===
[uv build output]
=== Build complete. Artifacts in build-artifacts/dist/ ===
```

#### gcptoolkit rebuild

Build and reinstall agent-gcptoolkit in one step:

```bash
gcptoolkit rebuild
```

**What it does:**
1. Runs `gcptoolkit build`
2. Finds the latest wheel in build-artifacts/dist/
3. Force reinstalls the wheel using `uv pip install --force-reinstall`

**When to use:**
- During active development on agent-gcptoolkit
- After making changes you want to test immediately
- When you need a fresh installation

**Example output:**
```
=== Rebuilding agent-gcptoolkit (build + reinstall) ===
=== Building agent-gcptoolkit ===
[build output]
=== Build complete. Artifacts in build-artifacts/dist/ ===
=== Updating agent-gcptoolkit from build-artifacts/dist/ ===
Installing: build-artifacts/dist/agent_gcptoolkit-0.1.0-py3-none-any.whl
[install output]
=== Update complete ===
```

#### gcptoolkit version

Show version information:

```bash
gcptoolkit version
gcptoolkit version --verbose  # Show package root path
```

### MyAgents Commands

The myagents package provides commands for managing itself.

#### myagents update

Reinstall myagents from current source:

```bash
myagents update
```

**What it does:**
- Reinstalls myagents package from current source directory
- Uses `uv pip install -e .`
- Preserves editable install mode

**When to use:**
- After pulling latest code changes
- When dependencies were updated in pyproject.toml
- To refresh package metadata
- For simpler updates without full rebuild

**Example output:**
```
Updating myagents from current source...
[install output]
Successfully updated myagents
```

#### myagents rebuild

Rebuild and reinstall myagents package:

```bash
myagents rebuild
```

**What it does:**
1. Cleans previous build artifacts (build/, dist/, *.egg-info/)
2. Builds the package using `python -m build`
3. Reinstalls using `uv pip install -e .`

**When to use:**
- After making significant code changes
- When you suspect stale build artifacts
- During active development with frequent changes
- When full rebuild is needed

**Example output:**
```
Rebuilding myagents package...
Cleaning previous build artifacts...
Building package...
[build output]
Reinstalling package...
[install output]
Successfully rebuilt and reinstalled myagents
```

### CLI Error Handling

All CLI commands include error handling:

**Missing dependencies:**
```
Error: Installation tool not found: uv
Please ensure uv is available in your PATH
```

**Build failures:**
```
Error building package:
[detailed error message from build tool]
```

**Installation failures:**
```
Error reinstalling myagents:
[detailed error message from install tool]
```

## Makefile Targets

The Makefile provides convenient shortcuts for common operations.

### rebuild-myagents

Rebuild the myagents package:

```bash
make rebuild-myagents
```

**What it does:**
- Calls `uv run myagents rebuild`
- Rebuilds and reinstalls myagents

**When to use:**
- Quick rebuild during development
- Part of automated workflows

### test-myagents

Run myagents test suite:

```bash
make test-myagents
```

**What it does:**
- Runs `uv run pytest tests/`
- Executes all tests in the tests/ directory

**When to use:**
- After making code changes
- Before committing changes
- As part of CI/CD workflows

## Workflows

### Initial Installation Workflow

For first-time setup:

```bash
# 1. Clone repository
cd /path/to/myagents

# 2. Run installation script
./scripts/installation.sh

# 3. Set environment variables
export GCP_PROJECT_ID="your-project-id"

# 4. Activate virtual environment
source .venv/bin/activate

# 5. Verify installation
myagents --help
gcptoolkit --help

# 6. Test basic functionality
myagents chat --agent echo
```

### Development Workflow

For making and testing changes:

```bash
# 1. Make code changes to myagents or agent-gcptoolkit

# 2. If changes to agent-gcptoolkit:
gcptoolkit rebuild

# 3. If changes to myagents:
myagents rebuild

# 4. Test changes
myagents chat

# 5. Run test suite
make test-myagents
```

### Update Workflow

For getting latest changes:

```bash
# 1. Pull latest code
git pull origin main

# 2. If dependencies changed, update them
uv sync

# 3. Update agent-gcptoolkit if needed
gcptoolkit rebuild

# 4. Update myagents
myagents update
# OR for full rebuild:
myagents rebuild

# 5. Verify updates
myagents --help
```

### Multi-Worktree Development

When working with multiple git worktrees:

```bash
# 1. Create worktree for feature branch
git worktree add ../MyAgents-feature-name feature-branch

# 2. Switch to new worktree
cd ../MyAgents-feature-name

# 3. Run installation script
./scripts/installation.sh

# 4. Make changes and test
# [make your changes]
myagents rebuild
make test-myagents

# 5. Switch back to main worktree
cd ../MyAgents

# 6. Update main worktree if needed
myagents update
```

### Common Scenarios

#### Scenario 1: Testing a Quick Change

```bash
# Edit a file
vim src/myagents/backend/services/agents/workflows/coding_agent.py

# Rebuild and test
make rebuild-myagents
make test-myagents
```

#### Scenario 2: Updating Dependencies

```bash
# Edit pyproject.toml
vim pyproject.toml

# Sync dependencies
uv sync

# Rebuild package
myagents rebuild

# Test
make test-myagents
```

#### Scenario 3: Working on Both Packages

```bash
# Make changes to agent-gcptoolkit
vim ../Agent-GCPtoolkit/agent_gcptoolkit/cli/main.py

# Rebuild gcptoolkit
gcptoolkit rebuild

# Make changes to myagents
vim frontend/cli/myagents_cli.py

# Rebuild myagents (will use updated gcptoolkit)
myagents rebuild

# Test everything
make test-myagents
```

#### Scenario 4: Switching Between Branches

```bash
# Save current work
git stash

# Switch branch
git checkout feature-branch

# Update installation
myagents update

# Work on feature
# [make changes]

# Switch back
git checkout main
git stash pop

# Update installation again
myagents update
```

## Artifact Registry Deployment

### Overview

MyAgents packages can be published to Google Artifact Registry for private distribution. This enables:
- Version-controlled package releases
- Private package hosting
- Integration with GCP infrastructure
- Centralized package management

For detailed registry setup and configuration, see [Registry Setup Guide](registry-setup.md).

### Quick Start

**Deployment Scripts:**
- `scripts/deploy-to-registry.sh` - Generic deployment script
- `scripts/deploy-gcptoolkit.sh` - Deploy Agent-GCPtoolkit
- `scripts/deploy-myagents.sh` - Deploy MyAgents package

**Deploy to Production:**
```bash
# Deploy MyAgents package
./scripts/deploy-myagents.sh

# Deploy Agent-GCPtoolkit package
./scripts/deploy-gcptoolkit.sh
```

### Registry Workflow

#### 1. Update Package Version

Edit `pyproject.toml` and increment the version:

```toml
[project]
name = "myagents"
version = "0.2.0"  # Increment version
```

#### 2. Test Locally

Before deploying, test the package locally:

```bash
# Rebuild and test
make rebuild-myagents
make test-myagents
```

#### 3. Deploy to Registry

Use the deployment script:

```bash
# Deploy MyAgents
./scripts/deploy-myagents.sh

# Deploy Agent-GCPtoolkit
./scripts/deploy-gcptoolkit.sh
```

The script will:
1. Validate prerequisites and configuration
2. Build the package using `uv build`
3. Upload to Artifact Registry
4. Verify successful upload

#### 4. Verify Deployment

Check the package was uploaded successfully:

```bash
gcloud artifacts packages list \
  --repository=myagents-python \
  --location=us-central1

gcloud artifacts versions list \
  --package=myagents \
  --repository=myagents-python \
  --location=us-central1
```

### Installing from Registry

Once packages are published, install them using pip:

```bash
# Install latest version (pip.conf already configured)
uv pip install myagents

# Install specific version
uv pip install myagents==0.2.0

# Force upgrade to latest
uv pip install --upgrade myagents
```

### Registry Configuration

#### Available Registries

| Registry | Environment | URL |
|----------|-------------|-----|
| myagents-python | Production | https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/ |
| myagents-python-test | Testing | https://us-central1-python.pkg.dev/myagents-475112/myagents-python-test/simple/ |

#### pip Configuration

Global pip configuration in `~/.config/pip/pip.conf`:

```ini
[global]
extra-index-url = https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/
```

This allows pip to search both PyPI and the private registry automatically.

### Deployment Script Details

#### deploy-to-registry.sh

Main deployment script with full functionality.

**Usage:**
```bash
./scripts/deploy-to-registry.sh REGISTRY_NAME PACKAGE_DIR PROJECT_ID
```

**Parameters:**
- `REGISTRY_NAME` - Target registry (e.g., myagents-python)
- `PACKAGE_DIR` - Absolute path to package directory
- `PROJECT_ID` - GCP project ID

**Features:**
- Parameter validation
- Build artifact cleanup
- Package building with uv
- Upload to Artifact Registry
- Upload verification
- Detailed logging with color coding

#### deploy-gcptoolkit.sh

Convenience wrapper for deploying Agent-GCPtoolkit.

**Usage:**
```bash
./scripts/deploy-gcptoolkit.sh
```

Pre-configured settings:
- Registry: myagents-python
- Package: /home/code/myagents/Agent-GCPtoolkit
- Project: myagents-475112

#### deploy-myagents.sh

Convenience wrapper for deploying MyAgents package.

**Usage:**
```bash
./scripts/deploy-myagents.sh
```

Pre-configured settings:
- Registry: myagents-python
- Package: /home/code/myagents/MyAgents-packaging-001
- Project: myagents-475112

### Common Registry Operations

#### List all packages
```bash
gcloud artifacts packages list \
  --repository=myagents-python \
  --location=us-central1
```

#### List package versions
```bash
gcloud artifacts versions list \
  --package=myagents \
  --repository=myagents-python \
  --location=us-central1
```

#### View package details
```bash
gcloud artifacts packages describe myagents \
  --repository=myagents-python \
  --location=us-central1
```

#### Delete a version
```bash
gcloud artifacts versions delete VERSION \
  --package=myagents \
  --repository=myagents-python \
  --location=us-central1
```

### Registry Troubleshooting

#### Authentication Issues

If you encounter authentication errors:

1. Verify keyring helper is installed:
   ```bash
   pip show keyrings.google-artifactregistry-auth
   ```

2. Re-authenticate with gcloud:
   ```bash
   gcloud auth application-default login
   ```

3. Verify pip configuration:
   ```bash
   cat ~/.config/pip/pip.conf
   ```

#### Build Failures

If package build fails:

1. Clean build artifacts:
   ```bash
   rm -rf dist/ build/ *.egg-info
   ```

2. Build manually to see errors:
   ```bash
   uv build --out-dir dist/
   ```

3. Check pyproject.toml is valid

#### Upload Failures

If upload to registry fails:

1. Verify registry exists:
   ```bash
   gcloud artifacts repositories describe myagents-python --location=us-central1
   ```

2. Check permissions on service account

3. Verify GCP project is correct:
   ```bash
   gcloud config get-value project
   ```

For more detailed troubleshooting, see [Registry Setup Guide](registry-setup.md#troubleshooting).

## For Agents

### Agent Usage Guidelines

When agents need to install or manage MyAgents:

**Initial Installation:**
```bash
# Clone repository
git clone <repo-url> /path/to/myagents
cd /path/to/myagents

# Run installation script
./scripts/installation.sh

# Verify installation
myagents --help
```

**Updating Package:**
```bash
# After code changes
myagents rebuild

# Or for simple updates
myagents update
```

**Testing Changes:**
```bash
# Run tests
make test-myagents

# Or manual testing
myagents chat
```

### Best Practices for Agents

1. **Always use installation script first**
   - Don't try to manually install dependencies
   - Script handles all setup steps

2. **Use CLI commands for updates**
   - Never re-run installation script for updates
   - Use `myagents update` or `myagents rebuild`

3. **Verify before proceeding**
   - Check `myagents --help` works
   - Test basic functionality before complex operations

4. **Handle errors gracefully**
   - Check command exit codes
   - Read error messages carefully
   - Report issues if commands fail

5. **Use Makefile targets when available**
   - More convenient than running commands directly
   - Handles dependencies automatically

### Agent Testing Guidelines

When testing packaging changes:

1. **Test in clean environment**
   - Use fresh worktree or container
   - Verify installation script works

2. **Test update workflow**
   - Install once
   - Make changes
   - Test rebuild commands
   - Verify updates work

3. **Test error handling**
   - Try invalid commands
   - Verify error messages are helpful
   - Ensure graceful failure

4. **Test dependencies**
   - Verify agent-gcptoolkit updates propagate
   - Test dependency resolution

## Troubleshooting

### Common Issues

#### Issue: Protobuf version conflicts

**Symptoms:**
```
ImportError: cannot import name 'builder' from 'google.protobuf.internal'
AttributeError: module 'google._upb._message' has no attribute 'MessageMapContainer'
```

**Cause:**
- Incompatible protobuf version (4.x, 5.x, or early 6.x)
- Version mismatch between gRPC and Google Genai SDK

**Solutions:**
1. Verify protobuf version: `pip show protobuf`
2. Upgrade to required version: `uv pip install "protobuf>=6.32.1,<7.0.0"`
3. Rebuild package: `myagents rebuild`
4. Check pyproject.toml has correct constraint: `protobuf>=6.32.1,<7.0.0`

**Prevention:**
- Always use `uv sync` after pulling code changes
- Verify dependencies after environment changes
- Check protobuf version before reporting import errors

#### Issue: Studio process management issues

**Symptoms:**
```
Studio is not running (port check shows running but PID file missing)
Studio status reports incorrect state
Cannot stop Studio (PID file is stale)
```

**How It's Fixed:**
- Dual detection method: PID file + port-based detection
- Port-based PID recovery using `lsof -ti :<port>`
- Automatic PID file recreation when port is in use
- Stale PID file cleanup when process doesn't exist

**Implementation Details:**
- `StudioManager.is_running()` checks PID file first
- If port is in use but PID missing, recovers PID using `lsof`
- Recreates PID file for proper process management
- Location: `/backend/services/studio/src/domains/studio_manager/manager.py`

**Manual Recovery:**
If Studio state is inconsistent:
1. Check port status: `lsof -i :2024`
2. Check PID file: `cat /tmp/myagents_studio.pid`
3. Stop Studio: `myagents studio stop --force`
4. Start fresh: `myagents studio start`

#### Issue: Global commands not working from any directory

**Symptoms:**
```
Error: Could not find langgraph.json
(when running myagents update from outside project directory)
```

**Cause:**
- Command incorrectly classified as project command
- Missing from global commands list in entry.py

**Solutions:**
1. Use from MyAgents project directory
2. Verify command should be global (update, rebuild, version)
3. Check implementation in `/frontend/cli/entry.py`

**Global vs Project Commands:**
- Global: Work from any directory using CLI source root
- Project: Require langgraph.json and project root detection

#### Issue: Command not found after installation

**Symptoms:**
```bash
$ myagents
-bash: myagents: command not found
```

**Solutions:**
1. Activate virtual environment: `source .venv/bin/activate`
2. Verify installation: `uv run myagents --help`
3. Reinstall: `uv pip install -e .`

#### Issue: Import errors after update

**Symptoms:**
```
ModuleNotFoundError: No module named 'backend'
```

**Solutions:**
1. Rebuild package: `myagents rebuild`
2. Check virtual environment is activated
3. Verify package is installed: `pip list | grep myagents`

#### Issue: Build fails with missing dependencies

**Symptoms:**
```
Error building package:
ModuleNotFoundError: No module named 'build'
```

**Solutions:**
1. Install build dependency: `uv pip install build`
2. Or sync all dependencies: `uv sync`

#### Issue: Agent-gcptoolkit not found

**Symptoms:**
```
Error: Could not locate Agent-GCPtoolkit source repository
```

**Solutions:**
1. Verify Agent-GCPtoolkit exists: `ls ../Agent-GCPtoolkit`
2. Check pyproject.toml path configuration
3. Ensure editable install: `uv pip install -e ../Agent-GCPtoolkit`

#### Issue: Permission denied during installation

**Symptoms:**
```
Permission denied: '/usr/local/bin/uv'
```

**Solutions:**
1. Don't use sudo with uv
2. Install uv for your user: `curl -LsSf https://astral.sh/uv/install.sh | sh`
3. Ensure ~/.cargo/bin is in PATH

#### Issue: Tests fail after rebuild

**Symptoms:**
```
FAILED tests/test_something.py::test_function
```

**Solutions:**
1. Check if code changes broke tests
2. Update tests if needed
3. Verify test dependencies installed: `uv sync`

### Getting Help

If you encounter issues not covered here:

1. Check command help: `myagents --help`, `gcptoolkit --help`
2. Review installation output for errors
3. Check virtual environment is activated
4. Verify Python version: `python3 --version`
5. Try in clean environment (new worktree)

### Known Limitations

1. **No Windows support verified**
   - Scripts tested on Linux/macOS only
   - Windows users may need WSL

2. **Requires Python 3.11+**
   - Earlier versions not supported
   - Check version: `python3 --version`

3. **Assumes uv available**
   - Falls back to pip if needed
   - Best experience with uv

4. **Editable installs required**
   - Development mode only
   - Not for production deployment

## Additional Resources

- [Architecture](architecture.md) - Packaging architecture decisions
- [Setup Guide](setup.md) - Initial environment setup
- [README](../README.md) - Project overview and quick start
- [Agent-GCPtoolkit README](../../Agent-GCPtoolkit/README.md) - GCPtoolkit documentation
