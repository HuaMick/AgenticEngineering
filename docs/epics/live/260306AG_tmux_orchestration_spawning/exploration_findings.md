# Exploration Findings: Tmux Orchestration Spawning

## Executive Summary

The goal is to replace subprocess-based agent spawning in `ExecutionRunner._run_phase()` with tmux-based spawning using the existing `AgenticTmux` / `SessionService` infrastructure. This document maps out the current architecture, identifies integration points, and highlights concerns.

---

## 1. Current Flow: How ExecutionRunner Spawns Agents

**File:** `modules/AgenticCLI/src/agenticcli/workflows/orchestration.py` (lines 615-690)

### `_run_phase()` method:

```
1. Builds CLI command:
   ["agentic", "-j", "session", "spawn", "--role", agent_type, "--plan", plan_folder, "-b"]
   Optionally appends: "--dangerously-skip-permissions"

2. Strips CLAUDECODE env var manually (duplicating get_clean_env() logic):
   env = os.environ.copy()
   env.pop("CLAUDECODE", None)

3. Spawns via subprocess.run() with 60s timeout (spawn only, not execution):
   result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=..., env=env)

4. Parses JSON output for session_id

5. Waits for completion via self.workflow.wait_for_session(session_id, timeout=600)
   - This polls StateStore every 10s checking status field
   - Also checks PID liveness via os.kill(pid, 0)
```

### Key insight:
The `subprocess.run()` call spawns `agentic session spawn` which ITSELF spawns `claude` via `subprocess.Popen()`. This is the subprocess-within-subprocess chain the epic wants to eliminate.

---

## 2. How `cmd_spawn` Currently Works

**File:** `modules/AgenticCLI/src/agenticcli/commands/session.py` (lines 646-954)

### Key steps:
1. **Context compilation:** `_compile_spawn_context(prompt, role, epic_folder)` pre-fetches bootstrap context (role process, inputs manifest, current task) and writes it to `~/.agentic/sessions/context/{session_id}.md`
2. **Claude CLI command:** `["claude", "--print", "--dangerously-skip-permissions", short_prompt]`
   - `--output-format json` added for background mode
   - `--max-turns N` if specified
3. **SDK path (preferred for background):** Uses `ClaudeAgentOptions` with `run_agent_sync()` - runs synchronously, no polling needed
4. **Subprocess path (fallback):**
   - Background: `subprocess.Popen()` with `start_new_session=True`, logs to files, detaches
   - Foreground: `subprocess.Popen()` with `process.communicate()`, captures output
5. **Session recording:** `_store.save(session_data)` to `~/.agentic/sessions/{session_id}.json`

---

## 3. AgenticTmux SessionService

**File:** `modules/AgenticGuidance/src/agenticguidance/services/session.py`

### Architecture:
- `SessionService` manages tmux sessions via subprocess calls to `tmux`
- Registry stored at `~/.config/agenticcli/sessions.json`
- Three states: `RUNNING`, `DETACHED`, `DEAD`

### Key methods:
| Method | What it does | Subprocess call |
|--------|-------------|-----------------|
| `create(name, worktree, plan_folder, start_directory)` | Creates detached tmux session | `tmux new-session -d -s <name> -c <dir>` |
| `attach(name)` | Returns attach command | Returns `["tmux", "attach-session", "-t", name]` |
| `list()` | Lists all sessions | `tmux list-sessions` |
| `kill(name, force)` | Kills session | `tmux kill-session -t <name>` |
| `get(name)` | Gets session info | `tmux list-sessions` |
| `cleanup_dead()` | Removes dead sessions | `tmux list-sessions` |

### CRITICAL GAP:
`SessionService.create()` only creates an empty tmux session (a new shell). It does NOT:
- Send any command to the session
- Run `claude` inside the session
- Handle `send-keys` to execute commands in the session

To run a command in the tmux session, you need to use `tmux send-keys -t <session> <command> Enter` AFTER creation.

---

## 4. Existing Tmux Patterns in the Codebase

### Ralph Loop (commands/ralph.py, lines 193-260)
The closest existing pattern. Ralph:
1. Builds a `claude_cmd` string: `f'claude --dangerously-skip-permissions -p "$(cat {prompt_path})"'`
2. Spawns tmux directly: `["tmux", "new-session", "-d", "-s", session_name, claude_cmd]`
   - Note: passes the command as a tmux session initial command (not send-keys)
   - Uses `get_clean_env()` for environment
3. Verifies session started: `tmux has-session -t <name>`
4. Records tmux_session name in state

### Orchestration Layout (utils/tmux_layout.py)
More sophisticated 3-pane layout using:
- `tmux new-session -d -s <name> -n orchestrator -x 200 -y 50 -P -F #{pane_id}`
- `tmux split-window` for pane creation
- `tmux send-keys -t <pane_id> <command> Enter` for executing commands
- `tmux select-pane` for titles and focus

### Tmux Utils (utils/tmux.py)
Helper functions:
- `is_in_tmux()` - checks TMUX env var
- `session_exists(name)` - `tmux has-session -t <name>`
- `send_to_pane(pane_id, content)` - sends content line-by-line with send-keys
- `get_or_create_notification_pane()` - split-window for notifications

---

## 5. State Management & Completion Detection

### StateStore (utils/state_store.py)
- JSON-on-disk: `~/.agentic/sessions/{session_id}.json`
- Fields: session_id, pid, status, started_at, ended_at, exit_code, etc.

### wait_for_session (workflows/planner_loop.py, lines 545-604)
- Polls StateStore every 10s
- Checks for terminal statuses: "completed", "failed", "stopped"
- If "running" but PID is dead, resolves to "completed" or "failed" based on exit_code
- Short-circuits after 3 consecutive read failures
- Default timeout: 600s (10 minutes)

### IMPORTANT for tmux migration:
With tmux spawning, the PID in StateStore will be the PID of the `claude` process running INSIDE the tmux session. The `wait_for_session()` polling should still work IF:
1. The session state JSON is still written with the correct PID
2. OR we add tmux session existence checking as an alternative to PID polling

---

## 6. Environment Handling

### get_clean_env() (utils/subprocess_utils.py)
Strips: `CLAUDECODE`, `CLAUDE_CODE_ENTRYPOINT`

### Current _run_phase() approach:
Manually strips CLAUDECODE (doesn't use get_clean_env(), duplicates the logic).

### Tmux advantage:
Tmux sessions start with a clean shell environment. They DON'T inherit `CLAUDECODE` from the parent process. This eliminates the need for `get_clean_env()` entirely when spawning via tmux.

**BUT:** When using `tmux new-session` with an explicit `env=get_clean_env()`, we're being extra safe. The Ralph loop does use `env=get_clean_env()` even for tmux (line 226).

---

## 7. Integration Points for the Migration

### What needs to change:

#### A. `ExecutionRunner._run_phase()` (orchestration.py)
**Current:** `subprocess.run(["agentic", "session", "spawn", ...])`
**Target:** Create tmux session + send `agentic session spawn` (or direct `claude`) command to it

Two approaches:
1. **Wrap existing spawn:** Create tmux session, then run the same `agentic session spawn` command inside it
   - Pro: Minimal changes, context compilation still works
   - Con: Still a subprocess chain (tmux -> agentic -> claude), though less fragile

2. **Direct claude in tmux:** Create tmux session, compile context, run `claude` directly in tmux
   - Pro: Eliminates all nesting, cleanest approach
   - Con: Must duplicate/extract context compilation from cmd_spawn
   - Con: Must handle StateStore recording separately

**Recommended: Approach 1** (wrap existing spawn in tmux). Reasons:
- Context compilation, session recording, and StateStore integration all stay in cmd_spawn
- Tmux provides the env isolation and observability benefits
- Much smaller diff, less risk

#### B. `cmd_spawn` in session.py
- Add `--tmux` flag support
- When `--tmux` is set: create tmux session, run claude inside it
- When `--tmux` is NOT set: existing behavior (backward compatible)

#### C. Completion detection
- Option 1: Keep StateStore polling (no change needed if PID is still trackable)
- Option 2: Add tmux session existence check as supplement:
  `tmux has-session -t <name>` returns non-zero when session is gone

#### D. Session naming
- Convention: `agentic-{plan_folder}-{phase_id}` or similar
- Must be unique, valid tmux session name

---

## 8. Key Files Summary

| File | Role | Lines of Interest |
|------|------|-------------------|
| `modules/AgenticCLI/src/agenticcli/workflows/orchestration.py` | ExecutionRunner._run_phase() | 615-690 |
| `modules/AgenticCLI/src/agenticcli/commands/session.py` | cmd_spawn() | 646-954 |
| `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` | wait_for_session() | 545-604 |
| `modules/AgenticCLI/src/agenticcli/utils/state_store.py` | StateStore, is_process_running | All |
| `modules/AgenticCLI/src/agenticcli/utils/subprocess_utils.py` | get_clean_env() | All |
| `modules/AgenticCLI/src/agenticcli/utils/tmux.py` | Tmux helpers | All |
| `modules/AgenticCLI/src/agenticcli/utils/tmux_layout.py` | Orchestration layout | All |
| `modules/AgenticCLI/src/agenticcli/commands/ralph.py` | Ralph tmux pattern | 193-260 |
| `modules/AgenticGuidance/src/agenticguidance/services/session.py` | SessionService (tmux mgmt) | All |
| `modules/AgenticGuidance/src/agenticguidance/services/session_config.py` | Session naming conventions | All |

---

## 9. Risks & Considerations

1. **Tmux availability:** Not all environments have tmux. Need graceful fallback to subprocess.
2. **Session name collisions:** Must ensure unique names when running multiple phase agents.
3. **Completion detection:** With tmux, when claude exits, the tmux session may linger (default bash shell). Need either:
   - `tmux new-session ... "claude ..."` so session closes when claude exits
   - Or detect claude exit within the tmux pane
4. **Log capture:** Currently subprocess captures stdout/stderr to log files. With tmux, output goes to the terminal (visible via attach) but isn't captured to files. May need `tee` or tmux pipe-pane.
5. **Testing:** tmux is hard to test in CI. Need mocking strategy.
6. **Two SessionServices:** There's `AgenticGuidance.services.session.SessionService` (tmux) AND the StateStore-based session tracking in `planner_loop.py`. These are separate systems. Integration between them needs to be explicit.
