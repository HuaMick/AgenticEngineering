# SDK-in-Tmux Spawn Architecture

## Problem Statement

The Claude Agent SDK's `query()` function cannot be called more than once per
Python process.  After the first call completes, the spawned `claude` child
process becomes a zombie and a second call silently kills the parent process.

**Root cause:** SDK internal state is never fully cleaned up between calls.
Tracked as SDK issues #434, #515, #573, #1089.

**Impact:** The planning loop spawns 3+ agents sequentially (story-writer,
explore, planner-orchestration).
Calling `query()` in a loop inside a single process caused the loop to die
after the first agent.

## Solution: One Process Per Agent Via Tmux

Each agent runs in its own tmux pane (separate OS process), calling `query()`
exactly once.  The parent orchestrator launches panes, then polls session state
files for completion.

```
                       PlannerLoopWorkflow
                              |
               _run_role_agent() per role
                              |
        +---------------------+---------------------+
        |                     |                     |
   [tmux pane 1]        [tmux pane 2]        [tmux pane N]
   sdk_pane_runner      sdk_pane_runner      sdk_pane_runner
   query() x1           query() x1           query() x1
        |                     |                     |
   state.json            state.json            state.json
   (atomic write)        (atomic write)        (atomic write)
        |                     |                     |
        +---------------------+---------------------+
                              |
                 Orchestrator polls state files
                 Aggregates cost/duration/turns
```

## Transport Selection

Transport selection determines how an agent process is spawned.  The priority
chain is defined in `agenticcli.utils.transport`:

```
Priority Order:
  1. sdk-tmux    — SDK available + tmux binary exists + tmux requested
  2. tmux        — tmux exists + tmux requested (no SDK)
  3. subprocess  — fallback (no tmux or not requested)
```

### Standard Transport (`transport.py`)

```python
def determine_transport(sdk_available, tmux_requested) -> str:
    if sdk_available and tmux_exists and tmux_requested:
        return "sdk-tmux"
    elif tmux_exists and tmux_requested:
        return "tmux"
    else:
        return "subprocess"
```

### Planner Loop Override (`planner_loop.py`)

The planner loop has its own routing with special override logic:

```
AGENTIC_FORCE_SDK_DIRECT=1?
    ├── YES + SDK → sdk-direct (WARNING: zombie bug risk)
    └── NO
         ├── SDK + tmux → sdk-tmux (default)
         ├── SDK only   → sdk-direct (WARNING: zombie bug risk)
         └── no SDK     → subprocess
```

The `AGENTIC_FORCE_SDK_DIRECT=1` env var is a debug override that bypasses
tmux isolation. It exists for testing only — it re-exposes the zombie bug.

## SDK Pane Runner Lifecycle

`sdk_pane_runner.py` is the entry point for each tmux pane:

```
┌─────────────────────────────────────────────┐
│           sdk_pane_runner.main()             │
├─────────────────────────────────────────────┤
│ 1. Parse args                               │
│    --role, --session-id, --context-file,     │
│    --working-dir, --timeout                  │
│                                             │
│ 2. Strip CLAUDECODE env vars                │
│    Prevents nested-session guard             │
│                                             │
│ 3. Read prompt from --context-file           │
│                                             │
│ 4. Build ClaudeAgentOptions                 │
│    - Role-specific tool allowlists           │
│    - Role-specific timeouts                  │
│    - permission_mode=bypassPermissions       │
│                                             │
│ 5. Call SDK query() exactly once             │
│    - Stream messages to stdout (tmux pane)   │
│    - Collect ResultMessage with metrics      │
│    - Handle timeout/errors                   │
│                                             │
│ 6. Write state file (atomic)                │
│    - Temp file + os.replace() pattern        │
│    - Prevents partial reads by poller        │
│                                             │
│ 7. Exit with code 0 (success) or 1 (fail)  │
└─────────────────────────────────────────────┘
```

**Invocation:**
```bash
python3 -m agenticcli.utils.sdk_pane_runner \
    --role explore \
    --session-id <uuid> \
    --context-file /path/to/context.md \
    --working-dir /home/code/project \
    --timeout 300
```

## Session State Flow

State transitions are managed by `session_state.py` helpers:

```
make_session_data()          mark_running()
  status: "starting"    →     status: "running"
  session_id                   pid, transport,
  role, epic_folder            tmux_session
  transport, working_dir
          │                          │
          │                          ├──→ mark_completed()
          │                          │      status: "completed"
          │                          │      exit_code: 0
          │                          │      cost_usd, duration_ms
          │                          │      num_turns, sdk_session_id
          │                          │
          │                          └──→ mark_failed()
          │                                 status: "failed"
          │                                 exit_code: 1
          │                                 error_code, error_type
          │                                 failure_reason {
          │                                   detail, retryable,
          │                                   suggested_action
          │                                 }
```

State files are stored at `~/.agentic/sessions/{session_id}.json` and written
atomically (temp file + `os.replace()`) to prevent partial reads.

## Metrics Capture

After each agent completes, the orchestrator reads SDK metrics from the
session state file via `read_sdk_metrics()`:

| Metric           | Source                    | Description                       |
|------------------|---------------------------|-----------------------------------|
| `cost_usd`       | `ResultMessage.total_cost_usd` | Total API cost in USD        |
| `duration_ms`    | `ResultMessage.duration_ms`    | Wall-clock duration          |
| `num_turns`      | `ResultMessage.num_turns`      | Agentic turn count           |
| `usage`          | `ResultMessage.usage`          | Token usage breakdown        |
| `sdk_session_id` | `ResultMessage.session_id`     | Claude SDK session identifier|
| `transport`      | Session state                  | Transport type used          |

These metrics are aggregated by the orchestration layer for cost tracking and
performance monitoring across the full planning loop.

## Utility Modules

Seven utility modules support the SDK-in-Tmux system:

| Module              | Purpose                                                    |
|---------------------|------------------------------------------------------------|
| `sdk_pane_runner.py`| Entry point for tmux panes — one `query()` per process     |
| `transport.py`      | Transport selection logic (sdk-tmux > tmux > subprocess)   |
| `session_state.py`  | State lifecycle helpers (make, mark_running/completed/failed)|
| `spawn_command.py`  | Builds normalized `agentic orchestrate session spawn` CLI commands |
| `session_id.py`     | Session UUID generation and tmux session naming             |
| `context_file.py`   | Writes compiled context (prompt) to `~/.agentic/sessions/` |
| `retry.py`          | Centralized retry with exponential and static backoff       |

## Debug Overrides

### `AGENTIC_FORCE_SDK_DIRECT=1`

Forces the planner loop to use SDK-direct path (bypassing tmux isolation).
This re-exposes the zombie subprocess bug and should only be used for
debugging.

**Behavior:** When set to `"1"`, `_run_role_agent()` calls `_run_via_sdk()`
directly instead of `_run_via_tmux_sdk()`.  A warning is logged:

```
WARNING: Using SDK-direct path (AGENTIC_FORCE_SDK_DIRECT=1) — zombie bug risk
```

**Usage:**
```bash
AGENTIC_FORCE_SDK_DIRECT=1 agentic orchestrate session plan ...
```

## Fallback Behavior

The system degrades gracefully when components are unavailable:

| SDK Available | tmux Available | Result                              |
|:---:|:---:|---------------------------------------------------------------------|
| Yes | Yes | **sdk-tmux** — full isolation, recommended path                     |
| Yes | No  | **sdk-direct** — zombie risk, warning logged                        |
| No  | Yes | **tmux** — legacy tmux spawn (no SDK metrics)                       |
| No  | No  | **subprocess** — basic `claude` process spawn                       |

The `sdk-tmux` path is the default and recommended configuration.  All
production environments should have both the Claude Agent SDK and tmux
installed.
