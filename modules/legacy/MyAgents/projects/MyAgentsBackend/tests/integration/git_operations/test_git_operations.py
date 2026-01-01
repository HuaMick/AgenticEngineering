"""Consolidated integration tests for git_operations domain and tools.

Tests both domain layer (GitOperations) and tool layer (git_tools) using parametrization
to reduce redundancy while maintaining comprehensive coverage.
"""

import pytest
import subprocess
import shutil
from pathlib import Path
from myagents.backend.services.agents.domains.git_operations import GitOperations
from myagents.backend.services.agents.tools.git_tools import (
    git_repo_root,
    git_status,
    git_diff,
    git_current_branch,
    get_all_tools,
    get_tool_by_name,
    ALL_TOOLS,
    TOOLS_BY_NAME
)


@pytest.fixture
def git_ops(temp_git_repo):
    """Create GitOperations instance with temp git repository."""
    return GitOperations(allowed_dir=temp_git_repo)


@pytest.mark.integration
class TestPathValidation:
    """Test path validation and security."""

    @pytest.mark.parametrize("invalid_path,error_pattern", [
        ("/etc", "Absolute paths not allowed"),
        ("/absolute/path", "Absolute paths not allowed"),
        ("../../etc", "Path outside allowed directory"),
        ("../../../root", "Path outside allowed directory"),
    ])
    def test_invalid_paths_rejected(self, git_ops, invalid_path, error_pattern):
        """Test that invalid and traversal paths are rejected across all methods."""
        with pytest.raises(ValueError, match=error_pattern):
            git_ops.get_status(invalid_path)

        with pytest.raises(ValueError, match=error_pattern):
            git_ops.get_diff(invalid_path)

        with pytest.raises(ValueError, match=error_pattern):
            git_ops.get_current_branch(invalid_path)

    def test_validate_path_subdirectory(self, git_ops, temp_git_repo):
        """Test validation of paths in subdirectories."""
        subdir = temp_git_repo / "subdir"
        subdir.mkdir()
        result = git_ops.validate_path("subdir/file.txt")
        assert result == temp_git_repo / "subdir" / "file.txt"

    def test_validate_path_nonexistent(self, git_ops):
        """Test validation allows nonexistent paths."""
        result = git_ops.validate_path("nonexistent/subdir")
        assert "nonexistent" in str(result)


@pytest.mark.integration
class TestGitRepoRoot:
    """Test get_repo_root functionality."""

    @pytest.mark.parametrize("test_path,expected", [
        (".", "."),
    ])
    def test_get_repo_root(self, git_ops, test_path, expected):
        """Test getting repo root from various paths."""
        result = git_ops.get_repo_root(test_path)
        assert result == expected

    def test_get_repo_root_from_subdirectory(self, git_ops, temp_git_repo):
        """Test getting repo root from subdirectory."""
        subdir = temp_git_repo / "subdir"
        subdir.mkdir()
        result = git_ops.get_repo_root("subdir")
        assert result == "."

    def test_get_repo_root_fails_outside_git_repo(self, temp_git_repo):
        """Test that get_repo_root fails when not in a git repository."""
        non_git_dir = temp_git_repo.parent / "non_git"
        non_git_dir.mkdir(exist_ok=True)
        git_ops = GitOperations(allowed_dir=non_git_dir)

        with pytest.raises(RuntimeError, match="Git command failed"):
            git_ops.get_repo_root(".")

        shutil.rmtree(non_git_dir)


@pytest.mark.integration
class TestGitStatus:
    """Test get_status functionality with parametrized scenarios."""

    def test_status_clean_repository(self, git_ops):
        """Test status on clean repository with no changes."""
        result = git_ops.get_status(".")
        assert result["modified"] == []
        assert result["added"] == []
        assert result["deleted"] == []
        assert result["untracked"] == []

    @pytest.mark.parametrize("setup_fn,status_key,expected_file", [
        (lambda repo: (repo / "README.md").write_text("# Modified"), "modified", "README.md"),
        (lambda repo: (repo / "new_file.txt").write_text("New"), "untracked", "new_file.txt"),
    ])
    def test_status_single_change(self, git_ops, temp_git_repo, setup_fn, status_key, expected_file):
        """Test status with various single file changes."""
        setup_fn(temp_git_repo)
        result = git_ops.get_status(".")
        assert expected_file in result[status_key]

    def test_status_staged_file(self, git_ops, temp_git_repo):
        """Test status with staged new file."""
        (temp_git_repo / "staged.txt").write_text("Staged")
        subprocess.run(["git", "add", "staged.txt"], cwd=temp_git_repo, capture_output=True)
        result = git_ops.get_status(".")
        assert "staged.txt" in result["added"]

    def test_status_deleted_file(self, git_ops, temp_git_repo):
        """Test status with deleted file."""
        (temp_git_repo / "to_delete.txt").write_text("Content")
        subprocess.run(["git", "add", "to_delete.txt"], cwd=temp_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add file"], cwd=temp_git_repo, capture_output=True)
        (temp_git_repo / "to_delete.txt").unlink()
        result = git_ops.get_status(".")
        assert "to_delete.txt" in result["deleted"]

    def test_status_from_subdirectory(self, git_ops, temp_git_repo):
        """Test status from subdirectory."""
        subdir = temp_git_repo / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("Content")
        result = git_ops.get_status("subdir")
        assert "subdir/file.txt" in result["untracked"]

    def test_status_multiple_changes(self, git_ops, temp_git_repo):
        """Test status with multiple types of changes."""
        (temp_git_repo / "README.md").write_text("# Modified")
        (temp_git_repo / "untracked.txt").write_text("Untracked")
        (temp_git_repo / "staged.txt").write_text("Staged")
        subprocess.run(["git", "add", "staged.txt"], cwd=temp_git_repo, capture_output=True)

        result = git_ops.get_status(".")
        assert "README.md" in result["modified"]
        assert "untracked.txt" in result["untracked"]
        assert "staged.txt" in result["added"]


@pytest.mark.integration
class TestGitDiff:
    """Test get_diff functionality with parametrized scenarios."""

    def test_diff_no_changes(self, git_ops):
        """Test diff on repository with no changes."""
        result = git_ops.get_diff(".")
        assert result == ""

    @pytest.mark.parametrize("file_name,content,expected_in_diff", [
        ("README.md", "# Modified Content\nNew line", [
            "README.md", "# Modified Content", "-# Test Repo", "+# Modified Content"
        ]),
    ])
    def test_diff_modified_file(self, git_ops, temp_git_repo, file_name, content, expected_in_diff):
        """Test diff with modified files."""
        (temp_git_repo / file_name).write_text(content)
        result = git_ops.get_diff(".")
        for expected in expected_in_diff:
            assert expected in result

    def test_diff_specific_file(self, git_ops, temp_git_repo):
        """Test diff for specific file."""
        (temp_git_repo / "README.md").write_text("# Modified")
        result = git_ops.get_diff(".", file_path="README.md")
        assert "README.md" in result
        assert "# Modified" in result

    def test_diff_nonexistent_file(self, git_ops):
        """Test diff for nonexistent file returns empty string."""
        result = git_ops.get_diff(".", file_path="nonexistent.txt")
        assert result == ""

    def test_diff_from_subdirectory(self, git_ops, temp_git_repo):
        """Test diff from subdirectory."""
        subdir = temp_git_repo / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("Content")
        subprocess.run(["git", "add", "."], cwd=temp_git_repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add file"], cwd=temp_git_repo, capture_output=True)
        (subdir / "file.txt").write_text("Modified Content")

        result = git_ops.get_diff("subdir")
        assert "file.txt" in result
        assert "Modified Content" in result


@pytest.mark.integration
class TestGitBranch:
    """Test get_current_branch functionality."""

    def test_current_branch_default(self, git_ops):
        """Test getting current branch on default branch."""
        result = git_ops.get_current_branch(".")
        assert result in ["main", "master"]

    @pytest.mark.parametrize("branch_name", [
        "feature-branch",
        "test-branch",
        "feature",
    ])
    def test_current_branch_after_checkout(self, git_ops, temp_git_repo, branch_name):
        """Test getting current branch after creating new branches."""
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=temp_git_repo, capture_output=True)
        result = git_ops.get_current_branch(".")
        assert result == branch_name

    def test_current_branch_from_subdirectory(self, git_ops, temp_git_repo):
        """Test getting current branch from subdirectory."""
        subdir = temp_git_repo / "subdir"
        subdir.mkdir()
        subprocess.run(["git", "checkout", "-b", "test-branch"], cwd=temp_git_repo, capture_output=True)
        result = git_ops.get_current_branch("subdir")
        assert result == "test-branch"

    def test_current_branch_detached_head(self, git_ops, temp_git_repo):
        """Test getting branch in detached HEAD state."""
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True
        )
        commit_hash = commit_result.stdout.strip()
        subprocess.run(["git", "checkout", commit_hash], cwd=temp_git_repo, capture_output=True)

        with pytest.raises(RuntimeError, match="Not currently on a branch"):
            git_ops.get_current_branch(".")


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling across domain."""

    def test_git_command_failure_non_git_dir(self, temp_git_repo):
        """Test handling of git command failures in non-git directory."""
        non_git_dir = temp_git_repo.parent / "non_git_error_test"
        non_git_dir.mkdir(exist_ok=True)
        git_ops = GitOperations(allowed_dir=non_git_dir)

        with pytest.raises(RuntimeError, match="Git command failed"):
            git_ops.get_status(".")

        with pytest.raises(RuntimeError, match="Git command failed"):
            git_ops.get_current_branch(".")

        shutil.rmtree(non_git_dir)

    def test_initialization_default(self):
        """Test GitOperations initialization with default allowed_dir."""
        git_ops = GitOperations()
        assert git_ops.allowed_dir is not None
        assert git_ops.allowed_dir.is_absolute()

    def test_initialization_custom(self, temp_git_repo):
        """Test GitOperations initialization with custom allowed_dir."""
        git_ops = GitOperations(allowed_dir=temp_git_repo)
        assert git_ops.allowed_dir == temp_git_repo.resolve()


@pytest.mark.integration
class TestToolDelegation:
    """Test that tools correctly delegate to domain."""

    def test_git_repo_root_tool(self, setup_git_test_env):
        """Test git_repo_root tool delegates to domain."""
        result = git_repo_root.invoke({"path": "."})
        assert result == "."

    @pytest.mark.parametrize("setup_fn,expected_pattern", [
        (lambda _: None, "No changes"),
        (lambda repo: (repo / "new_file.txt").write_text("New"), "Untracked: new_file.txt"),
        (lambda repo: (repo / "README.md").write_text("# Modified"), "Modified: README.md"),
    ])
    def test_git_status_tool(self, setup_git_test_env, setup_fn, expected_pattern):
        """Test git_status tool with various scenarios."""
        setup_fn(setup_git_test_env)
        result = git_status.invoke({"path": "."})
        assert expected_pattern in result

    def test_git_diff_tool_no_changes(self, setup_git_test_env):
        """Test git_diff tool with no changes."""
        result = git_diff.invoke({"path": "."})
        assert result == ""

    def test_git_diff_tool_with_changes(self, setup_git_test_env):
        """Test git_diff tool with changes."""
        (setup_git_test_env / "README.md").write_text("# Modified Content")
        result = git_diff.invoke({"path": "."})
        assert "README.md" in result
        assert "# Modified Content" in result

    def test_git_diff_tool_specific_file(self, setup_git_test_env):
        """Test git_diff tool for specific file."""
        (setup_git_test_env / "README.md").write_text("# Modified")
        result = git_diff.invoke({"path": ".", "file_path": "README.md"})
        assert "README.md" in result

    def test_git_current_branch_tool(self, setup_git_test_env):
        """Test git_current_branch tool."""
        result = git_current_branch.invoke({"path": "."})
        assert result in ["main", "master"]

    def test_git_current_branch_tool_after_checkout(self, setup_git_test_env):
        """Test git_current_branch after creating new branch."""
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=setup_git_test_env, capture_output=True)
        result = git_current_branch.invoke({"path": "."})
        assert result == "feature"

    @pytest.mark.parametrize("method,path,error_pattern", [
        ("git_status", "/etc", "Absolute paths not allowed"),
        ("git_diff", "/etc", "Absolute paths not allowed"),
        ("git_status", "../../etc", "Path outside allowed directory"),
        ("git_current_branch", "../../etc", "Path outside allowed directory"),
    ])
    def test_tools_propagate_errors(self, setup_git_test_env, method, path, error_pattern):
        """Test that domain errors are propagated through tool layer."""
        tool = get_tool_by_name(method)
        with pytest.raises(ValueError, match=error_pattern):
            tool.invoke({"path": path})


@pytest.mark.integration
class TestToolFormatting:
    """Test tool output formatting for LLM consumption."""

    def test_status_formats_multiple_changes(self, setup_git_test_env):
        """Test that git_status formats multiple changes correctly."""
        (setup_git_test_env / "README.md").write_text("# Modified")
        (setup_git_test_env / "untracked.txt").write_text("New file")
        (setup_git_test_env / "staged.txt").write_text("Staged file")
        subprocess.run(["git", "add", "staged.txt"], cwd=setup_git_test_env, capture_output=True)

        result = git_status.invoke({"path": "."})
        assert isinstance(result, str)
        assert "Modified:" in result or "Added:" in result or "Untracked:" in result

    @pytest.mark.parametrize("tool_name,invoke_fn,expected_type", [
        ("git_repo_root", lambda: git_repo_root.invoke({"path": "."}), str),
        ("git_status", lambda: git_status.invoke({"path": "."}), str),
        ("git_diff", lambda: git_diff.invoke({"path": "."}), str),
        ("git_current_branch", lambda: git_current_branch.invoke({"path": "."}), str),
    ])
    def test_tool_output_types(self, setup_git_test_env, tool_name, invoke_fn, expected_type):
        """Test that tools return correct output types."""
        result = invoke_fn()
        assert isinstance(result, expected_type)


@pytest.mark.integration
class TestToolRegistry:
    """Test tool registry infrastructure."""

    def test_registry_consistency(self):
        """Test that ALL_TOOLS and TOOLS_BY_NAME are consistent."""
        for tool in ALL_TOOLS:
            assert tool.name in TOOLS_BY_NAME
            assert TOOLS_BY_NAME[tool.name] is tool
        assert len(TOOLS_BY_NAME) == len(ALL_TOOLS)

    @pytest.mark.parametrize("tool_name,description_keyword", [
        ("git_repo_root", "repository root"),
        ("git_status", "status"),
        ("git_diff", "diff"),
        ("git_current_branch", "branch"),
    ])
    def test_tool_schemas(self, tool_name, description_keyword):
        """Test that tools have correct schemas for LLM."""
        tool = get_tool_by_name(tool_name)
        assert description_keyword in tool.description.lower()
        assert len(tool.description) >= 20
        assert tool.description != tool.name


