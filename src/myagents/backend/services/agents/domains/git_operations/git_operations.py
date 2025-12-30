"""
Git operations domain for MyAgents.

Provides core git operation functionality including repository status,
diff viewing, branch information, and repository root detection.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List


class GitOperations:
    """Domain class for git operations with security validation."""

    def __init__(self, allowed_dir: Path | None = None):
        """
        Initialize GitOperations domain.

        Args:
            allowed_dir: Base directory for all git operations (default: /home/code/myagents)
        """
        if allowed_dir is None:
            allowed_dir = Path(os.getenv("MYAGENTS_ALLOWED_DIR", "/home/code/myagents")).resolve()
        self.allowed_dir = allowed_dir.resolve()

    def validate_path(self, path: str) -> Path:
        """
        Validate path and prevent directory traversal attacks.

        Args:
            path: Path to validate (must be relative, not absolute)

        Returns:
            Resolved absolute Path object within allowed directory

        Raises:
            ValueError: If path is absolute or attempts to escape allowed directory
        """
        # SECURITY: Reject absolute paths (they could escape allowed directory)
        path_obj = Path(path)
        if path_obj.is_absolute():
            raise ValueError(f"Absolute paths not allowed. Use relative paths only: {path}")

        # Convert to Path and resolve to absolute path (handles .., symlinks, etc.)
        try:
            resolved = (self.allowed_dir / path).resolve()
        except (ValueError, RuntimeError) as e:
            raise ValueError(f"Invalid path: {path}") from e

        # Security check: ensure resolved path is within allowed directory
        if not str(resolved).startswith(str(self.allowed_dir)):
            raise ValueError(f"Path outside allowed directory: {path}")

        return resolved

    def get_repo_root(self, path: str = ".") -> str:
        """
        Get the root directory of the git repository.

        Args:
            path: Relative path to a directory within the repository (default: current)

        Returns:
            Relative path to repository root from allowed_dir

        Raises:
            RuntimeError: If not in a git repository or git command fails
        """
        validated_path = self.validate_path(path)

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=validated_path,
                capture_output=True,
                text=True,
                check=True
            )
            repo_root = Path(result.stdout.strip())

            # Return relative path from allowed_dir
            return str(repo_root.relative_to(self.allowed_dir))
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {e.stderr.strip()}") from e
        except ValueError as e:
            raise RuntimeError("Repository root outside allowed directory") from e

    def get_status(self, path: str = ".") -> Dict[str, List[str]]:
        """
        Get the status of files in the git repository.

        Args:
            path: Relative path to a directory within the repository (default: current)

        Returns:
            Dictionary with categorized file lists:
            - modified: List of modified files
            - added: List of staged new files
            - deleted: List of deleted files
            - untracked: List of untracked files
            - renamed: List of renamed files

        Raises:
            RuntimeError: If git command fails
        """
        validated_path = self.validate_path(path)

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=all"],
                cwd=validated_path,
                capture_output=True,
                text=True,
                check=True
            )

            # Parse git status output
            status_dict: Dict[str, List[str]] = {
                "modified": [],
                "added": [],
                "deleted": [],
                "untracked": [],
                "renamed": []
            }

            for line in result.stdout.splitlines():
                if not line.strip():
                    continue

                # Git status format: XY filename
                status_code = line[:2]
                filename = line[3:].strip()

                # Parse status codes
                if status_code[0] == "M" or status_code[1] == "M":
                    status_dict["modified"].append(filename)
                elif status_code[0] == "A":
                    status_dict["added"].append(filename)
                elif status_code[0] == "D" or status_code[1] == "D":
                    status_dict["deleted"].append(filename)
                elif status_code == "??":
                    status_dict["untracked"].append(filename)
                elif status_code[0] == "R":
                    status_dict["renamed"].append(filename)

            return status_dict
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {e.stderr.strip()}") from e

    def get_diff(self, path: str = ".", file_path: str | None = None) -> str:
        """
        Get the diff of changes in the repository.

        Args:
            path: Relative path to a directory within the repository (default: current)
            file_path: Optional specific file to get diff for (relative to path)

        Returns:
            Diff output as string

        Raises:
            RuntimeError: If git command fails
        """
        validated_path = self.validate_path(path)

        # Build git diff command
        cmd = ["git", "diff"]

        if file_path:
            # Use -- separator for file path to avoid ambiguity
            cmd.extend(["--", file_path])

        try:
            result = subprocess.run(
                cmd,
                cwd=validated_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {e.stderr.strip()}") from e

    def get_current_branch(self, path: str = ".") -> str:
        """
        Get the current branch name.

        Args:
            path: Relative path to a directory within the repository (default: current)

        Returns:
            Current branch name

        Raises:
            RuntimeError: If git command fails or not on a branch
        """
        validated_path = self.validate_path(path)

        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=validated_path,
                capture_output=True,
                text=True,
                check=True
            )
            branch = result.stdout.strip()

            if not branch:
                raise RuntimeError("Not currently on a branch (detached HEAD state)")

            return branch
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {e.stderr.strip()}") from e
