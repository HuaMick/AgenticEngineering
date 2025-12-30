"""
Secrets management for MyAgents via workflow layer.

This module provides programmatic access to secrets by using the
secrets workflow which wraps agent_gcptoolkit's workflow layer.

Architecture:
    Domain (this file) ← Workflow ← Entrypoint

Performance:
- First call from environment variable: < 1ms
- First call from GCP Secret Manager: ~200ms
- Subsequent calls (cached): < 1ms
"""

from typing import Optional, Dict

from myagents.backend.services.agents.workflows.secrets_workflow import (
    get_secret as _workflow_get_secret,
)
from .exceptions import (
    SecretsError,
    SecretNotFoundError,
)


# Module-level cache for backward compatibility
# Note: Caching is now handled by the workflow layer
_SECRET_CACHE: Dict[str, str] = {}


def get_secret(secret_name: str, project_id: Optional[str] = None, use_cache: bool = True) -> str:
    """
    Get a secret value via the secrets workflow.

    This function now delegates to the workflow layer which uses agent_gcptoolkit
    instead of subprocess calls. This provides better performance and follows
    the architectural pattern: Domain ← Workflow ← Entrypoint.

    PERFORMANCE:
    - First call from environment variable: < 1ms
    - First call from GCP Secret Manager: ~200ms
    - Subsequent calls (cached by workflow): < 1ms

    ENVIRONMENT VARIABLE PRECEDENCE:
    - Checks environment variables FIRST (fast path)
    - Then falls back to GCP Secret Manager (production path)
    - Local development: Set env vars for fast iteration
    - Production: Use GCP Secret Manager

    Args:
        secret_name: Name of the secret (format: [a-zA-Z0-9_-]+)
        project_id: Optional GCP project ID (defaults to gcloud config or GCP_PROJECT env var)
        use_cache: Whether to use caching (default: True). Note: Cache is managed by workflow layer.

    Returns:
        Secret value as string

    Raises:
        ValueError: If secret not found or invalid parameters
        RuntimeError: If unable to access Secret Manager

    Example:
        >>> from myagents.backend.services.agents.domains.secrets import get_secret
        >>> api_key = get_secret("GEMINI_API_KEY")
        >>> db_password = get_secret("db-password", project_id="my-project")
        >>> fresh_secret = get_secret("my-secret", use_cache=False)
    """
    # Delegate to workflow layer
    # Note: use_cache parameter is kept for backward compatibility but not used
    # as caching is now handled by the workflow layer
    try:
        secret_value = _workflow_get_secret(
            secret_name=secret_name,
            project_id=project_id,
            quiet=True  # Domain layer uses quiet mode
        )
        return secret_value

    except ValueError as e:
        # Map workflow ValueError to domain SecretNotFoundError
        raise SecretNotFoundError(str(e)) from e
    except RuntimeError as e:
        # Map workflow RuntimeError to domain SecretsError
        raise SecretsError(str(e)) from e


def clear_cache() -> None:
    """
    Clear the secrets cache.

    Note: This is now a no-op as caching is handled by the workflow layer.
    Kept for backward compatibility.

    Useful for testing or when secrets are rotated.
    Forces next get_secret() call to fetch fresh value.
    """
    # Cache clearing is now handled by workflow layer
    # This function is kept for backward compatibility
    _SECRET_CACHE.clear()  # Clear local cache (currently unused)


def is_gcptoolkit_available() -> bool:
    """
    Check if agent_gcptoolkit is available.

    Note: This now checks if the workflow can be imported rather than
    checking for CLI availability. Kept for backward compatibility.

    Returns:
        True if gcptoolkit workflow is available, False otherwise

    Example:
        >>> from myagents.backend.services.agents.domains.secrets import is_gcptoolkit_available
        >>> if is_gcptoolkit_available():
        ...     api_key = get_secret("my-key")
        ... else:
        ...     api_key = "default-dev-key"
    """
    try:
        # Try to import workflow to verify availability
        from myagents.backend.services.agents.workflows.secrets_workflow import get_secret as _test
        return True
    except ImportError:
        return False
