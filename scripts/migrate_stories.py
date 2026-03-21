#!/usr/bin/env python3
"""Migrate user stories from old format (as_a/i_want/so_that + acceptance_criteria)
to new format (description + steps with when/then pairs + prerequisites).

Also rewrites stale references to decommissioned systems (MMD, YAML persistence, etc.).

Usage:
    python3 scripts/migrate_stories.py [--dry-run]
"""
import re
import sys
from pathlib import Path

import yaml


# Stale reference replacements (order matters — more specific patterns first)
STALE_REPLACEMENTS = [
    # _orchestrate.yml (before generic patterns)
    (r'_orchestrate\.yml entrypoint', 'TinyDB phase routing'),
    (r'_orchestrate\.yml', 'TinyDB phase routing'),
    # ctx bootstrap
    (r'agentic ctx bootstrap', 'agentic agent context bootstrap'),
    # ep execute orchestrate
    (r'agentic ep execute orchestrate', 'agentic session orchestrate executing'),
    # epic YAML files
    (r'epic YAML files', 'TinyDB via EpicRepository'),
    (r'epic YAML', 'TinyDB epic records'),
    # MMD references (specific patterns first)
    (r'orchestration_\*\.mmd\s*file', 'TinyDB phase records via repo.list_phases()'),
    (r'orchestration_\*\.mmd', 'TinyDB phase records'),
    (r'orchestration\.mmd', 'TinyDB phase records'),
    (r'reads the \.mmd', 'reads TinyDB phase records'),
    (r'the MMD flowchart', 'the TinyDB phase sequence'),
    (r'MMD flowchart', 'TinyDB phase sequence'),
    (r'MMD STATUS headers', 'TinyDB phase status fields'),
    (r'AGENT_ROUTING metadata', 'TinyDB phase agent field'),
    (r'MMD AGENT_ROUTING', 'TinyDB phase agent routing'),
    (r'MMD metadata', 'TinyDB phase metadata'),
    (r'MMD-based', 'TinyDB-based'),
    (r'from MMD', 'from TinyDB'),
    (r'via MMD', 'via TinyDB phase records'),
    (r'\.mmd file', 'TinyDB phase records'),
    (r'MMD file', 'TinyDB phase records'),
    # Generic MMD (last, most aggressive)
    (r'\bMMD\b', 'TinyDB phase records'),
    # State persistence
    (r'persisted to epic YAML and TinyDB phase records', 'persisted to TinyDB via EpicRepository'),
    (r'persisted to epic YAML', 'persisted to TinyDB via EpicRepository'),
    # ticket YAML files
    (r'ticket_build\.yml', 'TinyDB ticket records (build phase)'),
    (r'ticket_test\.yml', 'TinyDB ticket records (test phase)'),
]


def apply_stale_replacements(text):
    """Apply all stale reference replacements to a string."""
    if not isinstance(text, str):
        return text
    for pattern, replacement in STALE_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)
    return text


def apply_deep(obj):
    """Recursively apply stale replacements to all strings in a data structure."""
    if isinstance(obj, str):
        return apply_stale_replacements(obj)
    elif isinstance(obj, list):
        return [apply_deep(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: apply_deep(v) for k, v in obj.items()}
    return obj


def convert_criteria_to_steps(criteria):
    """Convert acceptance_criteria list to steps with when/then pairs."""
    steps = []
    for i, criterion in enumerate(criteria, 1):
        if not isinstance(criterion, str):
            continue
        criterion = apply_stale_replacements(criterion.strip())

        # Try "If X, Y" pattern
        m = re.match(r'^[Ii]f\s+(.+?),\s+(.+)$', criterion)
        if m:
            steps.append({'step': i, 'when': m.group(1).strip(), 'then': [m.group(2).strip()]})
            continue

        # Try "When X, Y" pattern
        m = re.match(r'^[Ww]hen\s+(.+?),\s+(.+)$', criterion)
        if m:
            steps.append({'step': i, 'when': m.group(1).strip(), 'then': [m.group(2).strip()]})
            continue

        # Try "X does/should/must/will Y" — extract the action
        # Default: criterion becomes a "then" outcome
        is_error = any(w in criterion.lower() for w in
                       ['error', 'fail', 'invalid', 'missing', 'denied', 'timeout', 'not found',
                        'without', 'no such', 'already exists'])

        when = "an error condition occurs" if is_error else "the feature is used"
        steps.append({'step': i, 'when': when, 'then': [criterion]})

    return steps if steps else [{'step': 1, 'when': 'the feature is used', 'then': ['Expected behavior occurs']}]


def migrate_story(story):
    """Convert a single story from old format to new format."""
    new = {}

    # Core fields
    for f in ['id', 'title', 'category', 'priority']:
        if f in story:
            new[f] = story[f]

    # Description: merge as_a/i_want/so_that or keep existing
    if 'as_a' in story:
        parts = []
        parts.append(f"As a {story['as_a'].strip()}")
        parts.append(f"I want {story.get('i_want', '').strip()}")
        if story.get('so_that'):
            parts.append(f"so that {story['so_that'].strip()}")
        new['description'] = apply_stale_replacements(', '.join(parts) + '.')
    elif 'description' in story:
        new['description'] = apply_stale_replacements(str(story['description']))
    else:
        new['description'] = story.get('title', 'No description')

    # Prerequisites
    new['prerequisites'] = apply_deep(story.get('prerequisites', []) or [])

    # Steps: convert acceptance_criteria or keep existing
    if 'acceptance_criteria' in story and story['acceptance_criteria']:
        new['steps'] = convert_criteria_to_steps(story['acceptance_criteria'])
    elif 'steps' in story and story['steps']:
        new['steps'] = apply_deep(story['steps'])
    else:
        new['steps'] = [{'step': 1, 'when': 'the feature is used', 'then': ['Expected behavior occurs']}]

    # Related fields
    for f in ['related_commands', 'related_agents', 'related_files', 'related_stories']:
        if f in story:
            new[f] = apply_deep(story[f])

    # Test tracking fields
    new['last_tested'] = story.get('last_tested', None)
    new['test_status'] = story.get('test_status', 'untested')
    new['test_notes'] = story.get('test_notes', '')
    new['tested_by_plan'] = story.get('tested_by_plan', None)

    return new


def migrate_file(filepath):
    """Migrate a single story file. Returns (total, migrated) counts."""
    with open(filepath) as f:
        data = yaml.safe_load(f)

    if not data or 'stories' not in data:
        print(f"  SKIP {filepath.name} (no stories key)")
        return 0, 0

    stories = data.get('stories') or []
    if not stories:
        print(f"  SKIP {filepath.name} (empty)")
        return 0, 0

    total = len(stories)
    migrated = 0
    new_stories = []

    for story in stories:
        if not isinstance(story, dict):
            continue
        had_old = 'as_a' in story or 'acceptance_criteria' in story
        new_stories.append(migrate_story(story))
        if had_old:
            migrated += 1

    data['stories'] = new_stories

    with open(filepath, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)

    tag = "MIGRATED" if migrated > 0 else "CLEANED"
    print(f"  {tag} {filepath.name}: {migrated}/{total} stories")
    return total, migrated


def main():
    base = Path('docs/userstories')
    modules = ['AgenticCLI', 'AgenticGuidance', 'Orchestration']

    total_files = 0
    total_stories = 0
    total_migrated = 0

    for module in modules:
        module_dir = base / module
        if not module_dir.exists():
            print(f"SKIP module {module} (directory missing)")
            continue

        print(f"\n=== {module} ===")
        story_files = sorted(f for f in module_dir.glob('*.yml') if f.name != '00_metadata.yml')

        for filepath in story_files:
            stories, migrated = migrate_file(filepath)
            total_files += 1
            total_stories += stories
            total_migrated += migrated

    print(f"\n{'='*50}")
    print(f"Files processed: {total_files}")
    print(f"Total stories:   {total_stories}")
    print(f"Stories migrated: {total_migrated}")


if __name__ == '__main__':
    main()
