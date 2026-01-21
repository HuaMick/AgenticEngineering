"""Tests for preset template YAML validity.

Validates that all preset template files have correct structure and required fields.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
import yaml


class TestPresetTemplates:
    """Tests for preset template files."""

    PRESETS_DIR = Path(__file__).parent.parent / "src" / "agenticcli" / "templates" / "presets"

    def get_preset_files(self):
        """Get all preset YAML files."""
        if not self.PRESETS_DIR.exists():
            pytest.skip("Presets directory not found")
        return list(self.PRESETS_DIR.glob("*.yml"))

    def test_presets_dir_exists(self):
        """Test presets directory exists."""
        assert self.PRESETS_DIR.exists(), "presets/ directory should exist"

    def test_presets_dir_contains_files(self):
        """Test presets directory has preset files."""
        files = self.get_preset_files()
        assert len(files) > 0, "presets/ should contain at least one .yml file"

    def test_all_presets_valid_yaml(self):
        """Test all preset files are valid YAML."""
        for preset_file in self.get_preset_files():
            try:
                content = yaml.safe_load(preset_file.read_text())
                assert content is not None, f"{preset_file.name} is empty"
            except yaml.YAMLError as e:
                pytest.fail(f"{preset_file.name} has invalid YAML: {e}")

    def test_all_presets_have_required_fields(self):
        """Test all presets have name and tasks fields."""
        for preset_file in self.get_preset_files():
            content = yaml.safe_load(preset_file.read_text())

            assert "name" in content, f"{preset_file.name} missing 'name'"
            assert "tasks" in content, f"{preset_file.name} missing 'tasks'"
            assert isinstance(content["tasks"], list), f"{preset_file.name} 'tasks' must be list"

    def test_all_tasks_have_required_fields(self):
        """Test all tasks in presets have id and description."""
        for preset_file in self.get_preset_files():
            content = yaml.safe_load(preset_file.read_text())

            for i, task in enumerate(content.get("tasks", [])):
                assert "id" in task, f"{preset_file.name} task {i} missing 'id'"
                assert "description" in task, f"{preset_file.name} task {i} missing 'description'"

    def test_task_ids_unique_within_preset(self):
        """Test task IDs are unique within each preset."""
        for preset_file in self.get_preset_files():
            content = yaml.safe_load(preset_file.read_text())
            task_ids = [t.get("id") for t in content.get("tasks", [])]

            assert len(task_ids) == len(set(task_ids)), \
                f"{preset_file.name} has duplicate task IDs"

    def test_priority_values_valid(self):
        """Test priority values are low/medium/high if specified."""
        valid_priorities = {"low", "medium", "high"}

        for preset_file in self.get_preset_files():
            content = yaml.safe_load(preset_file.read_text())

            for task in content.get("tasks", []):
                if "priority" in task:
                    assert task["priority"] in valid_priorities, \
                        f"{preset_file.name} task {task.get('id')} has invalid priority"

    def test_preset_names_match_convention(self):
        """Test preset names follow naming convention."""
        for preset_file in self.get_preset_files():
            content = yaml.safe_load(preset_file.read_text())
            name = content.get("name", "")

            # Name should be lowercase with hyphens
            assert name == name.lower(), f"{preset_file.name} name should be lowercase"
            assert "_" not in name or "-" in name, f"{preset_file.name} should use hyphens"

    def test_planner_build_preset_exists(self):
        """Test planner-build preset exists (core preset)."""
        preset_files = [f.stem for f in self.get_preset_files()]
        assert any("planner-build" in f for f in preset_files), \
            "planner-build-preset.yml should exist"

    def test_builder_preset_exists(self):
        """Test builder preset exists (core preset)."""
        preset_files = [f.stem for f in self.get_preset_files()]
        assert any("builder" in f for f in preset_files), \
            "builder-preset.yml should exist"

    def test_preset_has_description(self):
        """Test presets have description field for documentation."""
        for preset_file in self.get_preset_files():
            content = yaml.safe_load(preset_file.read_text())
            # Description is recommended but not strictly required
            if "description" in content:
                assert isinstance(content["description"], str), \
                    f"{preset_file.name} description should be string"

    def test_preset_task_ids_follow_convention(self):
        """Test task IDs follow naming convention (prefix_NNN)."""
        import re
        pattern = re.compile(r"^[a-z]+_\d{3}$")

        for preset_file in self.get_preset_files():
            content = yaml.safe_load(preset_file.read_text())

            for task in content.get("tasks", []):
                task_id = task.get("id", "")
                assert pattern.match(task_id), \
                    f"{preset_file.name} task ID '{task_id}' should follow prefix_NNN pattern"
