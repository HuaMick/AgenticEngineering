# Plan Creation Tutorial

Step-by-step guide for creating plans using only CLI commands. This tutorial demonstrates how to build a complete plan without manually editing YAML or MMD files.

## Prerequisites

- AgenticCLI installed (`uv pip install -e .` from modules/AgenticCLI)
- In a git repository with access to the main worktree

## Quick Start

Create a plan in 5 commands:

```bash
# 1. Initialize worktree and plan folder
agentic plan init my-feature --description "add_new_feature"

# 2. Generate build plan with objective and phases
agentic template generate build \
  --output docs/plans/live/260128AB_add_new_feature/plan_build.yml \
  --objective "Implement the new feature" \
  --phases "P1:Implementation,P2:Testing,P3:Docs"

# 3. Add tasks to phases
agentic plan task add "Build core functionality" --phase P1

# 4. Generate orchestration MMD
agentic plan orchestration generate --plan docs/plans/live/260128AB_add_new_feature

# 5. Validate the plan
agentic plan validate docs/plans/live/260128AB_add_new_feature
```

---

## Detailed Walkthrough

### Step 1: Initialize Plan with Worktree

The `plan init` command creates both a git worktree (for code changes) and a plan folder (for tracking progress).

```bash
agentic plan init feature-auth --description "user_authentication" --base main
```

**What this does:**
1. Creates worktree at `../YourRepo-feature-auth`
2. Generates plan folder name: `YYMMDDXX_user_authentication`
3. Creates plan folder in main worktree: `docs/plans/live/260128AA_user_authentication/`
4. Scaffolds initial file structure

**Flags:**
- `--description`: Brief snake_case description (becomes part of folder name)
- `--base`: Base branch to branch from (default: main)

**Output example:**
```
Creating worktree for branch 'feature-auth' at /home/code/YourRepo-feature-auth
  Created worktree at /home/code/YourRepo-feature-auth
  Created plan folder at docs/plans/live/260128AA_user_authentication/

Plan initialized: 260128AA_user_authentication
Execution worktree: /home/code/YourRepo-feature-auth
Plan folder: /home/code/YourRepo/docs/plans/live/260128AA_user_authentication
```

---

### Step 2: Generate Build Plan from Template

Use the template generator to create a pre-filled plan YAML file.

```bash
agentic template generate build \
  --output docs/plans/live/260128AA_user_authentication/plan_build.yml \
  --objective "Implement OAuth2 authentication with Google and GitHub providers" \
  --phases "P1:OAuth Setup,P2:Google Provider,P3:GitHub Provider,P4:Testing" \
  --success-criteria "OAuth flow works,Unit tests pass,Integration tests pass"
```

**Flags explained:**
- `--output`, `-o`: Write to file instead of stdout
- `--objective`: Plan objective (inserted into YAML)
- `--phases`: Comma-separated list of `ID:Name` pairs
- `--success-criteria`: Comma-separated success criteria

**Template types available:**
```bash
agentic template list
```
| Type | Description |
|------|-------------|
| `build` | Implementation plan with phased tasks |
| `test` | Test plan with unit, integration, e2e phases |
| `cleanup` | Audit and cleanup plan |
| `guidance` | Agent friction analysis plan |

**Generated YAML structure:**
```yaml
name: plan-build
status: active
objective: Implement OAuth2 authentication with Google and GitHub providers
success_criteria:
  - OAuth flow works
  - Unit tests pass
  - Integration tests pass
phases:
  - phase_id: P1
    name: OAuth Setup
    status: pending
    tasks: []
  - phase_id: P2
    name: Google Provider
    status: pending
    tasks: []
  # ... more phases
```

---

### Step 3: Add Phases (if needed)

If you need to add more phases after initial generation:

```bash
# Add a single phase
agentic plan phase add \
  --id P5 \
  --name "Documentation" \
  --description "Write user docs and API reference" \
  --plan docs/plans/live/260128AA_user_authentication

# List all phases
agentic plan phase list --plan docs/plans/live/260128AA_user_authentication
```

**Output from phase list:**
```
Phases for 260128AA_user_authentication

  ID     Name              Status    Tasks
  ----   ---------------   -------   -----
  P1     OAuth Setup       pending   0
  P2     Google Provider   pending   0
  P3     GitHub Provider   pending   0
  P4     Testing           pending   0
  P5     Documentation     pending   0
```

**Update phase status:**
```bash
agentic plan phase update P1 --status in_progress
agentic plan phase update P1 --name "OAuth2 Core Setup" --status completed
```

---

### Step 4: Add Tasks to Phases

Add individual tasks to specific phases:

```bash
# Add task to specific phase
agentic plan task add "Set up OAuth2 client credentials" \
  --phase P1 \
  --id AUTH-001 \
  --plan docs/plans/live/260128AA_user_authentication

# Add another task
agentic plan task add "Implement token refresh flow" \
  --phase P1 \
  --id AUTH-002 \
  --priority high

# Add tasks to other phases
agentic plan task add "Configure Google OAuth app" --phase P2 --id AUTH-003
agentic plan task add "Implement Google callback handler" --phase P2 --id AUTH-004
agentic plan task add "Write unit tests for token validation" --phase P4 --id AUTH-010
```

**Task add flags:**
- `--phase`, `-p`: Target phase ID
- `--id`: Custom task ID (auto-generated if omitted)
- `--priority`: Task priority (low, medium, high)
- `--plan`: Path to plan folder (auto-detected if omitted)

**List all tasks:**
```bash
agentic plan task list --plan docs/plans/live/260128AA_user_authentication
```

---

### Step 5: Generate Orchestration MMD

Generate a Mermaid flowchart that defines execution order and agent routing:

```bash
agentic plan orchestration generate \
  --plan docs/plans/live/260128AA_user_authentication
```

**What the generated MMD contains:**
- Phase nodes from YAML with task IDs
- Agent routing metadata (which agent handles each phase)
- Test-fix loop structures for test phases
- Feedback triggers for failures
- CLI commands in comments for agent execution

**Custom output filename:**
```bash
agentic plan orchestration generate \
  --output orchestration_auth.mmd \
  --force
```

**Sample generated MMD header:**
```mermaid
%% =============================================================================
%% ORCHESTRATION: User Authentication
%% =============================================================================
%% PLAN: 260128AA_user_authentication
%% OBJECTIVE: Implement OAuth2 authentication with Google and GitHub providers
%%
%% CLI BOOTSTRAP:
%%   agentic plan task current --plan docs/plans/live/260128AA_user_authentication
%%
%% PHASES:
%%   P1: OAuth Setup (AUTH-001..002)
%%   P2: Google Provider (AUTH-003..004)
%%   P3: GitHub Provider (...)
%%   P4: Testing (AUTH-010)
%%   P5: Documentation
%%
%% AGENT_ROUTING:
%%   P1 -> builder
%%   P2 -> builder
%%   P3 -> builder
%%   P4 -> test-builder
%%   P5 -> build-docs-writer
%% =============================================================================
```

---

### Step 6: Validate the Plan

Check that the plan folder structure is valid and MMD matches YAML:

```bash
agentic plan validate docs/plans/live/260128AA_user_authentication
```

**Validation checks:**
- Plan folder exists
- Required YAML files present
- YAML syntax valid
- Orchestration MMD exists
- MMD phases match YAML phases
- Task IDs referenced correctly

**Strict mode (treat warnings as errors):**
```bash
agentic plan validate docs/plans/live/260128AA_user_authentication --strict
```

**Sample output:**
```
Plan Validation: 260128AA_user_authentication

  Orchestration: orchestration_auth.mmd
  YAML Files: plan_build.yml, plan_completed.yml
  Phases: 5 (P1, P2, P3, P4, P5)
  Tasks: 5 total (5 pending)

  Orchestration Validation: PASS
    - Orchestration file: orchestration_auth.mmd
    - Phases found: 5
    - Tasks referenced: 5

  Status: PASS
```

---

### Step 7: Execute Tasks

Once the plan is ready, use task management commands during execution:

```bash
# Get current task to work on
agentic plan task current --plan docs/plans/live/260128AA_user_authentication

# Start a task (marks as in_progress)
agentic plan task start AUTH-001

# Complete a task (marks as completed)
agentic plan task complete AUTH-001

# Check overall status
agentic plan status docs/plans/live/260128AA_user_authentication
```

**Status output shows progress:**
```
Plan Status: 260128AA_user_authentication

  Orchestration: orchestration_auth.mmd
  Status: active
  Action Required: execute

  Files:
    File               Pending   In Progress   Completed
    ----               -------   -----------   ---------
    plan_build.yml     3         1             1

  Total: 3 pending, 1 in progress, 1 completed
  Progress: 20.0%

  Next Action: Execute current task
    Command: agentic plan task current --plan docs/plans/live/260128AA_user_authentication
```

---

## Complete Example: Creating a Bug Fix Plan

```bash
# 1. Initialize
agentic plan init fix-login-bug --description "fix_login_timeout"

# 2. Generate minimal plan
agentic template generate build \
  --output docs/plans/live/260128FX_fix_login_timeout/plan_build.yml \
  --objective "Fix login timeout error that occurs after 30 seconds" \
  --phases "P1:Investigate,P2:Fix,P3:Test" \
  --success-criteria "Login succeeds within 5s,No timeout errors in logs"

# 3. Add investigation tasks
agentic plan task add "Reproduce timeout error" --phase P1 --id FIX-001
agentic plan task add "Trace network requests" --phase P1 --id FIX-002

# 4. Add fix tasks
agentic plan task add "Increase timeout configuration" --phase P2 --id FIX-003
agentic plan task add "Add retry logic" --phase P2 --id FIX-004

# 5. Add test tasks
agentic plan task add "Unit test timeout handling" --phase P3 --id FIX-005
agentic plan task add "Integration test login flow" --phase P3 --id FIX-006

# 6. Generate orchestration
agentic plan orchestration generate --plan docs/plans/live/260128FX_fix_login_timeout

# 7. Validate
agentic plan validate docs/plans/live/260128FX_fix_login_timeout

# 8. Check status
agentic plan status docs/plans/live/260128FX_fix_login_timeout
```

---

## User Stories Management

Plans can include user stories for acceptance testing. List and generate test scenarios:

```bash
# List all user stories in the plan
agentic plan stories list --plan docs/plans/live/260128AA_user_authentication

# Generate blind test scenarios
agentic plan stories test \
  --plan docs/plans/live/260128AA_user_authentication \
  --output tests/story_tests.yml \
  --format yaml
```

---

## Archiving Completed Plans

When all tasks are complete:

```bash
# Move completed tasks to plan_completed.yml
agentic plan move tasks --plan docs/plans/live/260128AA_user_authentication

# Archive the entire plan folder
agentic plan archive docs/plans/live/260128AA_user_authentication
```

---

## JSON Output Mode

All commands support JSON output for scripting:

```bash
# Get status as JSON
agentic -j plan status docs/plans/live/260128AA_user_authentication

# List phases as JSON
agentic -j plan phase list --plan docs/plans/live/260128AA_user_authentication

# Validate and get JSON result
agentic -j plan validate docs/plans/live/260128AA_user_authentication
```

---

## Command Reference

| Command | Description |
|---------|-------------|
| `agentic plan init <branch>` | Initialize worktree + plan folder |
| `agentic plan scaffold <name>` | Create plan folder only |
| `agentic template generate <type>` | Generate plan from template |
| `agentic plan phase add` | Add phase to plan |
| `agentic plan phase list` | List all phases |
| `agentic plan phase update` | Update phase status/name |
| `agentic plan task add` | Add task to phase |
| `agentic plan task list` | List all tasks |
| `agentic plan task start` | Mark task in_progress |
| `agentic plan task complete` | Mark task completed |
| `agentic plan task current` | Show current task |
| `agentic plan orchestration generate` | Generate MMD from YAML |
| `agentic plan orchestration validate` | Validate MMD matches YAML |
| `agentic plan status` | Show plan status |
| `agentic plan validate` | Validate plan structure |
| `agentic plan stories list` | List user stories |
| `agentic plan stories test` | Generate test scenarios |
| `agentic plan move tasks` | Move completed tasks |
| `agentic plan archive` | Archive plan folder |

---

## Tips

1. **Auto-detection**: Most commands auto-detect the plan folder if you're inside it or in the repo root.

2. **Naming convention**: Plan folders follow `YYMMDDXX_description` format. The CLI generates this automatically.

3. **Orchestration first**: Generate the orchestration MMD before executing tasks. It defines the execution flow.

4. **Validate often**: Run `plan validate` after making changes to catch issues early.

5. **JSON for scripting**: Use `-j` flag when building automation around the CLI.

---

*Part of [AgenticCLI](../../README.md)*
