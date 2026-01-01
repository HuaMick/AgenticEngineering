"""Studio service configuration loader."""

from pathlib import Path
from typing import TypedDict, Optional

import yaml  # type: ignore[import-untyped]


class ServerConfig(TypedDict):
    """Server configuration section."""
    host: str
    port: int
    allow_blocking: bool


class RuntimeConfig(TypedDict):
    """Runtime configuration section."""
    pid_file: str
    log_dir: str
    checkpoint_dir: str


class LangGraphConfig(TypedDict):
    """LangGraph configuration section."""
    project_name: str


class StudioConfig(TypedDict):
    """Complete studio configuration."""
    server: ServerConfig
    runtime: RuntimeConfig
    langgraph: LangGraphConfig


def load_config(config_path: Optional[Path] = None) -> StudioConfig:
    """Load studio configuration from YAML file.

    Handles config files and routing config files that contain a 'config_path'
    field pointing to the actual config.

    Args:
        config_path: Path to config file. If None, uses home directory config at
                    ~/.config/myagents/config.yml as the single source of truth.

    Returns:
        Typed dictionary with server, runtime, and langgraph sections

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
        KeyError: If required 'server' section is missing
    """
    if config_path is None:
        # Use home directory config as single source of truth
        home_config_dir = Path.home() / ".config" / "myagents"
        config_path = home_config_dir / "config.yml"

        # If not found, raise clear error directing to setup
        if not config_path.exists():
            raise FileNotFoundError(
                f"Studio config not found at: {config_path}\n"
                f"Please run 'myagents setup' to create the configuration."
            )

    if not config_path.exists():
        raise FileNotFoundError(f"Studio config not found at: {config_path}")

    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)

    # Handle routing config files that contain only a 'config_path' field
    # These files are used in ~/.config/myagents/config.yml to route to the actual config
    if config_data and 'config_path' in config_data and 'server' not in config_data:
        # This is a routing config - follow the config_path to the actual config
        routed_path = Path(config_data['config_path']).expanduser().resolve()
        if not routed_path.exists():
            raise FileNotFoundError(f"Routed config not found at: {routed_path}")

        with open(routed_path, 'r') as f:
            config_data = yaml.safe_load(f)

    # Verify the config has the required 'server' section
    if not config_data or 'server' not in config_data:
        raise KeyError(
            f"Config file '{config_path}' is missing required 'server' section. "
            f"Expected sections: server, runtime, langgraph"
        )

    return config_data
