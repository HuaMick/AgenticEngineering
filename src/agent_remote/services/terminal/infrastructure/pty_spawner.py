"""PTY spawner infrastructure using ptyprocess.

Wraps ptyprocess library to spawn pseudo-terminals for running Claude Code CLI.
Handles process lifecycle, I/O file descriptors, and terminal resize.
"""

import asyncio
import logging
import os
import signal
from dataclasses import dataclass
from typing import Optional

try:
    import ptyprocess
except ImportError:
    ptyprocess = None  # Will fail at runtime with helpful error

from agent_remote.services.terminal.domains.pty_manager import TerminalDimensions

logger = logging.getLogger(__name__)


class PTYSpawnError(Exception):
    """Error spawning PTY process."""
    pass


@dataclass
class PTYHandle:
    """Handle to a spawned PTY process.

    Provides access to the ptyprocess object for I/O operations.
    """
    process: "ptyprocess.PtyProcessUnicode"
    pid: int

    @property
    def fd(self) -> int:
        """Get file descriptor for the PTY."""
        return self.process.fd


class PTYSpawner:
    """Spawns and manages PTY processes.

    Uses ptyprocess library to create pseudo-terminals. Each spawn creates
    a PTY master/slave pair and forks the process.
    """

    def __init__(self):
        if ptyprocess is None:
            raise ImportError(
                "ptyprocess is required for PTY spawning. "
                "Install with: pip install ptyprocess"
            )

    def spawn(
        self,
        command: list[str],
        dimensions: TerminalDimensions,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> PTYHandle:
        """Spawn a new PTY process.

        Args:
            command: Command and arguments to execute
            dimensions: Terminal dimensions (rows, cols)
            env: Optional environment variables (defaults to current env)
            cwd: Optional working directory (defaults to current dir)

        Returns:
            PTYHandle with process object and PID

        Raises:
            PTYSpawnError: If spawn fails
        """
        try:
            # Use current environment as base, merge in provided env
            spawn_env = os.environ.copy()
            if env:
                spawn_env.update(env)

            # Set TERM if not specified
            if "TERM" not in spawn_env:
                spawn_env["TERM"] = "xterm-256color"

            process = ptyprocess.PtyProcessUnicode.spawn(
                command,
                dimensions=(dimensions.rows, dimensions.cols),
                env=spawn_env,
                cwd=cwd,
            )

            logger.info(
                f"Spawned PTY process: pid={process.pid}, "
                f"command={command}, dimensions={dimensions}"
            )

            return PTYHandle(process=process, pid=process.pid)

        except Exception as e:
            raise PTYSpawnError(f"Failed to spawn PTY: {e}") from e

    def resize(self, handle: PTYHandle, dimensions: TerminalDimensions) -> None:
        """Resize a PTY.

        Args:
            handle: PTY handle from spawn()
            dimensions: New terminal dimensions
        """
        handle.process.setwinsize(dimensions.rows, dimensions.cols)
        logger.debug(f"Resized PTY pid={handle.pid} to {dimensions}")

    def read(self, handle: PTYHandle, size: int = 4096) -> bytes:
        """Read output from PTY.

        Args:
            handle: PTY handle from spawn()
            size: Max bytes to read

        Returns:
            Output bytes from PTY (may contain ANSI codes, UTF-8, etc.)
        """
        return handle.process.read(size).encode('utf-8')

    async def read_async(self, handle: PTYHandle, size: int = 4096) -> bytes:
        """Async read output from PTY using asyncio.

        Args:
            handle: PTY handle from spawn()
            size: Max bytes to read

        Returns:
            Output bytes from PTY
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.read, handle, size)

    def write(self, handle: PTYHandle, data: bytes) -> None:
        """Write input to PTY.

        Args:
            handle: PTY handle from spawn()
            data: Input bytes to write to PTY stdin
        """
        handle.process.write(data.decode('utf-8'))

    def terminate(self, handle: PTYHandle, timeout: float = 5.0) -> int:
        """Terminate a PTY process.

        Sends SIGTERM, waits for exit. If timeout, sends SIGKILL.

        Args:
            handle: PTY handle from spawn()
            timeout: Seconds to wait for graceful termination

        Returns:
            Exit code from process
        """
        if not handle.process.isalive():
            return handle.process.exitstatus or 0

        # Try graceful termination
        handle.process.terminate(force=False)

        try:
            handle.process.wait()
            return handle.process.exitstatus or 0
        except Exception:
            pass

        # Force kill if still running
        if handle.process.isalive():
            handle.process.terminate(force=True)
            try:
                handle.process.wait()
            except Exception:
                pass

        return handle.process.exitstatus or -9

    def is_alive(self, handle: PTYHandle) -> bool:
        """Check if PTY process is still running.

        Args:
            handle: PTY handle from spawn()

        Returns:
            True if process is running, False otherwise
        """
        return handle.process.isalive()

    def get_exit_code(self, handle: PTYHandle) -> Optional[int]:
        """Get exit code if process has terminated.

        Args:
            handle: PTY handle from spawn()

        Returns:
            Exit code if terminated, None if still running
        """
        if handle.process.isalive():
            return None
        return handle.process.exitstatus
