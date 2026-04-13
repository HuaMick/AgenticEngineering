# Agents Directory

This directory contains agent process definitions for the AgenticGuidance module. Each agent represents a specialized role with specific inputs, processes, and outputs.

## Agent Catalog

### Summary

| Category | Agents | Description |
|----------|--------|-------------|
| [orchestration](#orchestration) | 2 | High-level coordination of planning and execution workflows |
| [planner](#planner) | 6 | Create executable implementation epics from objectives |
| [build](#build) | 4 | Code implementation for production deployment |
| [test](#test) | 4 | Validation through testing and quality assurance |
| [teacher](#teacher) | 2 | Improve agent guidance (paths, fences, signposts) |
| [deploy](#deploy) | 1 | Infrastructure and deployment tooling |

**Total: 19 active agents**

---

## orchestration

High-level orchestration agents that coordinate planning and execution workflows.

| Agent | Version | Description | Status |
|-------|---------|-------------|--------|
| orchestration-planning | 2.0 | Planning-only workflows - human-in-the-loop epic creation and approval | Complete |
| orchestration-executor | 2.0 | TinyDB-driven execution - dynamic agent routing from phase.agent field | Complete |

**Routing Logic:**
- `orchestration-planning`: Planning-only workflows, produces approved epics with TinyDB phase records for downstream use.
- `orchestration-executor`: TinyDB-driven execution (dynamic agent routing from phase.agent field). **Use this for all execution workflows.**

---

## planner

Planner agents are responsible for creating executable implementation epics from objectives. They analyze requests, structure work into phases and tickets, and produce live epics for other agent categories to execute.

| Agent | Version | Description | Status |
|-------|---------|-------------|--------|
| epic-creator | 2.0 | Epic scaffolding and initialization | Complete |
| planner-build | 2.0 | Create phased implementation epics for build/development tasks with proper context routing, parallelization, and CI/CD validation | Complete |
| planner-test | 2.0 | Create phased test epics including component testing, user flow testing, audit loops, and documentation validation | Complete |
| planner-explore | 2.0 | Discovery and exploration planning for codebase analysis and research tasks | Complete |
| planner-orchestration | 2.0 | Create TinyDB phase records with agent routing from approved ticket data | Complete |
| planner-audit | 2.0 | Audit epic folder compliance and identify files that should be archived, completed, or removed | Complete |

**Routing Logic:**
- `epic-creator`: Scaffolding new epics with folder structure and initial tickets
- `planner-build`: Planning code implementation and build tasks
- `planner-test`: Planning test strategy and validation tasks
- `planner-explore`: Planning discovery, research, and codebase exploration tasks
- `planner-orchestration`: Creating TinyDB phase records with agent routing
- `planner-audit`: Auditing epic folders for compliance with lifecycle rules

---

## build

Build agents handle code implementation for production deployment. Each sub-agent specializes in a specific technology stack.

| Agent | Version | Description | Status |
|-------|---------|-------------|--------|
| build-python | 2.0 | Python-specific build agent for backend services and CLI components | Complete |
| build-flutter | 2.0 | Flutter-specific build agent for mobile/web frontend components | Complete |
| build-story-writer | 2.0 | User story authoring for epics and features | Complete |
| build-docs-writer | 2.0 | Documentation authoring for agents, services, and APIs | Complete |

---

## test

Test agents validate implementations through various testing strategies. They execute tests but do not fix or implement code.

| Agent | Version | Description | Status |
|-------|---------|-------------|--------|
| test-builder | 2.0 | Create and update test files that expose defects (Unit, Integration, E2E coverage) | Complete |
| test-audit | 2.0 | Review test quality, coverage alignment, and identify gaps (reward hacking detection) | Complete |
| test-uat | 2.0 | User acceptance test simulation using only project documentation (agent-blind-test approach) | Complete |
| trace-explorer | 2.0 | Trace analysis and diagnostics for agent execution logs | Complete |

**Routing Logic:**
- `test-builder`: Creates and updates test files that expose defects (test-build strategy)
- `test-audit`: Reviews test quality, detects reward hacking (audit strategy)
- `test-uat`: Tests user stories via agent-blind-test strategy (UAT validation)
- `trace-explorer`: Analyses agent execution traces and diagnoses failures

---

## teacher

Teacher agents improve agent guidance by building paths, fences, and signposts. They analyze friction and enhance guidance quality.

| Agent | Version | Description | Status |
|-------|---------|-------------|--------|
| teacher-update-guidance | 2.0 | Update agent guidance by improving process.yml and inputs.yml files, and inline examples | Complete |
| teacher-update-assets | 2.0-p1 | Create/update shared assets (definitions, guidelines, examples) in modules/AgenticGuidance/assets/ | Complete |

**Routing Logic:**
- `teacher-update-guidance`: Analyze agent logs, improve process.yml and inputs.yml files, create examples
- `teacher-update-assets`: Create or update shared assets (definitions, guidelines, examples, shared inputs)

---

## deploy

Deploy agents handle infrastructure and deployment tooling. They do not write application code, create tests, or plan work.

| Agent | Version | Description | Status |
|-------|---------|-------------|--------|
| deploy-cicd | 2.0 | CI/CD pipeline configuration and validation | Complete |

**Routing Logic:**
- `deploy-cicd`: Route CI/CD, pipeline, cloudbuild, dockerfile requests

---

## Implementation Status Legend

Each agent directory contains:
- `manifest.yml` - Agent metadata, version, and dependencies
- `inputs.yml` - Required context files for the agent
- `process.yml` - Step-by-step behavioral guidance

**Status Values:**
- **Complete**: All three files (manifest.yml, inputs.yml, process.yml) exist
- **Partial**: Some files missing
- **Stub**: Only manifest.yml exists

All 19 agents in this directory are **Complete**.

---

## Categories Planned But Not Implemented

The following categories have infrastructure (definitions, guidelines, shared inputs) but no dedicated agent implementations. Their functionality is handled by existing agents:

| Category | Infrastructure | Current Workaround | Status |
|----------|---------------|-------------------|--------|
| cleaner | 2 files (cleaner-shared-guidelines.yml, cleaner-shared.yml) | `planner-explore` handles discovery and cleanup planning | Planned |
| documentation | Minimal | `build-docs-writer` and `teacher-update-assets` handle doc updates | Planned |

These categories may be implemented if dedicated agents become necessary, but current workarounds are sufficient.

---

## Directory Structure

```
modules/AgenticGuidance/agents/
├── manifest.yml                    # Top-level agent manifest
├── README.md                       # This file
├── orchestration/                  # Orchestration agents
│   ├── manifest.yml
│   ├── orchestration-planning/
│   └── orchestration-executor/
├── planner/                        # Planner agents
│   ├── manifest.yml
│   ├── epic-creator/
│   ├── planner-build/
│   ├── planner-test/
│   ├── planner-explore/
│   ├── planner-orchestration/
│   └── planner-audit/
├── build/                          # Build agents
│   ├── manifest.yml
│   ├── build-python/
│   ├── build-flutter/
│   ├── build-story-writer/
│   └── build-docs-writer/
├── test/                           # Test agents
│   ├── manifest.yml
│   ├── test-builder/
│   ├── test-audit/
│   ├── test-uat/
│   └── trace-explorer/
├── teacher/                        # Teacher agents
│   ├── manifest.yml
│   ├── teacher-update-guidance/
│   └── teacher-update-assets/
└── deploy/                         # Deploy agents
    ├── manifest.yml
    └── deploy-cicd/
```

---

## Design Decisions

### README Files as Injectable Context

README files in this repository serve a dual purpose:

1. **Human documentation** - Standard markdown documentation for developers
2. **Injectable context** - Content that can be injected into agent prompts to provide situational awareness

When agents need context about a directory's purpose or contents, the README.md file can be loaded as part of their input. This eliminates the need for separate context files that duplicate README content.

### Category Manifests Over Process Files

Agents should reference **category manifests** rather than individual process files:

```yaml
# Preferred: Reference the category manifest
test_agents: "modules/AgenticGuidance/agents/test/manifest.yml"

# Avoid: Direct process file references
test_builder: "modules/AgenticGuidance/agents/test/test-builder/process.yml"
```

Category manifests define routing logic and available sub-agents, providing a stable interface to agent capabilities.

---

## Related Files

- `modules/AgenticGuidance/agents/manifest.yml` - Lists all migrated and non-migrated agent categories
- `modules/AgenticGuidance/assets/definitions/agent-categories.yml` - Category definitions and characteristics
- `docs/agent-role-scope-matrix.md` - Role and scope documentation for all agents
