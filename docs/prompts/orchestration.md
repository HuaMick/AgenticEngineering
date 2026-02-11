You are running an orchestration loop across live plans.

## IMMEDIATE ACTIONS (no exploration needed)
1. Health check: `agentic --version && agentic plan list`
2. Get JSON state: `agentic --json plan list`
3. Get current task: `agentic --json plan task current`

## HOUSEKEEPING (before any execution)
1. For plans with _template_status: stub files, delete them (they inflate task counts)
2. Archive plans at 100% completion: `agentic plan move folder --plan <folder> --force`

## DISCOVERY (should take <2 minutes)
For each live plan, check: `ls docs/plans/live/<folder>/orchestration_*.mmd`
Classify:
- 100% complete → Archive: `agentic plan move folder --plan <folder> --force`
- Has MMD → EXECUTE
- No MMD → Generate MMD (write it directly, or use `agentic session spawn --role planner-orchestration --plan <folder> -b`)

## EXECUTE (use CLI sessions, NOT inline Task tool)
For each plan with an MMD:
1. Read the MMD, extract AGENT_ROUTING
2. **QUESTION GATE (MANDATORY)**: Before spawning ANY task for this plan:
   `agentic question list --plan <folder>`
   - If pending questions exist: **DO NOT** spawn tasks for this plan
   - Log: "Plan <folder> paused: N pending questions"
   - Show the question IDs and texts
   - Continue to next plan (don't block entire loop)
   - Re-check after questions are answered
3. Spawn remote session per plan:
   `agentic session spawn --role <agent> --plan <folder> -b --dangerously-skip-permissions`
   For task-level parallelism (non-overlapping target_files):
   `agentic session spawn --task <task_id> --plan <folder> -b --dangerously-skip-permissions`
   **NOTE**: `--role` and `--task` are mutually exclusive. Use `--task` for task-level spawns (role is inferred from the task's agent field).
4. Monitor: `agentic session list` (shows active sessions by default; use `--all` for completed too)
5. Track: `agentic plan task start/complete <id> --plan <folder>`
6. Check for blocked questions (safety check): `agentic question list --plan <folder>`
   The question gate in step 2 should prevent reaching here with pending questions, but this remains as a safety net to catch questions raised mid-execution by spawned agents.
7. Archive when done: `agentic plan move folder --plan <folder> --force`

## PARALLELISM
- Guidance-only plans (teacher-update-guidance): safe to run in parallel
- CLI build plans (build-python): run sequentially (shared files)
- Typer migration: run LAST (rewrites cli.py)

## CLI FLAG REMINDER
- `--json` is a ROOT-LEVEL flag: `agentic --json plan list` (not `agentic plan list -j`)

## HITL (Human-in-the-Loop) QUESTIONS
If a spawned agent creates a blocking question:
1. Check: `agentic question list --plan <folder>`
2. Show detail: `agentic question show <question_id> --plan <folder>`
3. Answer or defer: `agentic question answer <question_id> --text "answer"` / `agentic question defer <question_id>`
4. Foreground watcher: `agentic question watch --plan <folder>`
5. Background daemon: `agentic question watch-daemon --plan <folder>` (stop with `agentic question watch-stop`)
6. ntfy push notifications: If configured (`agentic preferences get ntfy.topic`), questions auto-notify to phone. Users can reply via ntfy to auto-answer questions.

## USEFUL PLAN COMMANDS
- `agentic plan task current --plan <folder>` — Get next task to work on
- `agentic plan task list --plan <folder>` — Show all tasks with status
- `agentic plan phase list --plan <folder>` — List all phases
- `agentic plan orchestration generate --plan <folder>` — Generate MMD from plan YAML
- `agentic plan orchestration validate --plan <folder>` — Validate MMD against plan
- `agentic plan unarchive --plan <folder>` — Restore archived plan to live
- `agentic context bootstrap --role <role>` — Get seed context for an agent role

## DOGFOOD RULE — CLI Error Recovery Protocol

**CRITICAL: When any CLI issue is encountered during orchestration, you MUST follow this protocol. Do NOT work around CLI errors manually.**

### Trigger Conditions
Any of these MUST trigger the protocol:
- Session spawn fails (`agentic session spawn` returns error)
- Plan commands error (`agentic plan task start/complete` fails)
- Task resolution fails (task_id not found, wrong field names)
- Import/syntax errors in CLI modules
- Any `agentic` command exits non-zero

### Mandatory Recovery Steps

**Step 1: Diagnose** — Capture the exact error output
```bash
agentic --json plan list   # Verify CLI is responsive
agentic --version          # Check basic health
```

**Step 2: Create a remediation plan** — Use `agentic plan init` with a descriptive name
```bash
agentic plan init <branch> --description 'fix: <describe the CLI issue>'
```
This creates a properly named plan folder in `docs/plans/live/`.

**Step 3: Plan the fix** — Spawn a planner-build session to design the remediation
```bash
agentic session spawn --role planner-build --plan <new-plan-folder> -b --dangerously-skip-permissions
```
Wait for the planner to produce a `plan_build.yml` with phases and tasks.

**Step 4: Execute the fix** — Spawn build-python sessions to implement
```bash
agentic session spawn --role build-python --plan <new-plan-folder> -b --dangerously-skip-permissions
```

**Step 5: Verify** — Confirm the CLI issue is resolved
```bash
agentic --version && agentic plan list
cd /home/code/AgenticEngineering/modules/AgenticCLI && python3 -m pytest tests/ -x -v
```

**Step 6: Resume orchestration** — Return to the original plan and continue from where you left off.

### Common CLI Pitfalls

| Pitfall | Wrong | Right |
|---------|-------|-------|
| `--json` flag position | `agentic plan list -j` | `agentic --json plan list` |
| Plan file naming | `plan.yml`, `build.yml` | `plan_build.yml`, `plan_test.yml`, `plan_teach.yml` |
| Task ID field | `id: P1-T1` in some contexts | Use `task_id` — check plan YAML for actual field name |
| `--role` vs `--task` | `--role build-python --task P1-T1` | Use ONE: `--role` OR `--task` (mutually exclusive) |
| Plan folder path | `260210OP_my_plan` (bare name) | `docs/plans/live/260210OP_my_plan` (full path for `ls`, bare name for `--plan`) |
| Manual plan edits | Editing `plan_build.yml` status fields directly | `agentic plan task start/complete <id> --plan <folder>` |

### FENCE
- You MUST NOT skip any step in this protocol
- You MUST NOT continue orchestration while CLI is broken
- You MUST NOT manually work around CLI errors (e.g., editing YAML directly)
- The CLI is the source of truth — if it's broken, fix it FIRST

Begin.
