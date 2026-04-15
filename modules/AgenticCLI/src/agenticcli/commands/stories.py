# story: US-STR-001
"""User stories discovery and test tracking commands.

Find, filter, and track test status of user stories.
"""

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agenticguidance.services.story import (
    Pattern, PatternService, Story, StoryService,
    get_canonical_stories_dir, get_epic_stories_path,
    _find_repo_root, _git_changed_files_since,
    load_global_watch, expand_watch_patterns, STORY_STATUS_SORT_ORDER,
    ANCHOR_UNREACHABLE,
)


def handle(args, ctx=None):
    """Route stories subcommands."""
    if args.stories_command == "find":
        cmd_find(args)
    elif args.stories_command == "init":
        cmd_init(args)
    elif args.stories_command == "cat":
        cmd_cat(args)
    elif args.stories_command == "status":
        cmd_status(args)
    elif args.stories_command == "update":
        cmd_update(args)
    elif args.stories_command == "health":
        cmd_health(args)
    elif args.stories_command == "untested":
        cmd_untested(args)
    elif args.stories_command == "batch-update":
        cmd_batch_update(args)
    elif args.stories_command == "affected":
        cmd_affected(args)
    elif args.stories_command == "sync":
        cmd_sync(args)
    elif args.stories_command == "run":
        cmd_run(args)
    elif args.stories_command == "promote":
        cmd_promote(args)
    elif args.stories_command == "deprecate":
        cmd_deprecate(args)
    elif args.stories_command == "archive":
        cmd_archive(args)
    elif args.stories_command == "code":
        cmd_code(args)
    elif args.stories_command == "audit":
        cmd_audit(args)
    elif args.stories_command == "patterns":
        cmd_patterns(args)
    elif args.stories_command == "pattern-cat":
        cmd_pattern_cat(args)
    elif args.stories_command == "pattern-claimants":
        cmd_pattern_claimants(args)
    elif args.stories_command == "pattern-verify":
        cmd_pattern_verify(args)
    elif args.stories_command == "pattern-check":
        cmd_pattern_check(args)
    else:
        print("Usage: agentic stories [find|init|cat|status|update|report|untested|batch-update|affected|sync|run|promote|deprecate|archive|code|audit|patterns|pattern-cat|pattern-claimants|pattern-verify|pattern-check]", file=sys.stderr)
        sys.exit(1)


def _find_userstories_dir() -> Path | None:
    """Find the userstories directory.

    Delegates to the canonical resolver in
    ``agenticguidance.services.story.get_canonical_stories_dir()``.
    """
    return get_canonical_stories_dir()


def _get_repo_db_path() -> Path:
    """Return the global TinyDB path (~/.agentic/epics.db)."""
    return Path.home() / ".agentic" / "epics.db"



def _get_project_from_path(story_file: Path, userstories_dir: Path) -> str:
    """Extract project name from the story file's directory path.

    Stories are organized as userstories/<project>/<story>.yml
    Returns the first directory component after userstories.
    """
    try:
        rel_path = story_file.relative_to(userstories_dir)
        parts = rel_path.parts
        if len(parts) >= 1:
            return parts[0]  # First directory is the project
    except ValueError:
        pass
    return ""


def _parse_story_file(story_file: Path, userstories_dir: Path | None = None) -> list[dict]:
    """Parse a user story file.

    Returns a list of stories (files may contain multiple stories in user_stories array).
    """
    # Get project from directory structure
    project = ""
    if userstories_dir:
        project = _get_project_from_path(story_file, userstories_dir)

    try:
        content = yaml.safe_load(story_file.read_text())
        if content and isinstance(content, dict):
            # Handle stories/user_stories array format
            story_list = None
            for key in ("stories", "user_stories"):
                if key in content and isinstance(content[key], list):
                    story_list = content[key]
                    break

            if story_list is not None:
                stories = []
                for story in story_list:
                    if isinstance(story, dict):
                        stories.append(
                            {
                                "file": story_file.name,
                                "path": str(story_file),
                                "id": story.get("id", story_file.stem),
                                "title": story.get("title", story.get("name", "")),
                                "project": story.get("project", project),
                                "status": story.get("status", ""),
                                "tags": story.get("tags", []),
                                "category": story.get("category", ""),
                            }
                        )
                if stories:
                    return stories

            # Handle single story format (legacy)
            return [
                {
                    "file": story_file.name,
                    "path": str(story_file),
                    "id": content.get("id", story_file.stem),
                    "title": content.get("title", content.get("name", "")),
                    "project": content.get("project", project),
                    "status": content.get("status", ""),
                    "tags": content.get("tags", []),
                    "category": content.get("category", ""),
                }
            ]
    except yaml.YAMLError:
        pass

    return [
        {
            "file": story_file.name,
            "path": str(story_file),
            "id": story_file.stem,
            "project": project,
            "error": "Could not parse",
        }
    ]


def _story_to_dict(s: Story) -> dict:
    """Convert a Story dataclass to the dict format expected by report/untested commands."""
    return {
        "id": s.id,
        "title": s.title,
        "category": s.category,
        "priority": s.priority,
        "description": s.description,
        "project": s.project,
        "path": s.source_file,
        "file": s.source_file,
        "status": s.test_status or "untested",
        "test_status": s.test_status or "untested",
        "last_tested": s.last_tested or None,
        "tested_by_plan": s.tested_by_plan or None,
        "related_stories": s.related_stories,
        "related_commands": s.related_commands,
        "related_files": s.related_files,
        "last_pass_commit": s.last_pass_commit or None,
        "last_uat_commit": s.last_uat_commit or None,
    }


def _collect_all_stories(project_filter: str | None = None) -> list[dict]:
    """Collect all stories from the unified docs/userstories/ directory.

    Each returned dict includes test metadata fields and file path info.
    Uses StoryService which reads from docs/userstories/ (including EpicStories/).
    """
    userstories_dir = _find_userstories_dir()

    if userstories_dir is None:
        print(
            "Warning: No userstories directory found. Run from repo root or set AGENTIC_REPO_ROOT.",
            file=sys.stderr,
        )

    # Load all stories via StoryService (covers manual + epic-generated)
    svc = StoryService(userstories_dir)
    all_stories = [_story_to_dict(s) for s in svc.load_all()]

    if project_filter:
        pf = project_filter.lower()
        all_stories = [s for s in all_stories if pf in s.get("project", "").lower()]

    return all_stories



_PREFIX_TO_MODULE = {
    "US-SET": "AgenticCLI",
    "US-SES": "AgenticCLI",
    "US-PLN": "AgenticCLI",
    "US-STR": "AgenticCLI",
    "US-GDN": "AgenticGuidance",
}


def _story_module(story_id: str) -> str:
    """Derive the module (AgenticCLI or AgenticGuidance) from a story ID prefix."""
    match = re.match(r"(US-[A-Z]+)", story_id)
    if match:
        return _PREFIX_TO_MODULE.get(match.group(1), "Unknown")
    return "Unknown"


def _categorize_stories(stories: list[dict]) -> dict:
    """Categorize stories by prefix."""
    categories = {}

    for story in stories:
        story_id = story.get("id", "")
        # Extract prefix (e.g., US-INSTALL, US-CLI, US-260402AG)
        match = re.match(r"(US-[A-Z0-9]+)", story_id)
        if match:
            prefix = match.group(1)
        else:
            prefix = "OTHER"

        if prefix not in categories:
            categories[prefix] = []
        categories[prefix].append(story)

    return categories


def cmd_find(args):
    """Find relevant user stories."""
    from agenticcli.console import (
        console,
        format_status,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )

    userstories_dir = _find_userstories_dir()

    if not userstories_dir:
        if is_json_output():
            print_json({"error": "Could not find userstories directory"})
        else:
            print_error("Could not find userstories directory")
            console.print("[dim]Searched in:[/dim]")
            console.print("  [dim]- docs/userstories/[/dim]")
            console.print("  [dim]- ../docs/userstories/[/dim]")
            console.print("  [dim]- userstories/[/dim]")
        sys.exit(1)

    # Load all stories via StoryService (covers manual + epic-generated in EpicStories/)
    svc = StoryService(userstories_dir)
    all_stories = [
        {
            "id": s.id, "title": s.title, "category": s.category,
            "priority": s.priority, "description": s.description,
            "project": s.project, "path": s.source_file,
            "status": s.test_status,
        }
        for s in svc.load_all()
    ]

    stories = all_stories

    # Filter by query if specified (matches ID, title, or description)
    if getattr(args, "query", None):
        query_lower = args.query.lower()
        stories = [
            s
            for s in stories
            if query_lower in s.get("id", "").lower()
            or query_lower in s.get("title", "").lower()
            or query_lower in s.get("description", "").lower()
            or query_lower in s.get("category", "").lower()
        ]

    # Filter by project if specified
    if args.project:
        project_filter = args.project.lower()
        stories = [s for s in stories if project_filter in s.get("project", "").lower()]

    # Filter by tag if specified
    if getattr(args, "tag", None):
        tag_lower = args.tag.lower()
        stories = [
            s
            for s in stories
            if tag_lower in [t.lower() for t in s.get("tags", [])]
        ]

    # Filter by changed files if specified
    if getattr(args, "changes", None):
        # Resolve 'git' shorthand to actual changed files from git diff
        raw_changes = args.changes
        if raw_changes == "git":
            import subprocess

            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
            )
            changed_paths = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        elif isinstance(raw_changes, list):
            changed_paths = raw_changes
        else:
            changed_paths = [p.strip() for p in raw_changes.split(",") if p.strip()]
        changed_lower = [p.lower() for p in changed_paths]

        def story_matches_changes(story: dict) -> bool:
            # Check if story category or path relates to changed files
            story_path = story.get("path", "").lower()
            story_category = story.get("category", "").lower()
            story_id = story.get("id", "").lower()

            for changed in changed_lower:
                # Basic matching - story is relevant if:
                # 1. Story file path contains the changed path
                # 2. Changed path contains the story category
                # 3. Changed path contains part of story ID
                if changed in story_path:
                    return True
                if story_category and story_category in changed:
                    return True
                # Extract meaningful parts from story ID (e.g., US-INSTALL -> install)
                id_parts = story_id.replace("us-", "").split("-")
                for part in id_parts:
                    if part and len(part) > 2 and part in changed:
                        return True
            return False

        stories = [s for s in stories if story_matches_changes(s)]

    # Categorize stories
    categories = _categorize_stories(stories)

    if is_json_output():
        print_json(
            {
                "directory": str(userstories_dir),
                "stories": stories,
                "categories": {k: len(v) for k, v in categories.items()},
                "total": len(stories),
            }
        )
        return

    print_header(f"User Stories: {userstories_dir}")

    for prefix in sorted(categories.keys()):
        cat_stories = categories[prefix]
        console.print(f"\n[bold magenta]{prefix}[/bold magenta] ({len(cat_stories)} stories)")
        console.print("[dim]" + "-" * 40 + "[/dim]")
        for story in cat_stories:
            if "error" in story:
                console.print(f"  [cyan]{story['id']}[/cyan]: [red][ERROR][/red] {story['error']}")
            else:
                title = story.get("title", "(no title)")[:50]
                status = story.get("status", "")
                status_marker = f" {format_status(status)}" if status else ""
                console.print(f"  [cyan]{story['id']}[/cyan]: {title}{status_marker}")

    console.print(f"\n[bold]Total:[/bold] [cyan]{len(stories)}[/cyan] stories found")


def cmd_init(args):
    """Initialize a new user story template."""
    from agenticcli.console import console, print_error, print_success

    target_dir = Path.cwd()
    if args.plan:
        # Write epic-scoped stories to docs/userstories/EpicStories/
        epic_stories_path = get_epic_stories_path(args.plan)
        target_dir = epic_stories_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / f"{args.id}.yml"
    if file_path.exists():
        print_error(f"Story file already exists: {file_path}")
        sys.exit(1)

    template = {
        "id": args.id,
        "title": args.title or "New User Story",
        "category": "testing",
        "priority": "medium",
        "starting_state": {"environment": {}},
        "journey": [
            {"step": 1, "action": "Do something", "expected": "Something happens"}
        ],
        "success_criteria": ["Criteria 1"],
    }

    file_path.write_text(yaml.dump(template, sort_keys=False))
    print_success(f"Created user story: {file_path}")


def cmd_cat(args):
    """Display a user story's content."""
    from agenticcli.console import console, print_error

    # Fast path: look up by ID via StoryService
    svc = StoryService(_find_userstories_dir())
    found = svc.get_by_id(args.id)
    if found and found.source_file:
        console.print(Path(found.source_file).read_text())
        return

    # Fallback: scan userstories directory by filename matching
    userstories_dir = _find_userstories_dir()
    story_files = []
    if userstories_dir:
        story_files.extend(list(userstories_dir.glob("**/*.yml")))

    target_story = None
    for f in story_files:
        # Check filename/stem match
        if f.stem == args.id or f.name == args.id or args.id in f.stem:
            target_story = f
            break

        # Check ID inside YAML
        try:
            stories = _parse_story_file(f)
            if any(s.get("id") == args.id for s in stories):
                target_story = f
                break
        except Exception:
            continue

    if not target_story:
        print_error(f"Story not found: {args.id}")
        sys.exit(1)

    console.print(target_story.read_text())


def cmd_status(args):
    """Display test status for a specific story."""
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json

    # Typer binding in cli.py passes `story_id` (matches the typer.Argument name);
    # fall back to `id` for legacy dispatch paths that used the shorter attribute.
    story_id = getattr(args, "story_id", None) or getattr(args, "id", None)
    svc = StoryService(_find_userstories_dir())
    story_obj = svc.get_by_id(story_id)

    if story_obj is None:
        if is_json_output():
            print_json({"error": f"Story not found: {story_id}"})
        else:
            print_error(f"Story not found: {story_id}")
        sys.exit(1)

    # Look up code coverage from TinyDB
    code_functions = []
    try:
        db_path = _get_repo_db_path()
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        code_functions = repo.get_code_for_story(story_id)
        repo.close()
    except Exception:
        pass

    status_data = {
        "id": story_obj.id,
        "title": story_obj.title,
        "lifecycle": story_obj.lifecycle,
        "test_status": story_obj.test_status or "untested",
        "last_tested": story_obj.last_tested or None,
        "test_notes": story_obj.test_notes,
        "tested_by_plan": story_obj.tested_by_plan or None,
        "code_functions": code_functions,
        "file": story_obj.source_file,
    }

    if is_json_output():
        print_json(status_data)
        return

    print_header(f"Story Status: {story_id}")
    console.print(f"  [bold]Title:[/bold] {status_data['title']}")
    console.print(f"  [bold]Lifecycle:[/bold] {status_data['lifecycle']}")

    ts = status_data["test_status"]
    if ts == "pass":
        console.print(f"  [bold]Test Status:[/bold] [green]{ts}[/green]")
    elif ts == "fail":
        console.print(f"  [bold]Test Status:[/bold] [red]{ts}[/red]")
    elif ts == "skip":
        console.print(f"  [bold]Test Status:[/bold] [yellow]{ts}[/yellow]")
    else:
        console.print(f"  [bold]Test Status:[/bold] [dim]{ts}[/dim]")

    if status_data["last_tested"]:
        console.print(f"  [bold]Last Tested:[/bold] {status_data['last_tested']}")
    else:
        console.print("  [bold]Last Tested:[/bold] [dim]never[/dim]")

    if status_data["test_notes"]:
        console.print(f"  [bold]Notes:[/bold] {status_data['test_notes']}")

    if status_data["tested_by_plan"]:
        console.print(f"  [bold]Tested By Plan:[/bold] {status_data['tested_by_plan']}")

    if status_data["code_functions"]:
        console.print(f"  [bold]Code Functions:[/bold] {len(status_data['code_functions'])}")
        for fn in status_data["code_functions"][:10]:
            console.print(f"    [dim]- {fn}[/dim]")
        if len(status_data["code_functions"]) > 10:
            console.print(f"    [dim]... and {len(status_data['code_functions']) - 10} more[/dim]")

    console.print(f"  [dim]File: {status_data['file']}[/dim]")


def cmd_update(args):
    """Update test status for a specific story.

    When ``--status pass`` is recorded, the current git HEAD commit is
    captured and written atomically alongside the status (to
    ``last_pass_commit`` by default, or ``last_uat_commit`` when
    ``--kind uat`` is passed). This closes the two-write-path gap where
    a story could be marked passing with no commit hash attached. Pass
    ``--commit <hash>`` to override the auto-detected HEAD.
    """
    import subprocess

    from agenticcli.console import is_json_output, print_error, print_json, print_success

    story_id = args.id
    svc = StoryService(_find_userstories_dir())

    # Verify story exists before attempting update
    story_obj = svc.get_by_id(story_id)
    if story_obj is None:
        if is_json_output():
            print_json({"error": f"Story not found: {story_id}"})
        else:
            print_error(f"Story not found: {story_id}")
        sys.exit(1)

    now = datetime.now(timezone.utc).isoformat()
    tested_by = (args.plan if hasattr(args, "plan") and args.plan else "")
    notes = args.notes if args.notes else ""
    kind = getattr(args, "kind", "test") or "test"

    # Capture the git HEAD at record time so passing stories always carry
    # a commit hash. Explicit --commit overrides the auto-detected value.
    commit = getattr(args, "commit", "") or ""
    if not commit and args.status in ("pass", "passing"):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                commit = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            commit = ""

    updated = svc.update_test_status(
        story_id,
        args.status,
        tested_by=tested_by,
        test_notes=notes,
        last_tested=now,
        commit=commit,
        commit_kind=kind,
    )

    if not updated:
        print_error(f"Could not update story {story_id}")
        sys.exit(1)

    if is_json_output():
        print_json({
            "updated": story_id,
            "test_status": args.status,
            "commit": commit or None,
            "commit_kind": kind if commit else None,
            "file": story_obj.source_file,
        })
    else:
        commit_suffix = f" @ {commit[:7]}" if commit else ""
        print_success(f"Updated {story_id}: test_status={args.status}{commit_suffix}")


def record_story_pass(
    story_ids,
    commit: str | None = None,
    commit_kind: str = "test",
    tested_by: str = "",
) -> dict:
    """Record test pass for one or more stories.

    Single write path shared by `cmd_update` and framework hooks
    (ExecutionRunner phase-completion, UatRunner session-completion).
    Resolves HEAD when `commit` is not provided and calls
    `StoryService.update_test_status` in-process for each story.

    Returns a dict: {"updated": [ids], "missing": [ids]}.
    """
    svc = StoryService(_find_userstories_dir())

    if not commit:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                commit = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            commit = ""

    now = datetime.now(timezone.utc).isoformat()
    updated: list[str] = []
    missing: list[str] = []

    for sid in story_ids:
        if svc.get_by_id(sid) is None:
            missing.append(sid)
            continue
        ok = svc.update_test_status(
            sid,
            "pass",
            tested_by=tested_by,
            test_notes="",
            last_tested=now,
            commit=commit or "",
            commit_kind=commit_kind,
        )
        if ok:
            updated.append(sid)
        else:
            missing.append(sid)

    return {"updated": updated, "missing": missing, "commit": commit or None}


def _scan_pytest_story_markers() -> set[str]:
    """Scan test files for @pytest.mark.story markers and return referenced story IDs.

    Searches for pytest.mark.story markers in both AgenticCLI and AgenticGuidance
    test directories (relative to the repo root).

    Returns:
        Set of story IDs found in @pytest.mark.story markers across test files.
    """
    import subprocess

    marker_ids: set[str] = set()

    # Find the repo root
    cwd = Path.cwd()
    repo_root = cwd
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent

    # Search test directories for @pytest.mark.story markers
    test_dirs = [
        repo_root / "modules" / "AgenticCLI" / "tests",
        repo_root / "modules" / "AgenticGuidance" / "tests",
    ]

    for test_dir in test_dirs:
        if not test_dir.exists():
            continue
        try:
            result = subprocess.run(
                ["grep", "-rh", r"@pytest.mark.story", str(test_dir)],
                capture_output=True, text=True, timeout=30,
            )
            if result.stdout:
                # Extract story IDs from markers like @pytest.mark.story("US-CLI-110")
                # Also handles epic-namespaced IDs like @pytest.mark.story("US-260402AG-001")
                for match in re.findall(r'["\']([A-Z]{2}-[A-Z0-9]+-\d+)["\']', result.stdout):
                    marker_ids.add(match)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return marker_ids


def _scan_pytest_flaky_markers(story_marker_ids: set[str]) -> set[str]:
    """Return the set of story IDs whose test files contain @pytest.mark.flaky.

    Strategy (regex, not AST — coarse but sufficient):
    For each test file, if the file contains both @pytest.mark.flaky AND a
    @pytest.mark.story("US-XXX-NNN") referencing a known story ID, that story
    ID is considered flaky.

    This is intentionally coarse: if ANY test in the file is flaky and the
    file covers a story, that story is flagged. Per-function precision requires
    AST; the regex approach is used here because test files are usually focused
    on one story and the cost of false positives is low.

    Args:
        story_marker_ids: Set of story IDs already known to have test markers
            (from _scan_pytest_story_markers). Used to restrict scanning.

    Returns:
        Set of story IDs that have at least one linked test with @pytest.mark.flaky.
    """
    flaky_story_ids: set[str] = set()

    # Find the repo root
    cwd = Path.cwd()
    repo_root = cwd
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent

    test_dirs = [
        repo_root / "modules" / "AgenticCLI" / "tests",
        repo_root / "modules" / "AgenticGuidance" / "tests",
    ]

    story_id_pattern = re.compile(r'["\']([A-Z]{2}-[A-Z0-9]+-\d+)["\']')
    flaky_marker_pattern = re.compile(r'@pytest\.mark\.flaky')

    for test_dir in test_dirs:
        if not test_dir.exists():
            continue
        for test_file in sorted(test_dir.rglob("test_*.py")):
            try:
                content = test_file.read_text()
            except OSError:
                continue

            if not flaky_marker_pattern.search(content):
                continue  # File has no flaky markers — skip

            # File has at least one @pytest.mark.flaky — find all story IDs in file
            story_ids_in_file = {
                m for m in story_id_pattern.findall(content)
                if m in story_marker_ids
            }
            flaky_story_ids |= story_ids_in_file

    return flaky_story_ids


def _scan_pytest_story_markers_detailed() -> dict[str, list[str]]:
    """Parse test files with ast to extract story_id -> [test_nodeids] mappings.

    Walks test directories for both modules, parses each test_*.py with ast,
    and finds @pytest.mark.story(...) decorators on function/class nodes.

    Returns:
        Dict mapping story_id to list of pytest-style nodeids
        (e.g. {"US-STR-001": ["modules/AgenticCLI/tests/test_foo.py::test_bar"]}).
    """
    import ast

    # Find the repo root
    cwd = Path.cwd()
    repo_root = cwd
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent

    test_dirs = [
        repo_root / "modules" / "AgenticCLI" / "tests",
        repo_root / "modules" / "AgenticGuidance" / "tests",
    ]

    mappings: dict[str, list[str]] = {}

    for test_dir in test_dirs:
        if not test_dir.exists():
            continue
        for test_file in sorted(test_dir.rglob("test_*.py")):
            try:
                source = test_file.read_text()
                tree = ast.parse(source, filename=str(test_file))
            except (SyntaxError, OSError):
                continue

            rel_path = str(test_file.relative_to(repo_root))

            # Extract module-level pytestmark story IDs
            # Handles: pytestmark = pytest.mark.story(...)
            #          pytestmark = [pytest.mark.unit, pytest.mark.story(...)]
            module_story_ids = _extract_pytestmark_story_ids(tree)

            # Collect all test nodeids in the file (for module-level markers)
            all_test_nodeids: list[str] = []

            # Process top-level functions and classes
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef):
                    story_ids = _extract_story_ids_from_decorators(node)
                    if story_ids:
                        nodeid = f"{rel_path}::{node.name}"
                        for sid in story_ids:
                            mappings.setdefault(sid, []).append(nodeid)
                    if node.name.startswith("test_"):
                        all_test_nodeids.append(f"{rel_path}::{node.name}")

                elif isinstance(node, ast.ClassDef):
                    # Check class-level markers (decorators + pytestmark attribute)
                    class_story_ids = _extract_story_ids_from_decorators(node)
                    class_story_ids |= _extract_pytestmark_story_ids(node)

                    for method in ast.iter_child_nodes(node):
                        if isinstance(method, ast.FunctionDef) and method.name.startswith("test_"):
                            method_story_ids = _extract_story_ids_from_decorators(method)
                            all_ids = class_story_ids | method_story_ids
                            nodeid = f"{rel_path}::{node.name}::{method.name}"
                            all_test_nodeids.append(nodeid)
                            if all_ids:
                                for sid in all_ids:
                                    mappings.setdefault(sid, []).append(nodeid)

            # Apply module-level pytestmark story IDs to all tests in the file
            if module_story_ids and all_test_nodeids:
                for sid in module_story_ids:
                    existing = set(mappings.get(sid, []))
                    for nodeid in all_test_nodeids:
                        if nodeid not in existing:
                            mappings.setdefault(sid, []).append(nodeid)

    return mappings


def _extract_pytestmark_story_ids(tree) -> set[str]:
    """Extract story IDs from pytestmark assignments (module or class level).

    Handles:
    - pytestmark = pytest.mark.story("US-XXX-NNN", ...)
    - pytestmark = [pytest.mark.unit, pytest.mark.story("US-XXX-NNN", ...)]
    """
    import ast

    story_ids: set[str] = set()

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        # Check if target is 'pytestmark'
        if not any(
            isinstance(t, ast.Name) and t.id == "pytestmark"
            for t in node.targets
        ):
            continue

        # Extract story IDs from the value
        calls_to_check: list[ast.Call] = []
        if isinstance(node.value, ast.Call):
            calls_to_check.append(node.value)
        elif isinstance(node.value, ast.List):
            for elt in node.value.elts:
                if isinstance(elt, ast.Call):
                    calls_to_check.append(elt)

        for call in calls_to_check:
            if _is_story_marker_call(call):
                for arg in call.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        story_ids.add(arg.value)

    return story_ids


def _is_story_marker_call(call: "ast.Call") -> bool:
    """Check if an ast.Call is a pytest.mark.story(...) or story(...) call."""
    import ast

    func = call.func
    # pytest.mark.story(...)
    if (isinstance(func, ast.Attribute) and func.attr == "story"
            and isinstance(func.value, ast.Attribute) and func.value.attr == "mark"):
        return True
    # story(...)
    if isinstance(func, ast.Name) and func.id == "story":
        return True
    # markers.story(...)
    if isinstance(func, ast.Attribute) and func.attr == "story":
        return True
    return False


def _extract_story_ids_from_decorators(node: "ast.FunctionDef | ast.ClassDef") -> set[str]:
    """Extract story IDs from @pytest.mark.story(...) or @story(...) decorators.

    Matches:
    - @pytest.mark.story("US-XXX-NNN", ...)
    - @story("US-XXX-NNN", ...)
    - @markers.story("US-XXX-NNN", ...)

    Returns:
        Set of story ID strings found in story markers.
    """
    import ast

    story_ids: set[str] = set()

    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue

        func = decorator.func

        is_story_call = False

        if isinstance(func, ast.Attribute) and func.attr == "story":
            inner = func.value
            # pytest.mark.story
            if isinstance(inner, ast.Attribute) and inner.attr == "mark":
                is_story_call = True
            # markers.story
            elif isinstance(inner, ast.Name) and inner.id == "markers":
                is_story_call = True
        elif isinstance(func, ast.Name) and func.id == "story":
            # bare @story(...)
            is_story_call = True

        if is_story_call:
            for arg in decorator.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    story_ids.add(arg.value)

    return story_ids


def _scan_production_code_story_markers() -> dict[str, list[str]]:
    """Scan production code for @story(...) decorators.

    Walks modules/*/src/ directories (excludes tests/) looking for
    @story(...) or @markers.story(...) decorators.

    Returns:
        Dict mapping story_id to list of code nodeids
        (e.g. {"US-CLI-110": ["modules/AgenticCLI/src/agenticcli/foo.py::bar"]}).
    """
    import ast

    cwd = Path.cwd()
    repo_root = cwd
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent

    src_dirs = sorted((repo_root / "modules").glob("*/src"))

    mappings: dict[str, list[str]] = {}

    for src_dir in src_dirs:
        if not src_dir.exists():
            continue
        for py_file in sorted(src_dir.rglob("*.py")):
            # Skip test files
            if "/tests/" in str(py_file) or py_file.name.startswith("test_"):
                continue
            try:
                source = py_file.read_text()
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, OSError):
                continue

            rel_path = str(py_file.relative_to(repo_root))

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    story_ids = _extract_story_ids_from_decorators(node)
                    if story_ids:
                        nodeid = f"{rel_path}::{node.name}"
                        for sid in story_ids:
                            mappings.setdefault(sid, []).append(nodeid)

                    # Also check methods inside classes
                    if isinstance(node, ast.ClassDef):
                        for method in ast.iter_child_nodes(node):
                            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                method_ids = _extract_story_ids_from_decorators(method)
                                if method_ids:
                                    nodeid = f"{rel_path}::{node.name}::{method.name}"
                                    for sid in method_ids:
                                        mappings.setdefault(sid, []).append(nodeid)

    return mappings


def cmd_health(args):
    """Show all stories in a dashboard table with test status summary.

    Columns: ID | Title | Status | Flags | testpass_commithash | uatpass_commithash

    Status values (7-value canonical enum):
      unhealthy, stale, never-passed, no-test, passing, uat-verified, archived

    Flags column: space-separated badges (e.g. !flaky). Empty when no modifiers.

    Use --all to include archived stories (hidden by default).
    """
    from rich.table import Table

    from agenticcli.console import console, is_json_output, print_header, print_json

    project_filter = getattr(args, "project", None)
    coverage_mode = getattr(args, "coverage", False)
    show_all = getattr(args, "all", False)

    userstories_dir = _find_userstories_dir()
    story_svc = StoryService(userstories_dir)
    repo_root = _find_repo_root()

    # Load global watch config (Phase 1 service function)
    global_watch_patterns = load_global_watch(userstories_dir)
    global_watch_files: list[str] = []
    if repo_root and global_watch_patterns:
        global_watch_files = list(expand_watch_patterns(global_watch_patterns, repo_root))

    # Unconditionally scan pytest markers (needed for never-passed vs no-test split)
    story_marker_ids: set[str] = _scan_pytest_story_markers()

    # Flaky marker detection (regex approach — coarse, per-file granularity)
    flaky_story_ids: set[str] = _scan_pytest_flaky_markers(story_marker_ids)

    all_story_objs = story_svc.load_all()
    if project_filter:
        pf = project_filter.lower()
        all_story_objs = [s for s in all_story_objs if pf in s.project.lower()]

    # Resolve pattern_watch per story (dict of file -> owning pattern_id).
    pat_svc = PatternService(userstories_dir)
    pattern_watch_by_story: dict[str, dict[str, str]] = {}
    if repo_root:
        for s in all_story_objs:
            if s.inherits_patterns:
                pattern_watch_by_story[s.id] = pat_svc.get_watch_files_for_story(s, repo_root)

    # --- Compute status and flags for every story ---
    # Each entry: (story, status, flags_dict)
    story_results: list[tuple] = []
    for s in all_story_objs:
        pw = pattern_watch_by_story.get(s.id, {})
        status = story_svc.compute_story_status(
            s, repo_root,
            story_markers=story_marker_ids,
            global_watch=global_watch_files,
            pattern_watch=pw,
        )
        flags = story_svc.compute_story_flags(
            s, repo_root,
            global_watch=global_watch_files,
            flaky_ids=flaky_story_ids,
            pattern_watch=pw,
        )
        story_results.append((s, status, flags))

    # --- Separate archived from visible ---
    archived_results = [(s, st, fl) for s, st, fl in story_results if st == "archived"]
    visible_results = [(s, st, fl) for s, st, fl in story_results if st != "archived"]

    if show_all:
        display_results = sorted(
            story_results,
            key=lambda r: (STORY_STATUS_SORT_ORDER.get(r[1], 999), _story_module(r[0].id), r[0].id),
        )
        hidden_archived_count = 0
    else:
        display_results = sorted(
            visible_results,
            key=lambda r: (STORY_STATUS_SORT_ORDER.get(r[1], 999), _story_module(r[0].id), r[0].id),
        )
        hidden_archived_count = len(archived_results)

    # --- Tally counts across ALL stories (not just shown) ---
    status_counts: dict[str, int] = {
        "broken": 0,
        "stale": 0,
        "never-passed": 0,
        "untested": 0,
        "passing": 0,
        "uat-verified": 0,
        "archived": 0,
    }
    for _, status, _ in story_results:
        if status in status_counts:
            status_counts[status] += 1

    flaky_count = sum(1 for _, _, fl in story_results if fl.get("flaky"))
    total_shown = len(display_results)

    # --- Pytest marker coverage analysis (--coverage mode) ---
    marker_coverage = None
    if coverage_mode:
        all_story_ids = {s.id for s in all_story_objs}
        covered = all_story_ids & story_marker_ids
        uncovered = all_story_ids - story_marker_ids
        orphan_markers = story_marker_ids - all_story_ids
        marker_coverage = {
            "total_stories": len(all_story_ids),
            "covered_by_markers": len(covered),
            "uncovered": sorted(uncovered),
            "orphan_markers": sorted(orphan_markers),
            "coverage_pct": (len(covered) / len(all_story_ids) * 100) if all_story_ids else 0,
        }

    # ==========================================================================
    # JSON output
    # ==========================================================================
    if is_json_output():
        stories_json = []
        for s, status, flags in display_results:
            # Determine staleness detail arrays
            # We share a single git diff call via compute_story_flags' stale_reason.
            # For related_files_changed / global_config_changed, do one diff call.
            related_files_changed: list[str] = []
            global_config_changed: list[str] = []
            pattern_watch_changed: list[str] = []
            stale_reason = flags.get("stale_reason")
            pw_for_story = pattern_watch_by_story.get(s.id, {})
            is_pattern_reason = isinstance(stale_reason, str) and stale_reason.startswith("pattern:")
            if (stale_reason in ("related_file", "global_config") or is_pattern_reason) \
                    and repo_root and s.last_pass_commit:
                changed = _git_changed_files_since(s.last_pass_commit, repo_root)
                if changed and changed is not ANCHOR_UNREACHABLE:
                    related_files_changed = sorted(set(s.related_files) & changed)
                    global_config_changed = sorted(set(global_watch_files) & changed)
                    pattern_watch_changed = sorted(set(pw_for_story.keys()) & changed)

            stories_json.append({
                "id": s.id,
                "module": _story_module(s.id),
                "title": s.title,
                "status": status,
                "flags": {
                    "flaky": flags.get("flaky", False),
                    "blocked": False,
                },
                "test": {
                    "status": s.test_status or None,
                    "last_pass_commit": s.last_pass_commit or None,
                    "last_pass_tree_hash": s.last_pass_tree_hash or None,
                    "last_tested": s.last_tested or None,
                },
                "uat": {
                    "last_uat_commit": s.last_uat_commit or None,
                },
                "staleness": {
                    "is_stale": status == "stale",
                    "reason": stale_reason,
                    "related_files_changed": related_files_changed,
                    "global_config_changed": global_config_changed,
                    "pattern_watch_changed": pattern_watch_changed,
                },
                "related_files": s.related_files,
                "lifecycle": s.lifecycle,
            })

        result = {
            "stories": stories_json,
            "summary": {
                "total_shown": total_shown,
                "hidden_archived": hidden_archived_count,
                "counts": status_counts,
                "flaky_count": flaky_count,
                "project_filter": project_filter,
            },
        }
        if marker_coverage is not None:
            result["marker_coverage"] = marker_coverage
        print_json(result)
        return

    # ==========================================================================
    # Table output
    # ==========================================================================
    _status_style = {
        "broken": "red",
        "stale": "yellow",
        "never-passed": "cyan",
        "untested": "dim",
        "passing": "green",
        "uat-verified": "bright_green",
        "archived": "grey50",
    }

    title = "Stories Health Dashboard"
    if project_filter:
        title += f" (project: {project_filter})"
    print_header(title)

    _module_style = {
        "AgenticCLI": "blue",
        "AgenticGuidance": "magenta",
    }

    table = Table(show_header=True, header_style="bold", expand=True, pad_edge=False)
    table.add_column("ID", style="cyan", no_wrap=True, min_width=14)
    table.add_column("Module", no_wrap=True, min_width=14)
    table.add_column("Title", ratio=1)
    table.add_column("Status", no_wrap=True, min_width=12)
    table.add_column("Flags", no_wrap=True)
    table.add_column("testpass_commithash", no_wrap=True, style="dim")
    table.add_column("uatpass_commithash", no_wrap=True, style="dim")

    for s, status, flags in display_results:
        style = _status_style.get(status, "dim")

        # Status cell — append stale_reason when available
        stale_reason = flags.get("stale_reason")
        if status == "stale" and stale_reason:
            status_cell = f"[{style}]stale ({stale_reason})[/{style}]"
        else:
            status_cell = f"[{style}]{status}[/{style}]"

        # Flags cell — space-separated badges
        badges = []
        if flags.get("flaky"):
            badges.append("!flaky")
        flags_cell = f"[yellow bold]{' '.join(badges)}[/yellow bold]" if badges else ""

        # Short commit hashes
        pass_hash = s.last_pass_commit[:7] if s.last_pass_commit else "\u2014"
        uat_hash = s.last_uat_commit[:7] if s.last_uat_commit else "\u2014"

        # Module cell
        module = _story_module(s.id)
        mod_style = _module_style.get(module, "dim")
        module_cell = f"[{mod_style}]{module}[/{mod_style}]"

        table.add_row(
            s.id,
            module_cell,
            s.title,
            status_cell,
            flags_cell,
            pass_hash,
            uat_hash,
        )

    console.print(table)
    console.print()

    # --- Summary footer ---
    status_label_style = {
        "broken": "red",
        "stale": "yellow",
        "never-passed": "cyan",
        "untested": "dim",
        "passing": "green",
        "uat-verified": "bright_green",
    }
    count_parts = [f"[bold]{total_shown} shown[/bold]"]
    for key in ("broken", "stale", "never-passed", "untested", "passing", "uat-verified"):
        n = status_counts.get(key, 0)
        if n:
            sty = status_label_style.get(key, "default")
            count_parts.append(f"[{sty}]{n} {key}[/{sty}]")
    if flaky_count:
        count_parts.append(f"[yellow bold]{flaky_count} flaky[/yellow bold]")

    footer = "  [bold]Stories:[/bold] " + " | ".join(count_parts)
    if hidden_archived_count:
        footer += f"   [dim]({hidden_archived_count} archived hidden \u2014 use --all)[/dim]"
    console.print(footer)

    # --- Pytest marker coverage (--coverage mode) ---
    if marker_coverage is not None:
        mc = marker_coverage
        console.print(f"\n  [bold cyan]Pytest Marker Coverage:[/bold cyan]")
        console.print(f"  [green]Covered:[/green]    {mc['covered_by_markers']}/{mc['total_stories']} ({mc['coverage_pct']:.0f}%)")
        if mc["uncovered"]:
            console.print(f"  [red]Uncovered:[/red]  {len(mc['uncovered'])} stories without @pytest.mark.story markers")
            for sid in mc["uncovered"][:20]:
                console.print(f"    [dim]- {sid}[/dim]")
            if len(mc["uncovered"]) > 20:
                console.print(f"    [dim]... and {len(mc['uncovered']) - 20} more[/dim]")
        else:
            console.print(f"  [green]All stories have @pytest.mark.story markers![/green]")
        if mc["orphan_markers"]:
            console.print(f"  [yellow]Orphan markers:[/yellow] {len(mc['orphan_markers'])} markers reference non-existent story IDs")
            for sid in mc["orphan_markers"]:
                console.print(f"    [dim]- {sid}[/dim]")


def cmd_untested(args):
    """List stories that have no test status or are marked untested."""
    from agenticcli.console import console, is_json_output, print_header, print_json

    project_filter = getattr(args, "project", None)
    stories = _collect_all_stories(project_filter=project_filter)

    untested = [s for s in stories if s.get("test_status", "untested") == "untested"]

    if is_json_output():
        print_json({
            "untested": untested,
            "count": len(untested),
            "project_filter": project_filter,
        })
        return

    title = "Untested Stories"
    if project_filter:
        title += f" (project: {project_filter})"
    print_header(title)

    if not untested:
        console.print("  [green]All stories have been tested![/green]")
        return

    # Group by project
    by_project: dict[str, list[dict]] = {}
    for s in untested:
        proj = s.get("project", "unknown")
        by_project.setdefault(proj, []).append(s)

    for proj in sorted(by_project):
        proj_stories = by_project[proj]
        console.print(f"\n  [bold magenta]{proj}[/bold magenta] ({len(proj_stories)} untested)")
        for s in proj_stories:
            title = s.get("title", "(no title)")[:60]
            console.print(f"    [cyan]{s['id']}[/cyan]: {title}")

    console.print(f"\n  [bold]Total untested:[/bold] {len(untested)}")


def _find_affected_story_ids(plan_folder: str) -> list[str]:
    """Find affected story IDs for an epic.

    Checks user_stories.yml in the epic folder for affected_stories lists.
    Epic/ticket data is stored in TinyDB; this function only looks for
    the standalone user_stories.yml artifact.
    """
    epic_dir = None
    for base in [Path.cwd() / "docs" / "epics" / "live",
                 Path.cwd() / "docs" / "epics" / "completed",
                 # Legacy paths for backward compatibility
                 Path.cwd() / "docs" / "plans" / "live",
                 Path.cwd() / "docs" / "plans" / "completed"]:
        candidate = base / plan_folder
        if candidate.exists():
            epic_dir = candidate
            break

    if not epic_dir:
        return []

    story_ids = []
    # Check user_stories.yml (standalone artifact, not plan YAML)
    stories_file = epic_dir / "user_stories.yml"
    if stories_file.exists():
        try:
            content = yaml.safe_load(stories_file.read_text())
        except yaml.YAMLError:
            content = None
        if content and isinstance(content, dict):
            affected = content.get("affected_stories", [])
            if isinstance(affected, list):
                for item in affected:
                    sid = str(item).split(":")[0].strip().strip('"').strip("'")
                    if sid and sid not in story_ids:
                        story_ids.append(sid)

    return story_ids


def cmd_batch_update(args):
    """Update all affected stories in a plan at once."""
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success

    plan_folder = args.plan
    story_ids = _find_affected_story_ids(plan_folder)

    if not story_ids:
        if is_json_output():
            print_json({"error": f"No affected_stories found for plan: {plan_folder}"})
        else:
            print_error(f"No affected_stories found for plan: {plan_folder}")
        sys.exit(1)

    updated = []
    errors = []
    now = datetime.now(timezone.utc).isoformat()
    notes = args.notes if args.notes else ""

    svc = StoryService(_find_userstories_dir())

    for story_id in story_ids:
        ok = svc.update_test_status(
            story_id,
            args.status,
            tested_by=plan_folder,
            test_notes=notes,
            last_tested=now,
        )
        if ok:
            updated.append(story_id)
        else:
            errors.append({"id": story_id, "error": "Story not found or could not be updated"})

    if is_json_output():
        print_json({
            "plan": plan_folder,
            "status": args.status,
            "updated": updated,
            "errors": errors,
            "count": len(updated),
        })
        return

    if updated:
        print_success(f"Updated {len(updated)} stories to {args.status}")
        for sid in updated:
            console.print(f"  [green]{sid}[/green]")

    if errors:
        for err in errors:
            console.print(f"  [red]{err['id']}[/red]: {err['error']}")


def cmd_affected(args):
    """List affected stories for a plan, by file changes, or by commit hash.

    When --commit is provided, uses git diff + story related_files and # story: headers
    to identify affected stories.
    When --changes is provided (comma-separated file paths or 'git' for git diff),
    cross-references testmon data and story_tests TinyDB to show which stories
    are affected by the file changes.
    """
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json

    commit = getattr(args, "commit", None)
    if commit:
        _cmd_affected_by_commit(args, commit)
        return

    changes = getattr(args, "changes", None)
    if changes:
        # Testmon-based affected analysis
        if changes == "git":
            import subprocess
            repo_root = Path.cwd()
            while repo_root != repo_root.parent:
                if (repo_root / ".git").exists():
                    break
                repo_root = repo_root.parent
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True, text=True, cwd=str(repo_root), timeout=30,
            )
            changed_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        else:
            changed_files = [f.strip() for f in changes.split(",") if f.strip()]

        story_map = _get_affected_stories_from_changes(changed_files)

        if is_json_output():
            print_json({
                "changed_files": changed_files,
                "affected_stories": {sid: tests for sid, tests in sorted(story_map.items())},
                "story_count": len(story_map),
            })
            return

        print_header("Stories Affected by Changes")
        if not story_map:
            console.print("  [dim]No story-linked tests affected by these changes[/dim]")
            console.print("  [dim](Ensure 'agentic stories sync' has been run and testmon data exists)[/dim]")
        else:
            for sid in sorted(story_map):
                tests = story_map[sid]
                console.print(f"  [cyan]{sid}[/cyan]: {len(tests)} affected test(s)")
                for t in tests[:5]:
                    console.print(f"    [dim]- {t}[/dim]")
                if len(tests) > 5:
                    console.print(f"    [dim]... and {len(tests) - 5} more[/dim]")
        console.print(f"\n  Changed files: {len(changed_files)}")
        console.print(f"  Affected stories: {len(story_map)}")
        return

    plan_folder = args.plan
    story_ids = _find_affected_story_ids(plan_folder)

    if not story_ids:
        if is_json_output():
            print_json({"error": f"No affected_stories found for plan: {plan_folder}"})
        else:
            print_error(f"No affected_stories found for plan: {plan_folder}")
        sys.exit(1)

    svc = StoryService(_find_userstories_dir())
    results = []
    for story_id in story_ids:
        story_obj = svc.get_by_id(story_id)
        if story_obj is None:
            results.append({"id": story_id, "title": "(not found)", "test_status": "unknown", "file": None})
        else:
            results.append({
                "id": story_obj.id,
                "title": story_obj.title,
                "test_status": story_obj.test_status or "untested",
                "last_tested": story_obj.last_tested or None,
                "tested_by_plan": story_obj.tested_by_plan or None,
                "file": story_obj.source_file,
            })

    if is_json_output():
        print_json({
            "plan": plan_folder,
            "affected_stories": results,
            "count": len(results),
        })
        return

    print_header(f"Affected Stories: {plan_folder}")

    for r in results:
        ts = r["test_status"]
        if ts == "pass":
            status_str = "[green]pass[/green]"
        elif ts == "fail":
            status_str = "[red]fail[/red]"
        elif ts == "regression":
            status_str = "[red]regression[/red]"
        elif ts == "skip":
            status_str = "[yellow]skip[/yellow]"
        else:
            status_str = f"[dim]{ts}[/dim]"

        title = r.get("title", "")[:50]
        console.print(f"  [cyan]{r['id']}[/cyan]: {title} [{status_str}]")

    console.print(f"\n  [bold]Total:[/bold] {len(results)} affected stories")


def _cmd_affected_by_commit(args, commit: str):
    """Handle --commit flag for cmd_affected: git-based story impact detection."""
    from agenticcli.console import console, is_json_output, print_header, print_json

    repo_root = _find_repo_root()
    if repo_root is None:
        print("Error: Not in a git repository.", file=sys.stderr)
        sys.exit(1)

    # Get changed files from commit
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{commit}~1..{commit}"],
            capture_output=True, text=True, cwd=str(repo_root), timeout=30,
        )
        if result.returncode != 0:
            # Fallback for initial commits or ranges
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{commit}"],
                capture_output=True, text=True, cwd=str(repo_root), timeout=30,
            )
        changed_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("Error: git command failed.", file=sys.stderr)
        sys.exit(1)

    if not changed_files:
        if is_json_output():
            print_json({"commit": commit, "changed_files": [], "affected_stories": [], "count": 0})
        else:
            print_header(f"Stories Affected by Commit: {commit}")
            console.print("  [dim]No files changed in this commit[/dim]")
        return

    # Two detection methods:
    # 1. Grep # story: headers in changed files
    # 2. Check story YAML related_files for matches
    affected: dict[str, dict] = {}  # story_id -> {title, source, status}

    svc = StoryService(_find_userstories_dir())
    all_stories = svc.load_all()

    # Method 1: scan # story: headers in changed files
    for f in changed_files:
        fpath = repo_root / f
        if not fpath.exists() or not fpath.suffix == ".py":
            continue
        try:
            first_lines = fpath.read_text().split("\n")[:5]
            for line in first_lines:
                m = re.match(r"^#\s*story:\s*(.+)$", line)
                if m:
                    for sid in re.findall(r"US-[A-Z0-9]+-\d+", m.group(1)):
                        if sid not in affected:
                            story_obj = svc.get_by_id(sid)
                            affected[sid] = {
                                "id": sid,
                                "title": story_obj.title if story_obj else "(unknown)",
                                "status": svc.compute_story_status(story_obj, repo_root) if story_obj else "unknown",
                                "source": "header",
                            }
        except OSError:
            continue

    # Method 2: check related_files on all stories
    changed_set = set(changed_files)
    for story in all_stories:
        if story.id in affected:
            continue
        if story.related_files and set(story.related_files) & changed_set:
            affected[story.id] = {
                "id": story.id,
                "title": story.title,
                "status": svc.compute_story_status(story, repo_root),
                "source": "related_files",
            }

    results = sorted(affected.values(), key=lambda x: x["id"])

    if is_json_output():
        print_json({
            "commit": commit,
            "changed_files": changed_files,
            "affected_stories": results,
            "count": len(results),
        })
        return

    print_header(f"Stories Affected by Commit: {commit}")
    if not results:
        console.print("  [dim]No stories affected by this commit[/dim]")
    else:
        _eff_style = {"passing": "green", "stale": "yellow", "broken": "red", "untested": "dim"}
        for r in results:
            style = _eff_style.get(r["status"], "dim")
            console.print(f"  [cyan]{r['id']}[/cyan]: {r['title'][:50]} [{style}]{r['status']}[/{style}]")
    console.print(f"\n  Changed files: {len(changed_files)} | Affected stories: {len(results)}")


def _testmon_affected_tests(changed_files: list[str]) -> set[str]:
    """Query testmon's SQLite DB to find tests affected by changed source files.

    Args:
        changed_files: List of file paths (relative to repo root) that changed.

    Returns:
        Set of test nodeid strings affected by the changes. Empty if testmon
        data is unavailable.
    """
    import sqlite3

    # Find repo root
    repo_root = Path.cwd()
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent

    # Look for .testmondata in module test dirs and repo root
    testmon_paths = [
        repo_root / ".testmondata",
        repo_root / "modules" / "AgenticCLI" / ".testmondata",
        repo_root / "modules" / "AgenticGuidance" / ".testmondata",
    ]

    affected_tests: set[str] = set()

    for db_path in testmon_paths:
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            # testmon stores file fingerprints and node dependencies
            # node_data table: node (test nodeid), fingerprint, ...
            # node_file table: node_id, file_fingerprint_id
            # file_fingerprint table: id, filename, fingerprint
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            if "node" not in tables:
                conn.close()
                continue

            # Get all test nodes that depend on the changed files
            for changed_file in changed_files:
                # testmon stores relative paths; try matching
                cursor.execute(
                    "SELECT DISTINCT node FROM node WHERE "
                    "node IN (SELECT node FROM node_file nf "
                    "JOIN file_fingerprint ff ON nf.file_fingerprint_id = ff.id "
                    "WHERE ff.filename LIKE ?)",
                    (f"%{Path(changed_file).name}",),
                )
                for row in cursor.fetchall():
                    affected_tests.add(row[0])

            conn.close()
        except (sqlite3.Error, OSError):
            continue

    return affected_tests


def _get_affected_stories_from_changes(changed_files: list[str]) -> dict[str, list[str]]:
    """Cross-reference changed files -> testmon -> story_tests TinyDB.

    Args:
        changed_files: List of changed file paths.

    Returns:
        Dict mapping story_id -> list of affected test nodeids.
    """
    # Get affected tests from testmon
    affected_tests = _testmon_affected_tests(changed_files)

    if not affected_tests:
        return {}

    # Cross-reference with story_tests TinyDB
    db_path = _get_repo_db_path()
    from agenticguidance.services.epic_repository import EpicRepository
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    story_map: dict[str, list[str]] = {}
    for test_nodeid in affected_tests:
        story_ids = repo.get_stories_for_test(test_nodeid)
        for sid in story_ids:
            story_map.setdefault(sid, []).append(test_nodeid)

    repo.close()
    return story_map


def cmd_sync(args):
    """Scan test files and production code for story markers and sync to TinyDB."""
    from agenticcli.console import console, is_json_output, print_json, print_success

    mappings = _scan_pytest_story_markers_detailed()
    all_story_ids = {s["id"] for s in _collect_all_stories()}

    # Count stats
    total_tests = sum(len(v) for v in mappings.values())
    orphan_markers = sorted(set(mappings.keys()) - all_story_ids)

    # Scan production code for @story() decorators
    code_mappings = _scan_production_code_story_markers()
    total_code_fns = sum(len(v) for v in code_mappings.values())

    # Write to TinyDB
    db_path = _get_repo_db_path()
    from agenticguidance.services.epic_repository import EpicRepository
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    repo.clear_story_tests()
    count = repo.sync_story_tests(mappings)
    repo.clear_story_code()
    code_count = repo.sync_story_code(code_mappings)
    repo.close()

    if is_json_output():
        print_json({
            "stories_synced": count,
            "test_functions": total_tests,
            "stories_covered": len(mappings),
            "orphan_markers": orphan_markers,
            "code_stories_synced": code_count,
            "code_functions": total_code_fns,
        })
        return

    print_success(f"Synced {count} stories with {total_tests} test functions")
    console.print(f"  Stories with test markers: {len(mappings)}")
    if code_count:
        print_success(f"Synced {code_count} stories with {total_code_fns} production code functions")
    else:
        console.print("  [dim]No @story() decorators found in production code[/dim]")
    if orphan_markers:
        console.print(f"  [yellow]Orphan markers ({len(orphan_markers)}):[/yellow] markers referencing non-existent story IDs")
        for sid in orphan_markers[:10]:
            console.print(f"    [dim]- {sid}[/dim]")
        if len(orphan_markers) > 10:
            console.print(f"    [dim]... and {len(orphan_markers) - 10} more[/dim]")


def cmd_run(args):
    """Run tests for a specific story ID using the TinyDB index."""
    import subprocess

    from agenticcli.console import is_json_output, print_error, print_json

    story_id = args.story_id
    module_filter = getattr(args, "module", None)
    use_testmon = getattr(args, "testmon", False)

    db_path = _get_repo_db_path()
    from agenticguidance.services.epic_repository import EpicRepository
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    test_nodeids = repo.get_tests_for_story(story_id)
    repo.close()

    if not test_nodeids:
        if is_json_output():
            print_json({"error": f"No tests found for story {story_id}. Run 'agentic stories sync' first."})
        else:
            print_error(f"No tests found for story {story_id}. Run 'agentic stories sync' first.")
        sys.exit(1)

    # Filter by module if requested
    if module_filter:
        test_nodeids = [n for n in test_nodeids if module_filter in n]
        if not test_nodeids:
            if is_json_output():
                print_json({"error": f"No tests for {story_id} in module '{module_filter}'"})
            else:
                print_error(f"No tests for {story_id} in module '{module_filter}'")
            sys.exit(1)

    # Find repo root for running pytest
    cwd = Path.cwd()
    repo_root = cwd
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent

    cmd = ["python3", "-m", "pytest", "-v"] + test_nodeids
    if use_testmon:
        cmd.insert(4, "--testmon")

    result = subprocess.run(cmd, cwd=str(repo_root))
    sys.exit(result.returncode)


def _lifecycle_transition(args, target_state: str, verb: str):
    """Common logic for lifecycle transition commands."""
    from agenticguidance.services.story import LIFECYCLE_TRANSITIONS

    from agenticcli.console import is_json_output, print_error, print_json, print_success

    story_id = args.story_id
    svc = StoryService(_find_userstories_dir())
    story_obj = svc.get_by_id(story_id)

    if story_obj is None:
        if is_json_output():
            print_json({"error": f"Story not found: {story_id}"})
        else:
            print_error(f"Story not found: {story_id}")
        sys.exit(1)

    if not story_obj.can_transition_to(target_state):
        allowed = LIFECYCLE_TRANSITIONS.get(story_obj.lifecycle, [])
        msg = (
            f"Cannot {verb} {story_id}: lifecycle is '{story_obj.lifecycle}', "
            f"allowed transitions: {allowed or 'none'}"
        )
        if is_json_output():
            print_json({"error": msg, "current_lifecycle": story_obj.lifecycle})
        else:
            print_error(msg)
        sys.exit(1)

    updated = svc.update_lifecycle(story_id, target_state)
    if not updated:
        print_error(f"Could not update story {story_id}")
        sys.exit(1)

    if is_json_output():
        print_json({
            "story_id": story_id,
            "previous_lifecycle": story_obj.lifecycle,
            "lifecycle": target_state,
        })
    else:
        print_success(f"{story_id}: {story_obj.lifecycle} -> {target_state}")


def cmd_promote(args):
    """Advance story lifecycle: proposal -> under-construction -> implemented."""
    from agenticguidance.services.story import LIFECYCLE_TRANSITIONS

    story_id = args.story_id
    svc = StoryService(_find_userstories_dir())
    story_obj = svc.get_by_id(story_id)

    if story_obj is None:
        from agenticcli.console import is_json_output, print_error, print_json
        if is_json_output():
            print_json({"error": f"Story not found: {story_id}"})
        else:
            print_error(f"Story not found: {story_id}")
        sys.exit(1)

    # Determine next promotion target
    promote_map = {
        "proposal": "under-construction",
        "under-construction": "implemented",
    }
    target = promote_map.get(story_obj.lifecycle)
    if not target:
        from agenticcli.console import is_json_output, print_error, print_json
        msg = f"Cannot promote {story_id}: lifecycle '{story_obj.lifecycle}' is not promotable"
        if is_json_output():
            print_json({"error": msg, "current_lifecycle": story_obj.lifecycle})
        else:
            print_error(msg)
        sys.exit(1)

    _lifecycle_transition(args, target, "promote")


def cmd_deprecate(args):
    """Mark story as deprecated: implemented -> deprecated."""
    _lifecycle_transition(args, "deprecated", "deprecate")


def cmd_archive(args):
    """Archive a deprecated story: deprecated -> archived."""
    _lifecycle_transition(args, "archived", "archive")


def cmd_code(args):
    """Show production code tagged with a story ID."""
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json

    story_id = args.story_id

    db_path = _get_repo_db_path()
    from agenticguidance.services.epic_repository import EpicRepository
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    code_fns = repo.get_code_for_story(story_id)
    repo.close()

    if is_json_output():
        print_json({
            "story_id": story_id,
            "code_functions": code_fns,
            "count": len(code_fns),
        })
        return

    if not code_fns:
        print_header(f"Code for {story_id}")
        console.print("  [dim]No production code tagged with this story. Run 'agentic stories sync' first.[/dim]")
        return

    print_header(f"Code for {story_id} ({len(code_fns)} functions)")
    for fn in code_fns:
        console.print(f"  {fn}")


def _story_has_uat_plan(story: dict) -> bool:
    """Return True if the story has a minimally-populated uat_plan block.

    A uat_plan is considered present when all of the following are set:
    - persona (non-empty string)
    - starting_state (non-empty string)
    - journey (list with at least one entry having both action and observe)
    - success_signals (non-empty list)

    Preconditions and cleanup are optional. This is the same bar
    `agentic stories audit` enforces and matches the Phase 1 forcing
    function for story writers.
    """
    plan = story.get("uat_plan")
    if not isinstance(plan, dict) or not plan:
        return False
    if not (plan.get("persona") and plan.get("starting_state")):
        return False
    journey = plan.get("journey") or []
    if not isinstance(journey, list) or not journey:
        return False
    has_step = any(
        isinstance(j, dict) and j.get("action") and j.get("observe")
        for j in journey
    )
    if not has_step:
        return False
    signals = plan.get("success_signals") or []
    if not isinstance(signals, list) or not signals:
        return False
    return True


# @story US-004
def cmd_audit(args):
    """Story audit: epic coverage, file↔YAML consistency, or ticket traceability."""
    check_files = getattr(args, "check_files", False)
    check_tickets = getattr(args, "check_tickets", False)
    check_uat_plan = getattr(args, "check_uat_plan", False)

    if check_files:
        _cmd_audit_check_files(args)
        return
    if check_tickets:
        _cmd_audit_check_tickets(args)
        return
    if check_uat_plan:
        _cmd_audit_check_uat_plan(args)
        return

    # Original epic-based audit
    from agenticcli.console import console, is_json_output, print_header, print_json

    epic_name = getattr(args, "epic", None) or getattr(args, "plan", None)
    if not epic_name:
        print("Error: --epic, --check-files, or --check-tickets is required.", file=sys.stderr)
        sys.exit(1)

    # Resolve epic folder via TinyDB lookup
    from agenticcli.commands.epic import find_epic_folder

    epic_folder = find_epic_folder(epic_name)

    # Deprecation check: warn if stories.yml exists at old epic-folder location
    old_stories_path = epic_folder / "stories.yml"
    if old_stories_path.exists():
        print(
            f"DEPRECATED: stories.yml found at {old_stories_path} — "
            f"stories should be at docs/userstories/EpicStories/{epic_folder.name}.yml",
            file=sys.stderr,
        )

    # Load stories from docs/userstories/EpicStories/{epic_folder_name}.yml
    stories_path = get_epic_stories_path(epic_folder.name)
    stories_list = []
    stories_missing = False
    if stories_path.exists():
        try:
            raw = yaml.safe_load(stories_path.read_text())
            stories_list = (raw or {}).get("stories", []) or []
        except Exception:
            stories_list = []
    else:
        stories_missing = True

    # Get tickets from TinyDB
    from agenticguidance.services.epic_repository import EpicRepository

    repo = EpicRepository()
    tickets = repo.get_tickets(epic_folder.name)
    repo.close()

    # Compute unlinked tickets (tickets with empty story_ids)
    unlinked_tickets = []
    for t in tickets:
        ticket_stories = getattr(t, "story_ids", None) or []
        if not ticket_stories:
            unlinked_tickets.append({
                "ticket_id": t.id,
                "description": t.name or t.description or "",
            })

    # Compute all story IDs referenced across all tickets
    all_ticket_story_ids = set()
    for t in tickets:
        ticket_stories = getattr(t, "story_ids", None) or []
        for sid in ticket_stories:
            all_ticket_story_ids.add(sid)

    # Compute orphan stories (stories not referenced by any ticket)
    orphan_stories = []
    for s in stories_list:
        story_id = s.get("id", "")
        if story_id and story_id not in all_ticket_story_ids:
            orphan_stories.append({
                "story_id": story_id,
                "title": s.get("title", ""),
            })

    # Compute stories missing a uat_plan (Phase 1 of Story-Writer UAT-First Restructure).
    # Deprecated/archived stories are excused because the journey is owned by a successor.
    missing_uat_plan = [
        s.get("id", "")
        for s in stories_list
        if s.get("id")
        and s.get("lifecycle") not in ("deprecated", "archived")
        and not _story_has_uat_plan(s)
    ]

    summary = {
        "total_tickets": len(tickets),
        "unlinked_ticket_count": len(unlinked_tickets),
        "total_stories": len(stories_list),
        "orphan_story_count": len(orphan_stories),
        "missing_uat_plan_count": len(missing_uat_plan),
        "stories_yml_missing": stories_missing,
        "fully_covered": len(unlinked_tickets) == 0 and len(orphan_stories) == 0,
    }

    if is_json_output():
        print_json({
            "epic": epic_folder.name,
            "unlinked_tickets": unlinked_tickets,
            "orphan_stories": orphan_stories,
            "missing_uat_plan": missing_uat_plan,
            "summary": summary,
        })
        return

    # Human-readable output
    print_header(f"Story Audit: {epic_folder.name}")

    if stories_missing:
        console.print(f"  [yellow]⚠ No story file found at {stories_path}[/yellow]")
        console.print()

    if summary["fully_covered"] and not stories_missing:
        console.print("  [green]✓ Full bidirectional coverage — zero gaps[/green]")
        console.print(f"    {summary['total_tickets']} ticket(s), {summary['total_stories']} story/stories")
        return

    if unlinked_tickets:
        console.print(f"  [red]Unlinked Tickets ({len(unlinked_tickets)}):[/red]")
        for ut in unlinked_tickets:
            console.print(f"    [dim]•[/dim] {ut['ticket_id']}: {ut['description']}")
        console.print()

    if orphan_stories:
        console.print(f"  [yellow]Orphan Stories ({len(orphan_stories)}):[/yellow]")
        for os_entry in orphan_stories:
            console.print(f"    [dim]•[/dim] {os_entry['story_id']}: {os_entry['title']}")
        console.print()

    if missing_uat_plan:
        console.print(f"  [yellow]Stories missing uat_plan ({len(missing_uat_plan)}):[/yellow]")
        for sid in missing_uat_plan:
            console.print(f"    [dim]•[/dim] {sid}")
        console.print()

    console.print(f"  [bold]Summary:[/bold] {summary['unlinked_ticket_count']} unlinked ticket(s), "
                  f"{summary['orphan_story_count']} orphan story/stories, "
                  f"{summary['missing_uat_plan_count']} missing uat_plan")


def _cmd_audit_check_files(args):
    """Validate bidirectional consistency between YAML related_files and # story: headers."""
    from agenticcli.console import console, is_json_output, print_header, print_json

    strict = getattr(args, "strict", False)
    repo_root = _find_repo_root()
    if repo_root is None:
        print("Error: Not in a git repository.", file=sys.stderr)
        sys.exit(1)

    svc = StoryService(_find_userstories_dir())
    all_stories = svc.load_all()

    # Build YAML-side mapping: file → story IDs from related_files
    yaml_file_to_stories: dict[str, set[str]] = {}
    for story in all_stories:
        for f in story.related_files:
            yaml_file_to_stories.setdefault(f, set()).add(story.id)

    # Build header-side mapping: file → story IDs from # story: comments
    header_file_to_stories: dict[str, set[str]] = {}
    for f in yaml_file_to_stories:
        fpath = repo_root / f
        if not fpath.exists():
            continue
        try:
            first_lines = fpath.read_text().split("\n")[:5]
            for line in first_lines:
                m = re.match(r"^#\s*story:\s*(.+)$", line)
                if m:
                    for sid in re.findall(r"US-[A-Z0-9]+-\d+", m.group(1)):
                        header_file_to_stories.setdefault(f, set()).add(sid)
        except OSError:
            continue

    # Also scan all source files for headers not in YAML
    src_dirs = list((repo_root / "modules").glob("*/src"))
    for src_dir in src_dirs:
        for py_file in sorted(src_dir.rglob("*.py")):
            if py_file.name in ("__init__.py", "conftest.py"):
                continue
            rel = str(py_file.relative_to(repo_root))
            if rel in header_file_to_stories:
                continue
            try:
                first_lines = py_file.read_text().split("\n")[:5]
                for line in first_lines:
                    m = re.match(r"^#\s*story:\s*(.+)$", line)
                    if m:
                        for sid in re.findall(r"US-[A-Z0-9]+-\d+", m.group(1)):
                            header_file_to_stories.setdefault(rel, set()).add(sid)
            except OSError:
                continue

    # Find mismatches
    mismatches = []

    # Files in YAML but missing header or with wrong IDs
    all_files = set(yaml_file_to_stories) | set(header_file_to_stories)
    for f in sorted(all_files):
        yaml_ids = yaml_file_to_stories.get(f, set())
        header_ids = header_file_to_stories.get(f, set())
        if yaml_ids != header_ids:
            mismatches.append({
                "file": f,
                "yaml_stories": sorted(yaml_ids),
                "header_stories": sorted(header_ids),
                "missing_in_header": sorted(yaml_ids - header_ids),
                "missing_in_yaml": sorted(header_ids - yaml_ids),
            })

    if is_json_output():
        print_json({
            "check": "files",
            "total_files": len(all_files),
            "mismatches": mismatches,
            "mismatch_count": len(mismatches),
            "consistent": len(mismatches) == 0,
        })
        if strict and mismatches:
            sys.exit(1)
        return

    print_header("Story File Audit: YAML ↔ Header Consistency")
    if not mismatches:
        console.print(f"  [green]All {len(all_files)} files are consistent[/green]")
        return

    for mm in mismatches:
        console.print(f"  [yellow]{mm['file']}[/yellow]")
        if mm["missing_in_header"]:
            console.print(f"    [red]Missing in header:[/red] {', '.join(mm['missing_in_header'])}")
        if mm["missing_in_yaml"]:
            console.print(f"    [red]Missing in YAML:[/red] {', '.join(mm['missing_in_yaml'])}")

    console.print(f"\n  {len(mismatches)} file(s) with mismatches out of {len(all_files)}")
    if strict:
        sys.exit(1)


def _cmd_audit_check_tickets(args):
    """Check that tickets on live epics have story_ids."""
    from agenticcli.console import console, is_json_output, print_header, print_json

    from agenticguidance.services.epic_repository import EpicRepository

    strict = getattr(args, "strict", False)
    repo = EpicRepository()
    all_epics = repo.list_epics()

    unlinked_by_epic = {}
    total_tickets = 0
    total_unlinked = 0

    for epic in all_epics:
        if epic.status in ("completed", "archived"):
            continue
        epic_name = epic.epic_folder_name
        tickets = repo.get_tickets(epic_name)
        epic_unlinked = []
        for t in tickets:
            total_tickets += 1
            ticket_stories = getattr(t, "story_ids", None) or []
            if not ticket_stories:
                total_unlinked += 1
                epic_unlinked.append({
                    "ticket_id": t.id,
                    "description": getattr(t, "name", "") or getattr(t, "description", "") or "",
                })
        if epic_unlinked:
            unlinked_by_epic[epic_name] = epic_unlinked

    repo.close()

    if is_json_output():
        print_json({
            "check": "tickets",
            "total_tickets": total_tickets,
            "unlinked_count": total_unlinked,
            "unlinked_by_epic": unlinked_by_epic,
            "all_linked": total_unlinked == 0,
        })
        if strict and total_unlinked > 0:
            sys.exit(1)
        return

    print_header("Story Audit: Ticket Traceability")
    if not unlinked_by_epic:
        console.print(f"  [green]All {total_tickets} tickets across live epics have story_ids[/green]")
        return

    for epic_name, tickets in sorted(unlinked_by_epic.items()):
        console.print(f"  [yellow]{epic_name}[/yellow] — {len(tickets)} unlinked ticket(s):")
        for t in tickets[:10]:
            console.print(f"    [dim]-[/dim] {t['ticket_id']}: {t['description'][:60]}")
        if len(tickets) > 10:
            console.print(f"    [dim]... and {len(tickets) - 10} more[/dim]")

    console.print(f"\n  {total_unlinked}/{total_tickets} tickets missing story_ids")
    if strict:
        sys.exit(1)


def _cmd_audit_check_uat_plan(args):
    """Scan ALL stories for a present-and-minimally-populated uat_plan block.

    Global (non-epic-scoped) audit. Walks every story loaded by StoryService
    and reports which stories are missing the uat_plan required by the
    Phase 1 guidance. Non-fatal by default; use --strict to exit non-zero
    when any stories are missing uat_plan (for CI gating of new categories).
    """
    from agenticcli.console import console, is_json_output, print_header, print_json

    strict = getattr(args, "strict", False)
    category_filter = getattr(args, "category", None)

    userstories_dir = _find_userstories_dir()
    if userstories_dir is None or not userstories_dir.exists():
        print("Error: userstories directory not found.", file=sys.stderr)
        sys.exit(1)
    missing_by_file: dict[str, list[str]] = {}
    missing_ids: list[str] = []
    total = 0

    for yml_path in sorted(userstories_dir.rglob("*.yml")):
        if yml_path.name == "00_metadata.yml":
            continue
        if category_filter and category_filter not in str(yml_path.relative_to(userstories_dir)):
            continue
        try:
            raw = yaml.safe_load(yml_path.read_text()) or {}
        except Exception:
            continue
        stories = raw.get("stories") or raw.get("user_stories") or []
        if not isinstance(stories, list):
            continue
        rel = str(yml_path.relative_to(userstories_dir))
        for s in stories:
            if not isinstance(s, dict):
                continue
            sid = s.get("id")
            if not sid:
                continue
            # Skip deprecated/archived stories — they're excused from uat_plan
            # coverage because the journey is owned by a successor story.
            if s.get("lifecycle") in ("deprecated", "archived"):
                continue
            total += 1
            if not _story_has_uat_plan(s):
                missing_ids.append(sid)
                missing_by_file.setdefault(rel, []).append(sid)

    if is_json_output():
        print_json({
            "check": "uat_plan",
            "total_stories": total,
            "missing_uat_plan": missing_ids,
            "missing_by_file": missing_by_file,
            "missing_count": len(missing_ids),
            "all_have_uat_plan": len(missing_ids) == 0,
        })
        if strict and missing_ids:
            sys.exit(1)
        return

    print_header("Story Audit: uat_plan Coverage")
    if not missing_ids:
        console.print(f"  [green]All {total} stories have a uat_plan[/green]")
        return

    for rel, ids in sorted(missing_by_file.items()):
        console.print(f"  [yellow]{rel}[/yellow] — {len(ids)} missing:")
        for sid in ids[:20]:
            console.print(f"    [dim]-[/dim] {sid}")
        if len(ids) > 20:
            console.print(f"    [dim]... and {len(ids) - 20} more[/dim]")

    console.print(f"\n  {len(missing_ids)}/{total} stories missing uat_plan")
    if strict:
        sys.exit(1)


# ===========================================================================
# PATTERN COMMANDS
# ===========================================================================


def cmd_patterns(args):
    """List all verification patterns, optionally filtered by domain."""
    from agenticcli.console import console, is_json_output, print_json

    pat_svc = PatternService(_find_userstories_dir())
    patterns = pat_svc.load_all()

    domain_filter = getattr(args, "domain", None)
    if domain_filter:
        patterns = [p for p in patterns if p.domain == domain_filter.upper()]

    if is_json_output():
        print_json([
            {"id": p.id, "title": p.title, "domain": p.domain,
             "tags": p.tags, "param_count": len(p.parameters),
             "source_file": p.source_file}
            for p in patterns
        ])
        return

    if not patterns:
        console.print("[dim]No patterns found.[/dim]")
        return

    console.print(f"[bold]Patterns ({len(patterns)}):[/bold]\n")
    current_domain = None
    for p in sorted(patterns, key=lambda x: x.id):
        if p.domain != current_domain:
            current_domain = p.domain
            console.print(f"  [bold cyan]{current_domain}[/bold cyan]")
        params = ", ".join(p.parameters.keys()) if p.parameters else "none"
        console.print(f"    {p.id}  {p.title}  [dim]params: {params}[/dim]")


def cmd_pattern_cat(args):
    """Display a pattern's full content."""
    from agenticcli.console import console, is_json_output, print_error, print_json

    pat_svc = PatternService(_find_userstories_dir())
    pattern = pat_svc.get_by_id(args.id)

    if not pattern:
        print_error(f"Pattern not found: {args.id}")
        sys.exit(1)

    if is_json_output():
        print_json({
            "id": pattern.id,
            "title": pattern.title,
            "description": pattern.description,
            "domain": pattern.domain,
            "tags": pattern.tags,
            "applicable_categories": pattern.applicable_categories,
            "parameters": pattern.parameters,
            "verification": pattern.verification,
            "source_file": pattern.source_file,
            "watch_files": list(pattern.watch_files),
        })
        return

    console.print(f"[bold]{pattern.id}[/bold] — {pattern.title}\n")
    if pattern.description:
        console.print(f"  {pattern.description.strip()}\n")
    if pattern.tags:
        console.print(f"  [dim]Tags:[/dim] {', '.join(pattern.tags)}")
    if pattern.applicable_categories:
        console.print(f"  [dim]Applies to:[/dim] {', '.join(pattern.applicable_categories)}")

    if pattern.parameters:
        console.print("\n  [bold]Parameters:[/bold]")
        for name, spec in pattern.parameters.items():
            req = "[red]*[/red]" if (isinstance(spec, dict) and spec.get("required", True)) else ""
            desc = spec.get("description", "") if isinstance(spec, dict) else str(spec)
            console.print(f"    {req}{name}: {desc}")

    verification = pattern.verification
    if verification.get("behavioral"):
        console.print("\n  [bold]Behavioral Verification:[/bold]")
        for step in verification["behavioral"].get("steps", []):
            console.print(f"    Step {step.get('step', '?')}: {step.get('action', '')}")
            console.print(f"      [green]Expect:[/green] {step.get('expect', '')}")

    if verification.get("structural"):
        console.print("\n  [bold]Structural Checks:[/bold]")
        for check in verification["structural"].get("checks", []):
            console.print(f"    {check.get('description', '')}")
            console.print(f"      [dim]grep:[/dim] {check.get('look_for', '')} [dim]in[/dim] {check.get('in_files', '')}")

    if verification.get("enforcement"):
        console.print("\n  [bold]Enforcement:[/bold]")
        console.print(f"    Sweep: {verification['enforcement'].get('sweep', 'N/A')}")

    if pattern.watch_files:
        console.print("\n  [bold]Watch Files:[/bold]")
        for wf in pattern.watch_files:
            console.print(f"    {wf}")


def cmd_pattern_claimants(args):
    """List stories that inherit a given pattern."""
    from agenticcli.console import console, is_json_output, print_error, print_json

    userstories_dir = _find_userstories_dir()
    pat_svc = PatternService(userstories_dir)
    story_svc = StoryService(userstories_dir)

    pattern = pat_svc.get_by_id(args.id)
    if not pattern:
        print_error(f"Pattern not found: {args.id}")
        sys.exit(1)

    claimants = pat_svc.get_claimants(args.id, story_svc)
    repo_root = _find_repo_root()

    def _inherited_watch_files(story) -> list[str]:
        if not pattern.watch_files or repo_root is None:
            return []
        pw = pat_svc.get_watch_files_for_story(story, repo_root)
        # Restrict to files claimed by this pattern (first-match ownership).
        return sorted(f for f, pid in pw.items() if pid == args.id)

    if is_json_output():
        print_json({
            "pattern_id": args.id,
            "pattern_title": pattern.title,
            "claimant_count": len(claimants),
            "claimants": [
                {
                    "id": s.id,
                    "title": s.title,
                    "source_file": s.source_file,
                    "inherited_watch_files": _inherited_watch_files(s),
                }
                for s in claimants
            ],
        })
        return

    console.print(f"[bold]{args.id}[/bold] — {pattern.title}")
    console.print(f"  Claimants: {len(claimants)}\n")

    if not claimants:
        console.print("  [dim]No stories inherit this pattern.[/dim]")
        return

    for s in claimants:
        # Find the binding for this pattern
        binding = next(
            (ref.get("bind", {}) for ref in s.inherits_patterns if ref.get("id") == args.id),
            {},
        )
        bind_summary = ", ".join(f"{k}={v}" for k, v in binding.items()) if binding else "no bindings"
        wf = _inherited_watch_files(s)
        wf_suffix = f"  [dim]watch_files: {len(wf)} files[/dim]" if pattern.watch_files else ""
        console.print(f"  {s.id}  {s.title}  [dim]({bind_summary})[/dim]{wf_suffix}")


def cmd_pattern_verify(args):
    """Run enforcement sweep for a pattern across all claimant stories."""
    from agenticcli.console import console, is_json_output, print_error, print_json

    userstories_dir = _find_userstories_dir()
    pat_svc = PatternService(userstories_dir)
    story_svc = StoryService(userstories_dir)

    pattern = pat_svc.get_by_id(args.id)
    if not pattern:
        print_error(f"Pattern not found: {args.id}")
        sys.exit(1)

    claimants = pat_svc.get_claimants(args.id, story_svc)
    results = []

    for story in claimants:
        ref = next(
            (r for r in story.inherits_patterns if r.get("id") == args.id),
            None,
        )
        if not ref:
            continue

        bindings = ref.get("bind", {})
        missing = [
            name for name in pattern.required_parameters
            if name not in bindings
        ]

        if missing:
            results.append({
                "story_id": story.id,
                "status": "FAIL",
                "reason": f"Missing required bindings: {', '.join(missing)}",
            })
        else:
            try:
                pat_svc.resolve_pattern(pattern, bindings)
                results.append({
                    "story_id": story.id,
                    "status": "PASS",
                    "reason": "All required parameters bound",
                })
            except ValueError as e:
                results.append({
                    "story_id": story.id,
                    "status": "FAIL",
                    "reason": str(e),
                })

    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")

    if is_json_output():
        print_json({
            "pattern_id": args.id,
            "total_claimants": len(claimants),
            "pass": pass_count,
            "fail": fail_count,
            "results": results,
        })
        return

    console.print(f"[bold]{args.id}[/bold] — Enforcement Sweep\n")
    console.print(f"  Claimants: {len(claimants)}  [green]PASS: {pass_count}[/green]  [red]FAIL: {fail_count}[/red]\n")

    for r in results:
        status_color = "green" if r["status"] == "PASS" else "red"
        console.print(f"  [{status_color}]{r['status']}[/{status_color}]  {r['story_id']}  [dim]{r['reason']}[/dim]")


def cmd_pattern_check(args):
    """Show inherited patterns and binding status for a story."""
    from agenticcli.console import console, is_json_output, print_error, print_json

    userstories_dir = _find_userstories_dir()
    pat_svc = PatternService(userstories_dir)
    story_svc = StoryService(userstories_dir)

    story = story_svc.get_by_id(args.id)
    if not story:
        print_error(f"Story not found: {args.id}")
        sys.exit(1)

    if not story.inherits_patterns:
        if is_json_output():
            print_json({"story_id": args.id, "patterns": []})
        else:
            console.print(f"[bold]{args.id}[/bold] — {story.title}")
            console.print("  [dim]No inherited patterns.[/dim]")
        return

    pattern_results = []
    for ref in story.inherits_patterns:
        pat_id = ref.get("id", "")
        bindings = ref.get("bind", {})
        pattern = pat_svc.get_by_id(pat_id)

        if not pattern:
            pattern_results.append({
                "pattern_id": pat_id,
                "status": "NOT_FOUND",
                "title": "",
                "bindings": bindings,
                "missing_params": [],
            })
            continue

        missing = [
            name for name in pattern.required_parameters
            if name not in bindings
        ]
        pattern_results.append({
            "pattern_id": pat_id,
            "status": "FAIL" if missing else "OK",
            "title": pattern.title,
            "bindings": bindings,
            "missing_params": missing,
        })

    if is_json_output():
        print_json({"story_id": args.id, "title": story.title, "patterns": pattern_results})
        return

    console.print(f"[bold]{args.id}[/bold] — {story.title}\n")
    for pr in pattern_results:
        if pr["status"] == "NOT_FOUND":
            console.print(f"  [red]NOT FOUND[/red]  {pr['pattern_id']}")
        elif pr["status"] == "FAIL":
            console.print(f"  [red]FAIL[/red]  {pr['pattern_id']}  {pr['title']}")
            console.print(f"    [red]Missing:[/red] {', '.join(pr['missing_params'])}")
        else:
            console.print(f"  [green]OK[/green]  {pr['pattern_id']}  {pr['title']}")
        if pr["bindings"]:
            for k, v in pr["bindings"].items():
                console.print(f"    [dim]{k}={v}[/dim]")
