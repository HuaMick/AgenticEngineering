# AgenticLangSmith Module

Integration module for LangSmith observability with Claude Code.

## Overview

This module provides:
- **LangSmith tracing** - Automatic trace capture from Claude Code sessions
- **Python API** - `LangSmithService` for querying traces, runs, and projects
- **Filter builders** - Composable functions for building query filters
- **Friction analysis** - Pattern detection to identify agent inefficiencies
- **Resolution recommendations** - Actionable suggestions for detected friction

## Installation

```bash
pip install -e modules/AgenticLangSmith
```

Requires: `langsmith` package and `LANGSMITH_API_KEY` environment variable.

---

## Python API

### LangSmithService

Core service class for interacting with LangSmith API.

```python
from agenticlangsmith import LangSmithService

# Initialize (reads LANGSMITH_API_KEY from environment)
service = LangSmithService()

# Or pass API key directly
service = LangSmithService(api_key="lsv2_pt_xxx")
```

**Methods:**

| Method | Description |
|--------|-------------|
| `list_runs(project_name, limit, run_type, error_only, filter_expr)` | List runs with filtering |
| `get_run(run_id)` | Get detailed info for a single run |
| `list_projects()` | List all projects in workspace |
| `get_project_stats(project_name, limit)` | Get aggregated statistics |
| `get_run_url(run_id)` | Generate shareable URL for a run |
| `get_run_feedback(run_id)` | Get feedback for a run |

**Example - List runs with errors:**

```python
service = LangSmithService()
error_runs = service.list_runs(
    project_name="agenticengineering-main",
    limit=50,
    error_only=True
)
for run in error_runs:
    print(f"{run['name']}: {run['error']}")
```

### Filter Builders

Composable functions for building LangSmith filter expressions.

```python
from agenticlangsmith import (
    build_time_filter,
    build_type_filter,
    build_error_filter,
    build_latency_filter,
    build_token_filter,
    build_tag_filter,
    build_name_filter,
    combine_filters,
    combine_filters_or,
)
```

**Filter functions:**

| Function | Description |
|----------|-------------|
| `build_time_filter(start, end)` | Filter by time range |
| `build_type_filter(run_type)` | Filter by run type (llm, chain, tool, retriever) |
| `build_error_filter(has_error)` | Filter by error status |
| `build_latency_filter(min_seconds, max_seconds)` | Filter by latency |
| `build_token_filter(min_tokens, max_tokens)` | Filter by token count |
| `build_tag_filter(tag)` | Filter by tag |
| `build_name_filter(name, exact)` | Filter by name pattern |
| `combine_filters(*filters)` | Combine with AND logic |
| `combine_filters_or(*filters)` | Combine with OR logic |

**Example - Complex filter:**

```python
from datetime import datetime, timedelta

# Find slow LLM calls from last 24 hours
filter_expr = combine_filters(
    build_time_filter(start=datetime.now() - timedelta(days=1)),
    build_type_filter("llm"),
    build_latency_filter(min_seconds=5.0),
)

runs = service.list_runs(
    project_name="my-project",
    filter_expr=filter_expr
)
```

### Friction Analysis

Detect inefficiency patterns in agent traces.

```python
from agenticlangsmith import FrictionAnalyzer, FrictionPatternType, Severity

analyzer = FrictionAnalyzer()  # Uses default LangSmithService
report = analyzer.analyze(
    project_name="agenticengineering-main",
    limit=100,
    lookback_days=7
)

print(f"Friction detected: {report.has_friction}")
print(f"Severity breakdown: {report.severity_breakdown}")

for pattern in report.patterns:
    print(f"{pattern.pattern_type.value}: {pattern.description}")
```

**Friction pattern types:**

| Pattern | Code | Description |
|---------|------|-------------|
| Excessive Retries | FP-001 | 3+ consecutive errors in same session |
| Exploration Drift | FP-002 | >60% exploration tools with 10+ tool calls |
| Missing Context | FP-003 | Frequent AskUserQuestion calls |
| Schema Violations | FP-004 | Validation/format errors |
| Convention Violations | FP-005 | Post-creation renames or corrections |
| Automatable Patterns | FP-006 | Repeated tool sequences across sessions |

### Resolution Recommendations

Generate actionable recommendations from friction patterns.

```python
from agenticlangsmith import ResolutionRecommender, ResolutionType

recommender = ResolutionRecommender()
plan = recommender.recommend(report)

for rec in plan.recommendations:
    print(f"{rec.resolution_type.value}: {rec.description}")
    print(f"  Target: {rec.target_locations}")
    print(f"  Changes: {rec.suggested_changes}")

print(f"Next steps: {plan.next_steps}")
```

**Resolution types:**

| Type | Description |
|------|-------------|
| GUIDANCE_UPDATE | Update process.yml or inputs.yml files |
| CLI_OFFLOAD | Create AgenticCLI command |
| ASSET_UPDATE | Add examples or schema documentation |

---

## AgenticCLI Integration

The `agentic langsmith` (or `agentic ls`) command provides CLI access to all functionality.

```bash
# List recent runs
agentic ls runs --project agenticengineering-main --limit 20

# Show run details
agentic ls run <run-id>

# Get shareable URL
agentic ls run <run-id> --url

# List projects
agentic ls projects

# Get project statistics
agentic ls stats --project agenticengineering-main

# Friction analysis
agentic ls friction --project agenticengineering-main

# Friction with recommendations
agentic ls friction --project agenticengineering-main --recommend

# JSON output (for scripting)
agentic ls runs --project agenticengineering-main --json
```

**Friction command options:**

| Option | Description |
|--------|-------------|
| `--project` | LangSmith project name (or CC_LANGSMITH_PROJECT env) |
| `--limit` | Max runs to analyze (default: 100) |
| `--lookback-days` | Days to look back (default: 7) |
| `--recommend` | Include resolution recommendations |
| `--json` | Output as JSON |

---

## Exceptions

```python
from agenticlangsmith import LangSmithConfigError, LangSmithAPIError

try:
    service = LangSmithService()
except LangSmithConfigError as e:
    print(f"Configuration error: {e}")  # Missing API key

try:
    runs = service.list_runs(project_name="nonexistent")
except LangSmithAPIError as e:
    print(f"API error: {e}")  # API call failed
```

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
