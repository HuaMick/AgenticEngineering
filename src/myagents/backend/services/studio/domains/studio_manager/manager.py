#!/usr/bin/env python3
"""LangGraph Studio management module for MyAgents."""

import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

from myagents.backend.services.studio.config import StudioConfig, load_config


class StudioManager:
    """Manages LangGraph Studio lifecycle and status."""

    def __init__(
        self,
        home_config_dir: Optional[Path] = None,
        config_path: Optional[Path] = None
    ):
        """Initialize Studio manager.

        Args:
            home_config_dir: Path to home config directory (where langgraph.json is located).
                           Defaults to ~/.config/myagents/
            config_path: Optional path to config.yml (defaults to ~/.config/myagents/config.yml)
        """
        self.home_config_dir = home_config_dir or Path.home() / ".config" / "myagents"
        self.config: StudioConfig = load_config(config_path)

        # Extract config values
        self.port = self.config["server"]["port"]
        self.host = self.config["server"]["host"]
        # Expand ~ in paths to handle both absolute paths and legacy ~ paths
        self.pid_file = Path(self.config["runtime"]["pid_file"]).expanduser()

    def is_running(self) -> bool:
        """Check if Studio is currently running.

        Returns:
            True if Studio is running, False otherwise
        """
        # Method 1: Check PID file
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text().strip())
                # Check if process with this PID exists
                os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
                return True
            except (ProcessLookupError, ValueError, OSError):
                # PID file exists but process doesn't - clean up stale PID file
                self.pid_file.unlink(missing_ok=True)

        # Method 2: Check if port is in use
        port_in_use = self._is_port_in_use()

        # If port is in use but PID file is missing, try to recover PID file
        if port_in_use and not self.pid_file.exists():
            recovered_pid = self._find_process_by_port()
            if recovered_pid:
                try:
                    # Recreate PID file for process management
                    self.pid_file.parent.mkdir(parents=True, exist_ok=True)
                    self.pid_file.write_text(str(recovered_pid))
                except (OSError, IOError):
                    # If we can't write PID file, still report running status
                    pass

        return port_in_use

    def _is_port_in_use(self) -> bool:
        """Check if the Studio port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.settimeout(0.1)
                s.connect((self.host, self.port))
                return True
            except (socket.timeout, ConnectionRefusedError, OSError):
                return False

    def _find_process_by_port(self) -> Optional[int]:
        """Find process ID listening on Studio port.

        Returns:
            Process ID if found, None otherwise
        """
        try:
            # Use lsof to find process listening on the port
            result = subprocess.run(
                ["lsof", "-ti", f":{self.port}"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                # lsof returns PIDs, one per line - take the first one
                pid_str = result.stdout.strip().split('\n')[0]
                return int(pid_str)
        except (ValueError, FileNotFoundError, subprocess.SubprocessError):
            pass
        return None

    def get_status(self) -> dict:
        """Get detailed status of Studio.

        Returns:
            Dict with status information
        """
        running = self.is_running()
        status = {
            "running": running,
            "port": self.port,
            "host": self.host,
            "url": f"https://smith.langchain.com/studio/?baseUrl=http://{self.host}:{self.port}",
            "api_url": f"http://{self.host}:{self.port}",
        }

        if running and self.pid_file.exists():
            try:
                status["pid"] = int(self.pid_file.read_text().strip())
            except (ValueError, OSError):
                pass

        return status

    def start(self, background: bool = True, port: Optional[int] = None) -> Tuple[bool, str]:
        """Start LangGraph Studio.

        Args:
            background: Run in background (default: True)
            port: Override port for Studio server (default: None uses config port)

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Check for gcptoolkit config BEFORE any other operations
        from myagents.backend.services.agents.domains.config_checker import ensure_config_or_exit
        ensure_config_or_exit()

        # Use override port if provided, otherwise use config port
        effective_port = port if port is not None else self.port

        # Check if already running
        if self.is_running():
            return False, f"Studio is already running on port {self.port}"

        # Check if port is available (check effective_port, not self.port)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.settimeout(0.1)
                s.connect((self.host, effective_port))
                return False, f"Port {effective_port} is already in use by another process"
            except (socket.timeout, ConnectionRefusedError, OSError):
                pass  # Port is available

        # Verify langgraph.cli module is importable
        if not self._get_langgraph_module():
            return False, "langgraph-cli must be installed (pip install langgraph-cli)"

        # Prepare environment
        env = self._prepare_environment()

        try:
            # Prepare paths
            langgraph_config_path = self.home_config_dir / "langgraph.json"
            # Expand ~ in paths to handle both absolute paths and legacy ~ paths
            checkpoint_dir = Path(self.config["runtime"]["checkpoint_dir"]).expanduser()

            # Ensure checkpoint directory exists
            checkpoint_dir.mkdir(parents=True, exist_ok=True)

            # Build command with optional port override
            langgraph_bin = self._get_langgraph_bin()
            cmd = [langgraph_bin, "dev", "--allow-blocking", "--config", str(langgraph_config_path)]
            if port is not None:
                cmd.extend(["--port", str(port)])

            if background:
                # Start in background
                # Use --config to point to langgraph.json in home_config_dir
                # Use cwd=home_config_dir so langgraph.json paths resolve correctly

                # Open log files for error capture
                stdout_log = checkpoint_dir / "studio_stdout.log"
                stderr_log = checkpoint_dir / "studio_stderr.log"

                with open(stdout_log, 'a') as stdout_file, \
                     open(stderr_log, 'a') as stderr_file:
                    process = subprocess.Popen(
                        cmd,
                        cwd=self.home_config_dir,
                        env=env,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        start_new_session=True  # Detach from parent
                    )

                    # Save PID
                    self.pid_file.parent.mkdir(parents=True, exist_ok=True)
                    self.pid_file.write_text(str(process.pid))

                    # Wait for stability verification
                    # Per VERIFY DELAYED STATUS guideline: Service testing requires 10+ second delays
                    # to detect crashes that occur shortly after launch
                    time.sleep(10)

                    # Check if process is running on effective_port
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        try:
                            s.settimeout(0.5)
                            s.connect((self.host, effective_port))
                            is_responding = True
                        except (socket.timeout, ConnectionRefusedError, OSError):
                            is_responding = False

                    if is_responding:
                        # Build status with effective_port
                        return True, (
                            f"Studio started successfully!\n"
                            f"PID: {process.pid}\n"
                            f"WebUI: https://smith.langchain.com/studio/?baseUrl=http://{self.host}:{effective_port}\n"
                            f"API: http://{self.host}:{effective_port}"
                        )
                    else:
                        return False, "Studio process started but is not responding"
            else:
                # Run in foreground (blocking)
                result = subprocess.run(
                    cmd,
                    cwd=self.home_config_dir,
                    env=env
                )
                return result.returncode == 0, "Studio exited"

        except Exception as e:
            return False, f"Failed to start Studio: {e}"

    def stop(self, force: bool = False) -> Tuple[bool, str]:
        """Stop LangGraph Studio.

        Args:
            force: Force kill if graceful shutdown fails

        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_running():
            # Clean up stale PID file
            self.pid_file.unlink(missing_ok=True)
            return False, "Studio is not running"

        # Get PID from PID file
        pid = None
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text().strip())
            except (ValueError, OSError):
                pass

        # If PID file doesn't exist or is invalid, try to find process by port
        if not pid:
            pid = self._find_process_by_port()
            if not pid:
                return False, "Cannot find Studio process ID"

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
                    self.pid_file.unlink(missing_ok=True)
                    return True, f"Studio stopped successfully (PID: {pid})"

            # Still running after graceful shutdown attempt
            if force:
                os.kill(pid, signal.SIGKILL)
                self.pid_file.unlink(missing_ok=True)
                return True, f"Studio force killed (PID: {pid})"
            else:
                return False, "Studio did not stop gracefully. Use --force to force kill."

        except ProcessLookupError:
            # Process already gone
            self.pid_file.unlink(missing_ok=True)
            return True, "Studio process not found (already stopped)"
        except Exception as e:
            return False, f"Failed to stop Studio: {e}"

    def restart(self) -> Tuple[bool, str]:
        """Restart LangGraph Studio.

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Stop if running
        if self.is_running():
            success, msg = self.stop(force=True)
            if not success:
                return False, f"Failed to stop Studio: {msg}"
            time.sleep(1)  # Give it a moment

        # Start
        return self.start(background=True)

    def _get_langgraph_module(self) -> bool:
        """Verify langgraph.cli module is importable.

        Returns:
            bool: True if langgraph.cli can be imported
        """
        try:
            import langgraph_cli.cli
            return True
        except ImportError:
            return False

    def _prepare_environment(self) -> dict:
        """Prepare environment variables for Studio.

        REQUIRES secrets from gcptoolkit - no silent fallback allowed.

        Returns:
            Environment dict with required secrets configured

        Raises:
            RuntimeError: If gcptoolkit secrets are not available
        """
        env = os.environ.copy()

        try:
            from myagents.backend.services.agents.domains.secrets.manager import get_secret

            # Get required secrets - must succeed
            gemini_key = get_secret("GEMINI_API_KEY")
            langsmith_key = get_secret("LANGSMITH_API_KEY")

            # Verify both secrets are present
            if not gemini_key or not langsmith_key:
                raise ValueError("Required secrets not found")

            # Configure environment
            env["GEMINI_API_KEY"] = gemini_key
            env["LANGSMITH_API_KEY"] = langsmith_key
            env["LANGSMITH_TRACING"] = "true"
            env["LANGSMITH_PROJECT"] = self.config["langgraph"]["project_name"]

            # Map GEMINI_API_KEY to GOOGLE_API_KEY for LangGraph Studio compatibility
            env["GOOGLE_API_KEY"] = gemini_key

            # Auto-generate .env file for LangGraph Studio UI compatibility
            self._write_env_file(env)

        except Exception as e:
            raise RuntimeError(
                f"Studio requires secrets from gcptoolkit. "
                f"Ensure gcptoolkit is installed and secrets are configured. "
                f"Error: {e}"
            ) from e

        return env

    def _write_env_file(self, env: dict) -> None:
        """Write .env file for LangGraph Studio UI compatibility.

        Auto-generates .env file from gcptoolkit secrets. This is required because
        LangGraph Studio UI checks for .env file and shows "API key missing" error
        if not found, even though subprocess environment has the keys via gcptoolkit.

        Args:
            env: Environment dict containing the secrets to write

        Note:
            - File is written to home_config_dir/.env
            - GEMINI_API_KEY is mapped to GOOGLE_API_KEY (Studio expects this name)
            - Errors are logged but don't fail the operation (subprocess env still works)
        """
        env_file_path = self.home_config_dir / ".env"

        try:
            # Build .env file contents
            lines = [
                "# Auto-generated by MyAgents - DO NOT EDIT",
                "# This file is automatically generated from gcptoolkit secrets",
                "# Changes will be overwritten on next Studio start",
                "",
            ]

            # Write required keys for LangGraph Studio
            # Note: Use GOOGLE_API_KEY (not GEMINI_API_KEY) as Studio expects this name
            if "GOOGLE_API_KEY" in env:
                lines.append(f"GOOGLE_API_KEY={env['GOOGLE_API_KEY']}")
            if "LANGSMITH_API_KEY" in env:
                lines.append(f"LANGSMITH_API_KEY={env['LANGSMITH_API_KEY']}")
            if "LANGSMITH_TRACING" in env:
                lines.append(f"LANGSMITH_TRACING={env['LANGSMITH_TRACING']}")
            if "LANGSMITH_PROJECT" in env:
                lines.append(f"LANGSMITH_PROJECT={env['LANGSMITH_PROJECT']}")

            # Write to file
            env_file_path.write_text("\n".join(lines) + "\n")

        except Exception as e:
            # Log warning but don't fail - subprocess environment still works via gcptoolkit
            print(f"Warning: Failed to write .env file: {e}")
            print("Studio will still work via gcptoolkit secrets in subprocess environment")

    def _get_langgraph_bin(self) -> str:
        """Get path to langgraph binary.

        Returns global langgraph in PATH (home directory setup doesn't use project-specific venv).

        Returns:
            str: Path to langgraph binary
        """
        return "langgraph"

    def get_recent_errors(self, num_lines: int = 20) -> Optional[str]:
        """Get recent error messages from stderr log.

        Args:
            num_lines: Number of recent lines to retrieve (default: 20)

        Returns:
            String containing recent error lines, or None if log doesn't exist
        """
        # Expand ~ in paths to handle both absolute paths and legacy ~ paths
        checkpoint_dir = Path(self.config["runtime"]["checkpoint_dir"]).expanduser()
        stderr_log = checkpoint_dir / "studio_stderr.log"

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
