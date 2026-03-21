"""Story data model and service for user story management."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# Lifecycle states and allowed transitions
LIFECYCLE_STATES = ("proposal", "under-construction", "implemented", "deprecated", "archived")
LIFECYCLE_TRANSITIONS = {
    "proposal": ["under-construction"],
    "under-construction": ["implemented"],
    "implemented": ["deprecated"],
    "deprecated": ["archived"],
    "archived": [],
}


@dataclass
class Story:
    """Represents a single user story."""
    id: str
    title: str
    category: str = ""
    priority: str = "medium"
    description: str = ""
    steps: list[dict] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    test_status: str = ""
    last_tested: str = ""
    test_notes: str = ""
    tested_by_plan: str = ""
    related_stories: list[str] = field(default_factory=list)
    related_commands: list[str] = field(default_factory=list)
    source_file: str = ""
    project: str = ""
    lifecycle: str = "implemented"

    @property
    def prefix(self) -> str:
        """Extract category prefix (e.g., 'US-SET' from 'US-SET-001')."""
        match = re.match(r"(US-[A-Z]+)", self.id)
        return match.group(1) if match else "OTHER"

    def can_transition_to(self, target: str) -> bool:
        """Check if transitioning to the target lifecycle state is allowed."""
        if self.lifecycle not in LIFECYCLE_TRANSITIONS:
            return False
        return target in LIFECYCLE_TRANSITIONS[self.lifecycle]


class StoryService:
    """Service for loading and querying user stories."""

    def __init__(self, userstories_dir: Path | None = None):
        self._userstories_dir = userstories_dir or self._find_userstories_dir()
        self._stories: list[Story] | None = None

    @staticmethod
    def _find_userstories_dir() -> Path | None:
        # Check AGENTIC_REPO_ROOT env var first
        env_root = os.environ.get("AGENTIC_REPO_ROOT")
        if env_root:
            candidate = Path(env_root) / "docs" / "userstories"
            if candidate.is_dir():
                return candidate

        # Check hardcoded search paths relative to cwd
        search_paths = [
            Path.cwd() / "docs" / "userstories",
            Path.cwd().parent / "docs" / "userstories",
            Path.cwd() / "userstories",
        ]
        for path in search_paths:
            if path.exists():
                return path

        # Walk up to 5 parents looking for a .git directory
        current = Path.cwd()
        for _ in range(5):
            if (current / ".git").is_dir():
                candidate = current / "docs" / "userstories"
                if candidate.is_dir():
                    return candidate
                break
            parent = current.parent
            if parent == current:
                break
            current = parent

        return None

    def load_all(self) -> list[Story]:
        """Load all stories from YAML files. Caches result."""
        if self._stories is not None:
            return self._stories

        if not self._userstories_dir or not self._userstories_dir.exists():
            self._stories = []
            return self._stories

        stories = []
        for yml_file in sorted(self._userstories_dir.glob("**/*.yml")):
            if yml_file.name == "00_metadata.yml":
                continue
            stories.extend(self._parse_file(yml_file))

        self._stories = stories
        return self._stories

    def _parse_file(self, path: Path) -> list[Story]:
        """Parse a single YAML story file into Story objects."""
        try:
            content = yaml.safe_load(path.read_text())
        except Exception:
            return []

        if not content or not isinstance(content, dict):
            return []

        result = []
        # Determine project from directory structure
        rel = path.relative_to(self._userstories_dir) if self._userstories_dir else path
        project = rel.parts[0] if len(rel.parts) > 1 else ""

        for key in ("stories", "user_stories"):
            items = content.get(key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or "id" not in item:
                    continue
                story = Story(
                    id=item["id"],
                    title=item.get("title", ""),
                    category=item.get("category", ""),
                    priority=item.get("priority", "medium"),
                    description=item.get("description", ""),
                    steps=item.get("journey", item.get("steps", [])),
                    success_criteria=item.get("success_criteria", []),
                    test_status=item.get("test_status", ""),
                    last_tested=item.get("last_tested", ""),
                    test_notes=item.get("test_notes", ""),
                    tested_by_plan=item.get("tested_by_plan", ""),
                    related_stories=item.get("related_stories", []),
                    related_commands=item.get("related_commands", []),
                    source_file=str(path),
                    project=project,
                    lifecycle=item.get("lifecycle", "implemented"),
                )
                result.append(story)
        return result

    def get_by_id(self, story_id: str) -> Story | None:
        """Find a story by its ID."""
        for story in self.load_all():
            if story.id == story_id:
                return story
        return None

    def get_by_category(self, category: str) -> list[Story]:
        """Get all stories matching a category prefix (e.g., 'US-SET')."""
        prefix = category.upper()
        return [s for s in self.load_all() if s.prefix == prefix or s.category.lower() == category.lower()]

    def get_by_project(self, project: str) -> list[Story]:
        """Get all stories for a project."""
        proj_lower = project.lower()
        return [s for s in self.load_all() if proj_lower in s.project.lower()]

    def all_ids(self) -> frozenset[str]:
        """Return all valid story IDs."""
        return frozenset(s.id for s in self.load_all())

    def update_lifecycle(self, story_id: str, new_status: str) -> bool:
        """Update the lifecycle state of a story (writes back to YAML).

        Only allows valid transitions as defined in LIFECYCLE_TRANSITIONS.
        """
        if new_status not in LIFECYCLE_STATES:
            return False

        story = self.get_by_id(story_id)
        if not story or not story.source_file:
            return False

        if not story.can_transition_to(new_status):
            return False

        path = Path(story.source_file)
        try:
            content = yaml.safe_load(path.read_text())
        except Exception:
            return False

        if not content or not isinstance(content, dict):
            return False

        for key in ("stories", "user_stories"):
            items = content.get(key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and item.get("id") == story_id:
                    item["lifecycle"] = new_status
                    path.write_text(yaml.dump(content, sort_keys=False, default_flow_style=False))
                    self._stories = None
                    return True
        return False

    def update_test_status(
        self,
        story_id: str,
        status: str,
        tested_by: str = "",
        test_notes: str = "",
        last_tested: str = "",
    ) -> bool:
        """Update test status for a story (writes back to YAML)."""
        story = self.get_by_id(story_id)
        if not story or not story.source_file:
            return False

        path = Path(story.source_file)
        try:
            content = yaml.safe_load(path.read_text())
        except Exception:
            return False

        if not content or not isinstance(content, dict):
            return False

        for key in ("stories", "user_stories"):
            items = content.get(key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and item.get("id") == story_id:
                    item["test_status"] = status
                    if tested_by:
                        item["tested_by_plan"] = tested_by
                    if test_notes:
                        item["test_notes"] = test_notes
                    if last_tested:
                        item["last_tested"] = last_tested
                    path.write_text(yaml.dump(content, sort_keys=False, default_flow_style=False))
                    # Invalidate cache
                    self._stories = None
                    return True
        return False
