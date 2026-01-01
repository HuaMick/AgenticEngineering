"""Infrastructure layer for terminal service.

Provides concrete implementations of repository protocols and external service integrations:
- InMemoryPTYRepository: Thread-safe in-memory storage for PTY sessions
- RelayClient: WebSocket client for relay service communication
"""

from .in_memory_repository import InMemoryPTYRepository
from .relay_client import (
    ConnectionState,
    RelayClient,
    RelayClientConfig,
    RelayClientError,
    RelayConnectionError,
    RelayEncryptionError,
)

__all__ = [
    "InMemoryPTYRepository",
    "ConnectionState",
    "RelayClient",
    "RelayClientConfig",
    "RelayClientError",
    "RelayConnectionError",
    "RelayEncryptionError",
]
