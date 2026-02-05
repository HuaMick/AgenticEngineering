# Plan 260204AL: Worktree Planning Alignment

**Plan ID**: 260204AL (Worktree Alignment)
**Plan Name**: worktree-planning-alignment
**Worktree**: `/home/code/AgenticEngineering-feature/worktree-planning-alignment`
**Branch**: `feature/worktree-planning-alignment`
**Created**: 2026-02-04

---

## Problem Statement

The current implementation violates the fundamental 1:1 relationship between git worktrees and planning folders:

### Current Issues

1. **No Worktree Enforcement in Plan Creation**
   - `agentic plan create` does not require or validate worktree branch parameter
   - All 8 current live plans are incorrectly assigned to `main` branch
   - Violates the core principle: 1 worktree = 1 live planning folder max

2. **Stale Worktrees** (PARTIALLY ADDRESSED)
   - Originally 36 worktrees existed - cleaned up to 8 active worktrees
   - `feature/langsmith-cli-enhancements` removed (replaced by agentic-cli)
   - Still need: Automated cleanup and stale worktree identification

3. **Missing Worktree Management**
   - No `agentic worktree create` command for standardized worktree creation
   - Manual git worktree commands lead to inconsistency

4. **Broken Plan-Worktree Relationship**
   - 8 live planning folders exist, ALL assigned to `main` branch
   - No mechanism to enforce or validate worktree-to-plan relationships

### Evidence from Analysis

**After cleanup (2026-02-04)**:
```
Current worktrees (8 total, cleaned from 36):
- /home/code/AgenticEngineering [main]
- /home/code/AgenticEngineering-agentic-cli [agentic-cli]
- /home/code/AgenticEngineering-agenticguidance [agenticguidance]
- /home/code/AgenticEngineering-agenticlangsmith [agenticlangsmith]
- /home/code/AgenticEngineering-agentictmux [agentictmux]
- /home/code/AgenticEngineering-agenticvoice [agenticvoice]
- /home/code/AgenticEngineering-260204PC-planning-context-improvements [260204PC-planning-context-improvements]
- /home/code/AgenticEngineering-feature/worktree-planning-alignment [feature/worktree-planning-alignment]
```

**Live Planning Folders (all on main - STILL A VIOLATION)**:
```
- 260203PS_plan_service
- 260203QC_question_cli
- 260203QG_question_guidance
- 260203QT_question_tmux
- 260203VP_voice_personaplex
- 260204AG_ralph_loop_cli_integration
- 260204RE_ralph_loop_remediation
- 260204US_user_story_testing_infrastructure
- 260204AL_worktree_planning_alignment (this plan)
- 260204IM_planning_context_improvements
```

---

## High-Level Approach

### Phase 1: CLI Enhancement - Worktree Commands

**Objective**: Add `agentic worktree create` command for standardized worktree creation with automatic workspace file updates

**Changes**:
- Create new file: `modules/AgenticCLI/src/agenticcli/commands/worktree.py`
- Implement worktree create/list/status/remove commands
- Enforce naming conventions and base branch validation
- **AUTO-UPDATE WORKSPACE**: Automatically update `.code-workspace` file when worktrees are created/removed

**Key Behaviors**:
- `agentic worktree create <branch-name> --base <base>`: Create new worktree AND update workspace file
- `agentic worktree list`: List all worktrees with status
- `agentic worktree status`: Current worktree context (already exists)
- `agentic worktree remove <branch-name>`: Safe worktree removal AND update workspace file

**Workspace Auto-Update**:
- On worktree create: Add entry to `folders[]` and `git.scanRepositories[]`
- On worktree remove: Remove entry from both arrays
- Detect workspace file location from main worktree (e.g., `agenticengineering.code-workspace`)
- Handle case where workspace file doesn't exist (skip update with warning)

### Phase 2: CLI Enhancement - Plan Command Enforcement

**Objective**: Make `agentic plan create` REQUIRE worktree branch parameter

**Changes**:
- Modify: `modules/AgenticCLI/src/agenticcli/commands/plan.py`
- Add required `--branch` parameter to plan create command
- Validate branch exists as worktree before allowing plan creation

**Key Behaviors**:
- `agentic plan create --branch <branch> --description <desc>`: Requires branch
- Error if branch is not a valid worktree
- Error if worktree already has a live planning folder

### Phase 3: Validation Service

**Objective**: Enforce 1:1 relationship between worktrees and live planning folders

**Changes**:
- Modify: `modules/AgenticGuidance/src/agenticguidance/services/plan.py`
- Add validation logic: max 1 live plan per worktree branch
- Add validation logic: plan cannot be created on main branch

**Key Validations**:
- Check if worktree already has live planning folder
- Prevent multiple live plans for same worktree
- Prevent live plans on main branch

### Phase 4: Cleanup Operations (PARTIALLY COMPLETE)

**Objective**: Remove stale worktrees and document cleanup process

**Actions**:
1. ~~Identify stale worktrees (no recent commits, merged branches)~~ DONE - 28 stale worktrees identified and removed
2. ~~Remove `feature/langsmith-cli-enhancements` (replaced by agentic-cli)~~ DONE
3. Document safe cleanup procedures in CLI help (PENDING)
4. Add `agentic worktree prune` command to identify/remove stale worktrees (PENDING)

### Phase 5: Remediation Orchestration

**Objective**: Fix existing 8 live plans to proper worktree assignments

**Strategy**:
1. For each live plan:
   - Create corresponding worktree if missing
   - Move plan folder to correct worktree context
   - Update plan metadata with correct branch
2. Validate no plans remain on main branch
3. Verify 1:1 relationship for all plans

---

## Key Files Impacted

### Primary Changes

1. **modules/AgenticCLI/src/agenticcli/commands/plan.py**
   - Add `--branch` required parameter to plan create
   - Add worktree validation before plan creation

2. **modules/AgenticCLI/src/agenticcli/commands/worktree.py** (NEW)
   - Implement worktree management commands
   - Enforce naming conventions

3. **modules/AgenticGuidance/src/agenticguidance/services/plan.py**
   - Add 1:1 relationship validation
   - Add worktree-plan enforcement logic

### Supporting Changes

4. **modules/AgenticCLI/src/agenticcli/cli.py**
   - Register new worktree command group

5. **modules/AgenticGuidance/agents/deploy/deploy-worktree/inputs.yml**
   - Update with new CLI command patterns

---

## Success Criteria

1. `agentic plan create` REQUIRES `--branch` parameter
2. `agentic worktree create` command exists and works
3. Each worktree branch can have MAX 1 live planning folder
4. All 10 existing live plans reassigned to proper worktrees
5. No live plans exist on main branch
6. ~~Stale worktree `feature/langsmith-cli-enhancements` removed~~ DONE (28 stale worktrees removed)
7. **WORKSPACE AUTO-UPDATE**: `.code-workspace` file automatically updated when worktrees are created/removed via CLI

---

## Folder Structure

```
260204AL_worktree_planning_alignment/
├── README.md (this file)
├── live/              # Active planning tasks
├── completed/         # Completed planning tasks
├── analysis/          # Investigation and analysis artifacts
├── audit/             # Audit results and findings
├── plan_audit_clean.yml
├── plan_completed.yml
├── plan_teach.yml
└── plan_test.yml
```

---

## Dependencies

- Git worktree functionality
- AgenticCLI command structure
- AgenticGuidance validation services
- VS Code workspace file format

---

## Notes

- This plan itself demonstrates the new pattern: created on feature branch with dedicated worktree
- Plan folder naming: 260204AL uses AL suffix (auto-generated worktree ID)
- Main-First Planning: Plan folder exists in main worktree at `/home/code/AgenticEngineering/docs/plans/live/260204AL_worktree_planning_alignment/`
- Execution worktree: `/home/code/AgenticEngineering-feature/worktree-planning-alignment`
