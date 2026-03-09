"""Tests for context service."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticguidance.services.context import (
    MainFirstEpicResolver,
    get_role_process,
    get_role_inputs_manifest,
    generate_agent_bootstrap,
    _find_agents_directory,
)


class TestMainFirstEpicResolver:
    """Tests for MainFirstEpicResolver class."""

    def test_init_defaults_to_cwd(self):
        """Test resolver defaults to current working directory."""
        resolver = MainFirstEpicResolver()
        assert resolver.cwd == Path.cwd()

    def test_init_accepts_custom_cwd(self, tmp_path):
        """Test resolver accepts custom working directory."""
        resolver = MainFirstEpicResolver(cwd=tmp_path)
        assert resolver.cwd == tmp_path

    @patch("subprocess.run")
    def test_find_main_worktree_caches_result(self, mock_run):
        """Test main worktree is cached after first lookup."""
        mock_run.return_value = MagicMock(
            stdout="worktree /home/test/project\nHEAD abc123\nbranch refs/heads/main\n",
            returncode=0,
        )

        resolver = MainFirstEpicResolver()
        # __init__ calls subprocess.run once (git rev-parse for DB path).
        # Reset count so we only measure calls from find_main_worktree.
        mock_run.reset_mock()

        result1 = resolver.find_main_worktree()
        result2 = resolver.find_main_worktree()

        assert result1 == result2
        assert mock_run.call_count == 1  # Only called once due to caching

    @patch("subprocess.run")
    def test_find_main_worktree_returns_path_for_main(self, mock_run):
        """Test returns path when main branch worktree found."""
        mock_run.return_value = MagicMock(
            stdout="worktree /home/test/project\nHEAD abc123\nbranch refs/heads/main\n",
            returncode=0,
        )

        resolver = MainFirstEpicResolver()
        result = resolver.find_main_worktree()

        assert result == Path("/home/test/project")

    @patch("subprocess.run")
    def test_find_main_worktree_returns_path_for_master(self, mock_run):
        """Test returns path when master branch worktree found."""
        mock_run.return_value = MagicMock(
            stdout="worktree /home/test/project\nHEAD abc123\nbranch refs/heads/master\n",
            returncode=0,
        )

        resolver = MainFirstEpicResolver()
        result = resolver.find_main_worktree()

        assert result == Path("/home/test/project")

    @patch("subprocess.run")
    def test_find_main_worktree_returns_none_when_not_found(self, mock_run):
        """Test returns None when no main/master worktree."""
        mock_run.return_value = MagicMock(
            stdout="worktree /home/test/feature\nHEAD abc123\nbranch refs/heads/feature\n",
            returncode=0,
        )

        resolver = MainFirstEpicResolver()
        result = resolver.find_main_worktree()

        assert result is None

    @patch("subprocess.run")
    def test_find_main_worktree_handles_git_error(self, mock_run):
        """Test handles git command failure gracefully."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        resolver = MainFirstEpicResolver()
        result = resolver.find_main_worktree()

        assert result is None

    @patch("subprocess.run")
    def test_get_current_branch_returns_branch_name(self, mock_run):
        """Test returns current branch name."""
        mock_run.return_value = MagicMock(stdout="feature-branch\n", returncode=0)

        resolver = MainFirstEpicResolver()
        result = resolver.get_current_branch()

        assert result == "feature-branch"

    @patch("subprocess.run")
    def test_get_current_branch_caches_result(self, mock_run):
        """Test branch name is cached."""
        mock_run.return_value = MagicMock(stdout="main\n", returncode=0)

        resolver = MainFirstEpicResolver()
        # __init__ calls subprocess.run once (git rev-parse for DB path).
        # Reset count so we only measure calls from get_current_branch.
        mock_run.reset_mock()

        result1 = resolver.get_current_branch()
        result2 = resolver.get_current_branch()

        assert result1 == result2
        assert mock_run.call_count == 1

    @patch("subprocess.run")
    def test_get_current_branch_handles_error(self, mock_run):
        """Test handles git error gracefully."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        resolver = MainFirstEpicResolver()
        result = resolver.get_current_branch()

        assert result is None

    def test_extract_all_tickets_returns_empty_for_missing_folder(self, tmp_path):
        """Test returns empty list when live folder doesn't exist."""
        resolver = MainFirstEpicResolver()
        result = resolver.extract_all_tickets(tmp_path)

        assert result == []

    def test_extract_all_tickets_parses_plan_file(self, tmp_path):
        """Test extracts tasks from TinyDB for a given plan folder."""
        from agenticguidance.services.epic_repository import EpicRepository

        # Create an isolated TinyDB and populate it
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        epic_dir = tmp_path / "my_epic"
        epic_dir.mkdir()

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": "my_epic",
            "epic_folder": str(epic_dir),
            "name": "My Epic",
            "status": "active",
        })
        repo.add_ticket("my_epic", "Build Phase", {
            "id": "task_001",
            "name": "First task",
            "description": "Do something",
            "status": "pending",
        })

        resolver = MainFirstEpicResolver()
        resolver._repository = repo  # Inject isolated repo

        tasks = resolver.extract_all_tickets(epic_dir)

        assert len(tasks) == 1
        assert tasks[0]["id"] == "task_001"
        assert tasks[0]["name"] == "First task"
        assert tasks[0]["status"] == "pending"
        assert tasks[0]["phase"] == "Build Phase"

        repo.close()

    def test_extract_current_ticket_returns_in_progress_first(self, tmp_path):
        """Test returns in_progress task over pending (via TinyDB)."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        epic_dir = tmp_path / "my_epic"
        epic_dir.mkdir()

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": "my_epic",
            "epic_folder": str(epic_dir),
            "name": "My Epic",
            "status": "active",
        })
        repo.add_ticket("my_epic", "Build", {
            "id": "task_001",
            "name": "Pending task",
            "status": "pending",
        })
        repo.add_ticket("my_epic", "Build", {
            "id": "task_002",
            "name": "In progress task",
            "status": "in_progress",
        })

        resolver = MainFirstEpicResolver()
        resolver._repository = repo  # Inject isolated repo

        task = resolver.extract_current_ticket(epic_dir)

        assert task["id"] == "task_002"
        assert task["status"] == "in_progress"

        repo.close()

    def test_extract_current_ticket_returns_first_pending(self, tmp_path):
        """Test returns first pending when no in_progress (via TinyDB)."""
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        epic_dir = tmp_path / "my_epic"
        epic_dir.mkdir()

        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": "my_epic",
            "epic_folder": str(epic_dir),
            "name": "My Epic",
            "status": "active",
        })
        repo.add_ticket("my_epic", "Build", {
            "id": "task_001",
            "name": "First pending",
            "status": "pending",
        })
        repo.add_ticket("my_epic", "Build", {
            "id": "task_002",
            "name": "Second pending",
            "status": "pending",
        })

        resolver = MainFirstEpicResolver()
        resolver._repository = repo  # Inject isolated repo

        task = resolver.extract_current_ticket(epic_dir)

        assert task["id"] == "task_001"

        repo.close()


class TestGetRoleProcess:
    """Tests for get_role_process function."""

    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_none_when_agents_dir_not_found(self, mock_find):
        """Test returns None when agents directory not found."""
        mock_find.return_value = None

        result = get_role_process("planner-build")

        assert result is None

    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_none_when_agent_not_found(self, mock_find, tmp_path):
        """Test returns None when specific agent not found."""
        mock_find.return_value = tmp_path

        result = get_role_process("nonexistent-agent")

        assert result is None

    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_process_data_for_valid_role(self, mock_find, tmp_path):
        """Test returns parsed process and manifest data for a valid role."""
        import yaml as _yaml

        # Create agent directory structure: category/role-id/
        agent_dir = tmp_path / "build" / "build-python"
        agent_dir.mkdir(parents=True)

        # Write process.yml
        process_data = {
            "name": "Build Python",
            "description": "Build and test Python projects",
            "steps": ["analyze", "implement", "test"],
        }
        (agent_dir / "process.yml").write_text(_yaml.dump(process_data))

        # Write manifest.yml
        manifest_data = {
            "agent": {
                "name": "Build Python Agent",
                "invocation_context": "python-build",
            }
        }
        (agent_dir / "manifest.yml").write_text(_yaml.dump(manifest_data))

        mock_find.return_value = tmp_path

        result = get_role_process("build-python")

        assert result is not None, "Should return data for a valid role"
        assert result["role_id"] == "build-python"
        assert result["category"] == "build"
        assert result["process"] is not None
        assert result["process"]["name"] == "Build Python"
        assert result["process"]["steps"] == ["analyze", "implement", "test"]
        assert result["manifest"] is not None
        assert result["manifest"]["agent"]["name"] == "Build Python Agent"
        assert result["invocation_context"] == "python-build"

    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_data_with_process_only(self, mock_find, tmp_path):
        """Test returns data when only process.yml exists (no manifest)."""
        import yaml as _yaml

        agent_dir = tmp_path / "build" / "build-go"
        agent_dir.mkdir(parents=True)

        process_data = {"name": "Build Go", "steps": ["build", "test"]}
        (agent_dir / "process.yml").write_text(_yaml.dump(process_data))

        mock_find.return_value = tmp_path

        result = get_role_process("build-go")

        assert result is not None
        assert result["process"]["name"] == "Build Go"
        assert result["manifest"] is None


class TestGetRoleInputsManifest:
    """Tests for get_role_inputs_manifest function."""

    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_none_when_agents_dir_not_found(self, mock_find):
        """Test returns None when agents directory not found."""
        mock_find.return_value = None

        result = get_role_inputs_manifest("planner-build")

        assert result is None

    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_empty_manifest_when_no_inputs_file(self, mock_find, tmp_path):
        """Test returns empty manifest when inputs.yml doesn't exist."""
        agent_dir = tmp_path / "planner" / "planner-build"
        agent_dir.mkdir(parents=True)
        mock_find.return_value = tmp_path

        result = get_role_inputs_manifest("planner-build")

        assert result == {"role": "planner-build", "inputs": [], "missing": []}

    @patch("subprocess.run")
    @patch("agenticguidance.services.context._find_agents_directory")
    def test_returns_manifest_with_path_resolution(self, mock_find, mock_subprocess, tmp_path):
        """Test returns manifest with resolved paths and existence flags."""
        import yaml as _yaml

        # Set up agent directory with inputs.yml
        agent_dir = tmp_path / "build" / "build-python"
        agent_dir.mkdir(parents=True)

        # Create some files that the inputs reference
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# main")

        inputs_data = {
            "inputs": [
                {"location": "src/main.py", "description": "Main entry point"},
                {"location": "src/missing.py", "description": "Missing module"},
            ],
            "layers": [
                {"type": "layer", "path": "assets/inputs/core.yml", "required": True},
            ],
        }
        (agent_dir / "inputs.yml").write_text(_yaml.dump(inputs_data))

        mock_find.return_value = tmp_path
        # Mock git rev-parse to return tmp_path as project root
        mock_subprocess.return_value = MagicMock(
            stdout=str(tmp_path) + "\n",
            returncode=0,
        )

        result = get_role_inputs_manifest("build-python")

        assert result is not None
        assert result["role"] == "build-python"
        assert len(result["inputs"]) == 2

        # First input should exist
        main_input = result["inputs"][0]
        assert main_input["relative_path"] == "src/main.py"
        assert main_input["exists"] is True
        assert main_input["path"] == str(tmp_path / "src" / "main.py")

        # Second input should be missing
        missing_input = result["inputs"][1]
        assert missing_input["relative_path"] == "src/missing.py"
        assert missing_input["exists"] is False

        # Missing list should contain the missing file
        assert len(result["missing"]) == 1
        assert "src/missing.py" in result["missing"]

        # Layers should be present
        assert len(result["layers"]) == 1


class TestGenerateAgentBootstrap:
    """Tests for generate_agent_bootstrap function."""

    @patch("agenticguidance.services.context._load_bootstrap_template")
    @patch("agenticguidance.services.context.get_role_process")
    def test_generates_content_from_template(self, mock_process, mock_template):
        """Test generates content with proper template substitution."""
        mock_process.return_value = {
            "role_id": "test-role",
            "category": "build",
            "process": {"name": "Test", "steps": ["do"]},
            "manifest": {
                "agent": {
                    "name": "Test Agent",
                    "bootstrap_notes": "Special test notes",
                }
            },
            "invocation_context": None,
        }
        mock_template.return_value = (
            "# {{ROLE_NAME}} Agent\n"
            "Role: {{ROLE_ID}}\n"
            "Notes: {{ROLE_SPECIFIC_NOTES}}"
        )

        result = generate_agent_bootstrap("test-role")

        assert result is not None
        assert "test-role" in result, "Should substitute ROLE_ID"
        assert "Test Agent" in result, "Should substitute ROLE_NAME from manifest"
        assert "Special test notes" in result, "Should substitute ROLE_SPECIFIC_NOTES"

    @patch("agenticguidance.services.context._load_bootstrap_template")
    @patch("agenticguidance.services.context.get_role_process")
    def test_uses_fallback_template_when_no_file(self, mock_process, mock_template):
        """Test uses inline fallback when template file not found."""
        mock_process.return_value = {
            "role_id": "fallback-role",
            "category": "build",
            "process": {"name": "Fallback"},
            "manifest": None,
            "invocation_context": None,
        }
        mock_template.return_value = None  # No template file

        result = generate_agent_bootstrap("fallback-role")

        assert result is not None
        assert "fallback-role" in result
        assert "agentic context bootstrap --role fallback-role" in result

    @patch("agenticguidance.services.context.get_role_process")
    def test_returns_none_when_role_not_found(self, mock_process):
        """Test returns None when role process not found."""
        mock_process.return_value = None

        result = generate_agent_bootstrap("nonexistent-role")

        assert result is None
