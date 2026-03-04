# CLI Restructure Migration Map

> Generated for plan: 260220NE_restructure_cli_into_user_facing_and_agent_facing
> Source: modules/AgenticCLI/src/agenticcli/cli.py + commands/*.py

## Overview

Split 83+ CLI commands into two tiers:
- **Tier 1 (User-Facing)**: Clean, minimal commands humans type daily
- **Tier 2 (Agent-Facing)**: Hidden `agentic agent` namespace for agent plumbing

All old paths remain functional via hidden aliases for backward compatibility.

---

## Tier 1: User-Facing Commands (Stay Visible)

These commands remain at their current paths and are visible in `agentic --help`.

### `agentic setup` (no change)
| Current Path | Target Path | Rationale |
|---|---|---|
| `agentic setup init` | `agentic setup init` | User onboarding |
| `agentic setup health` | `agentic setup health` | User health check |
| `agentic setup update` | `agentic setup update` | User self-update |
| `agentic setup rebuild` | `agentic setup rebuild` | User rebuild |

### `agentic configure` / `cfg` (no change)
| Current Path | Target Path | Rationale |
|---|---|---|
| `agentic configure preferences get` | no change | User preference mgmt |
| `agentic configure preferences set` | no change | User preference mgmt |
| `agentic configure preferences list` | no change | User preference mgmt |
| `agentic configure preferences delete` | no change | User preference mgmt |
| `agentic configure preferences clear` | no change | User preference mgmt |
| `agentic configure config show` | no change | User config mgmt |
| `agentic configure config init` | no change | User config mgmt |
| `agentic configure config get` | no change | User config mgmt |
| `agentic configure config set` | no change | User config mgmt |
| `agentic configure config list` | no change | User config mgmt |
| `agentic configure config delete` | no change | User config mgmt |
| `agentic configure config show-path` | no change | User config mgmt |
| `agentic configure config set-path` | no change | User config mgmt |
| `agentic configure config clear` | no change | User config mgmt |
| `agentic configure state list` | no change | User state inspection |
| `agentic configure state show` | no change | User state inspection |
| `agentic configure state clear` | no change | User state mgmt |
| `agentic configure state cleanup` | no change | User state mgmt |
| `agentic configure env show` | no change | User env inspection |
| `agentic configure env export` | no change | User env export |
| `agentic configure env run` | no change | User env execution |

### `agentic session` (no change)
| Current Path | Target Path | Rationale |
|---|---|---|
| `agentic session spawn` | no change | User launches sessions |
| `agentic session list` | no change | User monitors sessions |
| `agentic session stop` | no change | User stops sessions |
| `agentic session status` | no change | User checks sessions |
| `agentic session health` | no change | User monitors health |
| `agentic session logs` | no change | User views logs |
| `agentic session dashboard` | no change | User live dashboard |
| `agentic session orchestrate` | no change | User orchestration |
| `agentic session ralph start` | no change | User Ralph loop |
| `agentic session ralph stop` | no change | User Ralph loop |
| `agentic session ralph status` | no change | User Ralph loop |
| `agentic session ralph next` | no change | User Ralph loop |
| `agentic session ralph history` | no change | User Ralph loop |
| `agentic session terminal serve` | no change | User web terminal |
| `agentic session loop start` | no change | User loop mgmt |
| `agentic session loop stop` | no change | User loop mgmt |
| `agentic session loop status` | no change | User loop mgmt |
| `agentic session loop history` | no change | User loop mgmt |
| `agentic session planner start` | no change | User planner loop |
| `agentic session planner stop` | no change | User planner loop |
| `agentic session planner status` | no change | User planner loop |

### `agentic plan` (TRIMMED - agent plumbing moves out)
| Current Path | Target Path | Rationale |
|---|---|---|
| `agentic plan new` | no change | User creates plans |
| `agentic plan list` | no change | User views plans |
| `agentic plan status` | no change | User checks plan status |
| `agentic plan cancel` | **NEW** | User cancels plans |

### `agentic question` (TRIMMED - agent plumbing moves out)
| Current Path | Target Path | Rationale |
|---|---|---|
| `agentic question list` | no change | User views questions |
| `agentic question show` | no change | User views question |
| `agentic question answer` | no change | User answers questions |
| `agentic question dashboard` | no change | User live dashboard |

### `agentic langsmith` / `ls` (no change)
| Current Path | Target Path | Rationale |
|---|---|---|
| `agentic langsmith runs` | no change | User/analyst trace review |
| `agentic langsmith run` | no change | User/analyst trace review |
| `agentic langsmith projects` | no change | User/analyst project list |
| `agentic langsmith stats` | no change | User/analyst stats |
| `agentic langsmith friction` | no change | User/analyst friction |
| `agentic langsmith sessions` | no change | User/analyst sessions |

### `agentic devops` (no change)
| Current Path | Target Path | Rationale |
|---|---|---|
| `agentic devops worktree create` | no change | User creates worktrees |
| `agentic devops worktree list` | no change | User views worktrees |
| `agentic devops worktree remove` | no change | User removes worktrees |
| `agentic devops worktree status` | no change | User checks worktrees |
| `agentic devops worktree validate` | no change | User validates worktrees |
| `agentic devops worktree sync` | no change | User syncs worktrees |

---

## Tier 2: Agent-Facing Commands (Move to `agentic agent`)

These commands get duplicated under `agentic agent ...` (new canonical path) and
their original paths become hidden aliases for backward compatibility.

### `agentic agent plan task` (from `agentic plan task`)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic plan task start <id>` | `agentic agent plan task start <id>` | Copy + hide original | 25 agent .md files, .agent/instructions.md, agents.md |
| `agentic plan task complete <id>` | `agentic agent plan task complete <id>` | Copy + hide original | 25 agent .md files, .agent/instructions.md, agents.md |
| `agentic plan task prefill` | `agentic agent plan task prefill` | Copy + hide original | orchestration agents |
| `agentic plan task list` | `agentic agent plan task list` | Copy + hide original | 25 agent .md files, agents.md |
| `agentic plan task status <id>` | `agentic agent plan task status <id>` | Copy + hide original | agents.md |
| `agentic plan task add` | `agentic agent plan task add` | Copy + hide original | orchestration agents, .agent/instructions.md |
| `agentic plan task update <id>` | `agentic agent plan task update <id>` | Copy + hide original | 25 agent .md files |
| `agentic plan task current` | `agentic agent plan task current` | Copy + hide original | 25 agent .md files, agents.md |

### `agentic agent plan phase` (from `agentic plan phase`)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic plan phase add` | `agentic agent plan phase add` | Copy + hide original | orchestration-planning.md, .agent/instructions.md |
| `agentic plan phase list` | `agentic agent plan phase list` | Copy + hide original | planner agents |
| `agentic plan phase update <id>` | `agentic agent plan phase update <id>` | Copy + hide original | planner agents |

### `agentic agent plan` (direct commands, from `agentic plan`)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic plan init <branch>` | `agentic agent plan init <branch>` | Copy + hide original | deploy-worktree.md, orchestration-planning.md, .agent/instructions.md |
| `agentic plan bootstrap <branch>` | `agentic agent plan bootstrap <branch>` | Copy + hide original | orchestration agents, agents.md |
| `agentic plan scaffold <name>` | `agentic agent plan scaffold <name>` | Copy + hide original | deploy-worktree.md, planner agents |
| `agentic plan validate` | `agentic agent plan validate` | Copy + hide original | planner agents, orchestration agents |
| `agentic plan archive` | `agentic agent plan archive` | Copy + hide original | planner-cleaning.md, agents.md |
| `agentic plan unarchive` | `agentic agent plan unarchive` | Copy + hide original | agents.md |

### `agentic agent plan move` (from `agentic plan move`)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic plan move task <id>` | `agentic agent plan move task <id>` | Copy + hide original | planner-cleaning.md |
| `agentic plan move tasks` | `agentic agent plan move tasks` | Copy + hide original | planner-cleaning.md |
| `agentic plan move folder` | `agentic agent plan move folder` | Copy + hide original | planner-cleaning.md |

### `agentic agent plan orchestration` (from `agentic plan orchestration`)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic plan orchestration generate` | `agentic agent plan orchestration generate` | Copy + hide original | planner-orchestration.md, orchestration agents |
| `agentic plan orchestration validate` | `agentic agent plan orchestration validate` | Copy + hide original | planner-orchestration.md |

### `agentic agent plan stories` (from `agentic plan stories`)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic plan stories list` | `agentic agent plan stories list` | Copy + hide original | test-user-simulator.md |
| `agentic plan stories test` | `agentic agent plan stories test` | Copy + hide original | test-user-simulator.md |

### `agentic agent context` (from `agentic context` / `ctx`)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic context bootstrap` | `agentic agent context bootstrap` | Copy + hide group | ALL 25 agent .md files, .agent/instructions.md, agents.md, CCI_CONTEXT_ARCHITECTURE.md |
| `agentic context role <id>` | `agentic agent context role <id>` | Copy + hide group | agents.md, CCI_CONTEXT_ARCHITECTURE.md |
| `agentic context task` | `agentic agent context task` | Copy + hide group | agents.md, CCI_CONTEXT_ARCHITECTURE.md |
| `agentic context inputs` | `agentic agent context inputs` | Copy + hide group | CCI_CONTEXT_ARCHITECTURE.md |
| `agentic context generate-agent <id>` | `agentic agent context generate-agent <id>` | Copy + hide group | CCI_CONTEXT_ARCHITECTURE.md |

### `agentic agent entrypoint` (from `agentic entrypoint` / `ep`)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic entrypoint list` | `agentic agent entrypoint list` | Copy + hide group | agents.md, CCI_CONTEXT_ARCHITECTURE.md |
| `agentic entrypoint show <name>` | `agentic agent entrypoint show <name>` | Copy + hide group | agents.md |
| `agentic entrypoint execute <name>` | `agentic agent entrypoint execute <name>` | Copy + hide group | agents.md, CCI_CONTEXT_ARCHITECTURE.md |

### `agentic agent manifest` (from `agentic manifest` / `mf`)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic manifest show <path>` | `agentic agent manifest show <path>` | Copy + hide group | agents.md |
| `agentic manifest list` | `agentic agent manifest list` | Copy + hide group | agents.md |
| `agentic manifest validate <path>` | `agentic agent manifest validate <path>` | Copy + hide group | agents.md |

### `agentic agent stories` (from `agentic stories` / `st`)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic stories find` | `agentic agent stories find` | Copy + hide group | .agent/instructions.md, agents.md |
| `agentic stories init <id>` | `agentic agent stories init <id>` | Copy + hide group | agents.md |
| `agentic stories cat <id>` | `agentic agent stories cat <id>` | Copy + hide group | agents.md |
| `agentic stories status <id>` | `agentic agent stories status <id>` | Copy + hide group | agents.md |
| `agentic stories update <id>` | `agentic agent stories update <id>` | Copy + hide group | agents.md |
| `agentic stories report` | `agentic agent stories report` | Copy + hide group | agents.md |
| `agentic stories untested` | `agentic agent stories untested` | Copy + hide group | agents.md |
| `agentic stories batch-update` | `agentic agent stories batch-update` | Copy + hide group | agents.md |
| `agentic stories affected` | `agentic agent stories affected` | Copy + hide group | agents.md |

### `agentic agent question` (from `agentic question` - plumbing only)
| Current Path | Target Path | Action | Referencing Files |
|---|---|---|---|
| `agentic question ask` | `agentic agent question ask` | Copy + hide on question_app | .agent/instructions.md, agents.md, orchestration agents |
| `agentic question defer <id>` | `agentic agent question defer <id>` | Copy + hide on question_app | agents.md |
| `agentic question watch` | `agentic agent question watch` | Copy + hide on question_app | agents.md |
| `agentic question watch-daemon` | `agentic agent question watch-daemon` | Copy + hide on question_app | agents.md |
| `agentic question watch-stop` | `agentic agent question watch-stop` | Copy + hide on question_app | agents.md |

---

## Target Help Output After Migration

### `agentic --help` (visible groups only)
```
Commands:
  setup       Initial setup and health checks
  configure   Configuration management (alias: cfg)
  session     Session management
  plan        Plan management
  question    Question queue
  langsmith   LangSmith integration (alias: ls)
  devops      DevOps workflows
```

Hidden (still functional): agent, context, ctx, entrypoint, ep, manifest, mf, stories, st

### `agentic plan --help` (visible commands only)
```
Commands:
  new       Create plan and spawn planner agent
  list      List all plans
  status    Show plan status
  cancel    Cancel a plan (NEW)
```

Hidden (still functional): init, bootstrap, scaffold, validate, archive, unarchive, task, phase, move, orchestration, stories

### `agentic question --help` (visible commands only)
```
Commands:
  list        List questions
  show        Show question details
  answer      Answer a question
  dashboard   Live question dashboard
```

Hidden (still functional): ask, defer, watch, watch-daemon, watch-stop

### `agentic agent --help` (hidden from main, visible when called directly)
```
Commands:
  plan        Plan management plumbing
  context     CCI context retrieval
  entrypoint  Workflow entrypoints
  manifest    Agent manifests
  stories     User story management
  question    Question queue plumbing
```

---

## Files That Reference CLI Commands (Update in P06)

### Critical Files (must update)

| File | Commands Referenced |
|---|---|
| `.agent/instructions.md` | plan init, plan phase add, plan validate, stories find, context bootstrap, question ask, session spawn |
| `agents.md` | ALL commands - master routing table |
| `docs/CCI_CONTEXT_ARCHITECTURE.md` | context bootstrap/role/task/inputs/generate-agent |

### Agent Instruction Files (25 files in `.claude/agents/`)

All use this universal pattern:
```bash
agentic context bootstrap --role <role> -j    # -> agentic agent context bootstrap
agentic plan task current -j                  # -> agentic agent plan task current
agentic plan task update <id> --status <s>    # -> agentic agent plan task update
```

Files: build-python.md, build-flutter.md, deploy-cicd.md, deploy-worktree.md,
orchestration-executor.md, orchestration-planning.md, planner-build.md,
planner-test.md, planner-guidance.md, planner-cleaning.md, planner-audit.md,
planner-reviewer.md, planner-orchestration.md, planner-guidance-testing.md,
test-runner.md, test-builder.md, test-service.md, test-audit.md,
test-final-output.md, test-guidance-simulator.md, test-user-simulator.md,
teacher-update-guidance.md, teacher-update-assets.md, teacher-trace-diagnostics.md,
orchestration-friction.md

### Orchestration Prompts

| File | Commands Referenced |
|---|---|
| `docs/prompts/orchestration_planner.md` | plan init, plan task, session spawn |
| `docs/prompts/orchestration_executor.md` | plan task, session spawn |
| `docs/prompts/friction_analysis.md` | langsmith friction |

### CLI Documentation

| File | Commands Referenced |
|---|---|
| `modules/AgenticCLI/README.md` | ALL commands - primary docs (update optional, low priority) |

---

## Command Statistics

| Category | Count |
|---|---|
| Total commands | 83+ |
| Tier 1 (user-facing, visible) | 61 |
| Tier 2 (agent-facing, move to `agentic agent`) | 44 |
| New commands | 1 (`plan cancel`) |
| Hidden aliases created | 44 (all migrated commands keep old paths) |
| Files requiring update (P06) | ~30 |

## GLOBAL_COMMANDS / PROJECT_COMMANDS Impact

Current sets in cli.py:
- `GLOBAL_COMMANDS`: setup, configure, cfg, session, langsmith, ls, question
- `PROJECT_COMMANDS`: devops, plan, stories, st, manifest, mf, context, ctx, entrypoint, ep

After restructure, `PROJECT_COMMANDS` additions needed:
- Add `agent` to `PROJECT_COMMANDS` (since agent sub-commands need project context)

The hidden aliases (stories, manifest, context, entrypoint, etc.) stay in PROJECT_COMMANDS
since they still need project context validation when invoked via old paths.
