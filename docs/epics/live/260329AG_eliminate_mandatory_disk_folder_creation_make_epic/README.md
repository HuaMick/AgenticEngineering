# Epic: Eliminate Mandatory Disk Folder Creation

## Objective

Make epic creation and lifecycle fully TinyDB-first by eliminating all
mandatory disk folder creation. After this epic, an epic can be created,
managed (phases, tickets, status), archived, and discovered using only TinyDB
records — disk folders become optional artifacts for agent output, not required
infrastructure.

## Problem Statement

Although epic creation (`cmd_init`, `create_epic`) already writes to TinyDB
without creating folders, several code paths still **mandate** disk folders:

| Location | Line | What it creates | Why it's a problem |
|---|---|---|---|
| `planner_loop.py` | 1455 | `docs/epics/live/{epic}/` | Forces folder for story agent output |
| `ticket_workflow.py` | 32 | `docs/epics/live/` | Forces parent dir in TicketPresetWorkflow init |
| `epic.py` (service) | 394 | `docs/epics/completed/` | Forces folder during archival |
| `_ensure_epic_in_db()` | 144 | — | Checks `is_dir()` on disk before registering |
| `find_epic_folder()` | 255 | — | Checks `path_obj.exists()` on disk |
| `archive_epic_folder()` | 386-395 | folder move | Requires source folder for shutil.move |
| `cmd_init` output | 1045 | — | Says "Created epic folder" (misleading) |

Additionally, the `epic_folder` field in TinyDB stores an absolute disk path
that may not exist, coupling the data model to filesystem state.

## Affected User Stories

### Primary (directly modified behavior)
- **US-PLN-002**: Scaffold Epic Folder Only — folder scaffolding becomes optional
- **US-PLN-006**: Archive Completed Epics — archival becomes TinyDB-only
- **US-PLN-064**: Epic Explicit Archival — folder move becomes optional
- **US-PLN-082**: Epic CRUD Operations — CRUD without folder dependency
- **US-PLN-084**: Epic Movement Workflow — movement without disk moves
- **US-PLN-085**: Epic Listing and Discovery — discovery via TinyDB only
- **US-SET-017**: TinyDB Epic Repository - CRUD Operations
- **US-SET-020**: CLI Epic Commands Use EpicRepository
- **US-SET-022**: TinyDB Database Location and Lifecycle
- **US-GDN-085**: Initialize Plan Folder Structure

### Secondary (UAT coverage)
- **US-PLN-001**: Initialize Epic with Worktree
- **US-PLN-003**: View Epic Status
- **US-PLN-004**: List All Epics
- **US-PLN-009**: List Epic Tickets
- **US-PLN-015**: Manage Epic Phases

## Phases Overview

### Phase 1: Data Model — Make epic_folder Optional
Decouple the TinyDB data model from mandatory disk paths. Make `epic_folder`
an optional/computed field rather than a required attribute.

### Phase 2: Remove Disk-Dependent Code Paths
Eliminate `_ensure_epic_in_db()` disk fallback, update `find_epic_folder()` to
not check disk existence, make `archive_epic_folder()` TinyDB-status-only by
default, remove mandatory `mkdir` from `TicketPresetWorkflow`.

### Phase 3: Decouple Planner Pipeline from Mandatory Folders
Make `planner_loop.py` folder creation lazy/conditional (only when agent
actually needs to write output files). Handle missing `stories.yml` gracefully.

### Phase 4: Test Updates
Update test fixtures that pre-create epic folders to verify folder-free paths.
Add explicit tests for folder-free epic lifecycle.

### Phase 5: UAT
Validate the full epic lifecycle works without disk folders, anchored to
affected user stories.

## Dependencies and Prerequisites

- TinyDB infrastructure (`~/.agentic/epics.db`) must remain intact — this
  epic only targets `docs/epics/` folder creation
- EpicRepository init (`~/.agentic/` mkdir) is infrastructure, not epic data
- Agent output file writing (stories.yml, epic.md) remains valid when folders
  exist — this epic makes folders *optional*, not *prohibited*

## Success Criteria

1. `agentic epic init --branch X` creates NO disk folders (TinyDB only)
2. `agentic epic list`, `agentic epic status` work for epics with no disk folder
3. `agentic epic phase add / ticket add` work for epics with no disk folder
4. `agentic epic archive` sets TinyDB status=completed without requiring folder move
5. `find_epic_folder()` resolves epics purely from TinyDB without disk checks
6. `_ensure_epic_in_db()` no longer checks `is_dir()` on disk
7. Planner pipeline creates folders lazily only when agent writes output
8. All existing tests pass (no regressions)
9. New tests verify folder-free epic lifecycle

## Architecture Pattern

Domain -> Workflow -> Entrypoint:
- **Domain**: `EpicData`, `EpicMetadata` (make `epic_folder` Optional)
- **Workflow**: `EpicMovementWorkflow` (TinyDB-only archival)
- **Entrypoint**: CLI commands (`cmd_init`, `cmd_status`, `cmd_archive`)

## Open Questions

None — the approach is well-defined: make disk folders optional rather than
prohibited. All code paths that currently create folders get guarded with
"only if agent needs to write output" checks.
