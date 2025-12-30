# Live Planning Directory

This directory contains active and permanent planning folders for the MyAgents ecosystem.

## Directory Structure

### Permanent Fixtures (Worktree Logs)
These folders are permanent and serve as the single source of truth for the state of the long-lived branches/worktrees. They are used for pre-deployment testing, refinement, and state tracking.

- `YYMMDDMAG_main/`: Permanent fixture for the `main` branch of MAG.
- `YYMMDDMAG_staging/`: Permanent fixture for the `staging` branch of MAG.
- Similar folders exist for other projects (MA, RA, MAF).

### Active Feature Plans
Folders prefixed with `YYMMDD` represent specific feature branches or focused work-streams.

- **Naming Convention**: `YYMMDD[PROJECT]_[BRANCH_NAME]`
- **Lifecycle**: These folders are created during `deploy-worktree` and copied to `../completed/` when a phase completes or when the feature is fully merged and the worktree is deleted.

## Follow-On Work Pattern

When a plan phase completes but related work continues, the plan folder may contain both completed and active work. This section explains how to manage this lifecycle.

### When to Add Follow-On Work vs Create New Folder

**Add follow-on work to existing folder when:**
- Work is directly related to the same feature branch
- New phase builds on or extends previous phase results
- Both phases share the same worktree and deployment context

**Create new folder when:**
- Work addresses a different feature or concern
- New worktree or branch is required
- Work is logically independent of the previous effort

### How to Document Relationship

Use metadata references in plan files to link related work:

```yaml
metadata:
  related_plans:
    - path: ../completed/251221MAG_guidance-refinement-v1/plan_completed.yml
      relationship: "Previous phase (teach) completed"
    - path: plan_live_teach.yml
      relationship: "Original teach phase (snapshot maintained)"
```

### Example: Follow-On Work Structure

When Phase 1 completes and Phase 2 begins, the folder structures look like this:

```
live/251221MAG_guidance-refinement-v1/
  ├── live/
  │   ├── plan_live_teach.yml              # Original (completed, kept as reference)
  │   └── plan_live_test_guidance.yml      # Follow-on (active planning)
  ├── completed/
  │   └── plan_completed.yml               # Completed items accumulating
  ├── analysis/
  │   └── proposal_planner-test-guidance.md

completed/251221MAG_guidance-refinement-v1/
  ├── live/
  │   └── plan_live_teach.yml              # Snapshot at completion
  ├── completed/
  │   └── plan_completed.yml               # Executed items from teach phase
  └── analysis/                            # Artifacts at time of snapshot
```

**Key Observation**: Both folders exist side-by-side with identical names but different contents. The completed/ folder is a snapshot of work at a point in time, while the live/ folder continues to evolve with new phases and artifacts.

### Snapshot (completed/) vs Active (live/)

**Completed folder** (`../completed/`):
- Contains snapshots of plan files at the moment of phase completion
- Preserves historical state of what was planned and executed
- Acts as immutable record for that phase
- Multiple snapshots may exist from different phases

**Live folder** (`./`):
- Contains all plan files (both completed and active)
- Completed plans serve as reference/context for follow-on work
- Active plans are being executed or refined
- This is the working directory for ongoing efforts

**Key principle**: Completed snapshots are copied (not moved), so `live/` retains the full history while `completed/` captures point-in-time states.

## Usage
- **Orchestration**: Use these folders as the target for the Orchestration Agent (`_plan.yml`, `_execute.yml`).
- **State Management**: The `live/` subdirectory within each plan folder contains the active YAML definitions of the current work phases.
- **Testing Logs**: Use the `logs/` and `results/` subdirectories in the permanent fixtures to track pre-deployment validation history.
