"""Configuration loader for Agent-GCPtoolkit."""
import os
import logging
from pathlib import Path
from typing import Dict, Any
import yaml  # type: ignore[import-untyped]

from .preferences import get_preference

logger = logging.getLogger(__name__)


def _get_config_path() -> str:
    """
    Get config file path using XDG Base Directory standard.

    Priority order:
    1. User preference (stored in ~/.config/agent-gcptoolkit/preferences.json)
    2. Default location: ~/.config/agent-gcptoolkit/config.yml

    Returns:
        Absolute path to config file

    Raises:
        FileNotFoundError: If config file doesn't exist in any location
    """
    # 1. Check user preference
    config_path_pref = get_preference("config_path")
    if config_path_pref:
        config_path = Path(config_path_pref)
        if config_path.exists():
            logger.info(f"Using config from preference: {config_path}")
            return str(config_path)
        else:
            logger.warning(f"Config path from preference doesn't exist: {config_path}")

    # 2. Check default location
    default_config = Path.home() / ".config" / "agent-gcptoolkit" / "config.yml"
    if default_config.exists():
        logger.info(f"Using default config location: {default_config}")
        return str(default_config)

    # Config not found - raise clear error with setup instructions
    raise FileNotFoundError(
        "Configuration file not found. Please set up your config file using one of these methods:\n\n"
        "1. Use the default location:\n"
        f"   mkdir -p {default_config.parent}\n"
        f"   cp /path/to/your/config.yml {default_config}\n\n"
        "2. Point to an existing config file:\n"
        "   myagents config set-path /path/to/your/config.yml\n\n"
        "3. Run interactive setup:\n"
        "   myagents config init\n"
    )


class ConfigError(Exception):
    """Configuration error exception."""
    pass


def load_config() -> Dict[str, Any]:
    """
    Load and validate configuration from YAML file.

    Returns:
        Dict containing configuration with keys:
        - authentication: dict with type and service_account_path
        - gcp: dict with project_id

    Raises:
        ConfigError: If config file is missing, invalid, or service account file doesn't exist
    """
    # Get config path dynamically each time (not cached at module level)
    config_path = _get_config_path()

    # Check if config file exists
    if not os.path.exists(config_path):
        raise ConfigError(
            f"Configuration file not found at: {config_path}\n"
            f"Please create the config file with required authentication settings."
        )

    # Load YAML
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML config at {config_path}: {e}")
    except Exception as e:
        raise ConfigError(f"Failed to read config file at {config_path}: {e}")

    # Validate required fields
    if not config:
        raise ConfigError(f"Config file at {config_path} is empty")

    if 'authentication' not in config:
        raise ConfigError(
            f"Missing 'authentication' section in config at {config_path}\n"
            f"Required format:\n"
            f"authentication:\n"
            f"  type: service_account\n"
            f"  service_account_path: /path/to/service-account.json"
        )

    auth = config['authentication']

    if 'type' not in auth:
        raise ConfigError("Missing 'authentication.type' in config")

    if auth['type'] != 'service_account':
        raise ConfigError(
            f"Unsupported authentication type: {auth['type']}\n"
            f"Only 'service_account' is supported."
        )

    if 'service_account_path' not in auth:
        raise ConfigError(
            "Missing 'authentication.service_account_path' in config\n"
            "Please specify the absolute path to your service account JSON file."
        )

    service_account_path = auth['service_account_path']

    # Validate service account file exists
    if not os.path.exists(service_account_path):
        raise ConfigError(
            f"Service account file not found at: {service_account_path}\n"
            f"Please ensure the file exists or update the path in {config_path}"
        )

    if not os.path.isfile(service_account_path):
        raise ConfigError(
            f"Service account path is not a file: {service_account_path}"
        )

    # Validate GCP section
    if 'gcp' not in config:
        raise ConfigError(
            f"Missing 'gcp' section in config at {config_path}\n"
            f"Required format:\n"
            f"gcp:\n"
            f"  project_id: your-project-id"
        )

    if 'project_id' not in config['gcp']:
        raise ConfigError("Missing 'gcp.project_id' in config")

    logger.info(f"Configuration loaded successfully from {config_path}")
    logger.debug(f"Using service account: {service_account_path}")
    logger.debug(f"Using project ID: {config['gcp']['project_id']}")

    return config
