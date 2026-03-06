"""Ticket workflow - CLI-adapted wrapper around AgenticGuidance preset service.

Provides TicketPresetWorkflow with CLI-specific conventions:
- PRESETS_DIR class attribute for monkeypatching in tests
- Loads ticket presets into TinyDB via EpicRepository
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

import yaml

from agenticguidance.services.preset import PresetLoadResult

logger = logging.getLogger(__name__)


class TicketPresetWorkflow:
    """CLI-adapted workflow for loading ticket presets into TinyDB.

    Loads preset template YAML files and adds their tickets to TinyDB
    via EpicRepository.
    """

    PRESETS_DIR: Path = Path(__file__).parent.parent.parent.parent.parent / "AgenticGuidance" / "assets" / "templates" / "presets"

    def __init__(self, plan_path: Path, presets_dir: Optional[Path] = None):
        self.plan_path = plan_path
        self.live_dir = plan_path / "live"
        self.live_dir.mkdir(parents=True, exist_ok=True)

        # Initialize EpicRepository for TinyDB-based operations
        self._repository = None
        try:
            from agenticguidance.services.epic_repository import EpicRepository

            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    capture_output=True, text=True, check=True,
                    cwd=str(plan_path),
                )
                repo_root = Path(result.stdout.strip())
            except subprocess.CalledProcessError:
                repo_root = plan_path
            db_path = repo_root / ".agentic" / "epics.db"
            self._repository = EpicRepository(db_path=db_path)
        except Exception:
            logger.warning("Failed to initialize EpicRepository for TicketPresetWorkflow")

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
        """Load a preset template and add its tickets to TinyDB.

        Args:
            preset_name: Name of the preset template to load.
            dry_run: If True, don't actually add tickets.

        Returns:
            PresetLoadResult with operation outcome.
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

        epic_folder_name = self.plan_path.name

        if self._repository is None:
            return PresetLoadResult(
                preset_name=preset_name,
                tasks_added=0,
                tasks=tasks,
                target_file="(TinyDB unavailable)",
            )

        # Get existing ticket IDs to avoid duplicates
        try:
            existing_tickets = self._repository.get_tickets(epic_folder_name)
            existing_ids = {t.id for t in existing_tickets}
        except Exception:
            existing_ids = set()

        added_count = 0
        phase_name = preset_data.get("phase_name", f"Preset: {preset_name}")

        # Ensure the phase exists
        try:
            self._repository.add_phase(
                epic_folder_name,
                {"phase_name": phase_name, "description": f"Loaded from preset: {preset_name}"},
            )
        except Exception:
            pass  # Phase may already exist

        for task in tasks:
            task_id = task.get("id", "")
            if task_id and task_id not in existing_ids:
                try:
                    self._repository.add_ticket(
                        epic_folder_name,
                        phase_name,
                        {
                            "task_id": task_id,
                            "name": task.get("name", ""),
                            "description": task.get("description", ""),
                            "status": task.get("status", "pending"),
                            "agent": task.get("agent_type", ""),
                            "inputs": task.get("inputs", []),
                            "target_files": task.get("target_files", []),
                            "guidance": task.get("guidance", ""),
                        },
                    )
                    added_count += 1
                except Exception:
                    logger.warning("Failed to add ticket %s to TinyDB", task_id)

        return PresetLoadResult(
            preset_name=preset_name,
            tasks_added=added_count,
            tasks=tasks,
            target_file="(TinyDB)",
        )


__all__ = [
    "PresetLoadResult",
    "TicketPresetWorkflow",
]
