"""
File operations domain for MyAgents.

Provides core file operation functionality including path validation,
file reading, directory listing, and file editing.
"""

import os
from pathlib import Path
from typing import List


class FileOperations:
    """Domain class for file operations with security validation."""

    def __init__(self, allowed_dir: Path | None = None):
        """
        Initialize FileOperations domain.

        Args:
            allowed_dir: Base directory for all file operations (default: /home/code/myagents)
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

    def read_file(self, path: str, max_size: int = 100_000) -> str:
        """
        Read file contents with size validation.

        Args:
            path: Relative path to file
            max_size: Maximum file size in bytes (default: 100KB)

        Returns:
            File contents as string

        Raises:
            ValueError: If file is too large or path is invalid
        """
        validated_path = self.validate_path(path)

        # Size check
        if validated_path.stat().st_size > max_size:
            raise ValueError(f"File too large (>{max_size} bytes)")

        return validated_path.read_text()

    def list_files(self, path: str, include_hidden: bool = False) -> List[str]:
        """
        List files in directory.

        Args:
            path: Relative path to directory
            include_hidden: Whether to include hidden files (default: False)

        Returns:
            List of file/directory names

        Raises:
            ValueError: If path is not a directory
        """
        validated_path = self.validate_path(path)

        if not validated_path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        # Filter based on hidden files
        if include_hidden:
            files = [f.name for f in validated_path.iterdir()]
        else:
            files = [f.name for f in validated_path.iterdir() if not f.name.startswith('.')]

        return files

    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        """
        Edit file by replacing old_text with new_text (first occurrence only).

        Args:
            path: Relative path to file
            old_text: Text to find and replace
            new_text: Replacement text

        Returns:
            Success message with path

        Raises:
            ValueError: If old_text not found in file or path is invalid
        """
        validated_path = self.validate_path(path)

        content = validated_path.read_text()
        if old_text not in content:
            raise ValueError("Text not found in file")

        updated = content.replace(old_text, new_text, 1)
        validated_path.write_text(updated)

        return f"Updated {path}"

    def create_file(self, path: str, content: str) -> str:
        """
        Create a new file with specified content.

        Args:
            path: Relative path to file
            content: Content to write to file

        Returns:
            Success message with path

        Raises:
            ValueError: If path is invalid or file already exists
        """
        validated_path = self.validate_path(path)

        # Check if file already exists
        if validated_path.exists():
            raise ValueError(f"File already exists: {path}")

        # Create parent directories if they don't exist
        validated_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content to file
        validated_path.write_text(content)

        return f"Created {path}"

    def search_in_files(
        self, pattern: str, directory: str = ".", file_pattern: str = "*", max_results: int = 100
    ) -> List[dict]:
        """
        Search for text pattern in files.

        Args:
            pattern: Text pattern to search for
            directory: Relative path to search directory (default: current)
            file_pattern: Glob pattern for file names (default: *)
            max_results: Maximum number of matches to return (default: 100)

        Returns:
            List of dicts with file, line_number, and line content

        Raises:
            ValueError: If directory path is invalid
        """
        validated_dir = self.validate_path(directory)

        if not validated_dir.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        results: List[dict] = []
        for file_path in validated_dir.rglob(file_pattern):
            if len(results) >= max_results:
                break

            if not file_path.is_file():
                continue

            try:
                content = file_path.read_text()
            except (UnicodeDecodeError, PermissionError):
                # Skip binary files or files we can't read
                continue

            for line_num, line in enumerate(content.splitlines(), start=1):
                if pattern in line:
                    # Get relative path from allowed_dir
                    rel_path = str(file_path.relative_to(self.allowed_dir))
                    results.append({
                        "file": rel_path,
                        "line_number": line_num,
                        "line": line
                    })
                    if len(results) >= max_results:
                        break

        return results

    def find_files(self, name_pattern: str, directory: str = ".", max_results: int = 100) -> List[str]:
        """
        Find files matching a name pattern.

        Args:
            name_pattern: Glob pattern for file names (e.g., *.py)
            directory: Relative path to search directory (default: current)
            max_results: Maximum number of files to return (default: 100)

        Returns:
            List of relative file paths

        Raises:
            ValueError: If directory path is invalid
        """
        validated_dir = self.validate_path(directory)

        if not validated_dir.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        results = []
        for file_path in validated_dir.rglob(name_pattern):
            if not file_path.is_file():
                continue

            # Get relative path from allowed_dir
            rel_path = str(file_path.relative_to(self.allowed_dir))
            results.append(rel_path)

            if len(results) >= max_results:
                break

        return results
