# Epic: Tmux-Based Orchestration Spawning

## Problem

The `ExecutionRunner` in `orchestration.py` spawns agent sessions via `subprocess.run(["agentic", "session", "spawn", ...])`, which itself calls `subprocess.Popen(["claude", ...])`. This creates a subprocess-within-subprocess chain with these issues:

1. **CLAUDECODE env inheritance** — Running inside Claude Code means `CLAUDECODE=1` is inherited by child processes, triggering the nested session guard. We work around this with `get_clean_env()` stripping the variable, but it's fragile.
2. **No live observability** — Once a phase agent is spawned, you can only poll `StateStore` or read log files. No way to "step into" a running agent session.
3. **No interactive debugging** — If an agent gets stuck or needs intervention, there's no way to interact with it.

## Solution

Replace subprocess-based spawning in `ExecutionRunner` with tmux-based spawning via the existing `AgenticTmux` module (`SessionService`). Each phase agent gets its own tmux window/pane, providing:

- **Natural env isolation** — tmux sessions don't inherit `CLAUDECODE` from the parent, eliminating the need for `get_clean_env()` workarounds.
- **Live observability** — `tmux attach` to watch any agent in real-time.
- **Interactive debugging** — Attach to a tmux pane to inspect or intervene with a running agent.
- **Parallel execution potential** — Multiple tmux panes can run agents concurrently (future enhancement).

## Scope

### In Scope
- Modify `ExecutionRunner._run_phase()` to spawn agent sessions via tmux instead of `subprocess.run()`
- Use `AgenticTmux.SessionService` to create tmux sessions/windows for each phase
- Maintain the existing `StateStore`-based completion polling (tmux is just the execution container)
- Update `cmd_spawn` in session.py to support a `--tmux` flag for tmux-based spawning
- Ensure the `agentic session spawn` command works correctly when run inside a tmux pane
- Update session status tracking to work with tmux-based sessions

### Out of Scope
- SDK-based spawning (separate concern, can coexist)
- Parallel phase execution (future enhancement, tmux enables it but don't implement yet)
- Tmux UI/dashboard for monitoring all agents (future enhancement)

## Key Files
- `modules/AgenticCLI/src/agenticcli/workflows/orchestration.py` — ExecutionRunner._run_phase()
- `modules/AgenticCLI/src/agenticcli/commands/session.py` — cmd_spawn()
- `modules/AgenticTmux/src/agentictmux/services/session.py` — SessionService
- `modules/AgenticCLI/src/agenticcli/utils/subprocess_utils.py` — get_clean_env()

## Success Criteria
- ExecutionRunner spawns agents in tmux sessions instead of bare subprocesses
- `tmux attach -t <session>` allows live observation of running agents
- Completion detection still works (StateStore polling or tmux session exit detection)
- CLAUDECODE workaround no longer needed for tmux-spawned sessions
- Existing orchestration flow (planning, executing) works end-to-end with tmux spawning
