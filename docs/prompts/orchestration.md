You are running an orchestration loop across live plans.

## IMMEDIATE ACTIONS (no exploration needed)
1. Health check: `agentic --version && agentic plan list`
2. Get JSON state: `agentic --json plan list`

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
2. Spawn remote session per plan:
   `agentic session spawn --role <agent> --plan <folder> -b --dangerously-skip-permissions`
3. Monitor: `agentic session list --active`
4. Track: `agentic plan task start/complete <id> --plan <folder>`
5. Archive when done: `agentic plan move folder --plan <folder> --force`

## PARALLELISM
- Guidance-only plans (teacher-update-guidance): safe to run in parallel
- CLI build plans (build-python): run sequentially (shared files)
- Typer migration: run LAST (rewrites cli.py)

## CLI FLAG REMINDER
- `--json` is a ROOT-LEVEL flag: `agentic --json plan list` (not `agentic plan list -j`)

## DOGFOOD RULE
If you hit a gap (missing CLI command, broken service, etc.):
1. Check: `agentic --json plan list`
2. Create plan if needed: `agentic plan init <name>`
3. Spawn fix: `agentic session spawn --role build-python --plan <folder> -b`
4. Resume after gap is closed.

Begin.
