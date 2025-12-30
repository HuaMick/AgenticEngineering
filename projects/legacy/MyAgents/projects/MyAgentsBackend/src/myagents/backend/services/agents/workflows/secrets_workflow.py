"""
Secrets workflow for MyAgents.

This workflow wraps agent_gcptoolkit's secrets workflow to provide
a MyAgents-specific interface following the Domain → Workflow → Entrypoint pattern.

Architectural Pattern:
    MyAgents Entrypoint (e.g., CLI, API)
      ↓ imports from
    MyAgents Workflow (this file)
      ↓ imports from
    gcptoolkit Workflow (agent_gcptoolkit.secrets.workflows.secret_operations)
      ↓ imports from
    gcptoolkit Domain (agent_gcptoolkit.secrets.domains.*)

Per architecture_checklist.md lines 87-89:
- ✓ Import from agent_gcptoolkit.secrets.workflows.secret_operations (workflow layer)
- ✗ Never import from agent_gcptoolkit.secrets.domains.* (bypasses gcptoolkit's workflow layer)
"""

import logging
from typing import Optional

from agent_gcptoolkit.secrets.workflows.secret_operations import (
    get_secret as _gcptoolkit_get_secret,
)

logger = logging.getLogger(__name__)


def get_secret(
    secret_name: str,
    project_id: Optional[str] = None,
    quiet: bool = False
) -> str:
    """
    Get a secret from Google Cloud Secret Manager or environment variables.

    This is a MyAgents workflow function that wraps gcptoolkit's get_secret workflow.
    It follows the architectural pattern: Entrypoint → Workflow → Domain.

    The wrapped gcptoolkit workflow provides:
    - Environment variable checking FIRST (fast path for development)
    - GCP Secret Manager fallback (production path)
    - In-memory caching (per-process)
    - Auto-detection of project_id from GCP_PROJECT env var or config

    Args:
        secret_name: Name of the secret to retrieve (format: [a-zA-Z0-9_-]+)
        project_id: Optional GCP project ID. If not specified, gcptoolkit will
                   auto-detect from GCP_PROJECT env var or gcloud config.
        quiet: If True, suppress output messages. Default is False.

    Returns:
        str: The secret value

    Raises:
        ValueError: If secret not found or invalid parameters
        RuntimeError: If unable to access Secret Manager

    Examples:
        >>> from myagents.backend.services.agents.workflows.secrets_workflow import get_secret
        >>> api_key = get_secret("GEMINI_API_KEY")
        >>> db_password = get_secret("DB_PASSWORD", project_id="my-project")
        >>> secret = get_secret("my-secret", quiet=True)  # Silent operation

    Performance:
        - First call from environment variable: < 1ms
        - First call from GCP Secret Manager: ~200ms
        - Subsequent calls (cached): < 1ms

    Note:
        This function maintains the architectural boundary between MyAgents and gcptoolkit.
        Currently, it's a thin wrapper, but MyAgents-specific logic (logging, metrics,
        validation) can be added here without modifying gcptoolkit.
    """
    try:
        # Wrap gcptoolkit workflow - maintains architectural boundary
        # This is where MyAgents-specific orchestration happens
        secret_value = _gcptoolkit_get_secret(
            secret_name=secret_name,
            project_id=project_id,
            quiet=quiet
        )

        # Enforce fail-loud behavior: raise ValueError if secret not found
        # This ensures tests and workflows fail immediately with clear error
        # instead of silently continuing with None
        if secret_value is None:
            raise ValueError(
                f"Secret '{secret_name}' not found in GCP Secret Manager or environment variables"
            )

        return secret_value

    except Exception as e:
        # Log error and re-raise (MyAgents-specific error handling)
        logger.error(
            f"Failed to retrieve secret '{secret_name}': {type(e).__name__}: {str(e)}"
        )
        raise


def clear_secret_cache() -> None:
    """
    Clear the gcptoolkit secrets cache.

    This forces the next get_secret() call to fetch fresh values from
    environment variables or GCP Secret Manager instead of using cached values.

    Useful for:
    - Testing scenarios
    - Secret rotation handling
    - Forcing cache refresh after configuration changes

    Examples:
        >>> from myagents.backend.services.agents.workflows.secrets_workflow import (
        ...     get_secret, clear_secret_cache
        ... )
        >>> api_key = get_secret("API_KEY")  # Cached
        >>> clear_secret_cache()
        >>> api_key = get_secret("API_KEY")  # Fresh fetch

    Note:
        Currently a placeholder - gcptoolkit's cache is module-level and
        not exposed for clearing. Future enhancement could add cache management
        if gcptoolkit provides an API for it.
    """
    logger.info("Secret cache clear requested (not yet implemented in gcptoolkit)")
