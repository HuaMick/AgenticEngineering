"""Task Preset Workflow - load and manage task presets.

Handles loading task presets from templates and adding them to plans.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class PresetLoadResult:
    """Result of loading a preset."""

    preset_name: str
    tasks_added: int
    tasks: list[dict] = field(default_factory=list)
    target_file: Optional[str] = None
    dry_run: bool = False


class TaskPresetWorkflow:
    """Workflow for loading task presets into plan files.

    Provides:
    - Loading preset templates from templates/presets/
    - Adding preset tasks to plan_tasks.yml files
    - Listing available presets
    """

    def __init__(self, plan_path: Path, presets_dir: Optional[Path] = None):
        """Initialize task preset workflow.

        Args:
            plan_path: Path to the plan folder.
            presets_dir: Path to presets directory. Defaults to AgenticGuidance templates.
        """
        self.plan_path = plan_path

        # Default to AgenticGuidance templates directory
        if presets_dir:
            self.presets_dir = presets_dir
        else:
            # Try to find AgenticGuidance templates directory
            self.presets_dir = self._find_presets_dir()

    def _find_presets_dir(self) -> Path:
        """Find the presets directory in AgenticGuidance."""
        # Try relative to this file
        module_root = Path(__file__).parent.parent.parent.parent.parent
        candidates = [
            module_root / "assets" / "templates" / "presets",
            module_root / "templates" / "presets",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Return a default path even if it doesn't exist
        return module_root / "assets" / "templates" / "presets"

    def list_presets(self) -> list[str]:
        """List available preset names.

        Returns:
            List of preset names (without .yml extension).
        """
        if not self.presets_dir.exists():
            return []
        return [f.stem for f in self.presets_dir.glob("*.yml")]

    def get_preset_path(self, preset_name: str) -> Path:
        """Get path to a preset file.

        Args:
            preset_name: Name of the preset (with or without .yml).

        Returns:
            Path to preset file.

        Raises:
            FileNotFoundError: If preset doesn't exist.
        """
        # Support both "planner-build" and "planner-build-preset"
        candidates = [
            self.presets_dir / f"{preset_name}.yml",
            self.presets_dir / f"{preset_name}-preset.yml",
        ]

        for path in candidates:
            if path.exists():
                return path

        raise FileNotFoundError(f"Preset '{preset_name}' not found")

    def load_preset(
        self,
        preset_name: str,
        dry_run: bool = False,
    ) -> PresetLoadResult:
        """Load a preset and add tasks to plan.

        Args:
            preset_name: Name of the preset to load.
            dry_run: If True, don't make changes.

        Returns:
            PresetLoadResult with operation details.

        Raises:
            FileNotFoundError: If preset doesn't exist.
        """
        preset_path = self.get_preset_path(preset_name)
        preset_data = yaml.safe_load(preset_path.read_text())

        tasks = preset_data.get("tasks", [])

        if dry_run:
            return PresetLoadResult(
                preset_name=preset_name,
                tasks_added=len(tasks),
                tasks=tasks,
                dry_run=True,
            )

        # Find or create target file
        target_file = self._find_or_create_task_file()

        # Load existing content
        if target_file.exists():
            content = yaml.safe_load(target_file.read_text()) or {}
        else:
            content = {
                "name": f"tasks-{self.plan_path.name}",
                "preset_source": preset_name,
                "tasks": [],
            }

        # Add tasks
        existing_tasks = content.get("tasks", [])
        existing_ids = {t.get("id") for t in existing_tasks}

        added_count = 0
        for task in tasks:
            if task.get("id") not in existing_ids:
                existing_tasks.append(task)
                added_count += 1

        content["tasks"] = existing_tasks

        # Write back
        with open(target_file, "w") as f:
            yaml.dump(content, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        return PresetLoadResult(
            preset_name=preset_name,
            tasks_added=added_count,
            tasks=tasks,
            target_file=target_file.name,
        )

    def _find_or_create_task_file(self) -> Path:
        """Find existing task file or create path for new one.

        Returns:
            Path to task file (directly in plan_path).
        """
        # Create new task file if not present
        task_file = self.plan_path / "plan_tasks.yml"
        self.plan_path.mkdir(parents=True, exist_ok=True)
        return task_file
