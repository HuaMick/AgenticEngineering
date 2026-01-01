"""
Shell operations domain for MyAgents.

Provides secure shell command execution with working directory validation.
"""

import os
import subprocess
from pathlib import Path


class ShellOperations:
    """Domain class for shell operations with security validation."""

    def __init__(self, allowed_dir: Path | None = None):
        """
        Initialize ShellOperations domain.

        Args:
            allowed_dir: Base directory for all shell operations (default: /home/code/myagents)
        """
        if allowed_dir is None:
            allowed_dir = Path(os.getenv("MYAGENTS_ALLOWED_DIR", "/home/code/myagents")).resolve()
        self.allowed_dir = allowed_dir.resolve()

    def _validate_working_dir(self, working_dir: str | None) -> Path:
        """
        Validate and return safe working directory.

        Args:
            working_dir: Working directory path (relative to allowed_dir) or None

        Returns:
            Resolved absolute Path object within allowed directory

        Raises:
            ValueError: If working directory is invalid or attempts to escape allowed directory
        """
        if working_dir is None:
            return self.allowed_dir

        # Convert to Path
        path_obj = Path(working_dir)

        # Handle absolute paths
        if path_obj.is_absolute():
            try:
                resolved = path_obj.resolve()
            except (ValueError, RuntimeError) as e:
                raise ValueError(f"Invalid working directory: {working_dir}") from e
        else:
            # Relative path - resolve relative to allowed_dir
            try:
                resolved = (self.allowed_dir / working_dir).resolve()
            except (ValueError, RuntimeError) as e:
                raise ValueError(f"Invalid working directory: {working_dir}") from e

        # Security check: ensure resolved path is within allowed directory
        if not str(resolved).startswith(str(self.allowed_dir)):
            raise ValueError(f"Working directory outside allowed directory: {working_dir}")

        # Check that directory exists
        if not resolved.is_dir():
            raise ValueError(f"Working directory does not exist: {working_dir}")

        return resolved

    def execute_shell(self, command: str, working_dir: str | None = None, timeout: int = 30) -> dict:
        """
        Execute shell command with security constraints.

        Args:
            command: Shell command to execute
            working_dir: Working directory (relative to allowed_dir or absolute within it)
            timeout: Command timeout in seconds (default: 30)

        Returns:
            Dict with stdout, stderr, returncode, and success keys

        Raises:
            ValueError: If working directory is invalid
        """
        validated_dir = self._validate_working_dir(working_dir)

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=validated_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired as e:
            return {
                "stdout": e.stdout if e.stdout else "",
                "stderr": e.stderr if e.stderr else f"Command timed out after {timeout} seconds",
                "returncode": -1,
                "success": False,
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "success": False,
            }
