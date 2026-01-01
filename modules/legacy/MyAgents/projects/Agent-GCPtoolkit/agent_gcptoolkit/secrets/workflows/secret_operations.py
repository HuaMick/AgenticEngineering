"""Workflow for secret operations with caching and fallback."""
import os
import logging
from typing import Optional
from ..domains.models import Secret
from ..domains.gcp_client import GCPSecretClient

logger = logging.getLogger(__name__)

# Module-level cache: {project_id:secret_name -> Secret}
# BLIND TESTING FIX #10: Clarified - this is per-process cache, NOT per-CLI invocation
_secret_cache: dict[str, Secret] = {}


def get_secret(secret_name: str, project_id: Optional[str] = None, quiet: bool = False) -> Optional[str]:
    """
    Fetch secret from GCP Secret Manager with memory caching.

    Args:
        secret_name: Name of the secret to fetch
        project_id: GCP project ID (auto-detected if not provided)
        quiet: If True, suppress fallback warnings to stderr (BLIND TESTING FIX #4)

    Returns:
        Secret value as string, or None if not found

    Behavior:
        - Checks environment variables FIRST (fast path for development)
        - Caches secrets in memory (per-process only, NOT across CLI invocations)
        - Auto-detects project_id from GCP_PROJECT env var or config file
        - Falls back to GCP Secret Manager if env var not set (production path)
        - With quiet=False: Logs source information to stderr
        - With quiet=True: Silent operation (for scripts/production use)
    """
    # PERFORMANCE FIX: Check environment variable FIRST before initializing GCP client
    # This avoids 12-second GCP authentication timeout during local development
    env_value = os.getenv(secret_name)
    if env_value:
        # Use a simplified cache key for env vars (no project_id needed)
        cache_key = f"env:{secret_name}"
        if cache_key not in _secret_cache:
            secret = Secret(
                name=secret_name,
                value=env_value,
                project_id="local",
                source="env"
            )
            _secret_cache[cache_key] = secret
        return env_value

    # Environment variable not set, try GCP Secret Manager
    client = GCPSecretClient()

    # Auto-detect project_id if not provided
    if not project_id:
        project_id = client.get_project_id() or "unknown"

    # Check cache for GCP secrets
    cache_key = f"{project_id}:{secret_name}"
    if cache_key in _secret_cache:
        return _secret_cache[cache_key].value

    # Try fetching from GCP
    secret_value = client.fetch_secret(secret_name, project_id, quiet=quiet)

    if secret_value:
        secret = Secret(
            name=secret_name,
            value=secret_value,
            project_id=project_id,
            source="gcp"
        )
        _secret_cache[cache_key] = secret
        return secret_value

    # If we get here, secret not found in either environment or GCP
    return None
