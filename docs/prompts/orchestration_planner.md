# Orchestration Planner

Launch a planning-only orchestration session. Creates and approves plans without executing them.

## Quick Start

```bash
agentic orchestrate --mode planning
agentic orchestrate --mode planning --plan <folder>
```

## What It Does

- Spawns specialized planners (planner-build, planner-test, planner-guidance, etc.)
- Manages review/approval loops via planner-reviewer
- Creates orchestration phases in TinyDB via planner-orchestration
- Enforces story-first planning and UAT fences

## Plan Creation Protocol

CRITICAL: When creating a new plan, follow this mandatory sequence to ensure proper worktree and workspace file management:

### Correct Pattern (REQUIRED)

1. **Create plan folder via CLI first**
   ```bash
   agentic agent plan init <branch> --description <description>
   ```
   This command atomically:
   - Creates the worktree (or reuses an idle one)
   - Creates the plan folder structure
   - Updates the workspace file
   - Registers the plan in docs/worktrees.yml

2. **Then spawn planner agents with the folder path**
   ```bash
   # CLI returns the plan folder path, use it:
   agentic orchestrate session spawn --role planner-build --plan <plan-folder-name>
   ```

3. **Review and approve the plan**
   The planner creates plan YAML files, orchestration creates TinyDB phase records

### Incorrect Pattern (DO NOT USE)

```bash
# WRONG: Spawning planner without running plan init first
agentic orchestrate session spawn --role planner-build --plan 260214XX_new_feature
# ^ This will fail the FENCE in planner-build/process.yml
```

```python
# WRONG: Using Write tool to create plan folder directly
Write("docs/plans/live/260214XX_new_feature/plan.yml", content)
# ^ This bypasses worktree creation and workspace sync
```

### Why This Matters

The workspace file (`agenticengineering.code-workspace`) and worktree registry (`docs/worktrees.yml`) must stay synchronized with plan folders. There are multiple code paths that can create plan folders:

- `agentic agent plan init` (CORRECT - creates worktree + folder + workspace update)
- `agentic worktree create` (only creates worktree, no plan folder)
- `agentic agent plan scaffold` (DEPRECATED - folder only, no worktree)
- Agent Write tool (WRONG - bypasses all CLI infrastructure)

Only `agentic agent plan init` handles the full lifecycle correctly. All other paths create drift.

### Main-Only Plans (No Worktree)

If you explicitly want a plan without a worktree (e.g., documentation-only changes):

```bash
agentic agent plan init main --description <description> --no-worktree
```

This creates the plan folder and updates the workspace file without creating a worktree.

### Enforcement

The planner agents (planner-build, planner-test, planner-cleaning, planner-audit) have FENCES that check for plan folder existence before proceeding. If the folder doesn't exist, they will STOP and report:

```
FENCE VIOLATION: Plan folder not found at docs/plans/live/{plan_folder_name}/

REQUIRED ACTION:
Run: agentic agent plan init <branch> --description <description>
```

This ensures that all plans are created through the CLI pipeline.

## Agent Profile

Source of truth for the full process definition:

```
modules/AgenticGuidance/agents/orchestration/orchestration-planning/
  manifest.yml   - spawns fence, outputs, purpose
  process.yml    - full process definition with all steps
  inputs.yml     - input contract
```

## See Also

- `agentic orchestrate --mode executor` - Execute approved plans
- `agentic orchestrate --mode friction` - Analyze traces for friction patterns
