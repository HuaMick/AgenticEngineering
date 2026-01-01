"""
Secrets domain for MyAgents.

Provides access to secrets via gcptoolkit CLI with caching.
"""

from .manager import get_secret, clear_cache, is_gcptoolkit_available
from .exceptions import (
    SecretsError,
    SecretNotFoundError,
    InvalidSecretNameError,
    GCPToolkitNotFoundError,
)

__all__ = [
    "get_secret",
    "clear_cache",
    "is_gcptoolkit_available",
    "SecretsError",
    "SecretNotFoundError",
    "InvalidSecretNameError",
    "GCPToolkitNotFoundError",
]
