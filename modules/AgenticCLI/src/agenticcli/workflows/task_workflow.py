"""Task workflow - CLI-adapted wrapper around AgenticGuidance preset service.

Provides TaskPresetWorkflow with CLI-specific conventions:
- PRESETS_DIR class attribute for monkeypatching in tests
- live_dir instance attribute pointing to plan's live subdirectory
- File operations target live_dir instead of plan_path directly
"""

from pathlib import Path
from typing import Optional

import yaml

from agenticguidance.services.preset import PresetLoadResult


class TaskPresetWorkflow:
    """CLI-adapted workflow for loading task presets into plan files.

    Differences from agenticguidance.services.preset.TaskPresetWorkflow:
    - PRESETS_DIR class attribute for preset discovery
    - live_dir for file output (plan_path / "live")
    """

    PRESETS_DIR: Path = Path(__file__).parent.parent.parent.parent.parent / "AgenticGuidance" / "assets" / "templates" / "presets"

    def __init__(self, plan_path: Path, presets_dir: Optional[Path] = None):
        self.plan_path = plan_path
        self.live_dir = plan_path / "live"
        self.live_dir.mkdir(parents=True, exist_ok=True)

    @property
    def presets_dir(self) -> Path:
        return self.PRESETS_DIR

    def list_presets(self) -> list[str]:
        if not self.presets_dir.exists():
            return []
        return [f.stem for f in self.presets_dir.glob("*.yml")]

    def get_preset_path(self, preset_name: str) -> Path:
        candidates = [
            self.presets_dir / f"{preset_name}.yml",
            self.presets_dir / f"{preset_name}-preset.yml",
        ]
        for path in candidates:
            if path.exists():
                return path
        raise FileNotFoundError(f"Preset '{preset_name}' not found")

    def load_preset(self, preset_name: str, dry_run: bool = False) -> PresetLoadResult:
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

        target_file = self._find_or_create_task_file()

        if target_file.exists():
            content = yaml.safe_load(target_file.read_text()) or {}
        else:
            content = {
                "name": f"tasks-{self.plan_path.name}",
                "preset_source": preset_name,
                "tasks": [],
            }

        existing_tasks = content.get("tasks", [])
        existing_ids = {t.get("id") for t in existing_tasks}

        added_count = 0
        for task in tasks:
            if task.get("id") not in existing_ids:
                existing_tasks.append(task)
                added_count += 1

        content["tasks"] = existing_tasks

        with open(target_file, "w") as f:
            yaml.dump(content, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        return PresetLoadResult(
            preset_name=preset_name,
            tasks_added=added_count,
            tasks=tasks,
            target_file=target_file.name,
        )

    def _find_or_create_task_file(self) -> Path:
        task_file = self.live_dir / "plan_tasks.yml"
        if task_file.exists():
            return task_file

        for f in self.live_dir.glob("plan_*.yml"):
            return f

        self.live_dir.mkdir(parents=True, exist_ok=True)
        return task_file


__all__ = [
    "PresetLoadResult",
    "TaskPresetWorkflow",
]
