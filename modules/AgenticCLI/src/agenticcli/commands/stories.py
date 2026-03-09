"""User stories discovery and test tracking commands.

Find, filter, and track test status of user stories.
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


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
    else:
        print("Usage: agentic stories [find|init|cat|status|update|report|untested|batch-update|affected]", file=sys.stderr)
        sys.exit(1)


def _find_userstories_dir() -> Path | None:
    """Find the userstories directory."""
    # Look in common locations
    search_paths = [
        Path.cwd() / "docs" / "userstories",
        Path.cwd().parent / "docs" / "userstories",
        Path.cwd() / "userstories",
    ]

    for path in search_paths:
        if path.exists():
            return path

    return None


def _get_repo_db_path() -> Path:
    """Derive the repo-local TinyDB path (.agentic/epics.db under repo root)."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return current / ".agentic" / "epics.db"
        current = current.parent
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
            # Handle user_stories array format
            if "user_stories" in content and isinstance(content["user_stories"], list):
                stories = []
                for story in content["user_stories"]:
                    if isinstance(story, dict):
                        stories.append(
                            {
                                "file": story_file.name,
                                "path": str(story_file),
                                "id": story.get("id", story_file.stem),
                                "title": story.get("name", story.get("title", "")),
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


def _collect_all_stories(project_filter: str | None = None) -> list[dict]:
    """Collect all stories from userstories directory and plan story dirs.

    Each returned dict includes test metadata fields and file path info.
    """
    userstories_dir = _find_userstories_dir()
    story_files = []
    if userstories_dir:
        story_files.extend(list(userstories_dir.glob("**/*.yml")))
    for d in _find_plan_stories_dirs():
        story_files.extend(list(d.glob("*.yml")))

    all_stories = []
    for f in story_files:
        # Skip metadata files
        if f.name == "00_metadata.yml":
            continue
        try:
            content = yaml.safe_load(f.read_text())
        except yaml.YAMLError:
            continue
        if not content or not isinstance(content, dict):
            continue

        # Determine project
        project = ""
        if userstories_dir:
            project = _get_project_from_path(f, userstories_dir)
        if f.parent.name == "user_stories":
            project = f.parent.parent.name

        # Process stories from either format
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


def _find_story_in_file(story_file: Path, story_id: str) -> tuple[dict | None, str | None]:
    """Find a story by ID in a YAML file.

    Returns (story_dict, list_key) where list_key is 'stories' or 'user_stories'.
    """
    try:
        content = yaml.safe_load(story_file.read_text())
    except yaml.YAMLError:
        return None, None
    if not content or not isinstance(content, dict):
        return None, None

    for key in ("stories", "user_stories"):
        items = content.get(key, [])
        if not isinstance(items, list):
            continue
        for story in items:
            if isinstance(story, dict) and story.get("id") == story_id:
                return story, key

    return None, None


def _find_story_file_by_id(story_id: str) -> Path | None:
    """Find the file containing a story with the given ID."""
    userstories_dir = _find_userstories_dir()
    story_files = []
    if userstories_dir:
        story_files.extend(list(userstories_dir.glob("**/*.yml")))
    for d in _find_plan_stories_dirs():
        story_files.extend(list(d.glob("*.yml")))

    for f in story_files:
        if f.name == "00_metadata.yml":
            continue
        story, _ = _find_story_in_file(f, story_id)
        if story is not None:
            return f
    return None


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

    # Find all story files
    story_files = []
    if userstories_dir:
        story_files.extend(list(userstories_dir.glob("**/*.yml")))

    plan_story_dirs = _find_plan_stories_dirs()
    for d in plan_story_dirs:
        story_files.extend(list(d.glob("*.yml")))

    # Parse files (each file may contain multiple stories)
    all_stories = []
    for f in story_files:
        # Determine appropriate project name for plan-local stories
        p_dir = f.parent
        if p_dir.name == "user_stories":
            project = p_dir.parent.name
        else:
            project = _get_project_from_path(f, userstories_dir) if userstories_dir else ""

        parsed = _parse_story_file(f, userstories_dir)
        for s in parsed:
            if project:
                s["project"] = project
            all_stories.append(s)

    stories = all_stories

    # Filter by project if specified
    if args.project:
        project_filter = args.project.lower()
        stories = [s for s in stories if project_filter in s.get("project", "").lower()]

    # Filter by changed files if specified
    if args.changes:
        # Match stories that might be affected by changed files
        # Look for file paths in story content or category matching
        changed_paths = args.changes if isinstance(args.changes, list) else [args.changes]
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
        plan_dir = Path.cwd() / "docs" / "plans" / "live" / args.plan
        if not plan_dir.exists():
            print_error(f"Plan directory not found: {plan_dir}")
            sys.exit(1)
        target_dir = plan_dir / "user_stories"
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

    # Find the story
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
    story_file = _find_story_file_by_id(story_id)

    if not story_file:
        if is_json_output():
            print_json({"error": f"Story not found: {story_id}"})
        else:
            print_error(f"Story not found: {story_id}")
        sys.exit(1)

    story, _ = _find_story_in_file(story_file, story_id)
    if story is None:
        print_error(f"Story not found in file: {story_id}")
        sys.exit(1)

    status_data = {
        "id": story.get("id", story_id),
        "title": story.get("title", story.get("name", "")),
        "test_status": story.get("test_status", "untested"),
        "last_tested": story.get("last_tested"),
        "test_notes": story.get("test_notes", ""),
        "tested_by_plan": story.get("tested_by_plan"),
        "file": str(story_file),
    }

    if is_json_output():
        print_json(status_data)
        return

    print_header(f"Test Status: {story_id}")
    console.print(f"  [bold]Title:[/bold] {status_data['title']}")

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

    console.print(f"  [dim]File: {status_data['file']}[/dim]")


def cmd_update(args):
    """Update test status for a specific story."""
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    story_id = args.id
    story_file = _find_story_file_by_id(story_id)

    if not story_file:
        if is_json_output():
            print_json({"error": f"Story not found: {story_id}"})
        else:
            print_error(f"Story not found: {story_id}")
        sys.exit(1)

    # Read and modify the file
    try:
        content = yaml.safe_load(story_file.read_text())
    except yaml.YAMLError as e:
        print_error(f"YAML parse error: {e}")
        sys.exit(1)

    if not content or not isinstance(content, dict):
        print_error(f"Invalid story file: {story_file}")
        sys.exit(1)

    updated = False
    for key in ("stories", "user_stories"):
        items = content.get(key, [])
        if not isinstance(items, list):
            continue
        for story in items:
            if isinstance(story, dict) and story.get("id") == story_id:
                story["test_status"] = args.status
                story["last_tested"] = datetime.now(timezone.utc).isoformat()
                if args.notes:
                    story["test_notes"] = args.notes
                if hasattr(args, "plan") and args.plan:
                    story["tested_by_plan"] = args.plan
                updated = True
                break
        if updated:
            break

    if not updated:
        print_error(f"Could not find story {story_id} in {story_file}")
        sys.exit(1)

    story_file.write_text(yaml.dump(content, sort_keys=False, default_flow_style=False))

    if is_json_output():
        print_json({
            "updated": story_id,
            "test_status": args.status,
            "file": str(story_file),
        })
    else:
        print_success(f"Updated {story_id}: test_status={args.status}")


def cmd_report(args):
    """Show test status summary across stories."""
    from agenticcli.console import console, is_json_output, print_header, print_json

    project_filter = getattr(args, "project", None)
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

    if is_json_output():
        print_json({
            "total": total,
            "pass": counts["pass"],
            "fail": counts["fail"],
            "skip": counts["skip"],
            "regression": counts["regression"],
            "untested": counts["untested"],
            "project_filter": project_filter,
        })
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

    for story_id in story_ids:
        story_file = _find_story_file_by_id(story_id)
        if not story_file:
            errors.append({"id": story_id, "error": "Story not found"})
            continue

        try:
            content = yaml.safe_load(story_file.read_text())
        except yaml.YAMLError:
            errors.append({"id": story_id, "error": "YAML parse error"})
            continue

        if not content or not isinstance(content, dict):
            errors.append({"id": story_id, "error": "Invalid file"})
            continue

        found = False
        for key in ("stories", "user_stories"):
            items = content.get(key, [])
            if not isinstance(items, list):
                continue
            for story in items:
                if isinstance(story, dict) and story.get("id") == story_id:
                    story["test_status"] = args.status
                    story["last_tested"] = now
                    story["tested_by_plan"] = plan_folder
                    if args.notes:
                        story["test_notes"] = args.notes
                    found = True
                    break
            if found:
                break

        if found:
            story_file.write_text(yaml.dump(content, sort_keys=False, default_flow_style=False))
            updated.append(story_id)
        else:
            errors.append({"id": story_id, "error": "ID not found in file"})

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
    """List affected stories for a plan with their test status."""
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json

    plan_folder = args.plan
    story_ids = _find_affected_story_ids(plan_folder)

    if not story_ids:
        if is_json_output():
            print_json({"error": f"No affected_stories found for plan: {plan_folder}"})
        else:
            print_error(f"No affected_stories found for plan: {plan_folder}")
        sys.exit(1)

    results = []
    for story_id in story_ids:
        story_file = _find_story_file_by_id(story_id)
        if not story_file:
            results.append({"id": story_id, "title": "(not found)", "test_status": "unknown", "file": None})
            continue

        story, _ = _find_story_in_file(story_file, story_id)
        if story:
            results.append({
                "id": story_id,
                "title": story.get("title", story.get("name", "")),
                "test_status": story.get("test_status", "untested"),
                "last_tested": story.get("last_tested"),
                "tested_by_plan": story.get("tested_by_plan"),
                "file": str(story_file),
            })
        else:
            results.append({"id": story_id, "title": "(not found)", "test_status": "unknown", "file": str(story_file)})

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
