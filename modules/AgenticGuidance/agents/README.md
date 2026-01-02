# Agents Directory

This directory contains agent process definitions that have been migrated to the AgenticGuidance module. Each agent represents a specialized role with specific inputs, processes, and outputs.

## Purpose

The `agents/` directory organizes guidance for structured agent behaviors. Each agent category has:

- A **manifest** that lists sub-agents and their routing logic
- Individual **sub-agent directories** containing:
  - `manifest.yml` - Agent metadata and dependencies
  - `inputs.yml` - Required context files for the agent
  - `process.yml` - Step-by-step behavioral guidance

## Migration Status

### Migrated Agents

| Category | Sub-Agents | Status |
|----------|------------|--------|
| **planner** | 6 sub-agents | Fully migrated |

**Planner sub-agents:**
- `planner-build` - Implementation planning
- `planner-test` - Test planning with iteration loops
- `planner-cleaning` - Cleanup and audit planning
- `planner-guidance` - Guidance improvement planning
- `planner-reviewer` - Plan review and approval
- `planner-guidance-testing` - Guidance completeness testing

### Non-Migrated Agents (Legacy)

The following agent categories remain in the legacy location at `modules/legacy/MyAgents/`:

| Category | Description | Legacy Path |
|----------|-------------|-------------|
| build | Code implementation | `modules/legacy/MyAgents/` |
| test | Test execution | `modules/legacy/MyAgents/` |
| cleaner | Code cleanup | `modules/legacy/MyAgents/` |
| deploy | Deployment operations | `modules/legacy/MyAgents/` |
| teacher | Guidance creation | `modules/legacy/MyAgents/` |
| explore | Discovery and research | `modules/legacy/MyAgents/` |
| orchestration | Coordination | `modules/legacy/MyAgents/` |
| documentation | Documentation generation | `modules/legacy/MyAgents/` |

## Design Decisions

### README Files as Injectable Context

README files in this repository serve a dual purpose:

1. **Human documentation** - Standard markdown documentation for developers
2. **Injectable context** - Content that can be injected into agent prompts to provide situational awareness

When agents need context about a directory's purpose or contents, the README.md file can be loaded as part of their input. This eliminates the need for separate context files that duplicate README content.

**Implications:**
- Keep README files concise and factual
- Avoid verbose explanations that would waste prompt space
- Structure content for both human readers and agent consumption
- Use clear headings that agents can reference

### Category Manifests Over Process Files

Agents should reference **category manifests** rather than individual process files:

```yaml
# Preferred: Reference the category manifest
test_agents: "agents/test/manifest.yml"

# Avoid: Direct process file references
test_runner: "agents/test/test-runner/process.yml"
```

**Why:**
- Category manifests define routing logic and available sub-agents
- Individual process files may change during refactoring
- Manifests provide a stable interface to agent capabilities
- Reduces coupling between planner agents and execution agents

### Handling Non-Migrated Agents

When a planner agent needs to reference a non-migrated agent category:

1. **Use placeholder references** pointing to the legacy path
2. **Document the dependency** in the planner's manifest
3. **Do not migrate** the non-planner agent just to satisfy the reference

Example in a planner manifest:
```yaml
# Reference to non-migrated agent (placeholder)
execution_agent: "modules/legacy/MyAgents/agents/build/manifest.yml"
# Note: Will be updated when build agents are migrated
```

This approach:
- Maintains clear migration scope
- Preserves traceability of dependencies
- Allows independent migration timelines for different agent categories

## Future Migration Path

When migrating additional agent categories to AgenticGuidance:

1. **Update the top-level manifest** (`agents/manifest.yml`)
   - Move category from `not_migrated` to `categories`
   - Add sub-agent list with descriptions

2. **Create the category directory** (`agents/<category>/`)
   - Add `manifest.yml` with routing logic
   - Migrate each sub-agent directory

3. **Update planner references**
   - Change legacy paths to new AgenticGuidance paths
   - Update any hardcoded process.yml references to category manifests

4. **Validate dependencies**
   - Ensure all referenced definition files exist
   - Verify input layer files are present
   - Test agent loading with the new paths

## Directory Structure

```
agents/
├── manifest.yml              # Top-level agent manifest
├── README.md                 # This file
└── planner/                  # Planner agent category (migrated)
    ├── manifest.yml          # Category manifest with routing
    ├── planner-build/        # Sub-agent directories
    ├── planner-test/
    ├── planner-cleaning/
    ├── planner-guidance/
    ├── planner-reviewer/
    └── planner-guidance-testing/
```

## Related Files

- `agents/manifest.yml` - Lists all migrated and non-migrated agent categories
- `assets/definitions/agent-categories.yml` - Category definitions and characteristics
- `docs/agent-role-scope-matrix.md` - Role and scope documentation for all agents
