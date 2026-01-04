"""User stories discovery commands.

Find and filter user stories for testing.
"""

import re
import sys
from pathlib import Path

import yaml


def handle(args, ctx=None):
    """Route stories subcommands."""
    if args.stories_command == "find":
        cmd_find(args)
    else:
        print("Usage: agentic stories find [--project <project>]", file=sys.stderr)
        sys.exit(1)


def _find_userstories_dir() -> Path | None:
    """Find the userstories directory."""
    # Look in common locations
    search_paths = [
        Path.cwd() / "modules" / "AgenticGuidance" / "userstories",
        Path.cwd().parent / "modules" / "AgenticGuidance" / "userstories",
        Path.cwd() / "userstories",
    ]

    for path in search_paths:
        if path.exists():
            return path

    return None


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
            console.print("  [dim]- modules/AgenticGuidance/userstories/[/dim]")
            console.print("  [dim]- ../modules/AgenticGuidance/userstories/[/dim]")
            console.print("  [dim]- userstories/[/dim]")
        sys.exit(1)

    # Find all story files
    story_files = list(userstories_dir.glob("**/*.yml"))

    # Parse files (each file may contain multiple stories)
    all_stories = []
    for f in story_files:
        parsed = _parse_story_file(f, userstories_dir)
        all_stories.extend(parsed)

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
