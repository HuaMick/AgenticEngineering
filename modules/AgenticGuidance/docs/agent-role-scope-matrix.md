# Agent Role-Scope Matrix

Each agent has limited context. This matrix defines:

- **Inputs**: what context the agent should be given (mirrors `inputs.yml`).
- **Scope**: what the agent is allowed/expected to do. **Anything not explicitly in scope is out of scope** and should be escalated back to the orchestrator.

## Category Reference

Agent categories provide the organizational structure for all agents. See the canonical definition at:
`modules/AgenticGuidance/assets/definitions/agent-categories.yml`

This matrix organizes agents by their category, showing how sub-agents fit within their category's purpose and boundaries.

---

## Planner Category

**Purpose**: Create executable implementation plans from objectives
**Boundaries**: Planner agents plan; they do not implement or execute the plans

### Planner Agents

| Subtype | Role | Inputs | Scope (in-scope work only) |
|---------|------|--------|----------------------------|
| **planner-build** | Create implementation plans | Objectives, architecture, explore findings, user stories, agent manifest | Produce Live Plans with IMPLEMENTATION phases, file-level inputs, context routing for other agents |
| **planner-test** | Create test validation plans | Implementation plan, test strategies, user stories, loop definitions | Produce test phases with test-fix-loop and audit-test-fix-loop patterns; validate US-INSTALL-* stories |
| **planner-audit** | Audit compliance and create finalization plans | Live plan, user stories, loop definitions | Audit epic folder compliance, identify files to archive/complete/remove, create cleanup phases |

---

## Explore Category

**Purpose**: Codebase discovery and analysis before planning
**Boundaries**: Explore agents discover; they do not implement or modify code

### Explore Agents

| Subtype | Role | Inputs | Scope (in-scope work only) |
|---------|------|--------|----------------------------|
| **explore-architecture** | Discover project structure | Architecture docs, folder structure | Explore folder structure, design patterns, tech stack; output to `exploration.findings.architecture` |
| **explore-feature** | Find similar features | Feature objective, source code | Search for similar features, analyze patterns, identify reusable components; output to `exploration.findings.features` |
| **explore-dependency** | Analyze module coupling | Package manifests, import patterns | Map import graph, coupling points, external deps, flag risks; output to `exploration.findings.dependencies` |
| **explore-test** | Survey test infrastructure | Test directories, config files | Locate test dirs, frameworks, coverage patterns, conventions; output to `exploration.findings.tests` |
| **explore-synthesis** | Consolidate findings | All exploration findings | Synthesize findings from all explorers into actionable recommendations; output to `exploration_summary` |

---

## Build Category

**Purpose**: Implementation of code changes and new functionality
**Boundaries**: Build agents implement; they do not plan, test, or clean

### Build Agents

| Subtype | Role | Inputs | Scope (in-scope work only) |
|---------|------|--------|----------------------------|
| **build-python** | Implement Python code | Live Plan items, architecture, existing code | Build components, verify compilation (`py_compile`), run static analysis, execute from entrypoint |
| **build-flutter** | Implement Flutter code | Live Plan items, architecture, Flutter patterns | Build components, run `flutter pub get`, verify with `dart analyze` |

---

## Test Category

**Purpose**: Validation through testing and quality assurance
**Boundaries**: Test agents validate; they do not fix or implement (except test-builder writes tests)

### Test Agents

| Subtype | Role | Inputs | Scope (in-scope work only) |
|---------|------|--------|----------------------------|
| **test-builder** | Create and execute Python tests | Plan directives, code under test, test patterns | Write pytest tests (unit/integration/E2E), execute via pytest, capture results |
| **test-audit** | Review test quality | Assigned test package, test results XML, source code | Audit for silent failures, reward hacking, unjustified skips; flag gaps, no fixes |
| **test-uat** | Simulate user acceptance journeys | User story, README/architecture docs only | Execute actual commands in local + Docker; report pass/fail per step; reject excessive context |
| **trace-explorer** | Analyze execution traces | Execution logs, tmux output, agent trace data | Inspect trace data to identify failures, gaps, and anomalies; produce friction reports |

---

## Cleaner Category

**Purpose**: Safe removal of dead code and redundant content
**Boundaries**: Cleaner agents remove; they do not add new code or fix issues

### Cleaner Agents

| Subtype | Role | Inputs | Scope (in-scope work only) |
|---------|------|--------|----------------------------|
| **cleaner-core** | Identify and remove (non-voting) | Codebase, manifest, preserved_files patterns | Identify cleanup targets AND remove immediately; checkpoint commits; conservative approach |
| **cleaner-identify** | Vote on cleanup targets | Codebase, manifest, preserved_files patterns | Identify candidates with confidence scores (3-5); no deletions; output to `cleaner_voting.identification_results` |
| **cleaner-execute** | Remove approved items | Approved targets (3/3 votes), preserved_files | Remove ONLY unanimous targets; checkpoint commit; verify no import/syntax errors; revert on failure |

---

## Deploy Category

**Purpose**: Packaging, CI/CD, and infrastructure management
**Boundaries**: Deploy agents deploy; they do not write application code

### Deploy Agents

| Subtype | Role | Inputs | Scope (in-scope work only) |
|---------|------|--------|----------------------------|
| **deploy-packaging** | Rebuild and install packages | Build config, pyproject.toml, CLI scripts | Build wheels/sdists, reinstall CLI tools, verify PATH and imports; participates in test-fix-loop |
| **deploy-cicd** | Sync CI/CD infrastructure | cloudbuild.yaml, Dockerfile.test, pytest.ini, docker-compose | Audit CI config vs test structure, validate Dockerfile, report drift; participates in test-fix-loop |
| **deploy-worktree** | Create git worktrees | Worktree specs, branch strategy | Create worktrees, update VS Code workspace file; setup task only |

---

## Documentation Category

**Purpose**: Maintain minimal, accurate documentation
**Boundaries**: Documentation agents document; they do not change code behavior

### Documentation Agent

| Subtype | Role | Inputs | Scope (in-scope work only) |
|---------|------|--------|----------------------------|
| **documentation-core** | Maintain minimal docs | Existing docs, source code, doc scope definition | Remove verbose/redundant docs, update outdated, fill gaps; no new files unless explicit; participates in documentation-loop |

---

## Teacher Category

**Purpose**: Build paths, fences, and signposts for agents
**Boundaries**: Teacher agents guide; they improve agent guidance, not application code

### Teacher Agents

| Subtype | Role | Inputs | Scope (in-scope work only) |
|---------|------|--------|----------------------------|
| **teacher-plan** | Plan guidance improvements | Target agents, observed failures, process files | Map current path, build minimal verifiable plan (3-7 items); meta-level, not in iteration loops |
| **teacher-update-guidance** | Update process and input guidance | Agent logs, friction patterns, process files, inputs.yml files | Identify friction, generate prioritized recommendations, update process.yml and inputs.yml files with instructions/examples; has authority for cross-agent scope updates; meta-level |
| **teacher-update-assets** | Update shared assets | Asset type, existing assets, manifests | Add/update definitions, guidelines, examples in `modules/AgenticGuidance/assets/`; update shared inputs.yml entries (used by 2+ agents); ensure multi-agent reuse; update indexes |

---

## Orchestration Category

**Purpose**: Coordinate agent execution and manage workflows
**Boundaries**: Orchestration agents coordinate; they delegate work to specialist agents

### Orchestration Agents

| Subtype | Role | Inputs | Scope (in-scope work only) |
|---------|------|--------|----------------------------|
| **orchestrator** | Route and coordinate tasks | User objectives, agent manifest, live plans | Route tasks to appropriate agents, manage execution flow, handle escalations; coordinate workflow but delegate implementation |
