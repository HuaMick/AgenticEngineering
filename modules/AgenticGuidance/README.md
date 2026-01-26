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

The module contains 6 implemented agent categories with 23 active sub-agents (plus 2 deprecated):

### Orchestration (3 active, 2 deprecated)
High-level coordination of planning and execution workflows.

| Agent | Purpose |
|-------|---------|
| `orchestration-planning` | Human-in-the-loop plan creation + MMD generation |
| `orchestration-executor` | Dynamic agent routing from Plan-MMD |
| `orchestration-friction` | LangSmith trace friction analysis workflow |
| ~~`orchestration-build`~~ | **DEPRECATED** - replaced by `orchestration-executor` |
| ~~`orchestration-guidance`~~ | **DEPRECATED** - replaced by `orchestration-executor` |

### Planner (7 agents)
Create executable implementation plans from objectives.

| Agent | Purpose |
|-------|---------|
| `planner-build` | Implementation planning for code changes |
| `planner-test` | Test planning with execution loops |
| `planner-cleaning` | Cleanup and audit planning |
| `planner-guidance` | Guidance improvement planning |
| `planner-guidance-testing` | Guidance completeness testing |
| `planner-reviewer` | Plan review and approval |
| `planner-audit` | Plan folder compliance auditing |

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

### Teacher (3 agents)
Improve agent guidance by building paths, fences, and signposts.

| Agent | Purpose |
|-------|---------|
| `teacher-update-guidance` | Improve process.yml and inputs.yml files |
| `teacher-update-assets` | Create/update shared assets (definitions, guidelines) |
| `teacher-trace-diagnostics` | Analyze LangSmith traces for friction patterns |

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

### Definitions (35 files)
Stable concepts and terminology that define "what is X". Key definitions include:
- `agent-categories.yml` - Agent taxonomy
- `plans.yml` - Plan structure and lifecycle
- `agent-loops.yml` - Loop patterns for iterative work
- `rlm-patterns.yml` - RLM pattern definitions for context decomposition
- `friction.yml` - Friction pattern definitions
- `trace-diagnostics.yml` - Trace analysis definitions
- `path.yml` - Path concept for agent guidance
- `guidance-artifacts.yml` - Fence/signpost concepts

### Guidelines (44 files)
Behavioral rules and constraints that define "how to act":
- `less-is-more.yml` - Minimal sufficient changes
- `fix-the-source.yml` - Address root causes
- `context-minimisation.yml` - Just-in-time context loading
- `rlm-integration.yml` - RLM integration patterns
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

Four top-level entrypoints for initiating workflows:

| Entrypoint | Purpose |
|------------|---------|
| `_plan_build.yml` | Create implementation plans for code changes |
| `_plan_teach.yml` | Create guidance plans for teaching/documentation |
| `_orchestrate.yml` | Execute a pre-approved plan |
| `_analyze_friction.yml` | Analyze LangSmith traces for friction patterns |

### Usage

To initiate a workflow, **inject the content** of the appropriate entrypoint file into the agent's context window. This establishes the agent's role and orchestration process for the session.

### Workflow

1. **Planning Phase**: Use `_plan_build.yml` or `_plan_teach.yml` to create a plan
   - Invokes `orchestration-planning` agent
   - Spawns `deploy-worktree` for workspace setup
   - Runs planning loops with specialized planners and reviewers
   - Outputs approved plan to `docs/plans/live/YYMMDDXX_description/`

2. **Execution Phase**: Use `_orchestrate.yml` to execute the approved plan
   - Invokes `orchestration-executor` agent
   - Discovers `orchestration_*.mmd` file in plan folder
   - Executes phases using dynamic AGENT_ROUTING from MMD metadata
   - Orchestrates builder, tester, and teacher agents per phase definitions

## Path Resolution

AgenticGuidance uses two path resolution strategies:

| Path Type | Convention | Resolved Against |
|-----------|------------|------------------|
| Module-relative | Paths NOT starting with `docs/` | AgenticGuidance module root |
| Repo-relative | Paths starting with `docs/` | Target repository root |

## Implementation Status

This section is the **source of truth** for agent implementation status. Plan-reviewer agents should check this before planning work. Agents should not create tasks for unimplemented infrastructure.

### Status Legend
- Implemented: Agent guidance complete AND functional infrastructure exists
- Guidance Only: Agent guidance files exist but underlying infrastructure NOT yet built
- In Progress: Currently being worked on
- Not Implemented: No guidance or infrastructure

---

### Orchestration Agents

| Agent | Status | Notes |
|-------|--------|-------|
| orchestration-planning | Implemented | Human-in-the-loop plan creation, MMD generation |
| orchestration-executor | Implemented | Dynamic agent routing from Plan-MMD metadata |
| orchestration-friction | Implemented | LangSmith trace friction analysis workflow |
| ~~orchestration-build~~ | Deprecated | Replaced by orchestration-executor |
| ~~orchestration-guidance~~ | Deprecated | Replaced by orchestration-executor |

### Planner Agents

| Agent | Status | Notes |
|-------|--------|-------|
| planner-build | Implemented | Implementation planning for code changes |
| planner-test | Implemented | Test planning with execution loops |
| planner-cleaning | Implemented | Cleanup and audit planning |
| planner-guidance | Implemented | Guidance improvement planning |
| planner-guidance-testing | Implemented | Guidance completeness testing |
| planner-reviewer | Implemented | Plan review and approval |
| planner-audit | Implemented | Plan folder compliance auditing |

### Test Agents

| Agent | Status | Notes |
|-------|--------|-------|
| test-runner | Implemented | Execute Python tests and report results |
| test-audit | Implemented | Review test quality and detect reward hacking |
| test-final-output | Implemented | Validate final outputs and execution data |
| test-guidance-simulator | Implemented | Execute walkthrough-based guidance validation |
| test-builder | Implemented | Build test implementations |
| test-service | Implemented | Service-level testing |
| test-user-simulator | Implemented | User interaction simulation |

### Teacher Agents

| Agent | Status | Notes |
|-------|--------|-------|
| teacher-update-guidance | Implemented | Improve process.yml and inputs.yml files |
| teacher-update-assets | Implemented | Create/update shared assets |
| teacher-trace-diagnostics | Implemented | Analyze LangSmith traces for friction patterns |

### Build Agents

| Agent | Status | Notes |
|-------|--------|-------|
| build-python | Implemented | Python-specific build for backend/CLI |
| build-flutter | Implemented | Flutter-specific build for mobile/web |

### Deploy Agents

| Agent | Status | Notes |
|-------|--------|-------|
| deploy-worktree | Implemented | Git worktree and VS Code workspace management |
| deploy-cicd | **Guidance Only** | CI/CD pipeline NOT yet set up for this module. Agent guidance exists for validating CI/CD files, but no cloudbuild.yaml, Dockerfile.test, or GitHub Actions workflow exists for AgenticGuidance. CI/CD infrastructure only exists in legacy modules. |

---

### Infrastructure Status

| Infrastructure | Status | Notes |
|----------------|--------|-------|
| Agent Guidance Files | Implemented | 24 active agents with manifest.yml, inputs.yml, process.yml |
| Definition Files | Implemented | 35+ definition files in assets/definitions/ |
| Guideline Files | Implemented | 44+ guideline files in assets/guidelines/ |
| Shared Input Configs | Implemented | 11 shared input configurations |
| Entrypoints | Implemented | 4 top-level workflow entrypoints |
| Example Templates | Implemented | Reference implementations for all workflows |
| CI/CD Pipeline | **Not Implemented** | No automated testing pipeline for AgenticGuidance module |
| GitHub Actions | **Not Implemented** | No workflow files for this module |

### Categories Not Migrated

These categories have some infrastructure (definitions, guidelines) but no dedicated agent implementations. Current workarounds are sufficient:

| Category | Status | Workaround |
|----------|--------|------------|
| cleaner | Not Migrated | `planner-cleaning` handles cleanup planning |
| explore | Not Migrated | Planner agents handle ad-hoc discovery |
| documentation | Not Migrated | `teacher-update-assets` handles doc updates |

---

## Progress Tracking

This README serves as the **overall progress tracker** for the AgenticGuidance module:

1. **Source of Truth**: This Implementation Status section documents what is implemented, in progress, and NOT yet implemented.

2. **Planning Guidance**:
   - Plan-reviewer agents MUST check this section before approving plans
   - Do NOT create tasks that depend on unimplemented infrastructure (e.g., CI/CD validation tasks when no pipeline exists)
   - Mark items as "In Progress" when work begins

3. **Status Updates**:
   - Update agent status when implementation completes
   - Add notes explaining blockers or dependencies
   - Move completed items from "In Progress" to "Implemented"

4. **Key Gaps to Address**:
   - `deploy-cicd`: Infrastructure needs to be built (cloudbuild.yaml, GitHub Actions)
   - CI/CD Pipeline: No automated testing for guidance changes
   - Integration testing for agent workflows

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
