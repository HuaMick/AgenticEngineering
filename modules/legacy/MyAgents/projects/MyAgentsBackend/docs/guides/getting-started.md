# Getting Started with MyAgents

This guide will help you set up MyAgents from scratch. Follow these steps in order to get your development environment running.

## Prerequisites

Before you begin, ensure you have the following installed:

### Required Software

1. **Python 3.11 or higher**
   ```bash
   # Check your Python version
   python --version
   ```
   If you need to install Python 3.11+, visit [python.org](https://www.python.org/downloads/)

2. **uv Package Manager**

   uv is a fast Python package installer and resolver. Install it with:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   After installation, verify it's working:
   ```bash
   uv --version
   ```

3. **GCP Prerequisites** (for production use)
   - A Google Cloud Platform project
   - GCP Secret Manager API enabled
   - Gemini API key stored in GCP Secret Manager

   Note: For local development and testing, GCP is optional as the test suite uses mocks.

### Important: Private Registry Dependency

**MyAgents depends on `agent-gcptoolkit` which is currently hosted on a private GCP Artifact Registry.**

Until this package is published to public PyPI, installation options are:

1. **Local Development (Recommended):** Use `uv sync` which resolves `agent-gcptoolkit` from the local workspace
2. **Internal Developer Access:** Authenticate to the private GCP Artifact Registry (see below)
3. **Pre-built Wheels:** Contact the maintainer for pre-built wheel files

This guide covers the local development approach. For private registry access, see the main README.

## Clone the Repository

Clone the MyAgents repository to your local machine:

```bash
# Clone the repository
git clone https://github.com/HuaMick/MyAgents.git

# Navigate to the project directory
cd MyAgents
```

## Install Dependencies

MyAgents uses `uv` for dependency management. You have two options:

### Option 1: Using Make (Recommended)

```bash
make install
```

This command runs `uv sync` under the hood and installs all project dependencies.

### Option 2: Direct uv Command

```bash
uv sync
```

After dependencies are installed, install the package in editable mode:

```bash
pip install -e .
```

This makes the `myagents` command available globally on your system.

## Verify Installation

Check that MyAgents is installed correctly:

```bash
# Check version
myagents --version

# View help menu
myagents --help
```

You should see the version number and available commands.

## Run Tests

Running tests is the best way to verify your installation is complete and working.

### Quick Test

Run a fast subset of tests to verify basic functionality:

```bash
make test-myagents-quick
```

This runs 2 basic tests and should complete in seconds.

### Full Test Suite

Run the complete test suite (recommended before making changes):

```bash
make test-all
```

This command:
- Runs all 504 tests in the project
- Includes workflow health reporting
- Takes approximately 7-8 minutes to complete

You can also use the direct pytest command:

```bash
uv run pytest tests/ --workflow-health
```

### Expected Results

When all tests pass, you should see output similar to:

```
================= Workflow Health Report ==================
✓ coding_agent: HEALTHY (tests passing)
✓ echo_agent: HEALTHY (tests passing)
✓ infrastructure: HEALTHY (tests passing)

Overall: All workflows healthy
======================== 504 passed in ~7m ========================
```

### Individual Test Categories

You can run specific test categories:

```bash
# Run workflow tests
make test-workflow-health-check
make test-workflow-studio
make test-workflow-preferences
make test-workflow-help

# Run agent tests
make test-agent-chat
make test-agent-shell-operations

# Run end-to-end tests
make test-e2e
```

## Quick Start Commands

Here are the most common commands you'll use:

| Command | Description | Typical Duration |
|---------|-------------|------------------|
| `make install` | Install all dependencies | 30-60 seconds |
| `make test-myagents-quick` | Run quick smoke tests | 5-10 seconds |
| `make test-all` | Run full test suite with health report | 7-8 minutes |
| `make test-myagents` | Run all tests without health report | 6-7 minutes |
| `make test-workflow-*` | Run specific workflow tests | 30-120 seconds |
| `myagents chat` | Start the coding agent CLI | Immediate |
| `myagents studio start` | Start LangGraph Studio | 10-15 seconds |
| `myagents --help` | Show available commands | Immediate |

## Initial Setup (Optional)

For production use with real agents, run the setup command:

```bash
myagents setup
```

This creates the configuration directory at `~/.config/myagents/` with:
- `config.yml` - Runtime configuration
- `langgraph.json` - Agent workflow definitions (auto-created on first use)
- `preferences.json` - User preferences (created as needed)

You also need to set your GCP project ID:

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
```

For persistent configuration, add this to your `~/.bashrc` or `~/.zshrc`.

## Next Steps

Now that you have MyAgents installed and tested, you can:

1. **Explore the CLI**
   ```bash
   myagents --help
   ```

2. **Try the agents** (requires GCP setup)
   ```bash
   # Chat with the coding agent
   myagents chat

   # Chat with the echo agent
   myagents chat --agent echo
   ```

3. **Start LangGraph Studio** for visual debugging
   ```bash
   myagents studio start
   # Open http://localhost:2024 in your browser
   ```

4. **Read the documentation**
   - [Configuration Guide](configuration.md) - Configure agents and settings
   - [Usage Guide](usage.md) - Learn how to use the agents
   - [Architecture Overview](../architecture/architecture.md) - Understand the system design

## Troubleshooting

### Common Issues

#### 1. Python Version Too Old

**Problem:** Error about Python version when running `uv sync`

**Solution:**
```bash
# Check your Python version
python --version

# If less than 3.11, install Python 3.11 or higher
# Visit https://www.python.org/downloads/
```

#### 2. uv Not Found

**Problem:** `uv: command not found`

**Solution:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart your terminal or source your profile
source ~/.bashrc  # or ~/.zshrc
```

#### 3. myagents Command Not Found

**Problem:** After installation, `myagents` command is not available

**Solution:**
```bash
# Ensure you installed in editable mode
pip install -e .

# Check if it's in your PATH
which myagents

# If not found, try reinstalling
pip uninstall myagents
pip install -e .
```

#### 4. Tests Failing

**Problem:** Tests fail with import errors or missing dependencies

**Solution:**
```bash
# Rebuild the package and reinstall all dependencies
make rebuild-myagents

# Or manually
pip uninstall myagents
uv sync
pip install -e .

# Run tests again
make test-all
```

#### 5. Slow Test Execution

**Problem:** Tests take much longer than 7-8 minutes

**Solution:**
```bash
# Run parallel tests using Docker (faster)
make test-myagents-parallel

# Or run quick tests only during development
make test-myagents-quick
```

#### 6. GCP Authentication Errors

**Problem:** Errors about GCP credentials when trying to use agents

**Solution:**
```bash
# For testing, you don't need GCP - tests use mocks

# For production agent use:
# 1. Ensure GCP_PROJECT_ID is set
export GCP_PROJECT_ID="your-project-id"

# 2. Authenticate with GCP
gcloud auth application-default login

# 3. Verify Secret Manager API is enabled
gcloud services enable secretmanager.googleapis.com
```

#### 7. Port Already in Use (Studio)

**Problem:** Cannot start Studio - port 2024 already in use

**Solution:**
```bash
# Check Studio status
myagents studio status

# Stop any running Studio instance
myagents studio stop

# If stuck, force stop
myagents studio stop --force

# Restart
myagents studio start
```

### Getting Help

If you encounter issues not covered here:

1. **Check the main README**: [../README.md](../../README.md)
2. **Review architecture docs**: [../architecture/architecture.md](../architecture/architecture.md)
3. **Run health checks**:
   ```bash
   make test-workflow-health-check
   ```
4. **Check Studio status**:
   ```bash
   myagents studio status
   ```

### Debug Mode

For detailed error messages, run commands with pytest verbose mode:

```bash
uv run pytest tests/ -v
```

Or for even more detail:

```bash
uv run pytest tests/ -vv
```

## Development Workflow

Once you're set up, a typical development workflow looks like:

```bash
# 1. Make your changes to the code

# 2. Run quick tests during development
make test-myagents-quick

# 3. Before committing, run full test suite
make test-all

# 4. If you modified the package structure
make rebuild-myagents

# 5. Test your changes with the CLI
myagents chat
```

## Summary Checklist

Use this checklist to verify your setup is complete:

- [ ] Python 3.11+ installed (`python --version`)
- [ ] uv package manager installed (`uv --version`)
- [ ] Repository cloned (`cd MyAgents`)
- [ ] Dependencies installed (`make install`)
- [ ] Package installed (`pip install -e .`)
- [ ] Command available (`myagents --version`)
- [ ] Quick tests pass (`make test-myagents-quick`)
- [ ] Full tests pass (`make test-all`)
- [ ] Optional: GCP project configured (for production use)
- [ ] Optional: Configuration created (`myagents setup`)

Congratulations! You're ready to develop with MyAgents.

---

**Last Updated:** 2025-11-29
**Version:** 1.0
