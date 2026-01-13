# AgenticLangSmith Module

Integration module for LangSmith observability with Claude Code.

## Overview

This module provides LangSmith tracing integration for Claude Code sessions, enabling visibility into conversations, tool invocations, and assistant responses.

---

## Architecture: Cross-Worktree Hook Setup

This module uses a **repo-hosted hook with global symlink** approach to support multiple worktrees from a single source of truth.

### Directory Structure

```
~/.claude/
├── settings.json              # Global hook configuration
└── hooks/
    └── stop_hook.sh           # Symlink → repo canonical source

/home/code/AgenticEngineering-agenticguidance/
├── agenticengineering.code-workspace
├── modules/AgenticLangSmith/
│   ├── README.md
│   └── hooks/
│       └── stop_hook.sh       # Canonical source (version controlled)
└── .claude/
    └── settings.local.json    # Env vars for this worktree

/home/code/AgenticEngineering-agentic-cli/
└── .claude/
    └── settings.local.json    # Env vars for this worktree

/home/code/AgenticEngineering/ (main)
└── .claude/
    └── settings.local.json    # Env vars for this worktree
```

### Benefits

- **Version controlled**: Hook script lives in repo, changes are tracked
- **Single source of truth**: All worktrees use the same hook via symlink
- **Per-worktree config**: Each worktree can have different LangSmith project names
- **Automatic updates**: Symlink means hook updates propagate immediately

---

## Claude Code Integration

Source: https://github.com/langchain-ai/tracing-claude-code

### Platform Support

**macOS and Linux** (including WSL2)

- Linux: Uses native `date +%6N` for microseconds
- macOS: Uses `gdate` (GNU coreutils) or Python fallback

### Prerequisites

Required commands:
- `jq` - JSON processing
- `curl` - API calls
- `uuidgen` - UUID generation

---

## Setup Steps

### Step 1: Download hook to module

```bash
mkdir -p /home/code/AgenticEngineering-agenticguidance/modules/AgenticLangSmith/hooks
curl -o /home/code/AgenticEngineering-agenticguidance/modules/AgenticLangSmith/hooks/stop_hook.sh \
  https://raw.githubusercontent.com/langchain-ai/tracing-claude-code/main/stop_hook.sh
chmod +x /home/code/AgenticEngineering-agenticguidance/modules/AgenticLangSmith/hooks/stop_hook.sh
```

### Step 2: Create global symlink

```bash
mkdir -p ~/.claude/hooks
ln -sf /home/code/AgenticEngineering-agenticguidance/modules/AgenticLangSmith/hooks/stop_hook.sh \
  ~/.claude/hooks/stop_hook.sh
```

### Step 3: Configure global hook

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "bash ~/.claude/hooks/stop_hook.sh"
      }]
    }]
  }
}
```

**Note:** Merge with existing settings if file already exists.

### Step 4: Configure per-worktree environment

Create `.claude/settings.local.json` in each worktree root:

**For agenticguidance worktree:**
```json
{
  "env": {
    "TRACE_TO_LANGSMITH": "true",
    "CC_LANGSMITH_API_KEY": "lsv2_pt_xxxxx",
    "CC_LANGSMITH_PROJECT": "agenticengineering-agenticguidance"
  }
}
```

**For agentic-cli worktree:**
```json
{
  "env": {
    "TRACE_TO_LANGSMITH": "true",
    "CC_LANGSMITH_API_KEY": "lsv2_pt_xxxxx",
    "CC_LANGSMITH_PROJECT": "agenticengineering-agentic-cli"
  }
}
```

**For main worktree:**
```json
{
  "env": {
    "TRACE_TO_LANGSMITH": "true",
    "CC_LANGSMITH_API_KEY": "lsv2_pt_xxxxx",
    "CC_LANGSMITH_PROJECT": "agenticengineering-main"
  }
}
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TRACE_TO_LANGSMITH` | Yes | Set to `"true"` to activate tracing |
| `CC_LANGSMITH_API_KEY` | Yes | LangSmith API key (falls back to `LANGSMITH_API_KEY`) |
| `CC_LANGSMITH_PROJECT` | No | Project identifier (defaults to `"claude-code"`) |
| `CC_LANGSMITH_DEBUG` | No | Set to `"true"` for debug logging |

---

## How It Works

The stop hook runs after each Claude Code response and:

1. **Loads conversation transcript** from Claude Code session
2. **Groups messages into turns** (user input → assistant response cycles)
3. **Creates hierarchical traces**:
   - Top-level "turn" run for each conversation turn
   - Child "assistant" runs for LLM responses
   - Sibling "tool" runs for function executions
4. **Sends to LangSmith API** via multipart form uploads
5. **Maintains state** in `~/.claude/state/langsmith_state.json`

### Captured Data

- User messages
- Assistant responses (including multi-part streaming)
- Tool use requests and results
- Usage metadata (token counts, cache statistics)
- Timestamps with microsecond precision

**Note:** System prompts are not available in Claude Code transcripts.

### Logging

- Log file: `~/.claude/state/hook.log`
- State file: `~/.claude/state/langsmith_state.json`
- Enable debug logging with `CC_LANGSMITH_DEBUG=true`

---

## Implementation Checklist

### Module Setup
- [ ] Create `modules/AgenticLangSmith/hooks/` directory
- [ ] Download `stop_hook.sh` to module
- [ ] Make script executable

### Global Configuration
- [ ] Create `~/.claude/hooks/` directory
- [ ] Create symlink from global to module hook
- [ ] Add Stop hook configuration to `~/.claude/settings.json`

### Per-Worktree Configuration
- [ ] Create `.claude/settings.local.json` in agenticguidance worktree
- [ ] Create `.claude/settings.local.json` in agentic-cli worktree
- [ ] Create `.claude/settings.local.json` in main worktree
- [ ] Set unique `CC_LANGSMITH_PROJECT` for each worktree

### Verification
- [ ] Verify prerequisites installed (`jq`, `curl`, `uuidgen`)
- [ ] Test with `CC_LANGSMITH_DEBUG=true`
- [ ] Verify traces appear in LangSmith dashboard
- [ ] Confirm each worktree traces to correct project

---

## Disabling Tracing

To disable tracing for a specific worktree, set in `.claude/settings.local.json`:

```json
{
  "env": {
    "TRACE_TO_LANGSMITH": "false"
  }
}
```

Or remove the `TRACE_TO_LANGSMITH` variable entirely.
