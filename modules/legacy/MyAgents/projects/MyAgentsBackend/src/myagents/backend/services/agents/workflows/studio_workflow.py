"""Studio workflow for MyAgents.

This workflow provides LangGraph Studio lifecycle management functionality.
Moved from myagents.backend/services/studio to follow the centralized workflow pattern.

This module provides both a class-based workflow interface and backward-compatible
function-based entrypoints.
"""

from pathlib import Path
from typing import Optional, Tuple, Dict, Any


class StudioWorkflow:
    """Workflow for managing LangGraph Studio lifecycle.

    This workflow provides multiple entrypoints for:
    - Starting Studio service
    - Stopping Studio
    - Restarting Studio
    - Getting Studio status
    - Checking Studio health
    - Recovering Studio state

    Each method orchestrates domain logic from StudioManager.
    """

    def __init__(self, home_config_dir: Optional[Path] = None, config_path: Optional[Path] = None):
        """Initialize the Studio workflow.

        Args:
            home_config_dir: Path to home config directory (where langgraph.json is).
                           Defaults to ~/.config/myagents/
            config_path: Optional path to config.yml (defaults to ~/.config/myagents/config.yml)
        """
        self.home_config_dir = home_config_dir
        self.config_path = config_path

    def start_studio(
        self,
        config: Optional[Dict[str, Any]] = None,
        background: bool = True,
        port: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Start Studio service.

        Args:
            config: Optional configuration overrides (currently unused, for future extensibility)
            background: Run in background (default: True)
            port: Override port for Studio server (default: None uses config port)

        Returns:
            Tuple of (success: bool, message: str)
        """
        from myagents.backend.services.studio.domains.studio_manager.manager import StudioManager

        manager = StudioManager(
            home_config_dir=self.home_config_dir,
            config_path=self.config_path
        )
        return manager.start(background=background, port=port)

    def stop_studio(self, force: bool = False) -> Tuple[bool, str]:
        """Stop Studio.

        Args:
            force: Force kill if graceful shutdown fails

        Returns:
            Tuple of (success: bool, message: str)
        """
        from myagents.backend.services.studio.domains.studio_manager.manager import StudioManager

        manager = StudioManager(
            home_config_dir=self.home_config_dir,
            config_path=self.config_path
        )
        return manager.stop(force=force)

    def restart_studio(self, config: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """Restart Studio.

        Args:
            config: Optional configuration overrides (currently unused, for future extensibility)

        Returns:
            Tuple of (success: bool, message: str)
        """
        from myagents.backend.services.studio.domains.studio_manager.manager import StudioManager

        manager = StudioManager(
            home_config_dir=self.home_config_dir,
            config_path=self.config_path
        )
        return manager.restart()

    def get_studio_status(self) -> Dict[str, Any]:
        """Get current Studio status.

        Returns:
            Dict with status information including:
                - running: bool
                - port: int
                - host: str
                - url: str (WebUI URL)
                - api_url: str
                - pid: int (if available)
        """
        from myagents.backend.services.studio.domains.studio_manager.manager import StudioManager

        manager = StudioManager(
            home_config_dir=self.home_config_dir,
            config_path=self.config_path
        )
        return manager.get_status()

    def check_studio_health(self) -> Dict[str, Any]:
        """Verify Studio is responding and healthy.

        Returns:
            Dict with health check results:
                - healthy: bool
                - running: bool
                - responding: bool
                - port: int
                - error: str (if not healthy)
        """
        from myagents.backend.services.studio.domains.studio_manager.manager import StudioManager

        manager = StudioManager(
            home_config_dir=self.home_config_dir,
            config_path=self.config_path
        )

        status = manager.get_status()
        is_running = status["running"]

        # For now, "healthy" means "running"
        # Future enhancement: Could add HTTP health check to verify API responding
        return {
            "healthy": is_running,
            "running": is_running,
            "responding": is_running,
            "port": status["port"]
        }

    def recover_studio_state(self) -> Tuple[bool, str]:
        """Recover from inconsistent state.

        This handles scenarios like:
        - PID file exists but process is dead
        - Port is in use but PID file is missing
        - Stale processes need cleanup

        Returns:
            Tuple of (success: bool, message: str)
        """
        from myagents.backend.services.studio.domains.studio_manager.manager import StudioManager

        manager = StudioManager(
            home_config_dir=self.home_config_dir,
            config_path=self.config_path
        )

        # The is_running() method already handles state recovery:
        # - Cleans up stale PID files
        # - Recreates missing PID files for running processes
        is_running = manager.is_running()

        if is_running:
            status = manager.get_status()
            return True, (
                f"Studio state recovered successfully. "
                f"Running on port {status['port']} (PID: {status.get('pid', 'unknown')})"
            )
        else:
            return True, "Studio not running. State is clean."

    def get_recent_errors(self, num_lines: int = 20) -> Optional[str]:
        """Get recent error messages from Studio logs.

        Args:
            num_lines: Number of recent lines to retrieve (default: 20)

        Returns:
            String containing recent error lines, or None if log doesn't exist
        """
        from myagents.backend.services.studio.domains.studio_manager.manager import StudioManager

        manager = StudioManager(
            home_config_dir=self.home_config_dir,
            config_path=self.config_path
        )
        return manager.get_recent_errors(num_lines=num_lines)


# Backward-compatible function-based API
# These functions maintain the existing API for current CLI commands


def start_studio(
    home_config_dir: Optional[Path] = None,
    config_path: Optional[Path] = None,
    background: bool = True,
    port: Optional[int] = None
) -> Tuple[bool, str]:
    """Workflow function for starting LangGraph Studio.

    This is a backward-compatible wrapper around StudioWorkflow.start_studio().

    Args:
        home_config_dir: Path to home config directory. Defaults to ~/.config/myagents/
        config_path: Optional path to config.yml
        background: Run in background (default: True)
        port: Override port for Studio server (default: None uses config port)

    Returns:
        Tuple of (success: bool, message: str)
    """
    workflow = StudioWorkflow(home_config_dir=home_config_dir, config_path=config_path)
    return workflow.start_studio(background=background, port=port)


def stop_studio(
    home_config_dir: Optional[Path] = None,
    config_path: Optional[Path] = None,
    force: bool = False
) -> Tuple[bool, str]:
    """Workflow function for stopping LangGraph Studio.

    This is a backward-compatible wrapper around StudioWorkflow.stop_studio().

    Args:
        home_config_dir: Path to home config directory. Defaults to ~/.config/myagents/
        config_path: Optional path to config.yml
        force: Force kill if graceful shutdown fails

    Returns:
        Tuple of (success: bool, message: str)
    """
    workflow = StudioWorkflow(home_config_dir=home_config_dir, config_path=config_path)
    return workflow.stop_studio(force=force)


def restart_studio(
    home_config_dir: Optional[Path] = None,
    config_path: Optional[Path] = None
) -> Tuple[bool, str]:
    """Workflow function for restarting LangGraph Studio.

    This is a backward-compatible wrapper around StudioWorkflow.restart_studio().

    Args:
        home_config_dir: Path to home config directory. Defaults to ~/.config/myagents/
        config_path: Optional path to config.yml

    Returns:
        Tuple of (success: bool, message: str)
    """
    workflow = StudioWorkflow(home_config_dir=home_config_dir, config_path=config_path)
    return workflow.restart_studio()


def get_studio_status(
    home_config_dir: Optional[Path] = None,
    config_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Workflow function for getting LangGraph Studio status.

    This is a backward-compatible wrapper around StudioWorkflow.get_studio_status().

    Args:
        home_config_dir: Path to home config directory. Defaults to ~/.config/myagents/
        config_path: Optional path to config.yml

    Returns:
        Dict with status information
    """
    workflow = StudioWorkflow(home_config_dir=home_config_dir, config_path=config_path)
    return workflow.get_studio_status()


def get_studio_recent_errors(
    home_config_dir: Optional[Path] = None,
    config_path: Optional[Path] = None,
    num_lines: int = 20
) -> Optional[str]:
    """Workflow function for retrieving recent Studio error messages.

    This is a backward-compatible wrapper around StudioWorkflow.get_recent_errors().

    Args:
        home_config_dir: Path to home config directory. Defaults to ~/.config/myagents/
        config_path: Optional path to config.yml
        num_lines: Number of recent lines to retrieve (default: 20)

    Returns:
        String containing recent error lines, or None if log doesn't exist
    """
    workflow = StudioWorkflow(home_config_dir=home_config_dir, config_path=config_path)
    return workflow.get_recent_errors(num_lines=num_lines)
