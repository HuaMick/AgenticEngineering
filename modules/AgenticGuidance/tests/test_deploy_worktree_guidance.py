"""Tests verifying simplified deploy-worktree agent guidance."""

from pathlib import Path

import pytest
import yaml


AGENT_DIR = Path(__file__).parent.parent / "agents" / "deploy" / "deploy-worktree"


@pytest.fixture
def process_yml():
    """Load process.yml."""
    with open(AGENT_DIR / "process.yml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def inputs_yml():
    """Load inputs.yml."""
    with open(AGENT_DIR / "inputs.yml") as f:
        return yaml.safe_load(f)


@pytest.fixture
def manifest_yml():
    """Load manifest.yml."""
    with open(AGENT_DIR / "manifest.yml") as f:
        return yaml.safe_load(f)


class TestProcessYml:
    """Validate simplified process.yml structure."""

    def test_has_exactly_3_steps(self, process_yml):
        """Process should have exactly 3 steps (down from 7)."""
        steps = process_yml["process"]["steps"]
        assert len(steps) == 3

    def test_step_1_is_bootstrap(self, process_yml):
        """Step 1 should be CCI Bootstrap."""
        step = process_yml["process"]["steps"][0]
        assert "CCI BOOTSTRAP" in step

    def test_step_2_runs_cli(self, process_yml):
        """Step 2 should run agentic plan init."""
        step = process_yml["process"]["steps"][1]
        assert "agentic plan init" in step

    def test_step_3_reports_outputs(self, process_yml):
        """Step 3 should report outputs."""
        step = process_yml["process"]["steps"][2]
        assert "worktree_path" in step
        assert "plan_folder_path" in step
        assert "main_worktree_path" in step

    def test_no_manual_git_commands(self, process_yml):
        """Process should not reference manual git worktree commands."""
        content = yaml.dump(process_yml)
        assert "git worktree add" not in content
        assert "git worktree remove" not in content
        assert "git -C" not in content

    def test_no_manual_workspace_update_step(self, process_yml):
        """Process should not instruct agent to manually update workspace files."""
        steps = process_yml["process"]["steps"]
        for step in steps:
            # "Do NOT create folders manually" is acceptable (it forbids manual work)
            # But steps like "Update VS Code workspace file:" should not exist
            assert "Update VS Code workspace" not in step

    def test_required_outputs_present(self, process_yml):
        """All required outputs should be declared."""
        outputs = process_yml["process"]["outputs"]
        output_names = {o["name"] for o in outputs}
        expected = {"worktree_path", "plan_folder_path", "main_worktree_path",
                    "workspace_updated", "validation_status"}
        assert expected == output_names


class TestInputsYml:
    """Validate simplified inputs.yml definitions."""

    def test_no_git_worktree_commands(self, inputs_yml):
        """inputs.yml should not contain git_worktree_commands definition."""
        definitions = inputs_yml["inputs"].get("definitions", {})
        assert "git_worktree_commands" not in definitions

    def test_no_worktree_operations(self, inputs_yml):
        """inputs.yml should not contain worktree_operations definition."""
        definitions = inputs_yml["inputs"].get("definitions", {})
        assert "worktree_operations" not in definitions

    def test_no_workspace_file_definition(self, inputs_yml):
        """inputs.yml should not contain workspace_file definition."""
        definitions = inputs_yml["inputs"].get("definitions", {})
        assert "workspace_file" not in definitions

    def test_keeps_worktree_naming_convention(self, inputs_yml):
        """inputs.yml should keep worktree_naming_convention definition."""
        definitions = inputs_yml["inputs"].get("definitions", {})
        assert "worktree_naming_convention" in definitions

    def test_keeps_planning_scaffolding(self, inputs_yml):
        """inputs.yml should keep planning_scaffolding definition."""
        definitions = inputs_yml["inputs"].get("definitions", {})
        assert "planning_scaffolding" in definitions

    def test_has_cli_commands_reference(self, inputs_yml):
        """inputs.yml should have cli_commands definition."""
        definitions = inputs_yml["inputs"].get("definitions", {})
        assert "cli_commands" in definitions
        assert "agentic plan init" in definitions["cli_commands"]


class TestManifestYml:
    """Validate simplified manifest.yml."""

    def test_description_references_cli(self, manifest_yml):
        """Manifest description should reference CLI delegation."""
        desc = manifest_yml["description"]
        assert "CLI" in desc or "cli" in desc or "agentic" in desc

    def test_boundaries_no_manual_git(self, manifest_yml):
        """Boundaries should state no manual git commands."""
        boundaries = manifest_yml["boundaries"]
        boundary_text = " ".join(boundaries)
        assert "manual git" in boundary_text.lower() or "NOT run manual" in boundary_text

    def test_version_updated(self, manifest_yml):
        """Version should be 2.1 reflecting simplification."""
        assert manifest_yml["version"] == "2.1"
