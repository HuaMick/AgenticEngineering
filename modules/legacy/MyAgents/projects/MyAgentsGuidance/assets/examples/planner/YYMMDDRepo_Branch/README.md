# Follow-On Work Pattern Example

## Overview

This example demonstrates the **follow-on work pattern** - how planning folders evolve when initial work completes but related work continues. The example shows:

- How a single planning folder exists in both `live/` and `completed/` simultaneously
- When and why folders are copied (not moved) to `completed/`
- How to reference original work in follow-on plans
- When folders sync and when they diverge

This pattern is critical for managing plan lifecycles without creating excessive folder proliferation.

## Original Plan: plan_live_build.yml

**Date Completed**: 2025-12-21
**Purpose**: Initial implementation phase covering core functionality

The build phase included:
- Configuration system updates
- Service initialization changes
- CLI improvements
- Environment setup for testing

When this phase completed:
1. The entire planning folder was **COPIED** to `docs/plans/completed/251221MAG_example/`
2. The original folder **REMAINED** in `docs/plans/live/251221MAG_example/`
3. Both folders now coexist with identical names but different purposes

## Follow-On Work: plan_live_test.yml

**Date Added**: 2025-12-21
**Purpose**: Testing phase added after build phase completed

After completing the build phase, testing work was identified as necessary. Rather than creating a new planning folder (e.g., `251221MAG_example_test`), the follow-on work was added to the existing folder because:

- Work is directly related to the same feature branch
- Testing builds on build phase results
- Both phases share the same worktree and deployment context
- Keeping work together maintains context and reduces folder proliferation

## Folder Structure: Side-by-Side live/ and completed/

### Live Folder (Active Work)

```
docs/plans/live/251221MAG_example/
├── live/
│   ├── plan_live_build.yml              # Status: completed (kept as reference)
│   └── plan_live_test.yml               # Status: planning (follow-on work)
├── completed/
│   └── plan_completed.yml               # Accumulating items from both phases
├── analysis/
│   ├── friction-analysis.md             # Build phase artifacts
│   └── test-coverage-analysis.md        # Test phase artifacts (new)
└── README.md                            # Context for ongoing work
```

### Completed Folder (Historical Snapshot)

```
docs/plans/completed/251221MAG_example/
├── live/
│   └── plan_live_build.yml              # Snapshot at completion (2025-12-21)
├── completed/
│   └── plan_completed.yml               # Items completed during build phase
├── analysis/
│   └── friction-analysis.md             # Artifacts at time of snapshot
└── README.md                            # Summary of completed build work
```

**Key Observation**: Both folders share the same name (`251221MAG_example`) but contain different contents:
- **completed/** folder is a point-in-time snapshot of the build phase
- **live/** folder continues to evolve with test phase work

## Metadata Linking: How to Reference Original Work

Follow-on plans should include metadata references to link related work:

### Example from plan_live_test.yml

```yaml
plan_name: "Example Testing Phase"
worktree: "/home/code/myagents/MyAgents-example"
created: "2025-12-21"
status: "planning"

metadata:
  related_plans:
    - path: "/home/code/myagents/docs/plans/completed/251221MAG_example/live/plan_live_build.yml"
      relationship: "Build phase completed 2025-12-21 (snapshot maintained)"
      note: "Testing work builds on configuration and CLI changes from build phase"
    - path: "plan_live_build.yml"
      relationship: "Original build phase (same folder, completed status)"

context: |
  Follow-on testing work after build phase completion.
  Build phase completed all implementation tasks, now validating functionality.
```

### Metadata Best Practices

**DO**:
- Reference the completed snapshot using absolute path to `docs/plans/completed/`
- Reference the local completed plan using relative path within the same folder
- Explain the relationship between phases
- Note key dependencies or context from previous work

**DON'T**:
- Duplicate information from the original plan
- Create circular references
- Reference files that may be moved or archived

## Lifecycle Timeline: When Folders Sync and Diverge

### Timeline of Events

| Date | Event | Live Folder | Completed Folder | State |
|------|-------|-------------|------------------|-------|
| 2025-12-15 | Planning folder created | Created with build plan | Does not exist | `planning` |
| 2025-12-18 | Build work begins | Build plan active | Does not exist | `active` |
| 2025-12-21 | Build phase completes | Build plan marked complete | **COPIED** from live/ | `partially_completed` |
| 2025-12-21 | Test phase added | Test plan added | No change (snapshot frozen) | `partially_completed` |
| 2025-12-23 | Test work begins | Test plan active | No change | `partially_completed` |
| 2025-12-25 | Test phase completes | Test plan marked complete | **UPDATED** with test snapshot | `fully_completed` |

### When Folders Sync

Folders are synchronized when phases complete:

1. **Initial Completion** (build phase done):
   - Entire live folder **COPIED** to completed/
   - Snapshot created at this point in time
   - Both folders now exist

2. **Follow-On Completion** (test phase done):
   - Live folder **COPIED** again to completed/
   - Updates completed/ with latest snapshot
   - Overwrites previous snapshot with comprehensive view

### When Folders Diverge

Folders diverge during active work:

1. **During Follow-On Planning** (test phase planning):
   - Live folder receives new plan files
   - Completed folder unchanged (frozen snapshot)
   - Divergence begins

2. **During Follow-On Execution** (test phase active):
   - Live folder accumulates new artifacts
   - Completed items added to live/completed/plan_completed.yml
   - Completed folder remains frozen until next sync

3. **After Full Completion** (all work done):
   - Live folder may be deleted when worktree removed
   - Completed folder persists as historical record
   - Ultimate divergence: live/ removed, completed/ archived

## FENCE: What Agents Must NEVER Do

Agents have strict boundaries for folder lifecycle management:

### NEVER Archive

```yaml
# INCORRECT - Agents must NEVER do this
NEVER: "Move folders to docs/plans/archived/"
NEVER: "Copy folders to docs/plans/archived/"
NEVER: "Modify contents of docs/plans/archived/"
```

**Why**: Archival is a user-only decision based on age (6+ months) and relevance. Agents cannot make this judgment.

### NEVER Move (Only Copy)

```yaml
# INCORRECT - Agents must NEVER move
WRONG: "Move completed work to docs/plans/completed/"

# CORRECT - Agents must COPY
RIGHT: "Copy completed work to docs/plans/completed/ while keeping in live/"
```

**Why**: Moving removes the folder from live/, preventing follow-on work and breaking the pattern.

### NEVER Remove from Live Without User Confirmation

```yaml
# INCORRECT - Premature removal
WRONG: "All phases complete, removing from live/"

# CORRECT - Keep available for follow-on work
RIGHT: "All phases complete, copied to completed/, keeping in live/ for potential follow-on work"
```

**Why**: Even fully completed plans may receive follow-on work. Only users can decide when to remove.

## When to Create New Folder vs Add Follow-On Work

### Add Follow-On Work (Same Folder)

Use the existing folder when:
- Work relates to the same feature/branch
- New phases build on or extend previous results
- Both phases share deployment context
- Work maintains conceptual continuity

**Examples**:
- Build → Test (validating what was built)
- Teach → Test (validating what was taught)
- Build → Enhance (iterating on implementation)
- Fix → Audit (validating the fix)

### Create New Folder (New Planning Context)

Create a new folder when:
- Work addresses a different feature/concern
- Requires new worktree or branch
- Logically independent of previous work
- Different deployment or testing context

**Examples**:
- Authentication feature → Payment feature (different domains)
- Main branch work → Feature branch work (different contexts)
- Agent guidance → Agent implementation (different types of work)

## Summary

The follow-on work pattern enables:

1. **Context preservation**: Related work stays together
2. **Historical snapshots**: Completed/ captures point-in-time state
3. **Continued evolution**: Live/ folder grows with new work
4. **Clear lifecycle**: Copy-not-move pattern keeps folders discoverable
5. **User control**: Only users archive or remove folders

This pattern balances the need for historical records with the reality of iterative, evolving work.
