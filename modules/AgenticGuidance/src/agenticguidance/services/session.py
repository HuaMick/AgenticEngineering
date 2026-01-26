"""
Session management service for tmux session lifecycle.

This service handles the business logic for tmux session management,
including session creation, attachment, listing, and lifecycle tracking.
"""

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class SessionState(Enum):
    """Session lifecycle states."""

    RUNNING = "running"
    DETACHED = "detached"
    DEAD = "dead"


@dataclass
class SessionInfo:
    """Information about a tmux session."""

    name: str
    state: SessionState
    created_at: float
    attached: bool = False
    worktree: Optional[str] = None
    plan_folder: Optional[str] = None
    windows: int = 1
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "state": self.state.value,
            "created_at": self.created_at,
            "attached": self.attached,
            "worktree": self.worktree,
            "plan_folder": self.plan_folder,
            "windows": self.windows,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionInfo":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            state=SessionState(data.get("state", "running")),
            created_at=data.get("created_at", 0),
            attached=data.get("attached", False),
            worktree=data.get("worktree"),
            plan_folder=data.get("plan_folder"),
            windows=data.get("windows", 1),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SessionResult:
    """Result of a session operation."""

    success: bool
    message: str
    session: Optional[SessionInfo] = None
    data: Optional[dict] = None


class SessionService:
    """Service for managing tmux sessions.

    Provides CRUD operations for tmux sessions with integration
    to worktrees and plan folders.
    """

    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize session service.

        Args:
            registry_path: Path to session registry file.
                          Defaults to ~/.config/agenticcli/sessions.json
        """
        if registry_path is None:
            config_dir = Path.home() / ".config" / "agenticcli"
            config_dir.mkdir(parents=True, exist_ok=True)
            registry_path = config_dir / "sessions.json"

        self.registry_path = registry_path
        self._ensure_registry()

    def _ensure_registry(self):
        """Ensure registry file exists."""
        if not self.registry_path.exists():
            self.registry_path.write_text(json.dumps({"sessions": {}}))

    def _load_registry(self) -> dict:
        """Load session registry."""
        try:
            return json.loads(self.registry_path.read_text())
        except (json.JSONDecodeError, IOError):
            return {"sessions": {}}

    def _save_registry(self, data: dict):
        """Save session registry."""
        self.registry_path.write_text(json.dumps(data, indent=2))

    def _tmux_exists(self) -> bool:
        """Check if tmux is available."""
        try:
            subprocess.run(["tmux", "-V"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _get_tmux_sessions(self) -> list[str]:
        """Get list of active tmux sessions."""
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        return []

    def _is_session_attached(self, name: str) -> bool:
        """Check if a session is currently attached."""
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}:#{session_attached}"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.startswith(f"{name}:"):
                        return line.endswith(":1")
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        return False

    def create(
        self,
        name: str,
        worktree: Optional[str] = None,
        plan_folder: Optional[str] = None,
        start_directory: Optional[str] = None,
    ) -> SessionResult:
        """Create a new tmux session.

        Args:
            name: Session name (must be unique).
            worktree: Optional worktree path to link.
            plan_folder: Optional plan folder to link.
            start_directory: Starting directory for the session.

        Returns:
            SessionResult with success status and session info.
        """
        if not self._tmux_exists():
            return SessionResult(
                success=False,
                message="tmux is not installed or not in PATH",
            )

        # Check if session already exists
        active_sessions = self._get_tmux_sessions()
        if name in active_sessions:
            return SessionResult(
                success=False,
                message=f"Session '{name}' already exists",
            )

        # Determine start directory
        if start_directory is None:
            if worktree:
                start_directory = worktree
            else:
                start_directory = os.getcwd()

        # Create tmux session
        try:
            cmd = ["tmux", "new-session", "-d", "-s", name]
            if start_directory:
                cmd.extend(["-c", start_directory])

            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            return SessionResult(
                success=False,
                message=f"Failed to create session: {e.stderr.decode() if e.stderr else str(e)}",
            )

        # Create session info
        session = SessionInfo(
            name=name,
            state=SessionState.RUNNING,
            created_at=datetime.now().timestamp(),
            worktree=worktree,
            plan_folder=plan_folder,
        )

        # Save to registry
        registry = self._load_registry()
        registry["sessions"][name] = session.to_dict()
        self._save_registry(registry)

        return SessionResult(
            success=True,
            message=f"Created session '{name}'",
            session=session,
        )

    def attach(self, name: str) -> SessionResult:
        """Attach to an existing tmux session.

        Args:
            name: Session name to attach to.

        Returns:
            SessionResult with status.
        """
        if not self._tmux_exists():
            return SessionResult(
                success=False,
                message="tmux is not installed or not in PATH",
            )

        active_sessions = self._get_tmux_sessions()
        if name not in active_sessions:
            return SessionResult(
                success=False,
                message=f"Session '{name}' not found",
            )

        # Note: actual attachment must be done by the caller
        # since we can't attach from within a subprocess
        return SessionResult(
            success=True,
            message=f"tmux attach-session -t {name}",
            data={"command": ["tmux", "attach-session", "-t", name]},
        )

    def list(self) -> list[SessionInfo]:
        """List all sessions (both active and registered).

        Returns:
            List of SessionInfo objects.
        """
        registry = self._load_registry()
        active_sessions = set(self._get_tmux_sessions())

        sessions = []
        for name, data in registry.get("sessions", {}).items():
            session = SessionInfo.from_dict(data)

            # Update state based on actual tmux status
            if name in active_sessions:
                session.state = SessionState.RUNNING
                session.attached = self._is_session_attached(name)
            else:
                session.state = SessionState.DEAD

            sessions.append(session)

        # Add any tmux sessions not in registry
        for name in active_sessions:
            if name not in registry.get("sessions", {}):
                sessions.append(
                    SessionInfo(
                        name=name,
                        state=SessionState.RUNNING,
                        created_at=0,
                        attached=self._is_session_attached(name),
                    )
                )

        return sorted(sessions, key=lambda s: s.name)

    def get(self, name: str) -> Optional[SessionInfo]:
        """Get information about a specific session.

        Args:
            name: Session name.

        Returns:
            SessionInfo or None if not found.
        """
        registry = self._load_registry()
        active_sessions = self._get_tmux_sessions()

        if name in registry.get("sessions", {}):
            session = SessionInfo.from_dict(registry["sessions"][name])
            if name in active_sessions:
                session.state = SessionState.RUNNING
                session.attached = self._is_session_attached(name)
            else:
                session.state = SessionState.DEAD
            return session

        if name in active_sessions:
            return SessionInfo(
                name=name,
                state=SessionState.RUNNING,
                created_at=0,
                attached=self._is_session_attached(name),
            )

        return None

    def kill(self, name: str, force: bool = False) -> SessionResult:
        """Kill a tmux session.

        Args:
            name: Session name to kill.
            force: Force kill even if session has attached clients.

        Returns:
            SessionResult with status.
        """
        if not self._tmux_exists():
            return SessionResult(
                success=False,
                message="tmux is not installed or not in PATH",
            )

        active_sessions = self._get_tmux_sessions()
        if name not in active_sessions:
            # Remove from registry if exists
            registry = self._load_registry()
            if name in registry.get("sessions", {}):
                del registry["sessions"][name]
                self._save_registry(registry)
                return SessionResult(
                    success=True,
                    message=f"Removed dead session '{name}' from registry",
                )
            return SessionResult(
                success=False,
                message=f"Session '{name}' not found",
            )

        # Check if attached
        if not force and self._is_session_attached(name):
            return SessionResult(
                success=False,
                message=f"Session '{name}' has attached clients. Use --force to kill.",
            )

        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", name],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            return SessionResult(
                success=False,
                message=f"Failed to kill session: {e.stderr.decode() if e.stderr else str(e)}",
            )

        # Remove from registry
        registry = self._load_registry()
        if name in registry.get("sessions", {}):
            del registry["sessions"][name]
            self._save_registry(registry)

        return SessionResult(
            success=True,
            message=f"Killed session '{name}'",
        )

    def cleanup_dead(self) -> int:
        """Remove dead sessions from registry.

        Returns:
            Number of sessions cleaned up.
        """
        registry = self._load_registry()
        active_sessions = set(self._get_tmux_sessions())

        to_remove = []
        for name in registry.get("sessions", {}):
            if name not in active_sessions:
                to_remove.append(name)

        for name in to_remove:
            del registry["sessions"][name]

        if to_remove:
            self._save_registry(registry)

        return len(to_remove)

    def link_worktree(self, session_name: str, worktree_path: str) -> SessionResult:
        """Link a session to a worktree.

        Args:
            session_name: Session name.
            worktree_path: Path to worktree.

        Returns:
            SessionResult with status.
        """
        registry = self._load_registry()

        if session_name not in registry.get("sessions", {}):
            # Create entry if session exists in tmux
            if session_name in self._get_tmux_sessions():
                registry["sessions"][session_name] = SessionInfo(
                    name=session_name,
                    state=SessionState.RUNNING,
                    created_at=datetime.now().timestamp(),
                ).to_dict()
            else:
                return SessionResult(
                    success=False,
                    message=f"Session '{session_name}' not found",
                )

        registry["sessions"][session_name]["worktree"] = worktree_path
        self._save_registry(registry)

        return SessionResult(
            success=True,
            message=f"Linked session '{session_name}' to worktree '{worktree_path}'",
        )

    def link_plan(self, session_name: str, plan_folder: str) -> SessionResult:
        """Link a session to a plan folder.

        Args:
            session_name: Session name.
            plan_folder: Plan folder path.

        Returns:
            SessionResult with status.
        """
        registry = self._load_registry()

        if session_name not in registry.get("sessions", {}):
            if session_name in self._get_tmux_sessions():
                registry["sessions"][session_name] = SessionInfo(
                    name=session_name,
                    state=SessionState.RUNNING,
                    created_at=datetime.now().timestamp(),
                ).to_dict()
            else:
                return SessionResult(
                    success=False,
                    message=f"Session '{session_name}' not found",
                )

        registry["sessions"][session_name]["plan_folder"] = plan_folder
        self._save_registry(registry)

        return SessionResult(
            success=True,
            message=f"Linked session '{session_name}' to plan '{plan_folder}'",
        )
