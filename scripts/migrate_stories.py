#!/usr/bin/env python3
"""Migrate existing user story files to include test tracking metadata.

Adds the following fields to each story if not already present:
  - last_tested: null
  - test_status: untested
  - test_notes: ""
  - tested_by_plan: null

Idempotent: running multiple times will not duplicate fields.

Usage:
    python3 scripts/migrate_stories.py [--dry-run] [--path docs/userstories]
"""

import argparse
import sys
from pathlib import Path

import yaml


# Fields to add to each story with their defaults
TEST_METADATA_DEFAULTS = {
    "last_tested": None,
    "test_status": "untested",
    "test_notes": "",
    "tested_by_plan": None,
}


def migrate_story_file(file_path: Path, dry_run: bool = False) -> dict:
    """Migrate a single story file to include test metadata.

    Returns a dict with migration results.
    """
    result = {"file": str(file_path), "stories_updated": 0, "already_current": 0, "errors": []}

    try:
        content = yaml.safe_load(file_path.read_text())
    except yaml.YAMLError as e:
        result["errors"].append(f"YAML parse error: {e}")
        return result

    if not content or not isinstance(content, dict):
        result["errors"].append("Empty or non-dict content")
        return result

    modified = False

    # Handle stories array format (stories: [...])
    stories_list = content.get("stories", [])
    if isinstance(stories_list, list):
        for story in stories_list:
            if not isinstance(story, dict):
                continue
            story_modified = False
            for field, default in TEST_METADATA_DEFAULTS.items():
                if field not in story:
                    story[field] = default
                    story_modified = True
            if story_modified:
                result["stories_updated"] += 1
                modified = True
            else:
                result["already_current"] += 1

    # Handle user_stories array format
    user_stories_list = content.get("user_stories", [])
    if isinstance(user_stories_list, list):
        for story in user_stories_list:
            if not isinstance(story, dict):
                continue
            story_modified = False
            for field, default in TEST_METADATA_DEFAULTS.items():
                if field not in story:
                    story[field] = default
                    story_modified = True
            if story_modified:
                result["stories_updated"] += 1
                modified = True
            else:
                result["already_current"] += 1

    if modified and not dry_run:
        file_path.write_text(yaml.dump(content, sort_keys=False, default_flow_style=False))

    return result


def migrate_directory(base_path: Path, dry_run: bool = False) -> list[dict]:
    """Migrate all story files in a directory tree."""
    results = []
    for yml_file in sorted(base_path.glob("**/*.yml")):
        # Skip metadata files
        if yml_file.name == "00_metadata.yml":
            continue
        # Skip README
        if yml_file.name == "README.md":
            continue

        result = migrate_story_file(yml_file, dry_run=dry_run)
        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="Migrate user stories to include test metadata")
    parser.add_argument(
        "--path",
        default="docs/userstories",
        help="Path to userstories directory (default: docs/userstories)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without writing files",
    )
    args = parser.parse_args()

    base_path = Path(args.path)
    if not base_path.exists():
        print(f"Error: {base_path} does not exist", file=sys.stderr)
        sys.exit(1)

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Migrating stories in {base_path}")
    print("=" * 60)

    results = migrate_directory(base_path, dry_run=args.dry_run)

    total_updated = 0
    total_current = 0
    total_errors = 0

    for r in results:
        if r["stories_updated"] > 0:
            print(f"  Updated: {r['file']} ({r['stories_updated']} stories)")
            total_updated += r["stories_updated"]
        if r["already_current"] > 0:
            total_current += r["already_current"]
        if r["errors"]:
            for err in r["errors"]:
                print(f"  ERROR: {r['file']}: {err}", file=sys.stderr)
            total_errors += len(r["errors"])

    print("=" * 60)
    print(f"Updated: {total_updated} stories")
    print(f"Already current: {total_current} stories")
    if total_errors:
        print(f"Errors: {total_errors}")


if __name__ == "__main__":
    main()
