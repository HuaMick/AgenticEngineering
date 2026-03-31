"""Shared JSON-on-disk state store for CLI command modules.

Replaces duplicated _get_*_dir / _load_* / _save_* / _list_* boilerplate
in session.py, loop.py, and orchestrate.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class StateStore:
    """JSON file-per-record state store under ~/.agentic/<subdir>/."""

    def __init__(self, subdir: str, id_key: str = "id"):
        """Initialize a state store.

        Args:
            subdir: Directory name under ~/.agentic/ (e.g., "sessions", "loops").
            id_key: Key in the state dict used as the filename (e.g., "session_id").
        """
        self._subdir = subdir
        self._id_key = id_key

    def get_dir(self, override: Path | None = None) -> Path:
        """Get (and create) the state directory.

        Args:
            override: Optional directory override (useful for testing).
        """
        d = override or (Path.home() / ".agentic" / self._subdir)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, state: dict, *, state_dir: Path | None = None) -> None:
        """Write a state record to disk.

        Args:
            state: Dict containing at least the id_key field.
            state_dir: Optional directory override.
        """
        d = self.get_dir(state_dir)
        state_file = d / f"{state[self._id_key]}.json"
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)

    def load(self, record_id: str, *, state_dir: Path | None = None) -> dict | None:
        """Load a state record from disk.

        Args:
            record_id: The record identifier.
            state_dir: Optional directory override.

        Returns:
            State dict or None if not found.
        """
        d = self.get_dir(state_dir)
        state_file = d / f"{record_id}.json"
        if not state_file.exists():
            return None
        with open(state_file) as f:
            return json.load(f)

    def delete(self, record_id: str, *, state_dir: Path | None = None) -> bool:
        """Delete a state record from disk.

        Args:
            record_id: The record identifier.
            state_dir: Optional directory override.

        Returns:
            True if the file existed and was removed, False if it did not exist.
        """
        # @story US-007
        d = self.get_dir(state_dir)
        state_file = d / f"{record_id}.json"
        existed = state_file.exists()
        state_file.unlink(missing_ok=True)
        return existed

    def list_stale(
        self,
        is_alive_fn: callable,
        *,
        state_dir: Path | None = None,
    ) -> list[dict]:
        """List state records where the is_alive_fn predicate returns False.

        This enables cleanup services to identify dead/stale sessions without
        duplicating process-checking logic inside StateStore.

        Args:
            is_alive_fn: A callable(dict) -> bool that checks if a record
                represents a still-alive session. Receives the full record dict
                so the caller can inspect pid, status, age, etc.
            state_dir: Optional directory override.

        Returns:
            List of state dicts where is_alive_fn returned False (stale records).
        """
        # @story US-007
        d = self.get_dir(state_dir)
        stale: list[dict] = []
        for state_file in d.glob("*.json"):
            try:
                with open(state_file) as f:
                    record = json.load(f)
                    if not is_alive_fn(record):
                        stale.append(record)
            except (json.JSONDecodeError, OSError):
                continue
        return stale

    def list_all(
        self, *, state_dir: Path | None = None, filter_fn=None,
    ) -> list[dict]:
        """List all state records.

        Args:
            state_dir: Optional directory override.
            filter_fn: Optional callable(dict) -> bool to filter records.

        Returns:
            List of state dicts.
        """
        d = self.get_dir(state_dir)
        records = []
        for state_file in d.glob("*.json"):
            try:
                with open(state_file) as f:
                    record = json.load(f)
                    if filter_fn and not filter_fn(record):
                        continue
                    records.append(record)
            except (json.JSONDecodeError, OSError):
                continue
        return records


def is_process_running(pid: int) -> bool:
    """Check if a process is still running.

    Args:
        pid: Process ID to check.

    Returns:
        True if process is running, False otherwise.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
