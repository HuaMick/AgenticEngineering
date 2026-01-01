"""Remote Terminal workflow for MyAgents.

This workflow provides Remote Terminal service lifecycle management functionality.
It manages PTY sessions running on the desktop and accessible via WebSocket.

This module provides a class-based workflow interface following the Studio pattern.
"""

import os
import signal
import socket
import subprocess
import sys
import time
import json
import string
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Literal


class RemoteWorkflow:
    """Workflow for managing Remote Terminal service lifecycle.

    This workflow provides multiple entrypoints for:
    - Starting Remote Terminal service
    - Stopping Remote Terminal service
    - Getting service status and connection info
    - Managing service health

    Each method orchestrates process management and state tracking.
    """

    def __init__(self, home_config_dir: Optional[Path] = None):
        """Initialize the Remote Terminal workflow.

        Args:
            home_config_dir: Path to home config directory.
                           Defaults to ~/.config/myagents/
        """
        self.home_config_dir = home_config_dir or Path.home() / ".config" / "myagents"
        self.state_file = self.home_config_dir / "remote.state"
        self.log_dir = self.home_config_dir / "logs"

        # Default configuration
        self.default_port = 8080
        self.default_relay_url = "ws://localhost:8080"
        self.max_log_files = 5  # Keep last N log files

        # Ensure directories exist
        self.home_config_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def start_service(
        self,
        port: Optional[int] = None,
        relay_url: Optional[str] = None,
        background: bool = True
    ) -> Tuple[bool, str]:
        """Start Remote Terminal service.

        Args:
            port: Port for terminal service (default: 8080)
            relay_url: WebSocket relay URL (default: ws://localhost:8080)
            background: Run in background (default: True)

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Check if already running
        if self.is_running():
            status = self.get_status()
            return False, f"Remote Terminal service is already running (PID: {status.get('pid', 'unknown')})"

        # Use defaults if not specified
        port = port or self.default_port
        relay_url = relay_url or self.default_relay_url

        # Check if port is available
        if self._is_port_in_use(port):
            return False, f"Port {port} is already in use by another process"

        try:
            # Prepare command to start the terminal service
            # This should launch the FastAPI server for terminal service
            command = [
                sys.executable,
                "-m",
                "agent_remote.services.terminal.api.server"
            ]

            # Prepare environment
            env = os.environ.copy()
            env["TERMINAL_HOST"] = "0.0.0.0"
            env["TERMINAL_PORT"] = str(port)

            if background:
                # Rotate logs before starting new instance
                self._rotate_logs()

                # Start in background
                stdout_log = self.log_dir / "remote_stdout.log"
                stderr_log = self.log_dir / "remote_stderr.log"

                with open(stdout_log, 'a') as stdout_file, \
                     open(stderr_log, 'a') as stderr_file:
                    process = subprocess.Popen(
                        command,
                        env=env,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        start_new_session=True  # Detach from parent
                    )

                    # Save state with ISO timestamp
                    state = {
                        "pid": process.pid,
                        "port": port,
                        "host": "0.0.0.0",
                        "relay_url": relay_url,
                        "started_at": datetime.utcnow().isoformat() + "Z",
                        "log_file": str(stderr_log)
                    }
                    self._save_state(state)

                    # Wait for service to start
                    time.sleep(3)

                    # Verify it's running
                    if self.is_running():
                        status = self.get_status()
                        return True, (
                            f"Remote Terminal service started successfully!\n"
                            f"PID: {process.pid}\n"
                            f"WebSocket URL: ws://0.0.0.0:{port}\n"
                            f"Session ID: (connect to create session)"
                        )
                    else:
                        # Check logs for errors
                        recent_errors = self.get_recent_errors()
                        error_msg = "Service process started but is not responding"
                        if recent_errors:
                            error_msg += f"\n\nRecent errors:\n{recent_errors}"
                        return False, error_msg
            else:
                # Run in foreground (blocking)
                result = subprocess.run(command, env=env)
                return result.returncode == 0, "Service exited"

        except Exception as e:
            return False, f"Failed to start Remote Terminal service: {e}"

    def stop_service(self, force: bool = False) -> Tuple[bool, str]:
        """Stop Remote Terminal service.

        Args:
            force: Force kill if graceful shutdown fails

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_running():
            # Clean up stale state file
            if self.state_file.exists():
                self.state_file.unlink()
            return False, "Remote Terminal service is not running"

        # Get PID from state file
        state = self._load_state()
        if not state or "pid" not in state:
            return False, "Cannot find service process ID"

        pid = state["pid"]

        try:
            # Try graceful shutdown first
            os.kill(pid, signal.SIGTERM)

            # Wait for process to exit
            for _ in range(10):  # Wait up to 5 seconds
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)  # Check if still running
                except ProcessLookupError:
                    # Process is gone
                    if self.state_file.exists():
                        self.state_file.unlink()
                    # Clean up old log files
                    self._cleanup_old_logs()
                    return True, f"Remote Terminal service stopped successfully (PID: {pid})"

            # Still running after graceful shutdown attempt
            if force:
                os.kill(pid, signal.SIGKILL)
                if self.state_file.exists():
                    self.state_file.unlink()
                # Clean up old log files
                self._cleanup_old_logs()
                return True, f"Remote Terminal service force killed (PID: {pid})"
            else:
                return False, "Service did not stop gracefully. Use --force to force kill."

        except ProcessLookupError:
            # Process already gone
            if self.state_file.exists():
                self.state_file.unlink()
            return True, "Service process not found (already stopped)"
        except Exception as e:
            return False, f"Failed to stop service: {e}"

    def get_status(self) -> Dict[str, Any]:
        """Get current Remote Terminal service status.

        Returns:
            Dict with status information including:
                - running: bool
                - pid: int (if available)
                - port: int
                - websocket_url: str
                - uptime: str (if running)
                - connection_info: dict (from get_connection_info)
        """
        running = self.is_running()
        state = self._load_state() or {}

        status = {
            "running": running,
            "port": state.get("port", self.default_port),
        }

        if running:
            status["pid"] = state.get("pid")
            status["websocket_url"] = f"ws://0.0.0.0:{status['port']}"

            # Calculate uptime
            if "started_at" in state:
                try:
                    # Handle both ISO format and Unix timestamp for backward compatibility
                    started_at = state["started_at"]
                    if isinstance(started_at, str):
                        # Parse ISO format
                        started_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                        uptime_seconds = int((datetime.utcnow() - started_dt.replace(tzinfo=None)).total_seconds())
                    else:
                        # Legacy Unix timestamp
                        uptime_seconds = int(time.time() - started_at)
                    status["uptime"] = self._format_uptime(uptime_seconds)
                except Exception:
                    # If uptime calculation fails, just skip it
                    pass

            # Include connection information for pairing
            status["connection_info"] = self.get_connection_info()
        else:
            status["websocket_url"] = None
            status["connection_info"] = self.get_connection_info()

        return status

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for pairing desktop with web client.

        Returns connection details including session ID, pairing code,
        WebSocket URLs, and connection status. This information is needed
        for users to pair their desktop terminal with web clients.

        Returns:
            Dict with connection information including:
                - session_id: str (UUID if session exists, None otherwise)
                - pairing_code: str (6-char alphanumeric code)
                - websocket_url: str (WebSocket URL for desktop connection)
                - relay_url: str (HTTP URL for relay service)
                - status: str (CONNECTED, WAITING, or DISCONNECTED)

        Example:
            >>> workflow = RemoteWorkflow()
            >>> info = workflow.get_connection_info()
            >>> print(f"Pairing Code: {info['pairing_code']}")
            >>> print(f"WebSocket URL: {info['websocket_url']}")
        """
        state = self._load_state() or {}
        running = self.is_running()

        # Get port from state or use default
        port = state.get("port", self.default_port)
        host = state.get("host", "0.0.0.0")

        # Generate or retrieve session ID
        # For RemoteWorkflow, session_id is created when desktop connects to relay
        # At this level, we don't have a session yet, so we show placeholder
        session_id = state.get("session_id", None)

        # Generate a pairing code (6-char alphanumeric uppercase)
        # In practice, this would come from the relay service after session creation
        # For now, we generate one for display purposes
        pairing_code = state.get("pairing_code", None)
        if pairing_code is None and running:
            # Generate a new pairing code
            pairing_code = self._generate_pairing_code()
            # Save it to state for consistency
            state["pairing_code"] = pairing_code
            self._save_state(state)

        # Construct WebSocket URL
        websocket_url = f"ws://{host}:{port}/ws/desktop"
        if session_id:
            websocket_url += f"/{session_id}"

        # Construct relay URL
        relay_url = f"http://{host}:{port}"

        # Determine connection status
        if not running:
            status = "DISCONNECTED"
        elif session_id:
            status = "CONNECTED"
        else:
            status = "WAITING"

        return {
            "session_id": session_id,
            "pairing_code": pairing_code,
            "websocket_url": websocket_url,
            "relay_url": relay_url,
            "status": status
        }

    @staticmethod
    def format_pairing_code(code: str) -> str:
        """Format pairing code with separator for readability.

        Args:
            code: 6-character pairing code (e.g., "ABC123")

        Returns:
            Formatted code with separator (e.g., "ABC-123")

        Example:
            >>> formatted = RemoteWorkflow.format_pairing_code("ABC123")
            >>> print(formatted)  # "ABC-123"
        """
        if len(code) == 6:
            return f"{code[:3]}-{code[3:]}"
        return code

    @staticmethod
    def format_connection_info(info: Dict[str, Any]) -> str:
        """Format connection info as readable text for CLI output.

        Args:
            info: Connection info dict from get_connection_info()

        Returns:
            Formatted multi-line string for display

        Example:
            >>> workflow = RemoteWorkflow()
            >>> info = workflow.get_connection_info()
            >>> print(RemoteWorkflow.format_connection_info(info))
        """
        lines = []
        lines.append("Connection Information:")
        lines.append("-" * 50)

        # Status indicator
        status = info.get("status", "UNKNOWN")
        status_symbol = {
            "CONNECTED": "[ACTIVE]",
            "WAITING": "[PENDING]",
            "DISCONNECTED": "[OFFLINE]",
            "UNKNOWN": "[UNKNOWN]"
        }.get(status, "[UNKNOWN]")

        lines.append(f"Status: {status_symbol} {status}")

        # Pairing code (formatted)
        pairing_code = info.get("pairing_code")
        if pairing_code:
            formatted_code = RemoteWorkflow.format_pairing_code(pairing_code)
            lines.append(f"Pairing Code: {formatted_code}")
        else:
            lines.append("Pairing Code: (start service to generate)")

        # Session ID
        session_id = info.get("session_id")
        if session_id:
            lines.append(f"Session ID: {session_id}")
        else:
            lines.append("Session ID: (connect to create session)")

        # URLs
        lines.append(f"Relay URL: {info.get('relay_url', 'N/A')}")
        lines.append(f"WebSocket URL: {info.get('websocket_url', 'N/A')}")

        return "\n".join(lines)

    def _generate_pairing_code(self) -> str:
        """Generate a secure 6-character alphanumeric pairing code.

        Returns:
            6-character uppercase alphanumeric string (e.g., "A1B2C3")

        Example:
            >>> code = workflow._generate_pairing_code()
            >>> len(code)
            6
            >>> code.isupper()
            True
            >>> code.isalnum()
            True
        """
        # Use uppercase letters and digits (36 characters total)
        alphabet = string.ascii_uppercase + string.digits
        # Generate 6 random characters
        return ''.join(secrets.choice(alphabet) for _ in range(6))

    def is_running(self) -> bool:
        """Check if Remote Terminal service is currently running.

        Returns:
            True if service is running, False otherwise
        """
        # Method 1: Check state file
        state = self._load_state()
        if state and "pid" in state:
            try:
                pid = state["pid"]
                # Check if process with this PID exists
                os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
                return True
            except (ProcessLookupError, ValueError, OSError):
                # State file exists but process doesn't - clean up
                if self.state_file.exists():
                    self.state_file.unlink()

        # Method 2: Check if port is in use
        if state and "port" in state:
            return self._is_port_in_use(state["port"])

        return False

    def _is_port_in_use(self, port: int) -> bool:
        """Check if the service port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.settimeout(0.1)
                s.connect(("127.0.0.1", port))
                return True
            except (socket.timeout, ConnectionRefusedError, OSError):
                return False

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Save service state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save state: {e}")

    def _load_state(self) -> Optional[Dict[str, Any]]:
        """Load service state from file."""
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def get_recent_errors(self, num_lines: int = 20) -> Optional[str]:
        """Get recent error messages from stderr log.

        Args:
            num_lines: Number of recent lines to retrieve (default: 20)

        Returns:
            String containing recent error lines, or None if log doesn't exist
        """
        stderr_log = self.log_dir / "remote_stderr.log"

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

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime in human-readable format.

        Args:
            seconds: Uptime in seconds

        Returns:
            Formatted uptime string (e.g., "2h 15m")
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def _rotate_logs(self) -> None:
        """Rotate log files before starting new service instance.

        Renames current logs to timestamped versions and keeps only last N files.
        """
        stdout_log = self.log_dir / "remote_stdout.log"
        stderr_log = self.log_dir / "remote_stderr.log"

        # Rotate stdout log
        if stdout_log.exists() and stdout_log.stat().st_size > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_path = self.log_dir / f"remote_stdout.{timestamp}.log"
            try:
                stdout_log.rename(rotated_path)
            except Exception:
                pass  # Non-fatal

        # Rotate stderr log
        if stderr_log.exists() and stderr_log.stat().st_size > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_path = self.log_dir / f"remote_stderr.{timestamp}.log"
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
                self.log_dir.glob("remote_stdout.*.log"),
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
                self.log_dir.glob("remote_stderr.*.log"),
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
