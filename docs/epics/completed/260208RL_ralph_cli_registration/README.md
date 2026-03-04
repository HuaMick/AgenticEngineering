# Ralph CLI Registration

## Problem
The entire `agentic ralph` command family (next, start, status, etc.) has implementation code in `commands/ralph.py` but is NOT registered in the main CLI (`cli.py`). The ralph loop orchestration workflow is broken because none of the commands are accessible.

## Evidence
- `commands/ralph.py` has handlers for: next, start, status, and other subcommands
- `cli.py` has NO `ralph_app = typer.Typer(...)` or `app.add_typer(ralph_app, name="ralph")`
- Ralph loop guidance references `agentic ralph next -j` which silently fails
- The Ralph Loop skill in Claude Code (.claude/ralph-loop.local.md) depends on these commands

## Goals
1. Register `agentic ralph` command group in cli.py with Typer
2. Wire up all existing handlers from ralph.py
3. Verify `agentic ralph next -j` works end-to-end
4. Update any guidance that references ralph commands if signatures changed

## Open Questions
- Q1: Are the existing ralph.py handlers still correct for the current Typer-based CLI, or do they need migration from argparse?
- Q2: Should ralph commands require a project context (`_require_project`)?
- Q3: Is the Ralph Loop skill the primary consumer, or are there other workflows that depend on ralph commands?

## Scope
- Register ralph Typer app in cli.py
- Migrate handlers if needed (argparse -> typer)
- Test all ralph subcommands
- Verify Ralph Loop skill works end-to-end
