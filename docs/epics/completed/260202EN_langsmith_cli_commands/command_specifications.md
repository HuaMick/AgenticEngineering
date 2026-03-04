# LangSmith CLI Command Specifications

## Overview

This document defines specifications for new and enhanced LangSmith CLI commands following the patterns established in the existing `agenticcli.commands.langsmith` module.

## Design Patterns Identified

### Existing Patterns
- **Service layer**: Commands use `LangSmithService` from `agenticlangsmith` package
- **Error handling**: Try/except blocks with `print_error()` and `sys.exit(1)`
- **Output formatting**: Dual mode (JSON via `--json` flag or Rich tables/panels)
- **Helper functions**: `_truncate()` for text truncation, `_get_service()` for service initialization
- **Console utilities**: From `agenticcli.console` (print_header, print_json, console, Table, Panel)
- **Command routing**: Via `handle()` function that dispatches to `cmd_*` functions

### Reusable Helpers
- `_get_service()` - Service initialization with error handling
- `_truncate(text, max_length)` - Text truncation with ellipsis
- `is_json_output()` - Check if JSON output mode enabled
- `print_json()`, `print_header()`, `print_error()` - Console output functions

### Output Format Conventions
- **Tables**: Rich Table with magenta headers, styled columns
- **Panels**: Rich Panel for grouped content with border styles (cyan, blue, green)
- **Status colors**: green=success, red=error, yellow=running, dim=unknown
- **JSON mode**: All output as JSON when `--json` flag present

---

## Command 1: session-analyze

### Purpose
Provide detailed analysis of LangSmith sessions including timeline, statistics, and run breakdown.

### Command Signature
```bash
agentic langsmith session-analyze <session-id> [options]
```

### Arguments
- `session-id` (required): Session UUID to analyze

### Options
- `--project`, `-p`: Project name (optional, for validation)
- `--export`: Export format (json, csv, markdown)
- `--json`, `-j`: Output in JSON format (inherited global flag)

### Implementation Details

**Function**: `cmd_session_analyze(args)`

**Service methods needed**:
- `list_runs(project_name=None, limit=500, filter_expr=f'session_id="{session_id}"')`

**Processing**:
1. Get service instance
2. Fetch all runs for the session
3. Calculate session statistics:
   - Total runs
   - Error count/rate
   - Duration (first run to last run)
   - Run types breakdown
   - Token usage
   - Average latency
4. Build timeline of runs
5. Output in requested format

**Output Formats**:

JSON:
```json
{
  "session_id": "uuid",
  "statistics": {
    "total_runs": 25,
    "error_count": 2,
    "error_rate": 8.0,
    "duration_seconds": 1234.5,
    "total_tokens": 15000,
    "avg_latency_ms": 450.2
  },
  "run_types": {
    "llm": 10,
    "chain": 8,
    "tool": 7
  },
  "timeline": [
    {
      "run_id": "uuid",
      "name": "run_name",
      "run_type": "llm",
      "status": "success",
      "start_time": "2026-02-02T10:00:00",
      "latency_ms": 450
    }
  ]
}
```

CSV Export (--export csv):
```csv
run_id,name,run_type,status,start_time,latency_ms,tokens
uuid1,run1,llm,success,2026-02-02T10:00:00,450,1500
uuid2,run2,chain,error,2026-02-02T10:01:00,200,0
```

Markdown Export (--export markdown):
```markdown
# Session Analysis: uuid

## Statistics
- Total Runs: 25
- Error Rate: 8.0%
- Duration: 20m 34s
- Total Tokens: 15000

## Run Types
- llm: 10
- chain: 8
- tool: 7

## Timeline
| Run | Type | Status | Time | Latency |
|-----|------|--------|------|---------|
| uuid1 | llm | success | 10:00:00 | 450ms |
```

Table (default):
- Header panel with session ID and statistics
- Run types breakdown
- Timeline table

**Error Cases**:
- Session not found: "Session {session_id} not found in project {project}"
- No runs in session: "Session {session_id} has no runs"
- Service error: "Failed to analyze session: {error}"

---

## Command 2: batch-search

### Purpose
Search across multiple runs using regex patterns on inputs, outputs, or errors.

### Command Signature
```bash
agentic langsmith batch-search <pattern> [options]
```

### Arguments
- `pattern` (required): Regex pattern to search for

### Options
- `--project`, `-p`: Project name (required)
- `--field`, `-f`: Field to search (inputs, outputs, error, all) (default: all)
- `--type`, `-t`: Filter by run type
- `--status`, `-s`: Filter by status (success, error, running)
- `--since`: Start date (ISO format)
- `--until`: End date (ISO format)
- `--limit`, `-l`: Max runs to search (default: 100)
- `--group-by`: Group results by (session, type, status, none) (default: none)
- `--export`: Export format (json, csv)
- `--json`, `-j`: Output in JSON format

### Implementation Details

**Function**: `cmd_batch_search(args)`

**Service methods needed**:
- `list_runs(project_name, limit, run_type, error_only, filter_expr)`

**Processing**:
1. Get service instance
2. Validate regex pattern
3. Fetch runs with filters
4. Search pattern in specified fields
5. Group results if requested
6. Output in requested format

**Output Formats**:

JSON:
```json
{
  "pattern": "error.*timeout",
  "matches": 15,
  "results": [
    {
      "run_id": "uuid",
      "name": "run_name",
      "matched_field": "error",
      "match_snippet": "error: timeout waiting for...",
      "session_id": "uuid",
      "run_type": "llm",
      "start_time": "2026-02-02T10:00:00"
    }
  ]
}
```

CSV Export:
```csv
run_id,name,matched_field,match_snippet,session_id,run_type,start_time
uuid1,run1,error,"error: timeout...",session1,llm,2026-02-02T10:00:00
```

Table (default):
- Header with search summary
- Results table with columns: Run ID, Name, Field, Snippet, Type, Time

**Error Cases**:
- Invalid regex: "Invalid regex pattern: {error}"
- No project specified: "--project is required"
- No matches: "No matches found for pattern '{pattern}'"

---

## Command 3: run-inspect (Enhanced)

### Purpose
Enhanced version of existing `run` command with hierarchy visualization and detailed timing breakdown.

### Command Signature
```bash
agentic langsmith run-inspect <run-id> [options]
```

### Arguments
- `run-id` (required): Run UUID to inspect

### Options
- `--tree`: Show parent/child hierarchy as tree
- `--full`: Show full inputs/outputs (not truncated)
- `--format`: Output format (json, yaml, table) (default: table)
- `--timing`: Show detailed timing breakdown
- `--url`, `-u`: Include shareable URL
- `--json`, `-j`: Output in JSON format

### Implementation Details

**Function**: `cmd_run_inspect(args)` (replaces/enhances `cmd_run`)

**Service methods needed**:
- `get_run(run_id)`
- `get_run_feedback(run_id)`
- `get_run_url(run_id)`
- `list_runs()` with filters to find parent/children

**Processing**:
1. Get service instance
2. Fetch run details
3. If --tree: fetch parent and child runs recursively
4. Calculate timing breakdown if --timing
5. Format output based on --format flag

**Output Formats**:

JSON (with --tree):
```json
{
  "run": {
    "id": "uuid",
    "name": "run_name",
    "hierarchy": {
      "parent": null,
      "children": [
        {"id": "child1", "name": "child_run_1"},
        {"id": "child2", "name": "child_run_2"}
      ]
    },
    "timing": {
      "total_ms": 1500,
      "execution_ms": 1400,
      "overhead_ms": 100
    }
  }
}
```

Tree visualization (--tree):
```
Run: parent_run
├── child_run_1 [llm] (450ms)
│   └── grandchild_1 [tool] (100ms)
└── child_run_2 [chain] (850ms)
```

**Error Cases**:
- Run not found: "Run {run_id} not found"
- Invalid format: "Invalid format: {format}"

---

## Command 4: friction-report (Enhanced)

### Purpose
Enhanced version of existing `friction` command with export options and better organization.

### Command Signature
```bash
agentic langsmith friction-report [options]
```

### Options
- `--project`, `-p`: Project name (required)
- `--sessions`: Number of recent sessions to analyze
- `--since`: Start date (ISO format)
- `--limit`, `-l`: Max runs to analyze (default: 100)
- `--lookback-days`: Days to look back (default: 7)
- `--min-affected`: Min sessions affected (default: 2)
- `--recommend`, `-r`: Include recommendations
- `--validate`: Validate recommendations (default: true)
- `--export`: Export format (json, markdown, yaml)
- `--group-by`: Group patterns by (severity, type, session) (default: severity)
- `--json`, `-j`: Output in JSON format

### Implementation Details

**Function**: `cmd_friction_report(args)` (enhances `cmd_friction`)

**Service methods needed**:
- All existing methods from `cmd_friction`

**Processing**:
1. Use existing friction analysis logic
2. Add grouping options
3. Add export formats
4. Enhance output with more details

**Output Formats**:

Markdown Export (--export markdown):
```markdown
# Friction Analysis Report

**Project**: project_name
**Analyzed Runs**: 100
**Timeframe**: 7 days
**Patterns Found**: 5

## High Severity Patterns

### Excessive Retries (Frequency: 12)
Description: Multiple retry attempts detected
Sessions Affected: session1, session2, session3

**Evidence**:
- Run abc123: 5 retries
- Run def456: 3 retries

**Recommendation**:
Implement circuit breaker pattern...

## Medium Severity Patterns
...
```

YAML Export (--export yaml):
```yaml
report:
  project: project_name
  analyzed_runs: 100
  timeframe_days: 7
  patterns:
    - pattern_type: excessive_retries
      severity: high
      frequency: 12
      description: Multiple retry attempts detected
      evidence:
        - run_id: abc123
          retry_count: 5
      recommendations:
        - type: circuit_breaker
          description: Implement circuit breaker pattern
```

**Error Cases**:
- Same as existing `cmd_friction`

---

## CLI Parser Changes

### Location
`modules/AgenticCLI/src/agenticcli/cli.py` in `_add_langsmith_parser()` function

### New Subcommands to Add

```python
# langsmith session-analyze
session_analyze_parser = langsmith_subparsers.add_parser(
    "session-analyze",
    parents=[global_parent],
    help="Analyze a specific session with detailed statistics",
    description="Provide detailed analysis of a LangSmith session including timeline and stats.",
)
session_analyze_parser.add_argument(
    "session_id",
    help="Session UUID to analyze",
)
session_analyze_parser.add_argument(
    "--project", "-p",
    help="Project name for validation",
)
session_analyze_parser.add_argument(
    "--export",
    choices=["json", "csv", "markdown"],
    help="Export format",
)

# langsmith batch-search
batch_search_parser = langsmith_subparsers.add_parser(
    "batch-search",
    parents=[global_parent],
    help="Search runs by regex pattern",
    description="Search across multiple runs using regex patterns on inputs, outputs, or errors.",
)
batch_search_parser.add_argument(
    "pattern",
    help="Regex pattern to search for",
)
batch_search_parser.add_argument(
    "--project", "-p",
    required=True,
    help="Project name (required)",
)
batch_search_parser.add_argument(
    "--field", "-f",
    choices=["inputs", "outputs", "error", "all"],
    default="all",
    help="Field to search (default: all)",
)
batch_search_parser.add_argument(
    "--type", "-t",
    choices=["llm", "chain", "tool", "retriever"],
    help="Filter by run type",
)
batch_search_parser.add_argument(
    "--status", "-s",
    choices=["success", "error", "running"],
    help="Filter by status",
)
batch_search_parser.add_argument(
    "--since",
    help="Start date (ISO format, e.g., 2026-01-01)",
)
batch_search_parser.add_argument(
    "--until",
    help="End date (ISO format, e.g., 2026-01-01)",
)
batch_search_parser.add_argument(
    "--limit", "-l",
    type=int,
    default=100,
    help="Max runs to search (default: 100)",
)
batch_search_parser.add_argument(
    "--group-by",
    choices=["session", "type", "status", "none"],
    default="none",
    help="Group results by (default: none)",
)
batch_search_parser.add_argument(
    "--export",
    choices=["json", "csv"],
    help="Export format",
)

# langsmith run-inspect (rename from run, keep run as alias)
run_inspect_parser = langsmith_subparsers.add_parser(
    "run-inspect",
    parents=[global_parent],
    aliases=["run"],
    help="Inspect run with enhanced details and hierarchy",
    description="Display detailed run information with optional hierarchy visualization.",
)
run_inspect_parser.add_argument(
    "run_id",
    help="The run ID to inspect",
)
run_inspect_parser.add_argument(
    "--tree",
    action="store_true",
    help="Show parent/child hierarchy as tree",
)
run_inspect_parser.add_argument(
    "--full",
    action="store_true",
    help="Show full inputs/outputs (not truncated)",
)
run_inspect_parser.add_argument(
    "--format",
    choices=["json", "yaml", "table"],
    default="table",
    help="Output format (default: table)",
)
run_inspect_parser.add_argument(
    "--timing",
    action="store_true",
    help="Show detailed timing breakdown",
)
run_inspect_parser.add_argument(
    "--url", "-u",
    action="store_true",
    help="Include shareable URL",
)

# langsmith friction-report (rename from friction, keep friction as alias)
friction_report_parser = langsmith_subparsers.add_parser(
    "friction-report",
    parents=[global_parent],
    aliases=["friction"],
    help="Generate friction analysis report with export options",
    description="Analyze traces for friction patterns with enhanced export capabilities.",
)
# Copy all existing friction arguments...
friction_report_parser.add_argument(
    "--export",
    choices=["json", "markdown", "yaml"],
    help="Export format",
)
friction_report_parser.add_argument(
    "--group-by",
    choices=["severity", "type", "session"],
    default="severity",
    help="Group patterns by (default: severity)",
)
```

### Command Routing Updates

In `handle()` function:
```python
def handle(args, ctx=None):
    if args.langsmith_command == "session-analyze":
        cmd_session_analyze(args)
    elif args.langsmith_command == "batch-search":
        cmd_batch_search(args)
    elif args.langsmith_command in ("run-inspect", "run"):
        cmd_run_inspect(args)
    elif args.langsmith_command in ("friction-report", "friction"):
        cmd_friction_report(args)
    # ... existing commands
```

---

## Error Handling Approach

### Consistent Pattern
All commands follow this pattern:
```python
def cmd_example(args):
    from agenticcli.console import print_error, console, is_json_output, print_json

    service = _get_service()  # Handles service initialization errors

    try:
        # Command logic
        result = service.some_method()

        if is_json_output():
            print_json(result)
            return

        # Rich table/panel output
        console.print(...)

    except LangSmithAPIError as e:
        print_error(f"Failed to execute command: {e}")
        sys.exit(1)
    except ValueError as e:
        print_error(f"Invalid argument: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
```

### Error Categories
1. **Configuration errors**: Missing API key (handled by `_get_service()`)
2. **API errors**: LangSmith API failures (caught and wrapped)
3. **Validation errors**: Invalid arguments (ValueError)
4. **Not found errors**: Resources don't exist
5. **Unexpected errors**: Catch-all

---

## Testing Approach

### Unit Tests
- Mock `LangSmithService` methods
- Test command parsing
- Test output formatting
- Test error handling

### Integration Tests
- Test against real LangSmith projects
- Validate export file formats
- Test with various data sizes
- Verify backward compatibility

---

## Backward Compatibility

### Aliases
- `run` remains as alias for `run-inspect`
- `friction` remains as alias for `friction-report`

### Existing Commands
- All existing commands remain unchanged
- New features added via new flags
- No breaking changes to command signatures
