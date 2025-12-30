# UAT Testing Guide

This guide explains how to run User Acceptance Testing (UAT) using the `docker-compose.uat.yml` configuration.

## Overview

The UAT testing setup provides:
- Full integration test execution in isolated containers
- Service orchestration (relay, terminal services)
- Health check validation before test execution
- Test result artifacts for CI/CD integration
- Proper exit code propagation for automation

## Prerequisites

1. Docker and Docker Compose installed
2. GCP service account key available at:
   - Default: `/home/code/myagents/secrets/myagents-475112-60da581cc8d9.json`
   - Override with: `GCP_SA_KEY_PATH` environment variable

3. Required Docker images built or buildable:
   - MyAgents test image (from `MyAgents-cloud-deploy/Dockerfile.test`)
   - RemoteAgents services (relay, terminal)

## Quick Start

### Run UAT Tests Locally

```bash
# From /home/code/myagents directory
cd /home/code/myagents

# Run UAT with exit code propagation
docker-compose -f docker-compose.uat.yml up --exit-code-from test

# Cleanup after tests
docker-compose -f docker-compose.uat.yml down -v
```

### Run UAT in CI/CD

```bash
# Set environment variables
export WORKTREE_NAME=MyAgents-cloud-deploy
export GCP_SA_KEY_PATH=/path/to/service-account.json
export UAT_RESULTS_DIR=/path/to/results

# Run tests and capture exit code
docker-compose -f docker-compose.uat.yml up --build --exit-code-from test
EXIT_CODE=$?

# Collect artifacts
cp -r uat-results/* $ARTIFACTS_DIR/

# Cleanup
docker-compose -f docker-compose.uat.yml down -v

# Exit with test result code
exit $EXIT_CODE
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKTREE_NAME` | `MyAgents-cloud-deploy` | Name of the worktree to test |
| `GCP_SA_KEY_PATH` | `/home/code/myagents/secrets/myagents-475112-60da581cc8d9.json` | Path to GCP service account key |
| `UAT_RESULTS_DIR` | `./uat-results` | Directory to store test results |

### Service Architecture

```
┌─────────────────────────────────────────┐
│           Test Runner Service           │
│  - Runs pytest integration tests        │
│  - Waits for services to be healthy     │
│  - Collects test results                │
│  - Exits with test result code          │
└─────────────────┬───────────────────────┘
                  │ depends_on (healthy)
         ┌────────┴────────┐
         ▼                 ▼
    ┌─────────┐      ┌──────────┐
    │  Relay  │◄─────│ Terminal │
    │ :8080   │      │  :8081   │
    └─────────┘      └──────────┘
         │                │
         └────────┬───────┘
                  ▼
         myagents-uat-network
```

## Test Execution Flow

1. **Service Startup**
   - Relay service starts and health check begins
   - Terminal service waits for relay to be healthy
   - Test runner waits for both services to be healthy

2. **Health Check Validation**
   - Test runner uses curl to verify relay endpoint
   - Test runner verifies terminal endpoint
   - 60-second timeout per service

3. **Test Execution**
   - Runs all tests in `tests/integration/` directory
   - Generates JUnit XML report at `/test/results/uat-integration.xml`
   - Captures coverage data if available
   - Stops after 5 failures (fail fast)

4. **Result Collection**
   - Test results saved to mounted volume
   - XML reports available in `uat-results/` directory
   - Coverage reports copied if present
   - Exit code reflects test success/failure

## Test Results

After running UAT, results are available in the configured results directory:

```
uat-results/
├── uat-integration.xml    # JUnit XML test report
├── coverage_html/         # HTML coverage report (if available)
└── .coverage             # Coverage data file (if available)
```

### Interpreting Results

**Success:**
```bash
$ docker-compose -f docker-compose.uat.yml up --exit-code-from test
...
=== Test execution completed ===
myagents-uat-test-runner exited with code 0
```

**Failure:**
```bash
$ docker-compose -f docker-compose.uat.yml up --exit-code-from test
...
=== Test execution completed ===
myagents-uat-test-runner exited with code 1
```

## CI/CD Integration

### Google Cloud Build Example

```yaml
# cloudbuild-uat.yaml
steps:
  - name: 'docker/compose:1.29.2'
    id: 'uat-testing'
    args:
      - '-f'
      - 'docker-compose.uat.yml'
      - 'up'
      - '--build'
      - '--exit-code-from'
      - 'test'
    env:
      - 'WORKTREE_NAME=MyAgents-cloud-deploy'
      - 'GCP_SA_KEY_PATH=/workspace/service-account.json'
      - 'UAT_RESULTS_DIR=/workspace/uat-results'

  - name: 'gcr.io/cloud-builders/gsutil'
    id: 'upload-test-results'
    args:
      - 'cp'
      - '-r'
      - '/workspace/uat-results/*'
      - 'gs://${_ARTIFACT_BUCKET}/uat-results/${BUILD_ID}/'

  - name: 'docker/compose:1.29.2'
    id: 'cleanup'
    args:
      - '-f'
      - 'docker-compose.uat.yml'
      - 'down'
      - '-v'

artifacts:
  objects:
    location: 'gs://${_ARTIFACT_BUCKET}/uat-results/${BUILD_ID}'
    paths:
      - 'uat-results/**'
```

### GitHub Actions Example

```yaml
name: UAT Testing

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  uat:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Create GCP service account file
        run: |
          echo "${{ secrets.GCP_SA_KEY }}" | base64 -d > /tmp/service-account.json

      - name: Run UAT tests
        env:
          GCP_SA_KEY_PATH: /tmp/service-account.json
          WORKTREE_NAME: MyAgents-cloud-deploy
        run: |
          docker-compose -f docker-compose.uat.yml up --build --exit-code-from test

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: uat-test-results
          path: uat-results/

      - name: Cleanup
        if: always()
        run: |
          docker-compose -f docker-compose.uat.yml down -v
```

## Troubleshooting

### Services Not Becoming Healthy

**Problem:** Test runner times out waiting for services

**Solutions:**
1. Check service logs:
   ```bash
   docker-compose -f docker-compose.uat.yml logs relay
   docker-compose -f docker-compose.uat.yml logs terminal
   ```

2. Verify Dockerfiles exist:
   ```bash
   ls -la RemoteAgents-cloud-deploy/Dockerfile
   ls -la MyAgents-cloud-deploy/Dockerfile.test
   ```

3. Increase health check timeout in `docker-compose.uat.yml`

### Test Failures

**Problem:** Tests fail but services are healthy

**Solutions:**
1. Run tests locally for debugging:
   ```bash
   docker-compose -f docker-compose.uat.yml up -d relay terminal
   docker-compose -f docker-compose.uat.yml run test /bin/bash
   # Inside container:
   cd /workspace/MyAgents-cloud-deploy
   .venv/bin/pytest tests/integration/ -v
   ```

2. Check test logs in results directory:
   ```bash
   cat uat-results/uat-integration.xml
   ```

### Build Failures

**Problem:** Docker build fails for test image

**Solutions:**
1. Ensure Agent-GCPtoolkit is available:
   ```bash
   ls -la Agent-GCPtoolkit/
   ```

2. Check build context:
   ```bash
   docker-compose -f docker-compose.uat.yml build test
   ```

3. Verify pyproject.toml and uv.lock are present:
   ```bash
   ls -la MyAgents-cloud-deploy/pyproject.toml
   ls -la MyAgents-cloud-deploy/uv.lock
   ```

### Permission Issues

**Problem:** Cannot write to uat-results directory

**Solutions:**
```bash
# Ensure directory exists and is writable
mkdir -p uat-results
chmod 777 uat-results  # For CI/CD environments
```

## Advanced Usage

### Running Specific Test Suites

Modify the test command in `docker-compose.uat.yml`:

```yaml
# Run only docker_compose integration tests
command: >
  /bin/bash -c "
  ...
  /workspace/${WORKTREE_NAME}/.venv/bin/pytest \
    tests/integration/docker_compose/ \
    --junitxml=/test/results/uat-integration.xml \
    -v
  "
```

### Parallel Test Execution

For faster execution, use pytest-xdist:

```yaml
command: >
  /bin/bash -c "
  ...
  /workspace/${WORKTREE_NAME}/.venv/bin/pytest \
    tests/integration/ \
    --junitxml=/test/results/uat-integration.xml \
    -n auto \
    -v
  "
```

### Adding Additional Services

To test against additional services:

1. Add service definition to `docker-compose.uat.yml`
2. Add health check for the new service
3. Update test runner `depends_on` section
4. Add wait logic in test command

## Best Practices

1. **Always use `--exit-code-from test`** to capture test results
2. **Clean up after tests** with `down -v` to remove volumes
3. **Use build cache** in CI/CD by not using `--build` flag unnecessarily
4. **Store test artifacts** in CI/CD system for debugging
5. **Set resource limits** to prevent resource exhaustion
6. **Use fail-fast** (`--maxfail=5`) to save time in CI/CD
7. **Version pin** Docker Compose in CI/CD environments

## Resources

- Docker Compose Documentation: https://docs.docker.com/compose/
- Pytest Documentation: https://docs.pytest.org/
- JUnit XML Format: https://www.ibm.com/docs/en/developer-for-zos/14.1?topic=formats-junit-xml-format

## Support

For issues or questions:
1. Check CloudBuild logs in GCP Console
2. Review test results in `uat-results/` directory
3. Examine service health check logs
4. Verify environment variable configuration
