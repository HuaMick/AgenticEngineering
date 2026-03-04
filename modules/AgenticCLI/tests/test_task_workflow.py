"""Tests for TicketPresetWorkflow functionality.

Unit tests for PresetLoadResult dataclass and TicketPresetWorkflow class methods.
Note: TaskPresetWorkflow is an alias for TicketPresetWorkflow (backward compat).
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
import yaml


class TestPresetLoadResult:
    """Tests for PresetLoadResult dataclass."""

    def test_result_creation(self):
        """Test creating PresetLoadResult with required fields."""
        from agenticcli.workflows.ticket_workflow import PresetLoadResult

        result = PresetLoadResult(
            preset_name="planner-build",
            tasks_added=3,
            tasks=[{"id": "pb_001", "description": "Test"}],
        )

        assert result.preset_name == "planner-build"
        assert result.tasks_added == 3
        assert len(result.tasks) == 1
        assert result.target_file is None
        assert result.dry_run is False

    def test_result_with_all_fields(self):
        """Test PresetLoadResult with all optional fields."""
        from agenticcli.workflows.ticket_workflow import PresetLoadResult

        result = PresetLoadResult(
            preset_name="builder",
            tasks_added=5,
            tasks=[],
            target_file="plan_live_tasks.yml",
            dry_run=True,
        )

        assert result.target_file == "plan_live_tasks.yml"
        assert result.dry_run is True

    def test_result_default_tasks_list(self):
        """Test that tasks defaults to empty list."""
        from agenticcli.workflows.ticket_workflow import PresetLoadResult

        result = PresetLoadResult(
            preset_name="test",
            tasks_added=0,
        )

        assert result.tasks == []


class TestTaskPresetWorkflow:
    """Tests for TicketPresetWorkflow class (TaskPresetWorkflow is an alias)."""

    @pytest.fixture
    def temp_plan_dir(self, temp_dir):
        """Create temp plan directory structure."""
        plan_path = temp_dir / "test_plan"
        plan_path.mkdir()
        (plan_path / "live").mkdir()
        return plan_path

    @pytest.fixture
    def workflow(self, temp_plan_dir):
        """Create workflow instance with temp directory."""
        from agenticcli.workflows.ticket_workflow import TicketPresetWorkflow

        return TicketPresetWorkflow(temp_plan_dir)

    @pytest.fixture
    def preset_dir(self, temp_dir, monkeypatch):
        """Create mock presets directory."""
        from agenticcli.workflows import ticket_workflow

        preset_path = temp_dir / "presets"
        preset_path.mkdir()

        # Create sample preset files
        (preset_path / "planner-build.yml").write_text(
            "name: planner-build\ntasks: []"
        )
        (preset_path / "builder.yml").write_text(
            "name: builder\ntasks: []"
        )

        # Patch PRESETS_DIR
        monkeypatch.setattr(
            ticket_workflow.TicketPresetWorkflow,
            "PRESETS_DIR",
            preset_path
        )
        return preset_path

    def test_list_presets_returns_names(self, workflow, preset_dir):
        """Test list_presets returns preset names without extension."""
        presets = workflow.list_presets()

        assert "planner-build" in presets
        assert "builder" in presets
        assert len(presets) == 2

    def test_list_presets_empty_dir(self, workflow, temp_dir, monkeypatch):
        """Test list_presets returns empty list if no presets."""
        from agenticcli.workflows import ticket_workflow

        empty_dir = temp_dir / "empty_presets"
        empty_dir.mkdir()
        monkeypatch.setattr(
            ticket_workflow.TicketPresetWorkflow,
            "PRESETS_DIR",
            empty_dir
        )

        presets = workflow.list_presets()
        assert presets == []

    def test_list_presets_nonexistent_dir(self, workflow, monkeypatch):
        """Test list_presets returns empty list if dir doesn't exist."""
        from agenticcli.workflows import ticket_workflow

        monkeypatch.setattr(
            ticket_workflow.TicketPresetWorkflow,
            "PRESETS_DIR",
            Path("/nonexistent/path")
        )

        presets = workflow.list_presets()
        assert presets == []

    def test_get_preset_path_exact_name(self, workflow, preset_dir):
        """Test get_preset_path with exact preset name."""
        path = workflow.get_preset_path("planner-build")
        assert path.exists()
        assert path.name == "planner-build.yml"

    def test_get_preset_path_with_suffix(self, workflow, preset_dir):
        """Test get_preset_path supports -preset suffix."""
        # Create preset with -preset suffix
        (preset_dir / "test-agent-preset.yml").write_text(
            "name: test-agent\ntasks: []"
        )

        path = workflow.get_preset_path("test-agent")
        assert path.exists()

    def test_get_preset_path_not_found(self, workflow, preset_dir):
        """Test get_preset_path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            workflow.get_preset_path("nonexistent-preset")

        assert "nonexistent-preset" in str(exc_info.value)

    def test_load_preset_dry_run(self, workflow, preset_dir):
        """Test load_preset with dry_run=True doesn't write files."""
        # Create a preset with tasks
        (preset_dir / "test-preset.yml").write_text("""
name: test-preset
tasks:
  - id: "tp_001"
    description: "Test task 1"
    priority: "high"
  - id: "tp_002"
    description: "Test task 2"
    priority: "medium"
""")

        result = workflow.load_preset("test-preset", dry_run=True)

        assert result.dry_run is True
        assert result.tasks_added == 2
        assert len(result.tasks) == 2
        assert result.target_file is None  # No file written

        # Verify no file was created
        task_files = list(workflow.live_dir.glob("*.yml"))
        assert len(task_files) == 0

    def test_load_preset_dry_run_returns_tasks(self, workflow, preset_dir):
        """Test dry run returns task data for preview."""
        (preset_dir / "preview-preset.yml").write_text("""
name: preview-preset
tasks:
  - id: "pp_001"
    description: "Preview task"
""")

        result = workflow.load_preset("preview-preset", dry_run=True)

        assert result.tasks[0]["id"] == "pp_001"
        assert result.tasks[0]["description"] == "Preview task"

    def test_load_preset_creates_file(self, workflow, preset_dir):
        """Test load_preset creates task file."""
        (preset_dir / "create-preset.yml").write_text("""
name: create-preset
tasks:
  - id: "cr_001"
    description: "Create task"
    priority: "high"
""")

        result = workflow.load_preset("create-preset", dry_run=False)

        assert result.dry_run is False
        assert result.tasks_added == 1
        assert result.target_file is not None

        # Verify file was created
        task_file = workflow.live_dir / result.target_file
        assert task_file.exists()

        # Verify content
        content = yaml.safe_load(task_file.read_text())
        assert "tasks" in content
        assert any(t["id"] == "cr_001" for t in content["tasks"])

    def test_load_preset_skips_duplicates(self, workflow, preset_dir):
        """Test load_preset doesn't add duplicate task IDs."""
        (preset_dir / "dup-preset.yml").write_text("""
name: dup-preset
tasks:
  - id: "dup_001"
    description: "First add"
""")

        # First load
        result1 = workflow.load_preset("dup-preset", dry_run=False)
        assert result1.tasks_added == 1

        # Second load - same preset
        result2 = workflow.load_preset("dup-preset", dry_run=False)
        assert result2.tasks_added == 0  # No new tasks added

        # Verify only one task in file
        task_file = workflow.live_dir / result1.target_file
        content = yaml.safe_load(task_file.read_text())
        dup_tasks = [t for t in content["tasks"] if t["id"] == "dup_001"]
        assert len(dup_tasks) == 1

    def test_load_preset_appends_to_existing(self, workflow, preset_dir):
        """Test load_preset appends new tasks to existing file."""
        # Create first preset
        (preset_dir / "first-preset.yml").write_text("""
name: first-preset
tasks:
  - id: "first_001"
    description: "First preset task"
""")

        # Create second preset
        (preset_dir / "second-preset.yml").write_text("""
name: second-preset
tasks:
  - id: "second_001"
    description: "Second preset task"
""")

        # Load first preset
        result1 = workflow.load_preset("first-preset", dry_run=False)
        assert result1.tasks_added == 1

        # Load second preset - should append
        result2 = workflow.load_preset("second-preset", dry_run=False)
        assert result2.tasks_added == 1

        # Verify both tasks in file
        task_file = workflow.live_dir / result1.target_file
        content = yaml.safe_load(task_file.read_text())
        task_ids = [t["id"] for t in content["tasks"]]
        assert "first_001" in task_ids
        assert "second_001" in task_ids
