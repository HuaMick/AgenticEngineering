# AgenticGuidance

The guidance layer for Claude Code sessions within the AgenticEngineering ecosystem. AgenticGuidance provides structured agents, definitions, guidelines, and examples that shape how Claude Code works on complex tasks.

## Module Structure

```
AgenticGuidance/
├── agents/           # Agent definitions organized by category
├── assets/           # Shared definitions, guidelines, examples, inputs
├── entrypoints/      # Top-level workflow entry points
├── docs/             # Module documentation
└── userstories/      # User story definitions (legacy reference)
```

## Agent Categories

The module contains 6 implemented agent categories with 21 sub-agents:

### Planner (6 agents)
Create executable implementation plans from objectives.

| Agent | Purpose |
|-------|---------|
| `planner-build` | Implementation planning for code changes |
| `planner-test` | Test planning with execution loops |
| `planner-cleaning` | Cleanup and audit planning |
| `planner-guidance` | Guidance improvement planning |
| `planner-guidance-testing` | Guidance completeness testing |
| `planner-reviewer` | Plan review and approval |

### Orchestration (4 agents)
High-level coordination of planning and execution workflows.

| Agent | Purpose |
|-------|---------|
| `orchestration-planning` | Human-in-the-loop plan creation |
| `orchestration-build` | Code implementation and testing |
| `orchestration-guidance` | Context engineering for agent guidance |
| `orchestration-executor` | Dynamic agent routing from Plan-MMD |

### Test (7 agents)
Validation through testing and quality assurance.

| Agent | Purpose |
|-------|---------|
| `test-runner` | Execute Python tests and report results |
| `test-audit` | Review test quality and detect reward hacking |
| `test-final-output` | Validate final outputs and execution data |
| `test-guidance-simulator` | Execute walkthrough-based guidance validation |
| `test-builder` | Build test implementations |
| `test-service` | Service-level testing |
| `test-user-simulator` | User interaction simulation |

### Teacher (2 agents)
Improve agent guidance by building paths, fences, and signposts.

| Agent | Purpose |
|-------|---------|
| `teacher-update-guidance` | Improve process.yml and inputs.yml files |
| `teacher-update-assets` | Create/update shared assets (definitions, guidelines) |

### Build (2 agents)
Building and compiling code for production deployment.

| Agent | Purpose |
|-------|---------|
| `build-python` | Python-specific build for backend services and CLI |
| `build-flutter` | Flutter-specific build for mobile/web frontend |

### Deploy (2 agents)
Infrastructure and deployment tooling.

| Agent | Purpose |
|-------|---------|
| `deploy-worktree` | Git worktree and VS Code workspace management |
| `deploy-cicd` | CI/CD pipeline configuration |

## Assets

### Definitions (86 files)
Stable concepts and terminology that define "what is X". Key definitions include:
- `context-minimisation.yml` - Core principle for reducing context
- `agent-categories.yml` - Agent taxonomy
- `plans.yml` - Plan structure and lifecycle
- `agent-loops.yml` - Loop patterns for iterative work
- `fence.yml` / `fence-build-deploy.yml` - Boundary definitions
- `escalation.yml` - When and how to escalate

### Guidelines (15 files)
Behavioral rules and constraints that define "how to act":
- `less-is-more.yml` - Minimal sufficient changes
- `fix-the-source.yml` - Address root causes
- `context-minimisation.yml` - Just-in-time context loading
- `iteration.yml` - Iterative development approach
- `testing.yml` - Testing standards
- `safety.yml` - Safety constraints
- `reward-hacking-prevention.yml` - Prevent gaming metrics
- `orchestration-policy.yml` - Orchestration behavior rules
- `worktree-and-branching.yml` - Git workflow standards

### Examples
Reference implementations organized by agent category:
- `planner/` - Plan structure examples, phase templates (build, test, teach, cleanup, UAT)
- `teacher/` - Concise guidance examples
- `test/` - Test plan examples, final outcome reports
- `cleaner/` - Directory preservation rules

### Inputs (11 files)
Shared input configurations for agents:
- `core-system.yml` / `core-guidelines.yml` - Base system context
- `planner-shared.yml` / `planner-core-*.yml` - Planner configurations
- `test-shared.yml` - Test agent inputs
- `deploy-shared.yml` / `deploy-minimal.yml` - Deploy configurations
- `cleaner-shared.yml` - Cleaner configurations

### Test Fixtures
Test data and fixtures for guidance validation.

## Entrypoints

Three top-level entrypoints for initiating workflows:

| Entrypoint | Purpose |
|------------|---------|
| `_plan_build.yml` | Create implementation plans for code changes |
| `_plan_teach.yml` | Create guidance plans for teaching/documentation |
| `_orchestrate.yml` | Execute a pre-approved plan |

### Workflow

1. **Planning Phase**: Use `_plan_build.yml` or `_plan_teach.yml` to create a plan
   - Invokes `orchestration-planning` agent
   - Spawns `deploy-worktree` for workspace setup
   - Runs planning loops with specialized planners and reviewers
   - Outputs approved plan to `docs/plans/live/YYMMDDRepo_Branch/`

2. **Execution Phase**: Use `_orchestrate.yml` to execute the approved plan
   - Invokes `orchestration-build` agent
   - Executes phases in order defined by plan
   - Orchestrates builder and tester agents per phase definitions

## Path Resolution

AgenticGuidance uses two path resolution strategies:

| Path Type | Convention | Resolved Against |
|-----------|------------|------------------|
| Module-relative | Paths NOT starting with `docs/` | AgenticGuidance module root |
| Repo-relative | Paths starting with `docs/` | Target repository root |

## Implementation Status

**Implemented**:
- 6 agent categories with 21 sub-agents
- 86 definition files
- 15 guideline files
- 3 entrypoints
- Example templates for all major workflows
- Shared input configurations

**Not Migrated** (may be deprecated):
- `cleaner` category (cleanup logic exists in planner-cleaning)
- `explore` category
- `documentation` category

## Relationship to AgenticEngineering

AgenticGuidance is one of three project modules:

```
AgenticEngineering/
├── modules/
│   ├── AgenticBackend/    # Backend services
│   ├── AgenticFrontend/   # Frontend UI
│   └── AgenticGuidance/   # This module - guidance layer
```

---

*Part of [AgenticEngineering](../../docs/README.md) - scaffolding for Claude Code sessions*
