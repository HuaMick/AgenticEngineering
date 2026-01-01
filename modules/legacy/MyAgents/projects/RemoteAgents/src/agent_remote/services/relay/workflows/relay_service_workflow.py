"""RelayServiceWorkflow for CLI process management.

This workflow provides relay server lifecycle management functionality.
This is SEPARATE from RelayWorkflow (which handles session lifecycle).

This workflow manages:
- Starting/stopping the relay server process (uvicorn)
- Tracking server PID and status
- Querying server health and active sessions
- Graceful shutdown with session cleanup
"""

import os
import signal
import socket
import subprocess
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any


class RelayServiceWorkflow:
    """Workflow for managing relay server lifecycle.

    This workflow provides entrypoints for:
    - Starting relay server (uvicorn FastAPI)
    - Stopping relay server
    - Getting server status (URL, sessions, health)

    Each method orchestrates server process management.
    """

    def __init__(self, home_config_dir: Optional[Path] = None):
        """Initialize the RelayService workflow.

        Args:
            home_config_dir: Path to home config directory.
                           Defaults to ~/.config/myagents/
        """
        self.home_config_dir = home_config_dir or Path.home() / ".config" / "myagents"
        self.home_config_dir.mkdir(parents=True, exist_ok=True)

        # State file location
        self.state_file = self.home_config_dir / "relay.state"
        self.log_dir = self.home_config_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Default configuration
        self.default_host = "0.0.0.0"
        self.default_port = 8080
        self.max_log_files = 5  # Keep last N log files

    def start_relay(self, host: Optional[str] = None, port: Optional[int] = None,
                   background: bool = True) -> Tuple[bool, str]:
        """Start relay server.

        Args:
            host: Host to bind to (default: 0.0.0.0)
            port: Port to listen on (default: 8080)
            background: Run in background (default: True)

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Use defaults if not specified
        host = host or self.default_host
        port = port or self.default_port

        # Check if already running
        if self.is_running():
            status = self.get_status()
            return False, f"Relay server is already running on port {status['port']}"

        # Check if port is available
        if self._is_port_in_use(host, port):
            return False, f"Port {port} is already in use by another process"

        # Verify uvicorn is available
        if not self._verify_uvicorn():
            return False, "uvicorn must be installed (pip install uvicorn)"

        try:
            # Rotate logs before starting new instance
            self._rotate_logs()

            # Prepare log paths
            stdout_log = self.log_dir / "relay_stdout.log"
            stderr_log = self.log_dir / "relay_stderr.log"

            if background:
                # Start in background
                with open(stdout_log, 'a') as stdout_file, \
                     open(stderr_log, 'a') as stderr_file:
                    # Use uvicorn to run the relay server
                    # Configure for graceful shutdown within 10 seconds
                    process = subprocess.Popen(
                        [
                            "uvicorn",
                            "agent_remote.services.relay.api.server:app",
                            "--host", host,
                            "--port", str(port),
                            "--log-level", "info",
                            "--timeout-graceful-shutdown", "8"  # 8 second graceful shutdown timeout
                        ],
                        stdout=stdout_file,
                        stderr=stderr_file,
                        start_new_session=True  # Detach from parent
                    )

                    # Save state with ISO timestamp
                    self._save_state({
                        "pid": process.pid,
                        "host": host,
                        "port": port,
                        "started_at": datetime.utcnow().isoformat() + "Z",
                        "log_file": str(stderr_log)
                    })

                    # Wait for stability verification
                    time.sleep(3)

                    if self.is_running():
                        status = self.get_status()
                        ws_desktop_url = f"ws://{host}:{port}/ws/desktop/{{session_id}}"
                        ws_client_url = f"ws://{host}:{port}/ws/client/{{pairing_code}}"

                        return True, (
                            f"Relay server started successfully!\n"
                            f"PID: {process.pid}\n"
                            f"WebSocket URL: ws://{host}:{port}\n"
                            f"Desktop endpoint: {ws_desktop_url}\n"
                            f"Client endpoint: {ws_client_url}\n"
                            f"Active sessions: {status.get('active_sessions', 0)}"
                        )
                    else:
                        return False, "Relay server process started but is not responding"
            else:
                # Run in foreground (blocking)
                result = subprocess.run(
                    [
                        "uvicorn",
                        "agent_remote.services.relay.api.server:app",
                        "--host", host,
                        "--port", str(port),
                        "--log-level", "info",
                        "--timeout-graceful-shutdown", "8"  # 8 second graceful shutdown timeout
                    ]
                )
                return result.returncode == 0, "Relay server exited"

        except Exception as e:
            return False, f"Failed to start relay server: {e}"

    def stop_relay(self, force: bool = False) -> Tuple[bool, str]:
        """Stop relay server.

        Args:
            force: Force kill if graceful shutdown fails

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_running():
            # Clean up stale state file
            self.state_file.unlink(missing_ok=True)
            return False, "Relay server is not running"

        # Get state info before stopping (for session cleanup)
        state = self._load_state()
        if not state or "pid" not in state:
            return False, "Cannot find relay server process ID"

        pid = state["pid"]
        host = state.get("host", self.default_host)
        port = state.get("port", self.default_port)

        try:
            # Attempt graceful session cleanup by calling health endpoint
            # This signals the server to begin cleanup
            try:
                self._signal_shutdown(host, port)
                time.sleep(1)  # Give server time to signal active sessions
            except Exception:
                pass  # Non-fatal, proceed with shutdown

            # Try graceful shutdown with SIGTERM
            os.kill(pid, signal.SIGTERM)

            # Wait for process to exit (longer timeout for session cleanup)
            for _ in range(20):  # Wait up to 10 seconds for graceful shutdown
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)  # Check if still running
                except ProcessLookupError:
                    # Process is gone
                    self.state_file.unlink(missing_ok=True)
                    # Clean up old log files
                    self._cleanup_old_logs()
                    return True, f"Relay server stopped successfully (PID: {pid})"

            # Still running after graceful shutdown attempt
            if force:
                os.kill(pid, signal.SIGKILL)
                self.state_file.unlink(missing_ok=True)
                # Clean up old log files
                self._cleanup_old_logs()
                return True, f"Relay server force killed (PID: {pid})"
            else:
                return False, "Relay server did not stop gracefully. Use --force to force kill."

        except ProcessLookupError:
            # Process already gone
            self.state_file.unlink(missing_ok=True)
            return True, "Relay server process not found (already stopped)"
        except Exception as e:
            return False, f"Failed to stop relay server: {e}"

    def get_status(self) -> Dict[str, Any]:
        """Get current relay server status.

        Returns:
            Dict with status information including:
                - running: bool
                - port: int
                - host: str
                - ws_url: str (WebSocket base URL)
                - desktop_endpoint: str
                - client_endpoint: str
                - active_sessions: int
                - pid: int (if available)
                - healthy: bool
                - relay_info: dict (from get_relay_info)
        """
        running = self.is_running()
        state = self._load_state() or {}

        host = state.get("host", self.default_host)
        port = state.get("port", self.default_port)

        status = {
            "running": running,
            "host": host,
            "port": port,
            "ws_url": f"ws://{host}:{port}",
            "desktop_endpoint": f"/ws/desktop/{{session_id}}",
            "client_endpoint": f"/ws/client/{{pairing_code}}",
            "active_sessions": 0,
            "healthy": False,
        }

        if running and state:
            status["pid"] = state.get("pid")

            # Try to get health info from server
            health_info = self._get_health_info(host, port)
            if health_info:
                status["healthy"] = health_info.get("status") == "healthy"
                # Parse repository info for session count
                repo_str = health_info.get("repository", "")
                if "active=" in repo_str:
                    try:
                        # Extract active count from "InMemorySessionRepository(total=X, active=Y)"
                        active_part = repo_str.split("active=")[1].split(")")[0]
                        status["active_sessions"] = int(active_part)
                    except (IndexError, ValueError):
                        pass

        # Include relay information for connection setup
        status["relay_info"] = self.get_relay_info()

        return status

    def get_relay_info(self) -> Dict[str, Any]:
        """Get relay service information for connection setup.

        Returns relay server details including public URLs, WebSocket endpoints,
        and active session count. This information is needed for users to
        understand how to connect desktop and client endpoints.

        Returns:
            Dict with relay information including:
                - relay_url: str (HTTP URL for relay service)
                - websocket_endpoints: dict with desktop and client endpoint templates
                - active_sessions: int (count of active sessions)
                - health: str (HEALTHY, DEGRADED, or UNHEALTHY)

        Example:
            >>> workflow = RelayServiceWorkflow()
            >>> info = workflow.get_relay_info()
            >>> print(f"Relay URL: {info['relay_url']}")
            >>> print(f"Active Sessions: {info['active_sessions']}")
        """
        state = self._load_state() or {}
        running = self.is_running()

        # Get host and port from state or defaults
        host = state.get("host", self.default_host)
        port = state.get("port", self.default_port)

        # Construct relay URL
        relay_url = f"http://{host}:{port}"

        # Construct WebSocket endpoint templates
        websocket_endpoints = {
            "desktop": f"ws://{host}:{port}/ws/desktop/{{session_id}}",
            "client": f"ws://{host}:{port}/ws/client/{{pairing_code}}"
        }

        # Query active sessions and health
        active_sessions = 0
        health = "UNHEALTHY"

        if running:
            # Try to get health info from the relay server
            health_info = self._get_health_info(host, port)
            if health_info:
                # Server responded - at least DEGRADED
                health = "HEALTHY" if health_info.get("status") == "healthy" else "DEGRADED"

                # Extract active session count from repository info
                repo_str = health_info.get("repository", "")
                if "active=" in repo_str:
                    try:
                        # Extract active count from "InMemorySessionRepository(total=X, active=Y)"
                        active_part = repo_str.split("active=")[1].split(")")[0]
                        active_sessions = int(active_part)
                    except (IndexError, ValueError):
                        pass
            else:
                # Server not responding - DEGRADED if process is alive
                health = "DEGRADED"
        else:
            # Service not running
            health = "UNHEALTHY"

        return {
            "relay_url": relay_url,
            "websocket_endpoints": websocket_endpoints,
            "active_sessions": active_sessions,
            "health": health
        }

    @staticmethod
    def format_relay_info(info: Dict[str, Any]) -> str:
        """Format relay info as readable text for CLI output.

        Args:
            info: Relay info dict from get_relay_info()

        Returns:
            Formatted multi-line string for display

        Example:
            >>> workflow = RelayServiceWorkflow()
            >>> info = workflow.get_relay_info()
            >>> print(RelayServiceWorkflow.format_relay_info(info))
        """
        lines = []
        lines.append("Relay Service Information:")
        lines.append("-" * 50)

        # Health status with indicator
        health = info.get("health", "UNKNOWN")
        health_symbol = {
            "HEALTHY": "[OK]",
            "DEGRADED": "[WARN]",
            "UNHEALTHY": "[DOWN]",
            "UNKNOWN": "[?]"
        }.get(health, "[?]")

        lines.append(f"Health: {health_symbol} {health}")

        # Active sessions
        active_sessions = info.get("active_sessions", 0)
        lines.append(f"Active Sessions: {active_sessions}")

        # Relay URL
        relay_url = info.get("relay_url", "N/A")
        lines.append(f"Relay URL: {relay_url}")

        # WebSocket endpoints
        lines.append("")
        lines.append("WebSocket Endpoints:")
        endpoints = info.get("websocket_endpoints", {})
        if endpoints:
            for endpoint_type, url in endpoints.items():
                lines.append(f"  {endpoint_type.capitalize()}: {url}")
        else:
            lines.append("  (no endpoints available)")

        return "\n".join(lines)

    def is_running(self) -> bool:
        """Check if relay server is currently running.

        Returns:
            True if server is running, False otherwise
        """
        # Method 1: Check state file
        state = self._load_state()
        if state and "pid" in state:
            try:
                pid = state["pid"]
                os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
                return True
            except (ProcessLookupError, OSError):
                # State file exists but process doesn't - clean up stale file
                self.state_file.unlink(missing_ok=True)
                return False

        return False

    def _is_port_in_use(self, host: str, port: int) -> bool:
        """Check if the specified port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.settimeout(0.1)
                s.connect((host, port))
                return True
            except (socket.timeout, ConnectionRefusedError, OSError):
                return False

    def _verify_uvicorn(self) -> bool:
        """Verify uvicorn is available.

        Returns:
            bool: True if uvicorn can be imported
        """
        try:
            import uvicorn
            return True
        except ImportError:
            return False

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Save relay server state to file.

        Args:
            state: Dict containing pid, host, port
        """
        import json

        try:
            self.state_file.write_text(json.dumps(state))
        except Exception:
            # Non-fatal - state file is for convenience
            pass

    def _load_state(self) -> Optional[Dict[str, Any]]:
        """Load relay server state from file.

        Returns:
            Dict with state or None if file doesn't exist
        """
        import json

        if not self.state_file.exists():
            return None

        try:
            return json.loads(self.state_file.read_text())
        except Exception:
            return None

    def _get_health_info(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """Query relay server health endpoint.

        Args:
            host: Server host
            port: Server port

        Returns:
            Dict with health info or None if request fails
        """
        try:
            response = requests.get(
                f"http://{host}:{port}/health",
                timeout=2
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    def get_recent_errors(self, num_lines: int = 20) -> Optional[str]:
        """Get recent error messages from relay server logs.

        Args:
            num_lines: Number of recent lines to retrieve (default: 20)

        Returns:
            String containing recent error lines, or None if log doesn't exist
        """
        stderr_log = self.log_dir / "relay_stderr.log"

        if not stderr_log.exists():
            return None

        try:
            with open(stderr_log, 'r') as f:
                lines = f.readlines()
                if not lines:
                    return None
                # Get last num_lines
                recent_lines = lines[-num_lines:]
                return ''.join(recent_lines)
        except Exception:
            return None

    def _signal_shutdown(self, host: str, port: int) -> None:
        """Signal the server to begin graceful shutdown process.

        This allows the server to notify active sessions that it's shutting down.

        Args:
            host: Server host
            port: Server port
        """
        try:
            # Call health endpoint as a signal (server can detect this pattern)
            requests.get(
                f"http://{host}:{port}/health",
                timeout=1,
                headers={"X-Shutdown-Signal": "true"}
            )
        except Exception:
            pass  # Non-fatal

    def _rotate_logs(self) -> None:
        """Rotate log files before starting new service instance.

        Renames current logs to timestamped versions and keeps only last N files.
        """
        stdout_log = self.log_dir / "relay_stdout.log"
        stderr_log = self.log_dir / "relay_stderr.log"

        # Rotate stdout log
        if stdout_log.exists() and stdout_log.stat().st_size > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_path = self.log_dir / f"relay_stdout.{timestamp}.log"
            try:
                stdout_log.rename(rotated_path)
            except Exception:
                pass  # Non-fatal

        # Rotate stderr log
        if stderr_log.exists() and stderr_log.stat().st_size > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_path = self.log_dir / f"relay_stderr.{timestamp}.log"
            try:
                stderr_log.rename(rotated_path)
            except Exception:
                pass  # Non-fatal

        # Clean up old rotated logs
        self._cleanup_old_logs()

    def _cleanup_old_logs(self) -> None:
        """Keep only the last N log files, remove older ones.

        Keeps last N stdout and last N stderr log files.
        """
        try:
            # Clean up stdout logs
            stdout_logs = sorted(
                self.log_dir.glob("relay_stdout.*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            for old_log in stdout_logs[self.max_log_files:]:
                try:
                    old_log.unlink()
                except Exception:
                    pass  # Non-fatal

            # Clean up stderr logs
            stderr_logs = sorted(
                self.log_dir.glob("relay_stderr.*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            for old_log in stderr_logs[self.max_log_files:]:
                try:
                    old_log.unlink()
                except Exception:
                    pass  # Non-fatal
        except Exception:
            pass  # Non-fatal, don't let log cleanup break the service
