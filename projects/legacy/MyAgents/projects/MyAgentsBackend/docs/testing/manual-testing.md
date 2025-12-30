# Manual Testing Guide: Artifact Registry Migration

**Document Version:** 1.1
**Date:** 2025-11-14
**Status:** Migration Complete - Ready for Testing

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Test Agent Inputs](#test-agent-inputs)
- [Quick Start](#quick-start)
- [Docker Testing Environment](#docker-testing-environment)
- [Testing Phases](#testing-phases)
- [Automation for Agents](#automation-for-agents)
- [Manual Testing Procedures](#manual-testing-procedures)
- [Success Criteria](#success-criteria)
- [Troubleshooting](#troubleshooting)
- [Test Data Requirements](#test-data-requirements)

---

## Overview

This manual testing guide provides comprehensive validation procedures for the MyAgents Artifact Registry migration. All 5 phases of the migration are complete, and both packages (`myagents` and `agent-gcptoolkit`) are deployed to the production registry at `us-central1`.

### What This Tests

1. **Fresh Installation Workflow** - End user experience from scratch
2. **Registry Authentication** - GCP authentication and keyring setup
3. **Package Installation** - Installing from Artifact Registry
4. **Self-Update Mechanism** - Registry-based CLI updates
5. **Workspace Mode** - Developer editable installation protection
6. **Cross-Package Integration** - myagents + agent-gcptoolkit interaction
7. **Error Handling** - Graceful failures and helpful messages

### Test Environment

All tests run in isolated Docker containers to simulate fresh user environments without local development artifacts.

### Execution Modes

- **Automated**: Run via scripts for agent execution
- **Manual**: Step-by-step procedures for human testers

---

## Prerequisites

> **Note:** For comprehensive input requirements for autonomous test execution, see the [Test Agent Inputs](#test-agent-inputs) section below.

### System Requirements

- Docker Engine 20.10+
- 4GB available disk space
- Internet connectivity (for package downloads)
- GCP service account key with registry access

### Required Files

1. **Service Account Key**: `myagents-475112-60da581cc8d9.json`
   - Location: `/home/code/myagents/MyAgents-<worktree>/secrets/`
   - Permissions: `roles/artifactregistry.reader`

2. **GCP Project Configuration**
   - Project ID: `myagents-475112`
   - Registry: `myagents-python`
   - Location: `us-central1`

### GCP Resources

- Registry URL: `https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/`
- Packages Available:
  - `myagents` (version 0.0.1+)
  - `agent-gcptoolkit` (version 0.0.1+)

---

## Test Agent Inputs

This section explicitly defines all inputs required for autonomous test execution by an agent.

### Required Files

**Documentation Files:**
- `/home/code/myagents/MyAgents-<worktree>/README.md`
  - Purpose: Reference for installation and usage instructions
  - Used in: Phase 2 (Fresh Installation), Phase 4 (Workspace Mode)
  - Sections referenced: "For End Users", "For Developers", "Updating MyAgents"

- `/home/code/myagents/MyAgents-<worktree>/docs/guides/registry-setup.md`
  - Purpose: Detailed registry configuration instructions
  - Used in: Phase 6 (Registry Authentication)
  - Sections referenced: "Authentication Setup", "Troubleshooting"

**Script Files:**
- `/home/code/myagents/MyAgents-<worktree>/scripts/run-manual-tests.sh`
  - Purpose: Main test orchestration script
  - Permissions: Must be executable (chmod +x)

- `/home/code/myagents/MyAgents-<worktree>/scripts/test-suite.sh`
  - Purpose: Test execution script (runs inside container)
  - Permissions: Must be executable (chmod +x)

**Docker Files:**
- `/home/code/myagents/MyAgents-<worktree>/Dockerfile.test`
  - Purpose: Test container specification
  - Base image: python:3.12-slim

**Secrets:**
- `/home/code/myagents/secrets/myagents-475112-60da581cc8d9.json`
  - Purpose: GCP service account key for authentication
  - Permissions: Read-only (will be mounted as read-only volume)
  - Must not be copied into Docker image

### Configuration Values

**GCP Configuration:**
- Project ID: `myagents-475112`
- Service Account: `myagents@myagents-475112.iam.gserviceaccount.com`
- Region: `us-central1`

**Registry URLs:**
- Production Registry: `https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/`
- Test Registry: `https://us-central1-python.pkg.dev/myagents-475112/myagents-python-test/simple/`

**Package Information:**
- Package 1: `agent-gcptoolkit` (v0.1.0 in production)
- Package 2: `myagents` (v0.0.1 in production)

**Repository Location:**
- GitHub: `https://github.com/HuaMick/MyAgents.git`
- Branch: `packaging-001`
- Worktree: `/home/code/myagents/MyAgents-<worktree>`

### Environment Variables

Required environment variables for testing:
```bash
GOOGLE_APPLICATION_CREDENTIALS=/test/secrets/myagents-475112-60da581cc8d9.json
GCP_PROJECT_ID=myagents-475112
REGISTRY_URL=https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/
TEST_REGISTRY_URL=https://us-central1-python.pkg.dev/myagents-475112/myagents-python-test/simple/
```

### System Requirements

**Host System:**
- Docker installed and running
- Internet connectivity
- 4GB available disk space
- Bash shell (for running scripts)

**Docker Container:**
- Python 3.12+
- UV package manager
- gcloud CLI
- curl, git, gnupg

### Expected Outputs

**Results Files:**
- `/tmp/myagents-test-results.txt` - Structured summary
- `/tmp/myagents-test-execution.log` - Detailed logs

**Exit Codes:**
- 0: All tests passed
- 1: One or more tests failed
- 2: Prerequisites not met
- 3: Docker error
- 4: Service account key not found

### Test Execution Command

For autonomous test agent execution:
```bash
cd /home/code/myagents/MyAgents-<worktree>
./scripts/run-manual-tests.sh
```

The agent should:
1. Verify all input files exist
2. Verify prerequisites (Docker, service account)
3. Execute the test script
4. Read results from `/tmp/myagents-test-results.txt`
5. Parse exit code for pass/fail status
6. Report results to user

### Validation Before Execution

Test agent should validate:
- [ ] README.md exists and is readable
- [ ] docs/guides/registry-setup.md exists
- [ ] scripts/run-manual-tests.sh exists and is executable
- [ ] scripts/test-suite.sh exists and is executable
- [ ] Dockerfile.test exists
- [ ] Service account key exists at secrets/myagents-475112-60da581cc8d9.json
- [ ] Docker daemon is running
- [ ] Internet connectivity available
- [ ] Working directory is MyAgents-<worktree>

---

## Quick Start

> **Note:** Before executing tests, review the [Test Agent Inputs](#test-agent-inputs) section to validate all prerequisites are met.

### For Automated Testing (Agents)

```bash
# Navigate to project root
cd /home/code/myagents/MyAgents-<worktree>

# Validate inputs (optional but recommended)
# See "Validation Before Execution" in Test Agent Inputs section

# Run complete test suite
./scripts/run-manual-tests.sh
```

This executes all 7 testing phases automatically in a Docker container.

### For Manual Testing (Humans)

```bash
# IMPORTANT: Build must run from parent directory
cd /home/code/myagents

# Build test container with correct worktree name
docker build -f MyAgents-staging/Dockerfile.test --build-arg WORKTREE_NAME=MyAgents-staging -t myagents-test .

# Start interactive testing session
docker run -it --rm \
  -v $(pwd)/secrets:/test/secrets:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/test/secrets/myagents-475112-60da581cc8d9.json \
  myagents-test
```

Then follow the phase-by-phase procedures in this document.

---

## Docker Testing Environment

### Dockerfile Specification

**Location:** `/home/code/myagents/MyAgents-<worktree>/Dockerfile.test`

The test container includes:
- Base: `python:3.12-slim`
- System packages: curl, git, gnupg
- Google Cloud SDK (gcloud)
- UV package manager (latest)
- Clean environment (no cached packages)

### Container Build

**IMPORTANT: Directory Structure Requirement**

The Docker build **MUST** be run from the parent directory (`/home/code/myagents`), NOT from within the worktree directory. This is because:

1. The Dockerfile expects access to the worktree as a subdirectory
2. The Dockerfile requires access to the sibling `Agent-GCPtoolkit` directory
3. The COPY commands use relative paths expecting this structure:
   ```
   /home/code/myagents/
   ├── Agent-GCPtoolkit/          (sibling directory - REQUIRED)
   └── MyAgents-<worktree-name>/  (your worktree)
       └── Dockerfile.test
   ```

**Build Command:**

```bash
# MUST run from parent directory (/home/code/myagents)
cd /home/code/myagents

# Build with the correct worktree name as a build argument
docker build -f MyAgents-staging/Dockerfile.test --build-arg WORKTREE_NAME=MyAgents-staging -t myagents-test .

# For other worktrees, replace MyAgents-staging with your actual worktree name:
# docker build -f MyAgents-<your-worktree>/Dockerfile.test --build-arg WORKTREE_NAME=MyAgents-<your-worktree> -t myagents-test .

# Verify build
docker images | grep myagents-test
```

**Common Build Errors:**

- **"COPY failed: no source files were specified"** - You're running from the wrong directory. Must run from `/home/code/myagents`
- **"Agent-GCPtoolkit not found"** - The sibling directory must exist at `/home/code/myagents/Agent-GCPtoolkit`
- **Wrong worktree name** - Ensure `--build-arg WORKTREE_NAME=` matches your actual worktree folder name

### Container Usage

**Interactive Mode (Manual Testing):**
```bash
docker run -it --rm \
  -v $(pwd)/secrets:/test/secrets:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/test/secrets/myagents-475112-60da581cc8d9.json \
  -e GCP_PROJECT_ID=myagents-475112 \
  myagents-test /bin/bash
```

**Automated Mode (Script Execution):**
```bash
docker run --rm \
  -v $(pwd)/secrets:/test/secrets:ro \
  -v $(pwd)/scripts:/test/scripts:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/test/secrets/myagents-475112-60da581cc8d9.json \
  -e GCP_PROJECT_ID=myagents-475112 \
  myagents-test \
  /bin/bash /test/scripts/test-suite.sh
```

---

## Testing Phases

### Phase 1: Docker Environment Setup

**Estimated Time:** 5 minutes
**Prerequisites:** Docker installed, service account key available

**Objective:** Build and validate the test container environment.

**Steps:**

1. Navigate to parent directory (REQUIRED):
   ```bash
   cd /home/code/myagents
   ```

2. Verify service account key exists:
   ```bash
   ls -l MyAgents-<worktree>/secrets/myagents-475112-60da581cc8d9.json
   ```

3. Verify Agent-GCPtoolkit sibling directory exists:
   ```bash
   ls -ld Agent-GCPtoolkit
   ```

4. Build test container with correct worktree name:
   ```bash
   docker build -f MyAgents-staging/Dockerfile.test --build-arg WORKTREE_NAME=MyAgents-staging -t myagents-test .
   ```

5. Verify container build:
   ```bash
   docker images | grep myagents-test
   ```

6. Test container startup:
   ```bash
   docker run --rm myagents-test python --version
   docker run --rm myagents-test uv --version
   docker run --rm myagents-test gcloud --version
   ```

**Success Criteria:**
- Container builds without errors
- Python 3.12+ available
- UV package manager installed
- gcloud CLI accessible

**Troubleshooting:**
- If build fails, check Docker daemon is running
- If gcloud install fails, check network connectivity
- If permissions errors, ensure Docker has access to project directory

---

### Phase 2: Fresh Installation Testing (End User Workflow)

**Estimated Time:** 10 minutes
**Prerequisites:** Phase 1 complete
**Reference:** [README.md - For End Users](../README.md#for-end-users-from-artifact-registry)

**Objective:** Validate complete end-user installation from scratch.

**Test Steps:**

1. Start clean container:
   ```bash
   docker run -it --rm \
     -v $(pwd)/secrets:/test/secrets:ro \
     -e GOOGLE_APPLICATION_CREDENTIALS=/test/secrets/myagents-475112-60da581cc8d9.json \
     -e GCP_PROJECT_ID=myagents-475112 \
     myagents-test /bin/bash
   ```

2. Verify uv is installed (should be from Dockerfile):
   ```bash
   uv --version
   ```

3. Install keyring authentication helper:
   ```bash
   uv pip install --user --break-system-packages keyrings.google-artifactregistry-auth
   ```

4. Configure pip.conf with registry URL:
   ```bash
   mkdir -p ~/.config/pip
   cat > ~/.config/pip/pip.conf << 'EOF'
[global]
extra-index-url = https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/
EOF
   ```

5. Verify pip configuration:
   ```bash
   cat ~/.config/pip/pip.conf
   ```

6. Authenticate with GCP using service account:
   ```bash
   gcloud auth activate-service-account \
     --key-file=$GOOGLE_APPLICATION_CREDENTIALS
   gcloud config set project $GCP_PROJECT_ID
   ```

7. Verify authentication:
   ```bash
   gcloud auth list
   ```

8. Install myagents package:
   ```bash
   uv pip install myagents
   ```

9. Install agent-gcptoolkit package:
   ```bash
   uv pip install agent-gcptoolkit
   ```

10. Verify installations:
    ```bash
    myagents --version
    uv pip show myagents
    uv pip show agent-gcptoolkit
    ```

11. Test registry info command:
    ```bash
    myagents registry info
    ```

12. Test registry authentication check:
    ```bash
    myagents registry check-auth
    ```

13. Test help command:
    ```bash
    myagents --help
    ```

14. Test basic CLI command:
    ```bash
    myagents config show
    ```

**Success Criteria:**
- All packages install without errors
- Exit codes are 0 for successful commands
- `myagents --version` displays version number
- `myagents registry info` shows registry configuration
- `myagents registry check-auth` confirms authentication
- `myagents --help` displays command list
- No import errors or module not found errors

**Expected Output Examples:**

```bash
# myagents --version
myagents version 0.0.1

# myagents registry info
Registry Configuration:
  URL: https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/
  Project: myagents-475112
  Location: us-central1
  Repository: myagents-python

# myagents registry check-auth
Authentication Status: OK
Service Account: myagents-sa@myagents-475112.iam.gserviceaccount.com
Access: Read/Write
```

**Troubleshooting:**
- **Authentication fails**: Check service account key path and permissions
- **Package not found**: Verify pip.conf has correct registry URL
- **Permission denied**: Ensure service account has `artifactregistry.reader` role
- **Import errors**: Check both packages installed successfully

---

### Phase 3: Self-Update Testing

**Estimated Time:** 8 minutes
**Prerequisites:** Phase 2 complete (packages installed)

**Objective:** Validate registry-based self-update mechanism works correctly.

**Test Steps:**

1. In running container from Phase 2, check current version:
   ```bash
   myagents --version
   ```

2. Run myagents self-update:
   ```bash
   myagents self-update
   ```

3. Verify command completes:
   ```bash
   echo $?  # Should be 0
   ```

4. Check version after update:
   ```bash
   myagents --version
   ```

5. Run gcptoolkit self-update via delegation:
   ```bash
   myagents gcptoolkit self-update
   ```

6. Verify gcptoolkit update:
   ```bash
   echo $?  # Should be 0
   ```

7. Test workspace mode detection (should fail - not in workspace):
   ```bash
   # This should work because we're NOT in workspace mode
   myagents self-update
   ```

**Success Criteria:**
- `myagents self-update` executes without errors
- Exit code is 0
- If no newer version: "Already at latest version" message
- If update available: "Update complete" message
- `myagents gcptoolkit self-update` works via delegation
- No workspace mode false positives

**Expected Output Examples:**

```bash
# myagents self-update (no update available)
Checking for updates...
Current version: 0.0.1
Latest version: 0.0.1
Already at latest version.

# myagents self-update (update available)
Checking for updates...
Current version: 0.0.1
Latest version: 0.0.2
Updating myagents...
Update complete. Restart may be required.
```

**Troubleshooting:**
- **Update fails**: Check registry authentication still valid
- **"Workspace mode detected"**: Verify not running from repo directory
- **"No package found"**: Check registry has packages published

---

### Phase 4: Workspace Mode Testing (Developer Workflow)

**Estimated Time:** 12 minutes
**Prerequisites:** Git, uv installed in container
**Reference:** [README.md - For Developers](../README.md#for-developers-workspace-mode)

**Objective:** Validate workspace mode blocks self-update to protect editable installations.

**Test Steps:**

1. Start a new container with volume mount for git operations:
   ```bash
   docker run -it --rm \
     -v $(pwd)/secrets:/test/secrets:ro \
     -e GOOGLE_APPLICATION_CREDENTIALS=/test/secrets/myagents-475112-60da581cc8d9.json \
     -e GCP_PROJECT_ID=myagents-475112 \
     myagents-test /bin/bash
   ```

2. Clone repository inside container:
   ```bash
   cd /tmp
   git clone https://github.com/HuaMick/MyAgents.git
   cd MyAgents
   ```

3. Install in workspace mode (editable):
   ```bash
   uv sync
   ```

4. Verify editable installation:
   ```bash
   uv pip list | grep myagents
   myagents --version
   ```

5. Attempt self-update (should be blocked):
   ```bash
   myagents self-update
   echo $?  # Should be non-zero (error)
   ```

6. Verify error message is clear:
   ```bash
   # Expected: "Error: Cannot self-update in workspace mode. Use 'uv sync' instead."
   ```

7. Test that uv sync works:
   ```bash
   uv sync
   echo $?  # Should be 0
   ```

8. Test CLI commands work in workspace mode:
   ```bash
   myagents --help
   myagents config show
   myagents registry info
   ```

9. Verify workspace mode detection is consistent:
   ```bash
   myagents self-update  # Should still be blocked
   myagents gcptoolkit self-update  # Should also be blocked
   ```

**Success Criteria:**
- `uv sync` installs packages in editable mode
- `myagents self-update` is blocked with clear error message
- Error message includes helpful guidance: "Use 'uv sync' instead"
- Exit code is non-zero for blocked self-update
- CLI commands work normally in workspace mode
- `uv sync` can update dependencies successfully
- Workspace mode detection is consistent across restarts

**Expected Output Examples:**

```bash
# myagents self-update (blocked)
Error: Cannot self-update in workspace mode.
You are running MyAgents from an editable installation (workspace mode).
To update, use: uv sync

This protection prevents accidentally replacing your development installation.
```

**Troubleshooting:**
- **Self-update not blocked**: Check workspace mode detection logic
- **uv sync fails**: Verify uv.lock file present
- **Commands don't work**: Check editable installation succeeded

---

### Phase 5: Cross-Package Integration Testing

**Estimated Time:** 10 minutes
**Prerequisites:** Phase 2 complete (both packages installed)

**Objective:** Validate myagents and agent-gcptoolkit integration works correctly.

**Test Steps:**

1. In container with packages installed (from Phase 2):
   ```bash
   python3 -c "import myagents; print('myagents imported')"
   ```

2. Test agent-gcptoolkit import:
   ```bash
   python3 -c "import agent_gcptoolkit; print('agent_gcptoolkit imported')"
   ```

3. Test cross-package imports:
   ```bash
   python3 << 'EOF'
from myagents.backend.services.gcptoolkit.domains.config import ConfigManager
from myagents.backend.services.gcptoolkit.domains.secrets import SecretsManager
print("Cross-package imports successful")
EOF
   ```

4. Test config delegation commands:
   ```bash
   myagents config show
   myagents config init --help
   ```

5. Test secrets delegation:
   ```bash
   myagents secrets --help
   ```

6. Test gcptoolkit self-update delegation:
   ```bash
   myagents gcptoolkit self-update --help
   ```

7. Verify shared configuration access:
   ```bash
   # Set config via myagents
   myagents config show

   # Should be accessible by both packages
   python3 -c "from myagents.backend.services.gcptoolkit.domains.config import ConfigManager; cm = ConfigManager(); print('Config shared')"
   ```

**Success Criteria:**
- Both packages import successfully
- No `ImportError` or `ModuleNotFoundError`
- Delegation commands execute (subprocess calls work)
- myagents can invoke agent-gcptoolkit commands
- Shared configuration accessible to both packages
- No circular dependency errors

**Expected Output Examples:**

```bash
# Successful delegation
$ myagents config show
Config File: /root/.config/myagents/config.yml
Status: Not configured

# Successful secrets delegation
$ myagents secrets get --help
Usage: myagents secrets get <secret-name> [options]
...
```

**Troubleshooting:**
- **Import errors**: Verify both packages installed with dependencies
- **Delegation fails**: Check subprocess execution permissions
- **Config not shared**: Verify both packages use same config path

---

### Phase 6: Registry Authentication Testing

**Estimated Time:** 8 minutes
**Prerequisites:** Docker container running

**Objective:** Validate authentication failure modes and error messages.

**Test Steps:**

1. Start fresh container WITHOUT authentication:
   ```bash
   docker run -it --rm myagents-test /bin/bash
   ```

2. Try to install without authentication (should fail gracefully):
   ```bash
   mkdir -p ~/.config/pip
   cat > ~/.config/pip/pip.conf << 'EOF'
[global]
extra-index-url = https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/
EOF

   uv pip install myagents
   ```

3. Verify clear error message about authentication:
   ```bash
   # Expected: Clear message about missing authentication
   ```

4. Install keyring helper:
   ```bash
   uv pip install --user --break-system-packages keyrings.google-artifactregistry-auth
   ```

5. Exit container, start with authentication:
   ```bash
   exit
   docker run -it --rm \
     -v $(pwd)/secrets:/test/secrets:ro \
     -e GOOGLE_APPLICATION_CREDENTIALS=/test/secrets/myagents-475112-60da581cc8d9.json \
     myagents-test /bin/bash
   ```

6. Configure authentication:
   ```bash
   gcloud auth activate-service-account \
     --key-file=$GOOGLE_APPLICATION_CREDENTIALS
   gcloud config set project myagents-475112

   mkdir -p ~/.config/pip
   cat > ~/.config/pip/pip.conf << 'EOF'
[global]
extra-index-url = https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/
EOF

   uv pip install --user --break-system-packages keyrings.google-artifactregistry-auth
   ```

7. Try installation again (should succeed):
   ```bash
   uv pip install myagents
   ```

8. Test check-auth command:
   ```bash
   myagents registry check-auth
   ```

9. Test with invalid credentials (create dummy key file):
   ```bash
   echo '{"type":"service_account"}' > /tmp/invalid-key.json
   gcloud auth activate-service-account --key-file=/tmp/invalid-key.json
   myagents registry check-auth
   ```

**Success Criteria:**
- Installation without auth fails with clear error message
- Error message explains authentication needed
- Installation with valid auth succeeds
- `myagents registry check-auth` accurately reports status
- Invalid credentials produce helpful error (not stack trace)

**Expected Output Examples:**

```bash
# Without authentication
$ uv pip install myagents
ERROR: Could not authenticate to https://us-central1-python.pkg.dev/...
Authentication required. Please run:
  1. gcloud auth application-default login
  2. Install keyring: uv pip install keyrings.google-artifactregistry-auth

# With authentication
$ myagents registry check-auth
Authentication Status: OK
Authenticated as: myagents-sa@myagents-475112.iam.gserviceaccount.com
```

**Troubleshooting:**
- **No error on missing auth**: Check keyring helper installed
- **Unclear error messages**: May need to improve error handling
- **Auth works but check-auth fails**: Verify gcloud config correct

---

### Phase 7: Error Handling and Edge Cases

**Estimated Time:** 10 minutes
**Prerequisites:** Phase 2 complete (packages installed)

**Objective:** Validate all error scenarios produce helpful messages.

**Test Steps:**

1. In container with packages installed:
   ```bash
   myagents nonexistent-command
   ```

2. Verify helpful error message (not Python traceback):
   ```bash
   # Expected: "Unknown command. Try 'myagents --help'"
   ```

3. Test with invalid arguments:
   ```bash
   myagents preferences get
   # Expected: "Error: Missing argument <key>"
   ```

4. Test with too many arguments:
   ```bash
   myagents --version extra-arg
   # Expected: Clear error about unexpected arguments
   ```

5. Simulate network failure (disconnect network):
   ```bash
   # In another terminal
   docker network disconnect bridge <container-id>

   # In container
   myagents self-update
   # Expected: "Network error. Check internet connection."
   ```

6. Test workspace mode detection in various locations:
   ```bash
   cd /tmp
   myagents self-update  # Should work (not workspace)

   mkdir -p /tmp/fake-workspace/pyproject.toml
   cd /tmp/fake-workspace
   myagents self-update  # Should work (not real workspace)
   ```

7. Test registry unreachable:
   ```bash
   # Modify pip.conf to invalid URL
   echo "[global]" > ~/.config/pip/pip.conf
   echo "extra-index-url = https://invalid-registry.example.com/" >> ~/.config/pip/pip.conf

   myagents self-update
   # Expected: "Cannot reach registry. Check network/URL."
   ```

8. Test command abbreviations and typos:
   ```bash
   myagents hlep  # Typo
   # Expected: "Unknown command 'hlep'. Did you mean 'help'?"
   ```

**Success Criteria:**
- All errors produce user-friendly messages (not tracebacks)
- Error messages include actionable guidance
- Invalid commands suggest similar valid commands
- Missing arguments are clearly identified
- Network errors are distinguished from auth errors
- Workspace mode detection only triggers in actual workspaces

**Expected Output Examples:**

```bash
# Invalid command
$ myagents invalid
Error: Unknown command 'invalid'
Try 'myagents --help' to see available commands.

# Missing argument
$ myagents preferences get
Error: Missing required argument: <key>
Usage: myagents preferences get <key>

# Network error
$ myagents self-update
Error: Cannot connect to registry
Check your internet connection and try again.
```

**Troubleshooting:**
- **Stack traces shown**: Error handling needs improvement
- **Unclear error messages**: Update error message text
- **False positive workspace detection**: Check detection logic

---

## Automation for Agents

### Automated Execution

An agent can execute all testing phases automatically using the provided scripts.

> **Important:** Before starting automated execution, review the [Test Agent Inputs](#test-agent-inputs) section to ensure all required files, configurations, and prerequisites are available.

**Script Locations:**
- Test runner: `/home/code/myagents/MyAgents-<worktree>/scripts/run-manual-tests.sh`
- Test suite: `/home/code/myagents/MyAgents-<worktree>/scripts/test-suite.sh`

### Agent Execution Steps

1. **Validate inputs** (see [Validation Before Execution](#validation-before-execution)):
   - Verify all required files exist
   - Check Docker daemon is running
   - Confirm service account key is accessible

2. Navigate to project:
   ```bash
   cd /home/code/myagents/MyAgents-<worktree>
   ```

3. Verify prerequisites:
   ```bash
   ./scripts/run-manual-tests.sh --check
   ```

4. Run all tests:
   ```bash
   ./scripts/run-manual-tests.sh
   ```

5. Review results:
   ```bash
   cat /tmp/myagents-test-results.txt
   ```

### Test Output Format

The automation scripts produce structured output:

```
=== MyAgents Manual Testing Suite ===
Date: 2025-11-14 10:30:00

Phase 1: Docker Environment Setup
  Status: PASS
  Duration: 2m 15s

Phase 2: Fresh Installation Testing
  Status: PASS
  Duration: 8m 32s

Phase 3: Self-Update Testing
  Status: PASS
  Duration: 5m 18s

Phase 4: Workspace Mode Testing
  Status: PASS
  Duration: 10m 45s

Phase 5: Cross-Package Integration Testing
  Status: PASS
  Duration: 7m 22s

Phase 6: Registry Authentication Testing
  Status: PASS
  Duration: 6m 54s

Phase 7: Error Handling and Edge Cases
  Status: PASS
  Duration: 8m 10s

=== Summary ===
Total Tests: 7
Passed: 7
Failed: 0
Duration: 49m 16s

Overall Status: ALL TESTS PASSED
```

### Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed
- `2`: Prerequisites not met
- `3`: Docker error
- `4`: Service account key not found

---

## Manual Testing Procedures

### For Human Testers

Human testers can follow the phase-by-phase procedures in this document:

1. **Read Prerequisites** section thoroughly
2. **Execute Phase 1** to set up Docker environment
3. **Execute Phases 2-7** in order
4. **Document any failures** with exact error messages
5. **Check Success Criteria** for each phase
6. **Consult Troubleshooting** if issues arise

### Testing Checklist

Print or keep this checklist handy during manual testing:

- [ ] Phase 1: Docker environment built and validated
- [ ] Phase 2: Fresh installation completed successfully
- [ ] Phase 3: Self-update mechanism works
- [ ] Phase 4: Workspace mode protection verified
- [ ] Phase 5: Cross-package integration confirmed
- [ ] Phase 6: Authentication scenarios tested
- [ ] Phase 7: Error handling validated

### Documentation Requirements

For each test phase, document:
- **Start time**
- **Commands executed** (copy-paste from terminal)
- **Output received** (full output)
- **Any errors** (complete error messages)
- **Success/Failure status**
- **Notes or observations**

---

## Success Criteria

### Overall System Health

The Artifact Registry migration is considered successful when:

1. **Installation Works**
   - Users can install from registry without errors
   - Authentication setup is straightforward
   - Installation completes in reasonable time (<5 minutes)

2. **Self-Update Works**
   - CLI self-update commands execute successfully
   - Workspace mode protection prevents accidents
   - Error messages are clear and helpful

3. **Integration Works**
   - Both packages work together seamlessly
   - Command delegation functions correctly
   - Shared configuration accessible

4. **Error Handling Works**
   - All errors produce user-friendly messages
   - No Python tracebacks exposed to users
   - Troubleshooting guidance provided

### Phase-Specific Criteria

See individual phase sections for detailed success criteria.

### Performance Benchmarks

- Fresh installation: <5 minutes
- Self-update check: <30 seconds
- Self-update execution: <2 minutes
- Workspace mode detection: <1 second
- Registry authentication: <10 seconds

---

## Troubleshooting

### Common Issues

#### Docker Issues

**Problem:** Docker build fails with network timeout

**Solution:**
```bash
# Check Docker network
docker network ls
docker network inspect bridge

# Retry build with no cache
docker build --no-cache -t myagents-test -f Dockerfile.test .
```

**Problem:** Container cannot access service account key

**Solution:**
```bash
# Verify volume mount path
ls -l $(pwd)/secrets/myagents-475112-60da581cc8d9.json

# Check container can see volume
docker run --rm -v $(pwd)/secrets:/test/secrets:ro myagents-test ls -l /test/secrets/
```

#### Installation Issues

**Problem:** Package not found in registry

**Solution:**
```bash
# Verify registry URL in pip.conf
cat ~/.config/pip/pip.conf

# Check registry has packages
gcloud artifacts packages list \
  --repository=myagents-python \
  --location=us-central1
```

**Problem:** Authentication fails

**Solution:**
```bash
# Verify keyring helper installed
python3 -m pip show keyrings.google-artifactregistry-auth

# Re-authenticate
gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS

# Test authentication
gcloud auth list
```

#### Self-Update Issues

**Problem:** Self-update fails with "permission denied"

**Solution:**
```bash
# Check if running as correct user
whoami

# Verify package installation directory is writable
python3 -m site --user-site
ls -ld $(python3 -m site --user-site)
```

**Problem:** Workspace mode incorrectly detected

**Solution:**
```bash
# Check for pyproject.toml in parent directories
pwd
find . -name pyproject.toml -type f 2>/dev/null | head -5

# Verify not in editable install location
pip show myagents | grep Location
```

### Getting Help

If issues persist:

1. **Check logs**: Examine full command output
2. **Verify prerequisites**: Ensure all requirements met
3. **Review phase documentation**: Re-read relevant phase
4. **Check GCP status**: Verify registry accessible
5. **Test authentication**: Confirm credentials valid

### Debug Commands

Useful commands for debugging:

```bash
# Python environment
python3 --version
python3 -m site
python3 -m pip list

# UV environment
uv --version
uv pip list
uv cache dir

# GCP authentication
gcloud auth list
gcloud config list
gcloud artifacts repositories list --location=us-central1

# Package info
pip show myagents
pip show agent-gcptoolkit
which myagents

# Network
curl -I https://us-central1-python.pkg.dev/
ping -c 3 8.8.8.8
```

---

## Test Data Requirements

### Service Account

**Required File:** `myagents-475112-60da581cc8d9.json`

**Required Permissions:**
- `roles/artifactregistry.reader` (minimum)
- `roles/artifactregistry.writer` (for deployment testing)

**File Location:**
- Development: `/home/code/myagents/MyAgents-<worktree>/secrets/`
- Container: `/test/secrets/` (volume mount)

**Security:**
- Never commit service account keys to git
- Use `.gitignore` to exclude `secrets/` directory
- Rotate keys regularly
- Use least-privilege principle

### Environment Variables

**Required:**
```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
GCP_PROJECT_ID=myagents-475112
```

**Optional:**
```bash
REGISTRY_URL=https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/
REGISTRY_LOCATION=us-central1
REGISTRY_NAME=myagents-python
```

### Test Artifacts

No test artifacts required. All testing uses live registry packages.

---

## Appendix

### Related Documentation

- [README.md](../README.md) - Main project documentation
- [Registry Setup Guide](registry-setup.md) - Registry configuration details
- [Packaging Guide](packaging.md) - Package development workflow
- [Setup Guide](setup.md) - Initial installation instructions

### References

- [Google Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [UV Package Manager](https://github.com/astral-sh/uv)
- [Docker Documentation](https://docs.docker.com/)
- [Python Packaging Guide](https://packaging.python.org/)

### Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2025-11-14 | Added comprehensive Test Agent Inputs section with validation checklist |
| 1.0 | 2025-11-14 | Initial manual testing guide created |

---

**Document Maintained By:** MyAgents Team
**Last Updated:** 2025-11-14
**Status:** Active
