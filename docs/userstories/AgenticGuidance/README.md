# AgenticGuidance User Stories

Comprehensive user stories for the AgenticGuidance module - the guidance layer for Claude Code sessions within the AgenticEngineering ecosystem.

## Overview

This directory contains 143 user stories organized into 9 categories, covering all aspects of the AgenticGuidance module including agents, orchestration, planning, testing, teaching, assets, services, and deployment.

## Story Files

| File | Category | Stories | Description |
|------|----------|---------|-------------|
| `00_metadata.yml` | Metadata | - | Overview, conventions, and reference information |
| `01_agent_definitions.yml` | Agent Definitions | 9 | Agent manifests, discovery, categories, responsibilities |
| `02_process_and_inputs.yml` | Process & Inputs | 10 | Process.yml, inputs.yml, reference layers, CCI bootstrap |
| `03_orchestration.yml` | Orchestration | 11 | Planning workflows, MMD-driven execution, friction analysis |
| `04_planning.yml` | Planning | 16 | Plan creation, review loops, planner agents, MMD generation |
| `05_testing.yml` | Testing | 16 | Test execution, audit, guidance simulation, validation |
| `06_teaching.yml` | Teaching | 18 | Guidance updates, asset management, trace diagnostics |
| `07_assets.yml` | Assets | 18 | Definitions, guidelines, examples, specifications, inputs |
| `08_services.yml` | Services | 18 | PlanService, TaskService, QuestionService, state management |
| `09_deployment.yml` | Deployment | 18 | Worktree management, CI/CD, build processes |

**Total: 143 user stories**

## Story ID Format

Stories use the format `US-GD-XXX`:
- `US` = User Story
- `GD` = Guidance (module identifier)
- `XXX` = Sequential number (001-157)

## Priority Levels

- **critical**: Core functionality, blocking for basic usage
- **high**: Important functionality, impacts multiple workflows
- **medium**: Useful functionality, enhances specific workflows
- **low**: Nice-to-have, minor improvements

## Key Story Groups

### Agent System (US-GD-001 to US-GD-019)
- Agent discovery and manifests (001-003)
- Manifest structure and validation (004-007)
- Agent vs CLI boundaries (008-009)
- Process files and inputs (010-019)

### Orchestration (US-GD-020 to US-GD-030)
- Human-in-the-loop planning (020-022)
- MMD-driven execution (023-026)
- Friction analysis (027-030)

### Planning (US-GD-040 to US-GD-055)
- Implementation planning (040-043)
- Test planning (044-046)
- Guidance planning (047-048)
- Plan review (049-051)
- Cleanup and audit (052-053)
- MMD generation (054-055)

### Testing (US-GD-060 to US-GD-075)
- Test execution (060-062)
- Test audit and quality (063-065)
- Test creation (066-068)
- Guidance validation (069-070)
- Output validation (071-072)
- User story testing (073-074)
- Service testing (075)

### Teaching (US-GD-080 to US-GD-097)
- Process and inputs improvement (080-084)
- Asset creation and updates (085-089)
- Trace diagnostics (090-094)
- Guidance quality principles (095-097)

### Assets (US-GD-100 to US-GD-117)
- Definitions (100-101)
- Guidelines (102-103)
- Examples (104-108)
- Specifications (109-111)
- Shared inputs (112-114)
- Discovery and validation (115-117)

### Services (US-GD-120 to US-GD-137)
- PlanService (120-123)
- TaskService (124-127)
- QuestionService (128-131)
- State management (132-134)
- Service architecture (135-137)

### Deployment (US-GD-140 to US-GD-157)
- Worktree management (140-144)
- CI/CD pipeline (145-147)
- Python builds (148-150)
- Flutter builds (151-152)
- Build/deploy integration (153-157)

## Usage

### For Developers
Reference these stories when:
- Implementing new features
- Understanding module capabilities
- Planning architecture changes
- Writing tests for existing functionality

### For Planner Agents
Use these stories to:
- Understand what functionality exists
- Create implementation plans aligned with user needs
- Identify acceptance criteria for tasks
- Cross-reference related agents and commands

### For Documentation
Stories provide:
- Complete feature inventory
- Acceptance criteria for validation
- Related commands and files
- Agent and service relationships

## Related Documentation

- **Module README**: `/home/code/AgenticEngineering/modules/AgenticGuidance/README.md`
- **Agent Catalog**: `/home/code/AgenticEngineering/modules/AgenticGuidance/agents/README.md`
- **Asset Specifications**: `/home/code/AgenticEngineering/modules/AgenticGuidance/assets/specifications/`
- **Service Layer**: `/home/code/AgenticEngineering/modules/AgenticGuidance/src/agenticguidance/services/`

## Conventions

### Story Structure
Each story follows this YAML structure:
```yaml
- id: "US-GD-XXX"
  title: "Short descriptive title"
  category: "category_name"
  priority: "critical|high|medium|low"
  as_a: "user role or agent type"
  i_want: "to do something"
  so_that: "I achieve some goal"
  acceptance_criteria:
    - "Criterion 1"
    - "Criterion 2"
  related_agents:
    - "agent-name"
  related_commands:
    - "agentic command"
  related_services:
    - "ServiceName"
  related_files:
    - "path/to/file"
```

### Cross-References
Stories reference:
- **Related agents**: Which agents are involved
- **Related commands**: CLI commands used or affected
- **Related services**: Service layer components
- **Related files**: Key files in implementation

## Version

- **Module Version**: 2.0 (Reference Layer Architecture)
- **Stories Updated**: 2026-02-07
- **Total Stories**: 143
- **Total Categories**: 9

---

*Part of the [AgenticEngineering](../../README.md) project - scaffolding for Claude Code sessions*
