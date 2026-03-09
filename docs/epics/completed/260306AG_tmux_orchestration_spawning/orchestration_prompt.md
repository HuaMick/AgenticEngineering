# Tmux Orchestration Migration — Build Prompt

## Mission

Replace all subprocess-based agent spawning in the orchestration system with tmux-based spawning. This is the critical fix that unblocks the entire agentic system from running inside Claude Code sessions.

## The Problem

When any `agentic session orchestrate` command runs inside a Claude Code session, spawned agents fail with:
```
Error: Claude Code cannot be launched inside another Claude Code session.
```

The current subprocess chain (`agentic session spawn` → `subprocess.Popen(["claude", ...])`) inherits `CLAUDECODE=1` from the parent environment. We've been patching this with `get_clean_env()` workarounds but the SDK's `query()` function also sets `os.environ["CLAUDE_CODE_ENTRYPOINT"] = "sdk-py"` and merges `os.environ` into the subprocess env (see `/usr/local/lib/python3.12/dist-packages/claude_agent_sdk/_internal/transport/subprocess_cli.py` lines 346-348), making the env cleaning unreliable.

Tmux naturally isolates the environment — a command run via `tmux send-keys` doesn't inherit the caller's env vars the same way `subprocess.Popen` does.

## Epic & Tickets

Epic: `260306AG_tmux_orchestration_spawning` (registered in TinyDB, 4 phases, 10 tickets)
Run `agentic epic status --epic 260306AG_tmux_orchestration_spawning` to see full breakdown.

## Architecture

### Existing Components (USE these, don't rebuild)

1. **SessionService** at `modules/AgenticGuidance/src/agenticguidance/services/session.py`
   - `create(name, worktree, plan_folder, start_directory)` → creates tmux session via `tmux new-session -d -s {name}`
   - `get(name)` → returns SessionInfo with state (RUNNING/DEAD)
   - `kill(name)` → kills tmux session
   - `list()` → lists all sessions, reconciles registry with actual tmux state
   - Registry at `~/.config/agenticcli/sessions.json`

2. **cmd_spawn** at `modules/AgenticCLI/src/agenticcli/commands/session.py` (line ~646)
   - Already compiles full agent context into `~/.agentic/sessions/context/{session_id}.md`
   - Has SDK path (background) and subprocess path (foreground/fallback)
   - Already has `use_tmux = getattr(args, "tmux", False)` flag parsed (line 700)
   - Stores session metadata in `StateStore("sessions")`

3. **ExecutionRunner** at `modules/AgenticCLI/src/agenticcli/workflows/orchestration.py` (line ~411)
   - `_run_phase(plan_folder, phase_id, agent_type, routing)` at line 615 — this is the main target
   - Currently: `subprocess.run(["agentic", "session", "spawn", ...])` then polls `StateStore`
   - `wait_for_session(session_id, timeout=1800)` at `planner_loop.py` line ~496 — polls StateStore every 10s

4. **PlannerLoopWorkflow** at `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py`
   - `_spawn_agent(role, prompt, ...)` — uses SDK `run_agent_sync()` or subprocess fallback
   - `_build_sdk_options()` at line 94 — builds `ClaudeAgentOptions`

5. **get_clean_env()** at `modules/AgenticCLI/src/agenticcli/utils/subprocess_utils.py`
   - Strips `CLAUDECODE` and `CLAUDE_CODE_ENTRYPOINT` from env
   - Currently used in orchestration.py, session.py, ralph.py as a workaround

### The Tmux Spawn Pattern

Instead of:
```python
subprocess.run(["agentic", "session", "spawn", "--role", agent_type, ...], env=get_clean_env())
```

Do:
```python
from agenticguidance.services.session import SessionService

tmux_svc = SessionService()
session_name = f"orch-{epic_short}-{phase_id}"  # e.g., "orch-tmux-phase_1"

# 1. Create tmux session
result = tmux_svc.create(name=session_name, start_directory=working_dir)

# 2. Send the claude command into the tmux session
#    tmux send-keys doesn't inherit caller's env
cmd = f"claude --print --dangerously-skip-permissions -p 'Read {context_file} first. Then execute your task.' 2>&1 | tee {log_file}; tmux wait-for -S {session_name}-done"
subprocess.run(["tmux", "send-keys", "-t", session_name, cmd, "Enter"])

# 3. Wait for completion via tmux wait-for
subprocess.run(["tmux", "wait-for", f"{session_name}-done"], timeout=1800)
# OR poll: tmux has-session -t {session_name} returns non-zero when session is dead
```

Key tmux commands:
- `tmux new-session -d -s NAME -c WORKDIR` — create detached session
- `tmux send-keys -t NAME "command" Enter` — run command in session (NO env inheritance from caller)
- `tmux has-session -t NAME` — check if session exists (exit 0 = alive, exit 1 = dead)
- `tmux wait-for -S CHANNEL` — signal a channel (used at end of command)
- `tmux wait-for CHANNEL` — block until channel is signaled
- `tmux capture-pane -t NAME -p` — capture pane output (for logging)

### Completion Detection Strategy

Two options (implement the simpler one first):

**Option A: tmux wait-for (recommended)**
Append `; tmux wait-for -S {session_name}-done` to the command sent via send-keys. The orchestrator blocks on `tmux wait-for {session_name}-done`. When the claude process finishes, the wait-for unblocks.

**Option B: Poll tmux has-session**
Poll `tmux has-session -t {name}` every 10 seconds. When it returns non-zero, the session is dead (command finished). Combine with exit code capture via `tmux display-message -p '#{pane_dead_status}'`.

### Exit Code Capture

To get the exit code of the command that ran inside tmux:
```bash
# Option 1: Capture via remain-on-exit
tmux set-option -t SESSION remain-on-exit on
# Then after session exits:
tmux display-message -t SESSION -p '#{pane_dead_status}'  # 0 = success

# Option 2: Write exit code to a file
cmd = f"claude ... ; echo $? > /tmp/orch-{session_name}.exitcode; tmux wait-for -S {session_name}-done"
```

## Implementation Order

### Phase 1: Add tmux spawn path to cmd_spawn (TO_001, TO_002, TO_003)

1. In `session.py:cmd_spawn()`, add a third execution path after the SDK path:
   ```
   if use_tmux:
       # Create tmux session, send claude command, return session_id
   ```
2. The `--tmux` flag is already parsed (line 700). Wire it to the tmux spawn logic.
3. Session naming: `orch-{epic_folder[:12]}-{role}` or just `agentic-{session_id[:8]}`
4. Store `tmux_session_name` in session_data for later polling.

### Phase 2: Wire ExecutionRunner to tmux (TO_004, TO_005)

1. In `orchestration.py:_run_phase()`, replace the subprocess.run call with tmux spawning.
   - Either call `cmd_spawn` with `--tmux` flag, or directly use SessionService.
   - Direct SessionService is cleaner — avoid the subprocess-within-subprocess entirely.
2. In `planner_loop.py`, update `_spawn_agent()` to use tmux instead of SDK `run_agent_sync()`.
   - The SDK path is broken inside Claude Code (CLAUDECODE issue). Tmux works.
   - Keep SDK as a fallback for when tmux isn't available.

### Phase 3: Completion detection (TO_006, TO_007)

1. Implement `wait_for_tmux_session(session_name, timeout)` using `tmux wait-for`.
2. Integrate with existing `wait_for_session()` — detect tmux vs PID-based sessions.
3. Capture exit codes for success/failure reporting.

### Phase 4: Cleanup (TO_008, TO_009, TO_010)

1. Make tmux the default (not SDK, not bare subprocess) when tmux is available.
2. Remove `get_clean_env()` workarounds where tmux replaces them.
3. End-to-end test: `agentic session orchestrate planning --plan 260306AG_tmux_orchestration_spawning` should work from inside Claude Code.

## Key Files to Modify

| File | What to Change |
|------|---------------|
| `modules/AgenticCLI/src/agenticcli/commands/session.py` | Add tmux spawn path in cmd_spawn (~line 700-810) |
| `modules/AgenticCLI/src/agenticcli/workflows/orchestration.py` | Replace _run_phase() subprocess with tmux (~line 615-690) |
| `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` | Replace _spawn_agent() SDK path with tmux (~line 280-380) |
| `modules/AgenticGuidance/src/agenticguidance/services/session.py` | Add send_keys(), wait_for_completion() methods |

## What NOT to Do

- Don't remove the SDK path entirely — keep it as fallback for environments without tmux
- Don't change the StateStore-based session tracking — tmux is just the execution layer
- Don't refactor the entire cmd_spawn — just add the tmux path alongside existing paths
- Don't build a tmux dashboard/TUI — that's a separate future enhancement
- Don't change how context compilation works — the `~/.agentic/sessions/context/{session_id}.md` pattern stays

## Verification

After implementation, this command should work from inside Claude Code:
```bash
agentic session spawn --role explore --plan 260306AG_tmux_orchestration_spawning --tmux -b
```
And you should be able to watch it with:
```bash
tmux attach -t <session_name>
```

## Other Outstanding Epics (for context, don't work on these)

- `260305AG_decommission_yaml_tinydb_native` — 81% done, 5 tickets remaining (YAML file deletion + test updates)
- `260305AG_standardize_statuses_cli_docs` — 0% done, 12 tickets
- `260303AG_reduce_orchestration_context_overflow` — 0% done, 8 tickets
