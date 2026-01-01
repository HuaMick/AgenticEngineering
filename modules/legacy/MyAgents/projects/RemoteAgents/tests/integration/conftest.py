"""Pytest fixtures for integration tests.

This module provides fixtures for Docker-based integration testing including:
- Docker Compose environment management
- Network disconnect/reconnect helpers
- Relay service client fixtures
"""

import os
import time
from typing import Any, Dict, Generator

import docker
import httpx
import pytest

# Check if Docker is available
try:
    _docker_client = docker.from_env()
    _docker_client.ping()
    DOCKER_AVAILABLE = True
except Exception:
    DOCKER_AVAILABLE = False


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "docker: marks tests requiring Docker environment"
    )


def pytest_collection_modifyitems(config, items):
    """Skip docker tests if Docker is not available."""
    if DOCKER_AVAILABLE:
        return

    skip_docker = pytest.mark.skip(reason="Docker not available")
    for item in items:
        if "docker" in item.keywords:
            item.add_marker(skip_docker)


@pytest.fixture(scope="module")
def docker_client() -> docker.DockerClient:
    """Get Docker client instance.

    Returns:
        Docker client for container management
    """
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker not available")
    return docker.from_env()


@pytest.fixture(scope="module")
def docker_compose_project_dir() -> str:
    """Get the directory containing docker-compose.test.yml.

    Returns:
        Absolute path to the project directory
    """
    # Go up from tests/integration to project root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _check_docker_compose_compatibility() -> tuple[bool, str]:
    """Check if docker-compose is compatible with the current Docker version.

    Returns:
        Tuple of (is_compatible, error_message)
    """
    import subprocess
    import shutil

    # First try 'docker compose' (v2 plugin)
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and "version" in result.stdout.lower():
            return True, ""
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Fall back to 'docker-compose' (v1 standalone)
    if shutil.which("docker-compose"):
        # Check if the old docker-compose will work with current Docker
        # docker-compose 1.x is incompatible with Docker 28+ due to API changes
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                docker_version = result.stdout.strip()
                major = int(docker_version.split(".")[0])
                if major >= 28:
                    return False, (
                        f"Docker Compose 1.x is incompatible with Docker {docker_version}. "
                        "The old docker-compose cannot access 'ContainerConfig' from the new Docker API. "
                        "Please upgrade to Docker Compose V2: install docker-compose-plugin and use 'docker compose'."
                    )
        except (subprocess.SubprocessError, ValueError, IndexError):
            pass
        return True, ""

    return False, "Neither 'docker compose' (v2) nor 'docker-compose' (v1) is available"


# Check docker-compose compatibility at module load time
DOCKER_COMPOSE_COMPATIBLE, DOCKER_COMPOSE_ERROR = _check_docker_compose_compatibility()


@pytest.fixture(scope="module")
def relay_service(
    docker_client: docker.DockerClient,
    docker_compose_project_dir: str,
) -> Generator[Dict[str, Any], None, None]:
    """Start relay service container for testing.

    This fixture:
    1. Builds and starts the relay container using docker-compose
    2. Waits for health check to pass
    3. Yields service info
    4. Cleans up containers after test

    Yields:
        Dict with relay_url, container, and network info
    """
    import subprocess

    # Check docker-compose compatibility before trying to use it
    if not DOCKER_COMPOSE_COMPATIBLE:
        pytest.skip(DOCKER_COMPOSE_ERROR)

    compose_file = os.path.join(docker_compose_project_dir, "docker-compose.test.yml")

    # Try docker compose v2 first, fall back to docker-compose v1
    compose_cmd = ["docker", "compose"] if subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True
    ).returncode == 0 else ["docker-compose"]

    # Clean up any leftover containers from previous runs
    subprocess.run(
        compose_cmd + ["-f", compose_file, "down", "-v", "--remove-orphans"],
        cwd=docker_compose_project_dir,
        capture_output=True,
    )

    # Start containers with docker-compose
    try:
        # Build and start
        subprocess.run(
            compose_cmd + ["-f", compose_file, "up", "-d", "--build", "--force-recreate"],
            cwd=docker_compose_project_dir,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.decode() if e.stderr else str(e)
        # Check for the specific ContainerConfig error
        if "ContainerConfig" in error_output:
            pytest.skip(
                "Docker Compose 1.x is incompatible with current Docker version. "
                "Please upgrade to Docker Compose V2: install docker-compose-plugin and use 'docker compose'."
            )
        # Check for port already in use error
        if "address already in use" in error_output.lower():
            pytest.skip(
                "Port 8080 is already in use. Stop any running relay servers before running Docker integration tests."
            )
        pytest.fail(f"Failed to start docker-compose: {error_output}")

    # Wait for relay to be healthy
    max_wait = 60
    start_time = time.time()
    relay_url = "http://localhost:8080"

    while time.time() - start_time < max_wait:
        try:
            with httpx.Client() as client:
                response = client.get(f"{relay_url}/health", timeout=2.0)
                if response.status_code == 200:
                    break
        except Exception:
            pass
        time.sleep(1)
    else:
        # Cleanup on failure
        subprocess.run(
            compose_cmd + ["-f", compose_file, "down", "-v"],
            cwd=docker_compose_project_dir,
            capture_output=True,
        )
        pytest.fail("Relay service did not become healthy within timeout")

    # Get container and network info
    try:
        relay_container = docker_client.containers.get("agent-relay")
        network = docker_client.networks.get("agent-network")
    except docker.errors.NotFound as e:
        subprocess.run(
            compose_cmd + ["-f", compose_file, "down", "-v"],
            cwd=docker_compose_project_dir,
            capture_output=True,
        )
        pytest.fail(f"Container or network not found: {e}")

    yield {
        "relay_url": relay_url,
        "container": relay_container,
        "network": network,
        "compose_file": compose_file,
        "project_dir": docker_compose_project_dir,
        "compose_cmd": compose_cmd,
    }

    # Cleanup
    subprocess.run(
        compose_cmd + ["-f", compose_file, "down", "-v"],
        cwd=docker_compose_project_dir,
        capture_output=True,
    )


@pytest.fixture
def http_client() -> Generator[httpx.Client, None, None]:
    """Create HTTP client for REST API calls.

    Yields:
        httpx.Client configured for testing
    """
    with httpx.Client(timeout=10.0) as client:
        yield client


@pytest.fixture
def async_http_client() -> Generator[httpx.AsyncClient, None, None]:
    """Create async HTTP client for REST API calls.

    Yields:
        httpx.AsyncClient configured for testing
    """
    # Note: This fixture is not async, but the client is.
    # Use it in async tests with `async with client:` pattern
    client = httpx.AsyncClient(timeout=10.0)
    yield client
    # Client will be closed by the test using it
