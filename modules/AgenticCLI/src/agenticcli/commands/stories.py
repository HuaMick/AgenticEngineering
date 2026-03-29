"""User stories discovery and test tracking commands.

Find, filter, and track test status of user stories.
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agenticguidance.services.story import Story, StoryService


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
    elif args.stories_command == "report":
        cmd_report(args)
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
    else:
        print("Usage: agentic stories [find|init|cat|status|update|report|untested|batch-update|affected|sync|run|promote|deprecate|archive|code]", file=sys.stderr)
        sys.exit(1)


def _find_userstories_dir() -> Path | None:
    """Find the userstories directory."""
    # Check AGENTIC_REPO_ROOT env var first
    env_root = os.environ.get("AGENTIC_REPO_ROOT")
    if env_root:
        candidate = Path(env_root) / "docs" / "userstories"
        if candidate.is_dir():
            return candidate

    # Look in common locations
    search_paths = [
        Path.cwd() / "docs" / "userstories",
        Path.cwd().parent / "docs" / "userstories",
        Path.cwd() / "userstories",
    ]

    for path in search_paths:
        if path.exists():
            return path

    # Fallback: walk up from cwd looking for .git to find repo root
    current = Path.cwd()
    for _ in range(5):
        if (current / ".git").exists():
            userstories = current / "docs" / "userstories"
            if userstories.is_dir():
                return userstories
            break
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def _get_repo_db_path() -> Path:
    """Return the global TinyDB path (~/.agentic/epics.db)."""
    return Path.home() / ".agentic" / "epics.db"


def _find_plan_stories_dirs() -> list[Path]:
    """Find user_stories directories inside live epics, querying TinyDB."""
    try:
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_get_repo_db_path(), auto_bootstrap=False)
        metas = repo.list_epics(status="live")
    except Exception:
        metas = []

    story_dirs = []
    for meta in metas:
        epic_dir = meta.epic_folder
        if epic_dir is None:
            continue
        if epic_dir.is_dir():
            story_dir = epic_dir / "user_stories"
            if story_dir.exists():
                story_dirs.append(story_dir)
    return story_dirs


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
    }


def _collect_all_stories(project_filter: str | None = None) -> list[dict]:
    """Collect all stories from userstories directory and plan story dirs.

    Each returned dict includes test metadata fields and file path info.
    Uses StoryService for the main userstories directory and falls back
    to manual parsing for plan-local story directories.
    """
    userstories_dir = _find_userstories_dir()
    plan_story_dirs = _find_plan_stories_dirs()

    if userstories_dir is None and not plan_story_dirs:
        print(
            "Warning: No userstories directory found. Run from repo root or set AGENTIC_REPO_ROOT.",
            file=sys.stderr,
        )

    # Load main stories via StoryService
    svc = StoryService(userstories_dir)
    all_stories = [_story_to_dict(s) for s in svc.load_all()]

    # Also scan plan-local story dirs (epic user_stories/ folders)
    for d in plan_story_dirs:
        for f in d.glob("*.yml"):
            if f.name == "00_metadata.yml":
                continue
            try:
                content = yaml.safe_load(f.read_text())
            except yaml.YAMLError:
                continue
            if not content or not isinstance(content, dict):
                continue

            project = d.parent.name

            for key in ("stories", "user_stories"):
                items = content.get(key, [])
                if not isinstance(items, list):
                    continue
                for story in items:
                    if not isinstance(story, dict):
                        continue
                    entry = {
                        "id": story.get("id", f.stem),
                        "title": story.get("title", story.get("name", "")),
                        "project": story.get("project", project),
                        "file": str(f),
                        "test_status": story.get("test_status", "untested"),
                        "last_tested": story.get("last_tested"),
                        "test_notes": story.get("test_notes", ""),
                        "tested_by_plan": story.get("tested_by_plan"),
                    }
                    all_stories.append(entry)

    if project_filter:
        pf = project_filter.lower()
        all_stories = [s for s in all_stories if pf in s.get("project", "").lower()]

    return all_stories



def _categorize_stories(stories: list[dict]) -> dict:
    """Categorize stories by prefix."""
    categories = {}

    for story in stories:
        story_id = story.get("id", "")
        # Extract prefix (e.g., US-INSTALL, US-CLI)
        match = re.match(r"(US-[A-Z]+)", story_id)
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

    # Load stories from main userstories dir via StoryService
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

    # Also scan plan-local story dirs (epic user_stories/ folders)
    plan_story_dirs = _find_plan_stories_dirs()
    for d in plan_story_dirs:
        for f in d.glob("*.yml"):
            if f.name == "00_metadata.yml":
                continue
            project = d.parent.name
            parsed = _parse_story_file(f, userstories_dir)
            for s in parsed:
                s["project"] = project
                all_stories.append(s)

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
        epic_dir = Path.cwd() / "docs" / "epics" / "live" / args.plan
        if not epic_dir.exists():
            # Fallback to legacy path
            epic_dir = Path.cwd() / "docs" / "plans" / "live" / args.plan
        if not epic_dir.exists():
            print_error(
                f"Epic directory not found: {args.plan}. "
                "If this is a folder-free epic, omit --plan to use the current directory."
            )
            sys.exit(1)
        target_dir = epic_dir / "user_stories"
        target_dir.mkdir(exist_ok=True)

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

    # Fallback: scan plan-local story dirs and filename matching
    userstories_dir = _find_userstories_dir()
    story_files = []
    if userstories_dir:
        story_files.extend(list(userstories_dir.glob("**/*.yml")))
    for d in _find_plan_stories_dirs():
        story_files.extend(list(d.glob("*.yml")))

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

    story_id = args.id
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
    """Update test status for a specific story."""
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

    updated = svc.update_test_status(
        story_id,
        args.status,
        tested_by=tested_by,
        test_notes=notes,
        last_tested=now,
    )

    if not updated:
        print_error(f"Could not update story {story_id}")
        sys.exit(1)

    if is_json_output():
        print_json({
            "updated": story_id,
            "test_status": args.status,
            "file": story_obj.source_file,
        })
    else:
        print_success(f"Updated {story_id}: test_status={args.status}")


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
                for match in re.findall(r'["\']([A-Z]{2}-[A-Z]+-\d+)["\']', result.stdout):
                    marker_ids.add(match)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return marker_ids


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


def cmd_report(args):
    """Show test status summary across stories."""
    from agenticcli.console import console, is_json_output, print_header, print_json

    project_filter = getattr(args, "project", None)
    coverage_mode = getattr(args, "coverage", False)
    stories = _collect_all_stories(project_filter=project_filter)

    # Tally
    counts = {"pass": 0, "fail": 0, "skip": 0, "regression": 0, "untested": 0}
    for s in stories:
        ts = s.get("test_status", "untested")
        if ts in counts:
            counts[ts] += 1
        else:
            counts["untested"] += 1

    total = len(stories)

    # Pytest marker coverage analysis
    marker_coverage = None
    if coverage_mode:
        marker_ids = _scan_pytest_story_markers()
        all_story_ids = {s["id"] for s in stories}
        covered = all_story_ids & marker_ids
        uncovered = all_story_ids - marker_ids
        orphan_markers = marker_ids - all_story_ids  # Markers referencing non-existent stories

        marker_coverage = {
            "total_stories": len(all_story_ids),
            "covered_by_markers": len(covered),
            "uncovered": sorted(uncovered),
            "orphan_markers": sorted(orphan_markers),
            "coverage_pct": (len(covered) / len(all_story_ids) * 100) if all_story_ids else 0,
        }

    if is_json_output():
        result = {
            "total": total,
            "pass": counts["pass"],
            "fail": counts["fail"],
            "skip": counts["skip"],
            "regression": counts["regression"],
            "untested": counts["untested"],
            "project_filter": project_filter,
        }
        if marker_coverage is not None:
            result["marker_coverage"] = marker_coverage
        print_json(result)
        return

    title = "Story Test Report"
    if project_filter:
        title += f" (project: {project_filter})"
    print_header(title)

    console.print(f"  [green]Pass:[/green]       {counts['pass']}")
    console.print(f"  [red]Fail:[/red]       {counts['fail']}")
    console.print(f"  [red]Regression:[/red] {counts['regression']}")
    console.print(f"  [yellow]Skip:[/yellow]       {counts['skip']}")
    console.print(f"  [dim]Untested:[/dim]   {counts['untested']}")
    console.print(f"  [bold]Total:[/bold]      {total}")

    if total > 0:
        pct = (counts["pass"] / total) * 100
        console.print(f"\n  [bold]Coverage:[/bold] {pct:.0f}% passing")

    if marker_coverage is not None:
        console.print(f"\n  [bold cyan]Pytest Marker Coverage:[/bold cyan]")
        mc = marker_coverage
        console.print(f"  [green]Covered:[/green]    {mc['covered_by_markers']}/{mc['total_stories']} ({mc['coverage_pct']:.0f}%)")
        if mc["uncovered"]:
            console.print(f"  [red]Uncovered:[/red]  {len(mc['uncovered'])} stories without @pytest.mark.story markers")
            for sid in mc["uncovered"][:20]:  # Show first 20
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
    """List affected stories for a plan with their test status.

    When --changes is provided (comma-separated file paths or 'git' for git diff),
    cross-references testmon data and story_tests TinyDB to show which stories
    are affected by the file changes.
    """
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json

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
