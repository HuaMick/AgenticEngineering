"""Docker helper functions for network disconnect testing.

This module provides utilities for:
- Network disconnect/reconnect operations
- Container health monitoring
- Cleanup operations
"""

import time
from typing import Optional

import docker
from docker.models.containers import Container
from docker.models.networks import Network


class NetworkDisconnectError(Exception):
    """Raised when network disconnect/reconnect operations fail."""

    pass


def disconnect_container_from_network(
    client: docker.DockerClient,
    container_name: str,
    network_name: str,
) -> None:
    """Disconnect a container from a Docker network.

    Args:
        client: Docker client instance
        container_name: Name or ID of the container to disconnect
        network_name: Name of the network to disconnect from

    Raises:
        NetworkDisconnectError: If disconnect fails
    """
    try:
        network = client.networks.get(network_name)
        container = client.containers.get(container_name)
        network.disconnect(container, force=True)
    except docker.errors.NotFound as e:
        raise NetworkDisconnectError(f"Container or network not found: {e}")
    except docker.errors.APIError as e:
        raise NetworkDisconnectError(f"Docker API error during disconnect: {e}")


def reconnect_container_to_network(
    client: docker.DockerClient,
    container_name: str,
    network_name: str,
) -> None:
    """Reconnect a container to a Docker network.

    Args:
        client: Docker client instance
        container_name: Name or ID of the container to reconnect
        network_name: Name of the network to connect to

    Raises:
        NetworkDisconnectError: If reconnect fails
    """
    try:
        network = client.networks.get(network_name)
        container = client.containers.get(container_name)
        network.connect(container)
    except docker.errors.NotFound as e:
        raise NetworkDisconnectError(f"Container or network not found: {e}")
    except docker.errors.APIError as e:
        # Ignore "already connected" errors
        if "already exists" not in str(e).lower():
            raise NetworkDisconnectError(f"Docker API error during reconnect: {e}")


def is_container_connected_to_network(
    client: docker.DockerClient,
    container_name: str,
    network_name: str,
) -> bool:
    """Check if a container is connected to a network.

    Args:
        client: Docker client instance
        container_name: Name or ID of the container
        network_name: Name of the network

    Returns:
        True if connected, False otherwise
    """
    try:
        network = client.networks.get(network_name)
        network.reload()
        containers = network.attrs.get("Containers", {})
        for container_id, info in containers.items():
            if info.get("Name") == container_name or container_id.startswith(container_name):
                return True
        return False
    except docker.errors.NotFound:
        return False


def wait_for_container_healthy(
    container: Container,
    timeout: float = 30.0,
    interval: float = 1.0,
) -> bool:
    """Wait for a container to become healthy.

    Args:
        container: Docker container object
        timeout: Maximum wait time in seconds
        interval: Check interval in seconds

    Returns:
        True if healthy, False if timeout reached
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        container.reload()
        health_status = container.attrs.get("State", {}).get("Health", {}).get("Status")

        if health_status == "healthy":
            return True

        # If no health check defined, check if running
        if health_status is None and container.status == "running":
            return True

        time.sleep(interval)

    return False


def get_container_logs(
    container: Container,
    lines: int = 50,
) -> str:
    """Get recent container logs.

    Args:
        container: Docker container object
        lines: Number of lines to retrieve

    Returns:
        Container log output as string
    """
    try:
        logs = container.logs(tail=lines, timestamps=True)
        return logs.decode("utf-8", errors="replace")
    except Exception as e:
        return f"Failed to get logs: {e}"


def stop_container_gracefully(
    container: Container,
    timeout: int = 10,
) -> None:
    """Stop a container gracefully with timeout.

    Args:
        container: Docker container object
        timeout: Seconds to wait before force kill
    """
    try:
        container.stop(timeout=timeout)
    except Exception:
        # Force kill if graceful stop fails
        try:
            container.kill()
        except Exception:
            pass


def get_network_connected_containers(
    client: docker.DockerClient,
    network_name: str,
) -> list[str]:
    """Get list of container names connected to a network.

    Args:
        client: Docker client instance
        network_name: Name of the network

    Returns:
        List of container names
    """
    try:
        network = client.networks.get(network_name)
        network.reload()
        containers = network.attrs.get("Containers", {})
        return [info.get("Name", container_id) for container_id, info in containers.items()]
    except docker.errors.NotFound:
        return []
