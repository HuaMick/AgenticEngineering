# story: US-STR-001
"""Story data model and service for user story management."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import yaml

from .state import FileLock

logger = logging.getLogger(__name__)

# Sentinel returned by _git_changed_files_since() when the commit is unreachable.
# Callers distinguish: None = transient/unknown error; ANCHOR_UNREACHABLE = commit GC'd or squash-merged.
ANCHOR_UNREACHABLE = object()

# 7-value canonical status enum for story health.
StoryStatus = Literal["broken", "stale", "never-passed", "untested", "passing", "uat-verified", "archived"]

# Sort order for triage: lower index = higher priority.
STORY_STATUS_SORT_ORDER: dict[str, int] = {
    "broken": 0,
    "stale": 1,
    "never-passed": 2,
    "untested": 3,
    "passing": 4,
    "uat-verified": 5,
    "archived": 6,
}

# --- Canonical story path resolvers ---
# @story US-001


def get_canonical_stories_dir() -> Path | None:
    """Return the single source-of-truth directory for all user stories.

    Resolution order:
    1. ``AGENTIC_REPO_ROOT`` env-var  →  ``$AGENTIC_REPO_ROOT/docs/userstories``
    2. Common relative paths from cwd (``docs/userstories``, ``../docs/userstories``,
       ``userstories``)
    3. Walk up to 5 parent directories looking for a ``.git`` marker, then
       check ``<repo-root>/docs/userstories``

    Returns ``None`` when no directory can be located.
    """
    # 1. AGENTIC_REPO_ROOT env var
    env_root = os.environ.get("AGENTIC_REPO_ROOT")
    if env_root:
        candidate = Path(env_root) / "docs" / "userstories"
        if candidate.is_dir():
            return candidate

    # 2. Check common relative paths from cwd
    search_paths = [
        Path.cwd() / "docs" / "userstories",
        Path.cwd().parent / "docs" / "userstories",
        Path.cwd() / "userstories",
    ]
    for path in search_paths:
        if path.exists():
            return path

    # 3. Walk up to 5 parents looking for .git to find repo root
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


def get_epic_stories_path(epic_name: str) -> Path:
    """Return the canonical path for an epic-scoped story file.

    Convention: ``docs/userstories/EpicStories/<epic_name>.yml``

    The returned path may not exist yet (the caller is responsible for
    creating the file/directory as needed).  The ``EpicStories/`` subdirectory
    is auto-created when the parent ``docs/userstories/`` directory is present.
    """
    stories_dir = get_canonical_stories_dir()
    if stories_dir is None:
        # Fall back to a reasonable default even when the dir is missing
        return Path("docs") / "userstories" / "EpicStories" / f"{epic_name}.yml"
    return stories_dir / "EpicStories" / f"{epic_name}.yml"


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
class Pattern:
    """Represents a reusable cross-cutting verification pattern."""
    id: str
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    applicable_categories: list[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    source_file: str = ""
    watch_files: list[str] = field(default_factory=list)

    @property
    def domain(self) -> str:
        """Extract domain from pattern ID (e.g., 'CLI' from 'PAT-CLI-001')."""
        match = re.match(r"PAT-([A-Z]{2,4})", self.id)
        return match.group(1) if match else "OTHER"

    @property
    def required_parameters(self) -> list[str]:
        """Return names of required parameters."""
        return [
            name for name, spec in self.parameters.items()
            if isinstance(spec, dict) and spec.get("required", True)
        ]

    def resolve(self, bindings: dict) -> dict:
        """Resolve verification steps by substituting parameter bindings.

        Returns a copy of the verification dict with {param} placeholders
        replaced by bound values.
        """
        import copy
        import json

        resolved = copy.deepcopy(self.verification)
        text = json.dumps(resolved)
        for key, value in bindings.items():
            placeholder = "{" + key + "}"
            replacement = str(value) if not isinstance(value, list) else ", ".join(str(v) for v in value)
            text = text.replace(placeholder, replacement)
        return json.loads(text)


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
    related_files: list[str] = field(default_factory=list)
    last_pass_commit: str = ""
    last_uat_commit: str = ""
    source_file: str = ""
    project: str = ""
    lifecycle: str = "implemented"
    inherits_patterns: list[dict] = field(default_factory=list)
    flaky: bool = False
    last_pass_tree_hash: str = ""

    @property
    def prefix(self) -> str:
        """Extract category prefix from a story ID.

        Handles both manual story IDs (e.g., 'US-SET' from 'US-SET-001') and
        epic-namespaced story IDs (e.g., 'US-260402AG' from 'US-260402AG-001').
        The pattern matches alphanumeric characters after 'US-', so both
        all-letter prefixes and digit+letter epic prefixes are supported.
        """
        match = re.match(r"(US-[A-Z0-9]+)", self.id)
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
        """Delegate to the canonical resolver ``get_canonical_stories_dir()``."""
        return get_canonical_stories_dir()

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
            raw = path.read_text()
        except FileNotFoundError:
            logger.warning("Story file not found: %s", path)
            return []
        except OSError as e:
            logger.warning("Could not read story file %s: %s", path, e)
            return []

        if not raw.strip():
            logger.warning("Story file is empty: %s", path)
            return []

        try:
            content = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            logger.warning("YAML syntax error in story file %s: %s", path, e)
            return []

        if not content or not isinstance(content, dict):
            logger.warning(
                "Story file %s has unexpected content type: %s (expected dict)",
                path,
                type(content).__name__,
            )
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
                    related_files=item.get("related_files", []),
                    last_pass_commit=item.get("last_pass_commit", ""),
                    last_uat_commit=item.get("last_uat_commit", ""),
                    source_file=str(path),
                    project=project,
                    lifecycle=item.get("lifecycle", "implemented"),
                    inherits_patterns=item.get("inherits_patterns", []),
                    flaky=item.get("flaky", False),
                    last_pass_tree_hash=item.get("last_pass_tree_hash", ""),
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
        Uses FileLock for atomic read-modify-write to prevent corruption
        from concurrent updates.
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
            with FileLock(path):
                content = yaml.safe_load(path.read_text())

                if not content or not isinstance(content, dict):
                    return False

                for key in ("stories", "user_stories"):
                    items = content.get(key, [])
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if isinstance(item, dict) and item.get("id") == story_id:
                            item["lifecycle"] = new_status
                            path.write_text(
                                yaml.dump(content, sort_keys=False, default_flow_style=False)
                            )
                            self._stories = None
                            return True
        except TimeoutError:
            logger.error(
                "FileLock timeout updating lifecycle for %s in %s",
                story_id, path,
            )
            return False
        except Exception:
            return False
        return False

    def update_test_status(
        self,
        story_id: str,
        status: str,
        tested_by: str = "",
        test_notes: str = "",
        last_tested: str = "",
        commit: str = "",
        commit_kind: str = "test",
    ) -> bool:
        """Update test status for a story (writes back to YAML).

        Uses FileLock for atomic read-modify-write to prevent corruption
        from concurrent updates.

        When ``commit`` is supplied and ``status`` indicates a pass
        (``pass`` or ``passing``), the commit hash is written to
        ``last_pass_commit`` (``commit_kind="test"``) or ``last_uat_commit``
        (``commit_kind="uat"``) in the same atomic write. This prevents
        the two-write-path gap where a story could be recorded as passing
        with no commit hash attached.
        """
        story = self.get_by_id(story_id)
        if not story or not story.source_file:
            return False

        path = Path(story.source_file)
        try:
            with FileLock(path):
                content = yaml.safe_load(path.read_text())

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
                            if commit and status in ("pass", "passing"):
                                field = (
                                    "last_uat_commit"
                                    if commit_kind == "uat"
                                    else "last_pass_commit"
                                )
                                item[field] = commit
                            path.write_text(
                                yaml.dump(content, sort_keys=False, default_flow_style=False)
                            )
                            # Invalidate cache
                            self._stories = None
                            return True
        except TimeoutError:
            logger.error(
                "FileLock timeout updating test_status for %s in %s",
                story_id, path,
            )
            return False
        except Exception:
            return False
        return False

    def update_commit_status(
        self,
        story_id: str,
        commit: str,
        commit_type: str = "test",
    ) -> bool:
        """Update the commit hash where tests or UAT last passed.

        Args:
            story_id: The story ID to update.
            commit: Short or full git commit hash.
            commit_type: "test" updates last_pass_commit, "uat" updates last_uat_commit.

        Returns True on success, False on failure.
        """
        field_name = "last_uat_commit" if commit_type == "uat" else "last_pass_commit"

        story = self.get_by_id(story_id)
        if not story or not story.source_file:
            return False

        path = Path(story.source_file)
        try:
            with FileLock(path):
                content = yaml.safe_load(path.read_text())
                if not content or not isinstance(content, dict):
                    return False

                for key in ("stories", "user_stories"):
                    items = content.get(key, [])
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if isinstance(item, dict) and item.get("id") == story_id:
                            item[field_name] = commit
                            path.write_text(
                                yaml.dump(content, sort_keys=False, default_flow_style=False)
                            )
                            self._stories = None
                            return True
        except TimeoutError:
            logger.error("FileLock timeout updating %s for %s", field_name, story_id)
            return False
        except Exception:
            return False
        return False

    def get_stale_stories(
        self,
        repo_root: Path | None = None,
        global_watch: list[str] | None = None,
    ) -> list[Story]:
        """Return stories whose watched files changed since last_pass_commit.

        A story is stale when:
        - It has related_files AND last_pass_commit set
        - git diff shows at least one file in (related_files | global_watch) changed since that commit

        Args:
            repo_root: Git repository root. If None, auto-detected from cwd.
            global_watch: Optional extra file patterns to include in the staleness diff.
                When provided, any change in global_watch also triggers staleness.
                Pass the result of expand_watch_patterns() for glob-expanded paths.
        """
        if repo_root is None:
            repo_root = _find_repo_root()
        if repo_root is None:
            return []

        extra = set(global_watch or [])

        stale = []
        for story in self.load_all():
            if not story.related_files or not story.last_pass_commit:
                continue
            watch_set = set(story.related_files) | extra
            changed = _git_changed_files_since(story.last_pass_commit, repo_root)
            if changed is None or changed is ANCHOR_UNREACHABLE:
                continue
            if watch_set & changed:
                stale.append(story)
        return stale

    def compute_story_status(
        self,
        story: Story,
        repo_root: Path | None = None,
        story_markers: set[str] | None = None,
        global_watch: list[str] | None = None,
        pattern_watch: dict[str, str] | None = None,
    ) -> str:
        """Compute effective status for a story using the 7-value canonical enum.

        Priority order (first match wins):
          1. archived   — lifecycle is deprecated or archived
          2. unhealthy  — test_status is fail or regression
          3. never-passed / no-test — test not passing and no last_pass_commit
          4. stale      — files changed since last_pass_commit (or anchor unreachable)
          5. uat-verified — last_uat_commit matches last_pass_commit (simple equality check;
                            full git-ancestry comparison is not implemented — when commits differ,
                            we conservatively treat the story as passing, not uat-verified)
          6. passing    — default

        Args:
            story: The story to evaluate.
            repo_root: Git repository root. If None, auto-detected from cwd.
            story_markers: Set of story IDs that have a @pytest.mark.story marker in tests.
                When provided, distinguishes never-passed from no-test.
                When None, all untested stories degrade to no-test.
            global_watch: Extra file patterns (already expanded) included in staleness diff.
        """
        # 1. Archived / deprecated lifecycle overrides everything.
        if story.lifecycle in ("deprecated", "archived"):
            return "archived"

        ts = (story.test_status or "").lower()

        # 2. Failing test.
        if ts in ("fail", "regression"):
            return "broken"

        # 3. Not yet passing — distinguish never-passed from no-test.
        #    Also guard: "passing" without a recorded commit hash is unearned
        #    metadata (hand-authored YAML that never flowed through
        #    record_story_pass). Treat it as if the story had never passed so
        #    the dashboard prompts action instead of trusting stale labels.
        is_unearned_pass = ts in ("pass", "passing") and not story.last_pass_commit
        if ts not in ("pass", "passing") or is_unearned_pass:
            if story_markers is not None and story.id in story_markers:
                return "never-passed"
            return "untested"

        # Story has passed at least once (test_status == pass/passing).
        # 4. Staleness check.
        pattern_watch = pattern_watch or {}
        if story.related_files or global_watch or pattern_watch:
            if repo_root is None:
                repo_root = _find_repo_root()

            if repo_root is not None and story.last_pass_commit:
                extra = set(global_watch or [])
                watch_set = set(story.related_files) | extra | set(pattern_watch.keys())
                changed = _git_changed_files_since(story.last_pass_commit, repo_root)

                if changed is ANCHOR_UNREACHABLE:
                    # Commit unreachable — try tree_hash fallback.
                    match = _tree_hash_matches(story, repo_root, list(watch_set))
                    if match is True:
                        pass  # Tree unchanged — not stale, continue.
                    else:
                        # match is False or None (couldn't compute) — treat as stale.
                        return "stale"
                elif changed is not None and watch_set & changed:
                    return "stale"

        # 5. UAT-verified check.
        # Simple equality: if last_uat_commit is set and equals last_pass_commit, uat-verified.
        # When they differ we cannot easily check git ancestry here, so conservatively return passing.
        if story.last_uat_commit and story.last_uat_commit == story.last_pass_commit:
            return "uat-verified"

        # 6. Default.
        return "passing"

    def compute_story_flags(
        self,
        story: Story,
        repo_root: Path | None = None,
        global_watch: list[str] | None = None,
        flaky_ids: set[str] | None = None,
        pattern_watch: dict[str, str] | None = None,
    ) -> dict:
        """Return orthogonal flags for a story: flaky and stale_reason.

        Returns:
            dict with keys:
              - ``flaky`` (bool): True if story.flaky is set or story.id in flaky_ids.
              - ``stale_reason`` (str | None): Only populated when status is stale.
                Values: "related_file", "global_config", "anchor_unreachable".
        """
        is_flaky = story.flaky or (flaky_ids is not None and story.id in flaky_ids)

        stale_reason: str | None = None

        pattern_watch = pattern_watch or {}
        if story.related_files or global_watch or pattern_watch:
            if repo_root is None:
                repo_root = _find_repo_root()

            if repo_root is not None and story.last_pass_commit:
                extra = set(global_watch or [])
                pw_keys = set(pattern_watch.keys())
                watch_set = set(story.related_files) | extra | pw_keys
                changed = _git_changed_files_since(story.last_pass_commit, repo_root)

                if changed is ANCHOR_UNREACHABLE:
                    match = _tree_hash_matches(story, repo_root, list(watch_set))
                    if match is not True:
                        stale_reason = "anchor_unreachable"
                elif changed is not None and watch_set & changed:
                    # Priority: pattern:<id> > related_file > global_config
                    # pattern_watch insertion order encodes inherits_patterns order;
                    # pick the first pattern id whose file changed.
                    pattern_hit: str | None = None
                    for fpath, pid in pattern_watch.items():
                        if fpath in changed:
                            pattern_hit = pid
                            break
                    related_changed = bool(set(story.related_files) & changed)
                    global_changed = bool(extra & changed)
                    if pattern_hit is not None:
                        stale_reason = f"pattern:{pattern_hit}"
                    elif related_changed:
                        stale_reason = "related_file"
                    elif global_changed:
                        stale_reason = "global_config"

        return {"flaky": is_flaky, "stale_reason": stale_reason}


def _find_repo_root() -> Path | None:
    """Find the git repository root from cwd."""
    current = Path.cwd()
    for _ in range(10):
        if (current / ".git").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _git_changed_files_since(commit: str, repo_root: Path) -> set[str] | None | object:
    """Return set of files changed between commit and HEAD.

    Return values:
      - ``set[str]``: files changed (may be empty when nothing changed).
      - ``None``: transient/unknown error — callers should skip staleness check.
      - ``ANCHOR_UNREACHABLE``: commit is GC'd or squash-merged (git reports
        "fatal: bad object" / "unknown revision"). Callers should attempt the
        tree_hash fallback before deciding staleness.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{commit}..HEAD"],
            capture_output=True, text=True, cwd=str(repo_root), timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr or ""
            if (
                "bad object" in stderr
                or "unknown revision" in stderr
                or "Invalid revision range" in stderr
                or "ambiguous argument" in stderr
            ):
                return ANCHOR_UNREACHABLE
            return None
        return {f.strip() for f in result.stdout.strip().split("\n") if f.strip()}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _compute_tree_hash(files: list[str], repo_root: Path, ref: str = "HEAD") -> str | None:
    """Hash the blob SHAs for a set of files at a given git ref.

    Uses ``git ls-tree -r <ref> -- <files...>`` and SHA-256 hashes the output.
    Returns None when git fails or the file list is empty.
    """
    if not files:
        return None
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", ref, "--"] + files,
            capture_output=True, text=True, cwd=str(repo_root), timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        # Hash the full ls-tree output — deterministic for the same tree state.
        return hashlib.sha256(result.stdout.encode()).hexdigest()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _tree_hash_matches(story: Story, repo_root: Path, watched_files: list[str]) -> bool | None:
    """Compare HEAD tree hash of watched_files against story.last_pass_tree_hash.

    Returns:
      - True if hashes match (files unchanged).
      - False if hashes differ (files changed).
      - None if we can't compute the current tree hash.
    """
    if not story.last_pass_tree_hash:
        return None
    current = _compute_tree_hash(watched_files, repo_root)
    if current is None:
        return None
    return current == story.last_pass_tree_hash


# Default global_watch patterns (used when docs/userstories/.config.yml is absent).
_DEFAULT_GLOBAL_WATCH: list[str] = [
    "pyproject.toml",
    "modules/*/pyproject.toml",
    "conftest.py",
    "modules/**/conftest.py",
    ".env.example",
    "modules/AgenticCLI/src/agenticcli/cli.py",
]


def load_global_watch(userstories_dir: Path | None = None) -> list[str]:
    """Load global_watch patterns from docs/userstories/.config.yml.

    Returns raw glob patterns (not expanded). Pass the result through
    expand_watch_patterns() to get concrete file paths relative to repo root.

    Falls back to a sensible built-in default when the file is missing or malformed.
    """
    if userstories_dir is None:
        userstories_dir = get_canonical_stories_dir()

    if userstories_dir is not None:
        config_path = userstories_dir / ".config.yml"
        if config_path.exists():
            try:
                raw = config_path.read_text()
                content = yaml.safe_load(raw)
                if isinstance(content, dict):
                    patterns = content.get("global_watch")
                    if isinstance(patterns, list):
                        return [str(p) for p in patterns if p]
            except (OSError, yaml.YAMLError):
                pass  # Fall through to default.

    return list(_DEFAULT_GLOBAL_WATCH)


def expand_watch_patterns(patterns: list[str], repo_root: Path) -> set[str]:
    """Expand glob patterns relative to repo_root into a concrete set of file paths.

    Patterns are matched against repo_root using pathlib.Path.glob().
    Returned paths are relative to repo_root (as strings, using forward slashes).
    """
    result: set[str] = set()
    for pattern in patterns:
        try:
            matched = list(repo_root.glob(pattern))
            for p in matched:
                if p.is_file():
                    try:
                        rel = p.relative_to(repo_root)
                        result.add(str(rel))
                    except ValueError:
                        pass
        except (OSError, ValueError):
            pass
    return set(result)


class PatternService:
    """Service for loading and querying verification patterns."""

    PATTERNS_DIR_NAME = "Patterns"

    def __init__(self, userstories_dir: Path | None = None):
        self._userstories_dir = userstories_dir or get_canonical_stories_dir()
        self._patterns: list[Pattern] | None = None

    @property
    def patterns_dir(self) -> Path | None:
        """Return the Patterns directory path, or None if not found."""
        if not self._userstories_dir:
            return None
        d = self._userstories_dir / self.PATTERNS_DIR_NAME
        return d if d.is_dir() else None

    def load_all(self) -> list[Pattern]:
        """Load all patterns from YAML files. Caches result."""
        if self._patterns is not None:
            return self._patterns

        patterns_dir = self.patterns_dir
        if not patterns_dir:
            self._patterns = []
            return self._patterns

        patterns = []
        for yml_file in sorted(patterns_dir.glob("**/*.yml")):
            if yml_file.name == "00_metadata.yml":
                continue
            patterns.extend(self._parse_file(yml_file))

        self._patterns = patterns
        return self._patterns

    def _parse_file(self, path: Path) -> list[Pattern]:
        """Parse a single YAML pattern file into Pattern objects."""
        try:
            raw = path.read_text()
        except (FileNotFoundError, OSError) as e:
            logger.warning("Could not read pattern file %s: %s", path, e)
            return []

        if not raw.strip():
            return []

        try:
            content = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            logger.warning("YAML error in pattern file %s: %s", path, e)
            return []

        if not content or not isinstance(content, dict):
            return []

        items = content.get("patterns", [])
        if not isinstance(items, list):
            return []

        result = []
        for item in items:
            if not isinstance(item, dict) or "id" not in item:
                continue
            pattern = Pattern(
                id=item["id"],
                title=item.get("title", ""),
                description=item.get("description", ""),
                tags=item.get("tags", []),
                applicable_categories=item.get("applicable_categories", []),
                parameters=item.get("parameters", {}),
                verification=item.get("verification", {}),
                source_file=str(path),
                watch_files=list(item.get("watch_files", []) or []),
            )
            result.append(pattern)
        return result

    def get_by_id(self, pattern_id: str) -> Pattern | None:
        """Find a pattern by its ID."""
        for pattern in self.load_all():
            if pattern.id == pattern_id:
                return pattern
        return None

    def get_by_domain(self, domain: str) -> list[Pattern]:
        """Get all patterns for a domain (e.g., 'CLI', 'DAT')."""
        domain_upper = domain.upper()
        return [p for p in self.load_all() if p.domain == domain_upper]

    def get_watch_files_for_story(
        self,
        story: "Story",
        repo_root: Path,
    ) -> dict[str, str]:
        """Collect watch_files from all patterns a story inherits.

        Returns a dict mapping expanded file path (relative to repo_root) → the
        pattern id that first claimed that file. Iteration order follows
        ``story.inherits_patterns`` so the first-inherited pattern owns any
        overlapping file.
        """
        result: dict[str, str] = {}
        for ref in story.inherits_patterns or []:
            if not isinstance(ref, dict):
                continue
            pid = ref.get("id")
            if not pid:
                continue
            pattern = self.get_by_id(pid)
            if pattern is None or not pattern.watch_files:
                continue
            expanded = expand_watch_patterns(pattern.watch_files, repo_root)
            for f in expanded:
                if f not in result:
                    result[f] = pid
        return result

    def get_claimants(self, pattern_id: str, story_svc: StoryService) -> list[Story]:
        """Find all stories that inherit a given pattern."""
        return [
            s for s in story_svc.load_all()
            if any(ref.get("id") == pattern_id for ref in s.inherits_patterns)
        ]

    def resolve_pattern(self, pattern: Pattern, bindings: dict) -> dict:
        """Resolve a pattern's verification with concrete bindings.

        Validates that all required parameters are bound before resolving.
        Returns the resolved verification dict.
        Raises ValueError if required parameters are missing.
        """
        missing = [
            name for name in pattern.required_parameters
            if name not in bindings
        ]
        if missing:
            raise ValueError(
                f"Pattern {pattern.id} missing required bindings: {', '.join(missing)}"
            )
        return pattern.resolve(bindings)
