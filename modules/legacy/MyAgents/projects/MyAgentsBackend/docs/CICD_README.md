# CI/CD Documentation

This document provides a comprehensive guide to the CI/CD pipeline for the MyAgents repository, utilizing Google Cloud Build and integrated with GitHub.

## 1. Architecture

The pipeline is built on **Google Cloud Build**, using a containerized testing strategy for rapid feedback.

-   **Orchestrator:** Google Cloud Build
-   **VCS Integration:** Cloud Build GitHub App
-   **Artifacts:** Google Container Registry (GCR) or Artifact Registry
-   **Secrets:** Google Secret Manager

### Pipeline Stages
1.  **Setup:** Fetches authentication keys (Service Account) from Secret Manager.
2.  **Build:** Builds a unified test Docker image (`Dockerfile.test`) with caching.
3.  **Lint:** Runs static analysis (`ruff`) on the built image.
4.  **Test:** Executes test suites in parallel containers.

## 2. Branching & Triggers

We use a **Trunk-Based Development** workflow with a staging integration branch.

### Main Branch (`main`)
-   **Role:** Production-ready state.
-   **Trigger:** Push to `main` (typically via PR from `myagents-staging`).
-   **Action:** Full CI Suite (Build + Lint + All Tests + Coverage).
-   **Cloud Build Trigger:** `myagents-merge-full`
    -   Substitutions: `_TEST_SCOPE=all`, `_TIMEOUT=15m`
    -   Test Filter: None (runs all tests including costly tests)

### Staging Branch (`myagents-staging`)
-   **Role:** Integration branch for consolidating features before main.
-   **Worktree:** `/home/code/myagents/MyAgents-staging`
-   **Trigger:** Pull Request targeting `main`.
-   **Action:** Full CI Suite (validates before production merge).
-   **Workflow:**
    1.  Feature branches merge into `myagents-staging` with local testing.
    2.  Multiple features consolidated and validated locally.
    3.  PR from `myagents-staging` → `main` triggers full CI.

### Feature Branches (`feat/*`, `fix/*`, `myagents-*`)
-   **Role:** Short-lived development branches (often as worktrees).
-   **Trigger:** Pull Request targeting `myagents-staging` or `main`.
-   **Action:** Fast CI Checks (Lint + Unit Tests, excludes costly tests).
-   **Cloud Build Trigger:** `myagents-pr-checks`
    -   Substitutions: `_TEST_SCOPE=unit`, `_TIMEOUT=5m`
    -   Test Filter: `-m "unit and not costly"` (excludes expensive LLM calls)

### Workflow Summary
```
feature branches ──► myagents-staging ──► main
                     (local testing)      (full CI)
```

> **Note:** Detailed trigger creation commands (curl) can be found in the legacy `docs/cicd_triggers.md` history if needed.

## 3. Testing Strategy

We leverage `pytest` and containerized parallelism.

### Parallel Execution
Tests run in parallel containers defined in `cloudbuild.yaml` and `docker-compose.test.yml`.

| Docker Compose Service | Test Scope | Cloud Build Step ID |
| ---------------------- | ---------- | ------------------- |
| `test-cli-unification` | `tests/workflows/cli_unification/` | `test-cli` |
| `test-echo-agent` | `tests/workflows/agent_chat/` | `test-echo` |
| `test-infrastructure-workflow` | `tests/workflows/infrastructure/` | `test-infra` |
| `test-packaging` | `tests/workflows/e2e/` | `test-pkg` |
| `test-integration-file-ops` | `tests/integration/file_operations/` | `test-int-files` |

### Pytest Configuration
Configuration is centralized in `MyAgents/pytest.ini` and `MyAgents/pyproject.toml`.

**Markers:**
-   `unit`: Fast, isolated tests.
-   `integration`: Verify component interactions.
-   `e2e`: Full workflow tests.
-   `slow`: Time-consuming tests.
-   `costly`: Incur costs (e.g., real LLM calls).

**Coverage:**
-   Tools: `pytest-cov`
-   Reports: XML reports generated per parallel step, saved to `/test/results/coverage_*.xml`.

### Coverage Threshold

The pipeline tracks code coverage but does not automatically enforce a minimum threshold.

**Coverage Threshold:** 40%

**Configuration:**
-   Coverage enforcement (`--cov-fail-under=40`) is **not** included in `pytest.ini` defaults
-   **Reason:** CI/CD runs parallel test steps that each cover only a subset of the codebase
-   Coverage reports are generated per test suite and saved to `/test/results/coverage_*.xml`
-   Scope: Covers `backend`, `frontend`, and `myagents` packages

**Local Coverage Validation:**

For local full coverage validation, developers must explicitly add the threshold flag:

```bash
# Run with coverage threshold enforcement (40%)
uv run pytest --cov=backend --cov=frontend --cov=myagents --cov-fail-under=40 tests/

# Check current coverage percentage without enforcement
uv run pytest --cov=backend --cov=frontend --cov=myagents --cov-report=term tests/
```

**Rationale:** The 40% threshold provides a baseline quality gate while allowing flexibility for rapid development. Coverage is collected in CI/CD for visibility but not enforced automatically due to parallel execution constraints.

### Costly Test Gating

Tests marked as `costly` (e.g., those making real LLM API calls) are conditionally executed based on the build context to optimize CI/CD costs and feedback speed.

**Marking Costly Tests:**
```python
import pytest

@pytest.mark.costly
def test_llm_integration():
    # Test that makes real LLM API calls
    response = llm.generate("prompt")
    assert response
```

**Gating Strategy:**

| Build Context | Test Scope | Costly Tests | _TEST_SCOPE Value |
| ------------- | ---------- | ------------ | ----------------- |
| PR Checks (feature branches) | Unit tests only | Excluded | `unit` |
| Main Merges (production) | Full test suite | Included | `all` |

**Implementation:**
-   PR checks use pytest marker expression: `-m "unit and not costly"`
-   Main merges run all tests without marker filtering
-   Controlled via `_TEST_SCOPE` substitution variable in Cloud Build triggers

**Example from cloudbuild.yaml:**
```bash
# PR checks (unit scope) - excludes costly tests
uv run pytest -m "unit and not costly" tests/workflows/cli_unification/

# Main merges (full scope) - includes all tests
uv run pytest tests/workflows/cli_unification/
```

**Local Testing:**
```bash
# Run unit tests only (excludes costly tests) - fast feedback
pytest -m "unit and not costly" tests/

# Run all tests including costly (requires API keys)
pytest tests/

# Run only costly tests
pytest -m "costly" tests/
```

**Benefits:**
-   Faster PR feedback (typically 5 minutes vs 15 minutes)
-   Reduced API costs on frequent PR checks
-   Full validation still occurs before production merge
-   Developers can test costly scenarios locally when needed

## 4. Build & Caching

To ensure fast feedback:
1.  **Docker Layer Caching**: Uses `docker build --cache-from` with the `latest` image.
2.  **`uv` Cache**: `Dockerfile.test` caches dependency installation (`uv sync --dev`).

## 5. Infrastructure & Security

### Service Account
The pipeline runs as the default Cloud Build Service Account:
`452693195889@cloudbuild.gserviceaccount.com`

### Secrets
Managed via **Google Secret Manager**.

| Secret Name | Env Variable | Usage |
| ----------- | ------------ | ----- |
| `GEMINI_API_KEY` | `GEMINI_API_KEY` | LLM calls (test-coding-agent, test-echo-agent) |
| `LANGSMITH_API_KEY` | `LANGSMITH_API_KEY` | Tracing |
| `gcp-service-account-key` | Mounted file | Agent-GCPtoolkit authentication |

### Permissions
The Cloud Build Service Account requires `roles/secretmanager.secretAccessor` on the above secrets.

## 6. Linting
-   **Tools**: `ruff`
-   **Command**: `uv run ruff check .`
-   **Policy**: Build fails immediately on error.

## 7. Local Development

To run tests locally matching CI:

1.  **Install dev dependencies**:
    ```bash
    uv sync --dev
    ```

2.  **Run specific suite**:
    ```bash
    pytest tests/workflows/cli_unification/
    ```

3.  **Run with coverage**:
    ```bash
    pytest --cov=backend tests/
    ```

> **Note:** For testing in a containerized environment that exactly matches CI/CD, see [Section 8: Local Docker Testing](#8-local-docker-testing).

## 8. Local Docker Testing

Before pushing changes to trigger Cloud Build, you can test the Docker build and test suite locally to catch issues early.

### Prerequisites

1. **Docker installed** - Ensure Docker is installed and running on your machine
2. **Agent-GCPtoolkit sibling directory** - Required for dependency resolution
3. **Service Account Key** - GCP service account JSON key for authentication (optional for some tests)
4. **Environment Variables** - API keys for tests that require external services (optional)

### Directory Structure

The local filesystem must match the structure expected by `Dockerfile.test`:

```
/home/code/myagents/
├── MyAgents-staging/          # Your worktree (or MyAgents, MyAgents-feature, etc.)
│   ├── Dockerfile.test
│   ├── docker-compose.test.yml
│   ├── pyproject.toml
│   ├── tests/
│   └── ...
└── Agent-GCPtoolkit/          # MUST be sibling directory
    ├── pyproject.toml
    └── ...
```

This sibling structure allows `pyproject.toml`'s `path = "../Agent-GCPtoolkit"` reference to resolve correctly without path rewrites.

### Build Command

Build the Docker test image from the parent directory (`/home/code/myagents/`) using your worktree name:

```bash
# Navigate to parent directory
cd /home/code/myagents/

# Build with your worktree name (e.g., MyAgents-staging)
docker build \
  --build-arg WORKTREE_NAME=MyAgents-staging \
  -t myagents-test:local \
  -f MyAgents-staging/Dockerfile.test \
  .

# For other worktrees, replace MyAgents-staging with your worktree name:
# docker build --build-arg WORKTREE_NAME=MyAgents-feature-xyz -t myagents-test:local -f MyAgents-feature-xyz/Dockerfile.test .
```

**Key Points:**
- Build context is `.` (parent directory `/home/code/myagents/`)
- `WORKTREE_NAME` must match your actual worktree directory name
- `-f` flag points to the Dockerfile inside your worktree
- Tag as `myagents-test:local` for easy reference

### Run Tests in Container

Once built, run tests inside the container to verify everything works:

```bash
# Run all tests
docker run --rm myagents-test:local bash -c \
  "cd /workspace/MyAgents-staging && uv run pytest tests/ -v"

# Run specific test suite (e.g., CLI unification)
docker run --rm myagents-test:local bash -c \
  "cd /workspace/MyAgents-staging && uv run pytest tests/workflows/cli_unification/ -v"

# Run with coverage
docker run --rm myagents-test:local bash -c \
  "cd /workspace/MyAgents-staging && uv run pytest --cov=backend --cov=frontend --cov=myagents tests/ -v"

# Run unit tests only (excludes costly tests)
docker run --rm myagents-test:local bash -c \
  "cd /workspace/MyAgents-staging && uv run pytest -m 'unit and not costly' tests/ -v"

# Run linting
docker run --rm myagents-test:local bash -c \
  "cd /workspace/MyAgents-staging && uv run ruff check ."
```

### Run with Docker Compose

For parallel test execution matching the CI/CD pipeline, use `docker-compose.test.yml`:

```bash
# Navigate to your worktree
cd /home/code/myagents/MyAgents-staging/

# Set environment variables
export WORKTREE_NAME=MyAgents-staging
export GCP_SA_KEY_PATH=/path/to/your/service-account.json  # Optional

# Build and run all test services in parallel
docker-compose -f docker-compose.test.yml up --build

# Run specific test service
docker-compose -f docker-compose.test.yml up test-cli-unification

# Clean up after testing
docker-compose -f docker-compose.test.yml down -v
```

### Mounting Service Account and Secrets

For tests requiring GCP authentication or LLM API calls, mount credentials:

```bash
# With GCP Service Account
docker run --rm \
  -v /path/to/service-account.json:/root/service-account.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/root/service-account.json \
  myagents-test:local bash -c \
  "cd /workspace/MyAgents-staging && uv run pytest tests/ -v"

# With API keys for LLM tests
docker run --rm \
  -e GEMINI_API_KEY=your-api-key \
  -e LANGSMITH_API_KEY=your-api-key \
  myagents-test:local bash -c \
  "cd /workspace/MyAgents-staging && uv run pytest tests/ -v"
```

### Interactive Container Shell

For debugging or exploration, launch an interactive shell:

```bash
# Start interactive bash session
docker run --rm -it myagents-test:local bash

# Inside container, navigate and run tests manually
cd /workspace/MyAgents-staging
uv run pytest tests/workflows/cli_unification/ -v
uv run ruff check .
exit
```

### Troubleshooting

#### Error: "Agent-GCPtoolkit not found"

```
ERROR: Directory '/workspace/Agent-GCPtoolkit' does not exist
```

**Solution:** Ensure Agent-GCPtoolkit is a sibling directory to your worktree:
```bash
cd /home/code/myagents/
ls -la  # Should show both MyAgents-staging/ and Agent-GCPtoolkit/
```

#### Error: "WORKTREE_NAME mismatch"

```
ERROR: Directory '/workspace/MyAgents-staging' does not exist
```

**Solution:** Verify `WORKTREE_NAME` build arg matches your actual directory:
```bash
# If your worktree is MyAgents-feature-xyz:
docker build --build-arg WORKTREE_NAME=MyAgents-feature-xyz \
  -t myagents-test:local \
  -f MyAgents-feature-xyz/Dockerfile.test \
  .
```

#### Error: "Build context is too large"

**Solution:** Ensure you're building from `/home/code/myagents/` (not from inside the worktree):
```bash
# Wrong: cd /home/code/myagents/MyAgents-staging && docker build .
# Correct:
cd /home/code/myagents/
docker build --build-arg WORKTREE_NAME=MyAgents-staging -f MyAgents-staging/Dockerfile.test .
```

#### Error: "pyproject.toml path resolution failed"

```
ERROR: Could not find a version that satisfies the requirement agent-gcptoolkit
```

**Solution:** This indicates the sibling directory structure is incorrect. The Dockerfile expects Agent-GCPtoolkit at `/workspace/Agent-GCPtoolkit`. Verify:
1. Agent-GCPtoolkit exists as sibling to your worktree locally
2. Build context is the parent directory (`.` in `/home/code/myagents/`)
3. Dockerfile copies Agent-GCPtoolkit to `/workspace/Agent-GCPtoolkit`

#### Tests fail locally but pass in CI/CD

**Possible causes:**
1. Missing environment variables (API keys, service account)
2. Different Python/dependency versions (rebuild image to sync)
3. Local file changes not committed (Docker builds from filesystem, not git)

**Solution:** Rebuild the Docker image and ensure all dependencies are synced:
```bash
docker build --no-cache --build-arg WORKTREE_NAME=MyAgents-staging -t myagents-test:local -f MyAgents-staging/Dockerfile.test .
```

### Best Practices

1. **Test before pushing** - Run `docker build` locally to catch build failures early
2. **Use same WORKTREE_NAME** - Match your actual directory name to avoid path issues
3. **Run unit tests first** - Use `-m "unit and not costly"` for fast feedback
4. **Check coverage** - Ensure you meet the 40% threshold before pushing
5. **Clean up** - Remove old images periodically: `docker image prune -f`

### Integration with Development Workflow

```bash
# Typical development workflow:
# 1. Make changes in your worktree
cd /home/code/myagents/MyAgents-staging/
# ... edit code ...

# 2. Test locally (fast)
uv run pytest tests/workflows/cli_unification/ -v

# 3. Test in Docker (matches CI/CD)
cd /home/code/myagents/
docker build --build-arg WORKTREE_NAME=MyAgents-staging -t myagents-test:local -f MyAgents-staging/Dockerfile.test .
docker run --rm myagents-test:local bash -c "cd /workspace/MyAgents-staging && uv run pytest tests/ -v"

# 4. Push to trigger Cloud Build
cd /home/code/myagents/MyAgents-staging/
git add . && git commit -m "your message" && git push
```

## 9. Docker Container Structure

The Docker test container (`Dockerfile.test`) mirrors the **exact local filesystem structure** to eliminate path mismatches.

### Directory Layout

```
LOCAL FILESYSTEM:                       DOCKER CONTAINER:
/home/code/myagents/                    /workspace/
├── Agent-GCPtoolkit/                   ├── Agent-GCPtoolkit/     ← Sibling directory
├── MyAgents-staging/                   └── MyAgents-staging/
│   └── pyproject.toml                      └── pyproject.toml
```

### Why Sibling Structure?

The `pyproject.toml` references Agent-GCPtoolkit as:
```toml
[tool.uv.sources]
agent-gcptoolkit = { path = "../Agent-GCPtoolkit", editable = true }
```

By copying Agent-GCPtoolkit to `/workspace/Agent-GCPtoolkit` (sibling of the worktree), the `../Agent-GCPtoolkit` path resolves correctly **without any sed hacks**.

### Benefits

1. **No path rewriting needed** - pyproject.toml works unchanged
2. **True reflection of local structure** - same paths work locally and in Docker
3. **Eliminates format mismatch cycles** - no more switching between `workspace = true` and `path = "..."`

## 10. Agent Guidance: pyproject.toml Format

> **IMPORTANT FOR AI AGENTS**: Do not change the `agent-gcptoolkit` dependency format.

### Canonical Format

Always use the path format for the agent-gcptoolkit dependency:

```toml
[tool.uv.sources]
agent-gcptoolkit = { path = "../Agent-GCPtoolkit", editable = true }
```

### Why NOT `workspace = true`?

The `workspace = true` format requires running commands from the workspace root. This causes issues:

1. **Worktree isolation** - Each worktree should be independently functional
2. **Docker builds** - Container structure may not have workspace root
3. **CI/CD** - Build steps may not be in workspace root context

### Do NOT change to:

```toml
# ❌ DO NOT USE - breaks worktree isolation
agent-gcptoolkit = { workspace = true }
```

### If You See Format Mismatch

If `uv sync` changes the format, revert it:
```bash
git checkout pyproject.toml
```

Then investigate why uv is changing the format (likely a workspace root issue).

## 11. Cloud Build Workspace Structure

Cloud Build uses a **unique workspace restructuring process** that differs from both local development and local Docker testing. Understanding this structure is critical for Dockerfile COPY commands and dependency resolution.

### Workspace Transformation Process

Cloud Build starts with a standard git checkout, then **restructures the workspace** in Step 0.5 ("Prepare Workspace") to match the sibling directory pattern required by `pyproject.toml`.

#### Initial State (after git clone)

```
/workspace/
├── .git/
├── MyAgents/             ← Source code (from current branch)
├── cloudbuild.yaml
├── pyproject.toml
├── Dockerfile.test
└── ... (all repo files)
```

#### After Step 0.5 Workspace Restructuring

```
/workspace/
├── Agent-GCPtoolkit/     ← Cloned from GitHub (private repo)
├── MyAgents/             ← Source moved here (from root)
│   ├── .git/
│   ├── cloudbuild.yaml
│   ├── Dockerfile.test
│   ├── pyproject.toml
│   └── ...
├── config/               ← Created for containerized testing
│   └── config.yml
├── runtime/              ← Created for Dockerfile COPY (CRITICAL)
│   ├── studio/
│   │   └── logs/
│   ├── checkpoints/
│   └── studio.pid
└── service-account.json  ← From Secret Manager (Step 0)
```

### Why This Restructuring?

The restructuring serves three purposes:

1. **Dependency Resolution**: `pyproject.toml` references Agent-GCPtoolkit as `path = "../Agent-GCPtoolkit"`. By moving source to `/workspace/MyAgents/`, this relative path resolves correctly to `/workspace/Agent-GCPtoolkit/`.

2. **Dockerfile Build Context**: `Dockerfile.test` is inside `MyAgents/`, but expects `Agent-GCPtoolkit/` as a sibling. The docker build command uses:
   ```bash
   docker build -f MyAgents/Dockerfile.test .
   ```
   Build context is `.` (workspace root), so Dockerfile can access both `MyAgents/` and `Agent-GCPtoolkit/`.

3. **Runtime Directory Availability**: `Dockerfile.test` line 48 contains:
   ```dockerfile
   COPY runtime/ ./runtime/
   ```
   This directory must exist at workspace root (`/workspace/runtime/`) for the COPY to succeed.

### Step 0.5 Implementation

From `cloudbuild.yaml` lines 26-103:

```bash
# Clone private dependency
git clone https://x-access-token:$$GH_TOKEN@github.com/HuaMick/Agent-GCPtoolkit.git Agent-GCPtoolkit

# Restructure workspace
mkdir MyAgents_tmp
find . -maxdepth 1 -mindepth 1 \
  ! -name 'Agent-GCPtoolkit' \
  ! -name 'MyAgents_tmp' \
  ! -name 'service-account.json' \
  -exec mv {} MyAgents_tmp/ \;
mv MyAgents_tmp MyAgents

# Create directories for Dockerfile COPY commands
mkdir -p config
mkdir -p runtime/studio/logs
mkdir -p runtime/checkpoints
touch runtime/studio.pid

# Create config file (config.yml)
```

### Critical Files Created

| File/Directory | Purpose | Created By |
|----------------|---------|------------|
| `Agent-GCPtoolkit/` | Private dependency | Cloud Build: cloned; Dockerfile: COPY'd |
| `MyAgents/` | Source code | Cloud Build: workspace restructuring |
| `config/config.yml` | Studio service config | Cloud Build: Step 0.5; Dockerfile: RUN printf |
| `runtime/studio/logs/` | Studio log directory | Cloud Build: Step 0.5; Dockerfile: RUN mkdir |
| `runtime/checkpoints/` | LangGraph checkpoints | Cloud Build: Step 0.5; Dockerfile: RUN mkdir |
| `runtime/studio.pid` | Studio PID file | Cloud Build: Step 0.5; Dockerfile: RUN touch |

### Environment Comparison

| Aspect | Local Development | Local Docker Testing | Cloud Build |
|--------|-------------------|---------------------|-------------|
| **Workspace Root** | `/home/code/myagents/` | `/workspace/` | `/workspace/` |
| **Source Location** | `MyAgents-staging/` | `MyAgents-staging/` | `MyAgents/` |
| **Agent-GCPtoolkit** | Sibling (pre-existing) | COPY'd as sibling | Cloned as sibling |
| **runtime/** | Pre-existing | **Created in Dockerfile** ✅ | **Created in Step 0.5** ✅ |
| **config/** | User-created | **Created in Dockerfile** ✅ | **Created in Step 0.5** ✅ |
| **Build Context** | `.` (parent) | `.` (parent) | `.` (/workspace/) |

### Why runtime/ Issue Bypassed UAT (Historical)

**Background**: Prior to commit [SHA of this fix], the runtime/ directory issue bypassed comprehensive UAT testing:

1. **UAT tested local environment**: runtime/ directory existed at `/home/code/myagents/runtime/` (pre-existing)
2. **Old Dockerfile used COPY**: `COPY runtime/ ./runtime/` assumed runtime/ exists in build context
3. **Cloud Build Step 0.5**: Created runtime/ during workspace preparation
4. **Environment gap**: Local Docker could copy pre-existing runtime/, Cloud Build needed it created

**Result**: Cloud Build failed with `COPY runtime/ ./runtime/: file does not exist` despite 100% UAT pass rate.

**Fix**: Dockerfile.test now **creates** runtime/ and config/ directories (lines 54-95) instead of copying from build context. This matches Cloud Build Step 0.5 behavior exactly.

### Local Docker Now Matches Cloud Build

**Current State**: Local Docker testing and Cloud Build use identical approaches:

| Operation | Local Docker (Dockerfile.test) | Cloud Build (Step 0.5) | Match |
|-----------|-------------------------------|------------------------|-------|
| **runtime/ creation** | `RUN mkdir -p runtime/...` | `mkdir -p runtime/...` | ✅ |
| **config/ creation** | `RUN mkdir -p config` | `mkdir -p config` | ✅ |
| **config.yml** | `RUN printf '...' > config/config.yml` | `printf '...' > config/config.yml` | ✅ |
| **Build context** | `.` (parent directory) | `.` (/workspace/) | ✅ |

**No simulation needed**: Running local Docker build now tests the exact same logic Cloud Build uses.

### Best Practices for Dockerfile Modifications

When modifying `Dockerfile.test`:

1. **Don't COPY runtime/ or config/**: These are created by Dockerfile RUN commands (lines 54-95)
2. **Match Cloud Build Step 0.5**: If Cloud Build creates a directory, Dockerfile should too
3. **Test locally first**: Local Docker build now validates Cloud Build compatibility
4. **Self-contained Dockerfile**: Don't rely on host filesystem structure beyond source code

### Debugging Dockerfile Issues

If local Docker build fails with directory/file issues:

1. **Check Dockerfile RUN commands**: Ensure all required directories are created
2. **Compare with Cloud Build Step 0.5**: cloudbuild.yaml lines 49-95 show what Cloud Build creates
3. **Validate build context**: Build context is `.` (parent directory), not worktree
4. **Don't COPY generated files**: Files like config/*.yml should be created by RUN, not COPY

### References

- **Cloud Build Workspace Preparation**: `cloudbuild.yaml` lines 22-103 (Step 0.5)
- **Dockerfile runtime/config creation**: `Dockerfile.test` lines 51-95
- **UAT Bypass Investigation**: `/home/code/myagents/docs/plans/live/251126_myagents_staging.yml` lines 336-504
- **User Story for Testing**: `US-INFRA-001` Cloud Build Environment Parity Testing

