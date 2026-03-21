# Parallel Explore & Planning Pipeline Rearchitect

## Problem
The planning pipeline runs 6 sequential agents (~37 min) for what should be a 5-10 minute operation. Only 1 explore agent runs despite `spawn_explore_agents()` being named plural. The designer and reviewer duplicate work or rubber-stamp.

## Objective
Strip down the planning pipeline from 6 sequential agents to 3 steps with parallel exploration:

### Target Architecture
```
story-writer (renamed from story-generator)
    - Generates user stories from epic objective
    - Organizes stories into CATEGORIES (e.g., "cli-cleanup", "test-fixes", "module-refactor")
    - Writes stories.yml with category assignments
    ↓
N × explore agents (PARALLEL via ThreadPoolExecutor)
    - One per category from stories.yml
    - Each scoped to its category's stories + relevant codebase area
    - Enrich tickets with target-files, guidance, success-criteria
    - All run concurrently in separate tmux panes
    ↓
orchestration agent
    - Reads enriched tickets
    - Creates TinyDB phase records with agent routing
    - Includes lightweight validation (replaces reviewer)
```

### What Gets Cut
- **planner-reviewer**: Replace with programmatic pre-flight validation in Python
- **planner-design**: Merge architecture decisions into story-writer (categories) + orchestration (phase mapping)
- **design loop-back**: Remove the explore→design→needs_stories loop. One pass.

### What Gets Added
- **Category system in stories.yml**: Stories grouped by category with codebase scope hints
- **Parallel spawn in planner_loop.py**: `spawn_explore_agents()` uses ThreadPoolExecutor to run N agents
- **Category-scoped explore prompts**: Each explore agent gets its category's stories + scope
- **Pre-flight validation function**: Python code that does what reviewer did (field checks, agent existence, etc.)

## Constraints
- Must use sdk-tmux transport for parallel agents (never SDK-DIRECT due to zombie bug)
- TinyDB concurrent writes are safe (FileLock protected)
- Each explore agent gets unique session_id
- story-writer timeout: 600s, explore timeout: 600s each, orchestration timeout: 900s
- Target total planning time: <10 minutes for typical epics

## Key Files
- `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` — Main pipeline, _process_plan_inner
- `modules/AgenticCLI/src/agenticcli/utils/sdk_runner.py` — Timeouts, tool allowlists
- `modules/AgenticGuidance/agents/planner/story-generator/` — Rename to story-writer, add categories
- `modules/AgenticGuidance/agents/planner/planner-explore/` — Add category-scoped prompts
- `modules/AgenticGuidance/agents/planner/planner-reviewer/` — Delete or archive
- `modules/AgenticGuidance/agents/planner/planner-design/` — Delete or archive
- `modules/AgenticGuidance/agents/planner/planner-orchestration/` — Absorb lightweight validation
