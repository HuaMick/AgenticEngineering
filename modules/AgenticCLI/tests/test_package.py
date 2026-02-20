"""Tests for package management commands (update, rebuild)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestUpdateCommand:
    """Tests for 'agentic update' command."""

    def test_update_help(self, cli_runner):
        """Test update --help output."""
        stdout, stderr, code = cli_runner(["setup", "update", "--help"])
        assert "update" in stdout.lower() or "reinstall" in stdout.lower()
        assert code == 0

    def test_update_finds_package_root(self):
        """Test find_package_root returns valid path."""
        from agenticcli.commands.package import find_package_root

        root = find_package_root()
        assert root.exists()
        assert (root / "pyproject.toml").exists()

    @patch("subprocess.run")
    def test_update_runs_uv_sync(self, mock_run):
        """Test update command calls uv sync."""
        mock_run.return_value = MagicMock(returncode=0)

        from agenticcli.commands.package import handle_update

        args = MagicMock()
        handle_update(args)

        # Verify uv sync was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["uv", "sync"]

    @patch("subprocess.run")
    def test_update_handles_uv_error(self, mock_run):
        """Test update handles subprocess errors gracefully."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "uv sync")

        from agenticcli.commands.package import handle_update

        args = MagicMock()
        with pytest.raises(SystemExit) as exc_info:
            handle_update(args)
        assert exc_info.value.code == 1

    @patch("subprocess.run")
    def test_update_handles_missing_uv(self, mock_run):
        """Test update handles missing uv command."""
        mock_run.side_effect = FileNotFoundError()

        from agenticcli.commands.package import handle_update

        args = MagicMock()
        with pytest.raises(SystemExit) as exc_info:
            handle_update(args)
        assert exc_info.value.code == 1


class TestRebuildCommand:
    """Tests for 'agentic rebuild' command."""

    def test_rebuild_help(self, cli_runner):
        """Test rebuild --help output."""
        stdout, stderr, code = cli_runner(["setup", "rebuild", "--help"])
        assert "rebuild" in stdout.lower() or "reinstall" in stdout.lower()
        assert code == 0

    @patch("subprocess.run")
    @patch("shutil.rmtree")
    def test_rebuild_cleans_and_rebuilds(self, mock_rmtree, mock_run):
        """Test rebuild cleans artifacts and rebuilds."""
        mock_run.return_value = MagicMock(returncode=0)

        from agenticcli.commands.package import handle_rebuild

        args = MagicMock()
        handle_rebuild(args)

        # Verify build and uv sync were called
        assert mock_run.call_count == 2
        calls = mock_run.call_args_list
        # First call should be python -m build
        assert calls[0][0][0][0] == "python"
        assert "-m" in calls[0][0][0]
        assert "build" in calls[0][0][0]
        # Second call should be uv sync
        assert calls[1][0][0] == ["uv", "sync"]

    @patch("subprocess.run")
    def test_rebuild_handles_build_error(self, mock_run):
        """Test rebuild handles build errors gracefully."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "python -m build")

        from agenticcli.commands.package import handle_rebuild

        args = MagicMock()
        with pytest.raises(SystemExit) as exc_info:
            handle_rebuild(args)
        assert exc_info.value.code == 1


class TestFindPackageRoot:
    """Tests for find_package_root function."""

    def test_finds_pyproject_toml(self):
        """Test that find_package_root locates pyproject.toml."""
        from agenticcli.commands.package import find_package_root

        root = find_package_root()
        assert isinstance(root, Path)
        assert root.exists()
        assert (root / "pyproject.toml").exists()

    @patch("pathlib.Path.exists")
    def test_handles_missing_pyproject(self, mock_exists):
        """Test error when pyproject.toml not found."""
        mock_exists.return_value = False

        from agenticcli.commands.package import find_package_root

        with pytest.raises(SystemExit) as exc_info:
            find_package_root()
        assert exc_info.value.code == 1
