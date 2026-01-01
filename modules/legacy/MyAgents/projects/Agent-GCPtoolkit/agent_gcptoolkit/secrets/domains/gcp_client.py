"""GCP Secret Manager client wrapper."""
import os
import logging
from typing import Optional, Dict, Any
from google.cloud import secretmanager
from .config_loader import load_config, ConfigError

logger = logging.getLogger(__name__)

# Lazy loading: defer config loading until actually needed
# This allows CLI commands like --help to run without requiring a config file
_CONFIG: Optional[Dict[str, Any]] = None
_CONFIG_LOADED = False


def _get_config() -> Optional[Dict[str, Any]]:
    """
    Lazy load configuration on first use.

    This function loads the config file only when GCP operations are actually needed,
    not at import time. This allows commands like 'myagents --help' to run without
    requiring a config file to exist.

    Returns:
        Configuration dictionary

    Raises:
        ConfigError: If config file is missing or invalid
    """
    global _CONFIG, _CONFIG_LOADED

    if not _CONFIG_LOADED:
        _CONFIG = load_config()
        _CONFIG_LOADED = True

        # Set GOOGLE_APPLICATION_CREDENTIALS from config
        if _CONFIG and 'authentication' in _CONFIG and 'service_account_path' in _CONFIG['authentication']:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = _CONFIG['authentication']['service_account_path']
            sa_path = _CONFIG['authentication']['service_account_path']
            logger.info(f"Set GOOGLE_APPLICATION_CREDENTIALS from config: {sa_path}")

    return _CONFIG


class GCPSecretClient:
    """Wrapper around GCP Secret Manager client."""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> secretmanager.SecretManagerServiceClient:
        """Lazy-initialize client."""
        if self._client is None:
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def get_project_id(self) -> Optional[str]:
        """
        Get GCP project ID from config or environment variable.

        Priority order:
        1. GCP_PROJECT environment variable (allows override)
        2. Config file (primary source)

        Returns:
            Project ID string, or None if not found

        Raises:
            ValueError: If project_id is not found in config or environment
        """
        # Check GCP_PROJECT env var first (allows override)
        gcp_project_env = os.getenv("GCP_PROJECT")
        if gcp_project_env:
            logger.debug(f"Using GCP_PROJECT from environment: {gcp_project_env}")
            return gcp_project_env

        # Lazy load config only when needed
        try:
            config = _get_config()
            # Use config file project_id
            if config and 'gcp' in config and 'project_id' in config['gcp']:
                project_id = config['gcp']['project_id']
                logger.debug(f"Using project_id from config: {project_id}")
                return project_id
        except ConfigError as e:
            logger.error(f"Failed to load config: {e}")
            return None

        # No project ID found
        logger.error(
            "Project ID not found. Set GCP_PROJECT env var or configure project_id in config"
        )
        return None

    def fetch_secret(self, secret_name: str, project_id: str, quiet: bool = False) -> Optional[str]:
        """
        Fetch secret from GCP Secret Manager.

        Args:
            secret_name: Name of the secret
            project_id: GCP project ID
            quiet: If True, suppress warning logs (BLIND TESTING FIX #4)

        Returns:
            Secret value or None if fetch fails
        """
        try:
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            if not quiet:
                logger.warning(f"GCP fetch failed for {secret_name}: {e}")
            return None
