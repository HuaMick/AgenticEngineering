# Broken Behavior Examples - Global Flags

This document provides concrete examples of the current broken behavior with global flags in the Agentic CLI.

## Issue 1: Global Flags Only Work Before Subcommands

### Example 1a: -j flag positioning (BROKEN)

```bash
# BROKEN - flag at the end
$ agentic plan list -j
usage: agentic [-h] [--version] [--json] [--debug]
               {setup,preferences,prefs,pref,health,worktree,wt,plan,config,cfg,update,rebuild,langsmith,ls,inputs,template,tpl,stories,st,manifest,mf,cicd,state,session,loop,env,context,ctx,entrypoint,ep}
               ...
agentic: error: unrecognized arguments: -j

# WORKS - flag before subcommand
$ agentic -j plan list
{
  "plans": [
    {
      "name": "260201CL_fix_global_flags_ordering",
      "status": "planning",
      ...
    }
  ]
}
```

**Impact**: Agents and automation scripts that append `-j` to commands fail.

### Example 1b: Deep nesting (BROKEN)

```bash
# BROKEN - deeply nested command with -j at end
$ agentic context bootstrap --role build-python -j
usage: agentic [-h] [--version] [--json] [--debug]
               {setup,preferences,prefs,pref,health,worktree,wt,plan,config,cfg,update,rebuild,langsmith,ls,inputs,template,tpl,stories,st,manifest,mf,cicd,state,session,loop,env,context,ctx,entrypoint,ep}
               ...
agentic: error: unrecognized arguments: -j

# WORKS - flag at the beginning
$ agentic -j context bootstrap --role build-python
{
  "role": "build-python",
  "task": {...},
  "inputs": {...}
}
```

**Impact**: Bootstrap commands in agent initialization fail when `-j` is at the end.

### Example 1c: Task current command (BROKEN)

```bash
# BROKEN - commonly used by agents
$ agentic plan task current -j
agentic: error: unrecognized arguments: -j

# WORKS - unintuitive flag ordering
$ agentic -j plan task current
{
  "id": "01",
  "status": "in_progress",
  "description": "Search for usages of -j, -d, -v..."
}
```

**Impact**: Task status retrieval in automation fails.

## Issue 2: -v Flag Conflict (BROKEN)

### Example 2a: plan task list -v shows VERSION instead of VERBOSE

```bash
# BROKEN - shows version when verbose was intended
$ agentic plan task list -v
agentic 0.1.0

# CORRECT - using long form
$ agentic plan task list --verbose
Tasks in 260201CL_fix_global_flags_ordering
===========================================

01: Search for usages of -j, -d, -v in cli.py and other command files.
  Status: in_progress
  Phase: P1
  Description: Search for usages of -j, -d, -v in cli.py and other command files.
```

**Impact**: Users expecting verbose output get version number instead.

**Root Cause**: Global `-v` (--version) is captured by the top-level parser before the subparser can see it for `--verbose`.

## Issue 3: Workarounds Required in Code

### Example 3a: MCP Server Workaround

Current code in `mcp/orchestration_server.py`:

```python
# Line 212 - Must place -j BEFORE subcommand
["agentic", "-j", "session", "list", "--active"],

# Line 237
["agentic", "-j", "loop", "history", "--active"],
```

**Why**: The code MUST place `-j` before the subcommand, making commands harder to construct programmatically.

**Desired**: Should work as `["agentic", "session", "list", "--active", "-j"]`

### Example 3b: Help Text Examples

From `agent_help.py`:

```python
# Line 318-319 - Examples show -j BEFORE subcommand
f"agentic context bootstrap --role {agent_name} -j  # Get full seed context",
"agentic plan task current -j                       # Get current task details",
```

**Issue**: Examples teach the non-intuitive flag ordering, perpetuating the problem.

## Issue 4: -d Flag Conflicts (CURRENTLY WORKING BUT FRAGILE)

These currently work but would break with naive global flag propagation:

### Example 4a: plan init -d for description

```bash
# WORKS - local -d flag
$ agentic plan init test-branch -d "Test description"
Plan initialized: 260201BR_test_description
```

**Fragile**: Works only because `-d` must appear before global flags are parsed. If we naively propagate global `-d`, this would become ambiguous.

### Example 4b: session spawn -d for directory

```bash
# WORKS - local -d flag
$ agentic session spawn -p "test" -d /tmp
Command running in background with ID: b289281
```

**Fragile**: Same issue - would conflict with global `--debug` if naively propagated.

### Example 4c: loop start -d for directory

```bash
# WORKS - local -d flag
$ agentic loop start -p "task" -d /home/code/project
Loop started with ID: abc123
```

**Fragile**: Same conflict issue.

## Agent Impact Examples

### Agent Bootstrap Protocol (BROKEN)

Agent initialization typically looks like:

```bash
# Step 1: Bootstrap context
agentic context bootstrap --role build-python -j

# Step 2: Get current task
agentic plan task current -j

# Step 3: List inputs
agentic context inputs --role build-python -j
```

**Current State**: ALL THREE COMMANDS FAIL with `-j` at the end.

**Workaround**: Agents must know to place `-j` BEFORE all subcommands:

```bash
agentic -j context bootstrap --role build-python
agentic -j plan task current
agentic -j context inputs --role build-python
```

**Impact**:
- Harder to programmatically construct commands
- Unintuitive for developers
- Fragile string concatenation required

### Automation Script Example (BROKEN)

Common pattern in automation:

```python
# Construct command
base_cmd = "agentic plan task list"
filters = "--status pending"
output_format = "-j"

# Combine (natural order)
full_cmd = f"{base_cmd} {filters} {output_format}"
# Result: "agentic plan task list --status pending -j"

# Execute
result = subprocess.run(full_cmd.split(), capture_output=True)
# FAILS: unrecognized arguments: -j
```

**Workaround Required**:

```python
# Unnatural order - must prepend global flags
global_flags = "-j"
base_cmd = "agentic plan task list"
filters = "--status pending"

full_cmd = f"agentic {global_flags} plan task list {filters}"
# Result: "agentic -j plan task list --status pending"
```

## Summary of Broken Behavior

1. **Positional Requirement**: Global flags MUST be before subcommands
   - Affects: All global flags (`-j`, `-d`, `-v`)
   - Impact: Unintuitive, breaks automation, requires workarounds

2. **Flag Capture Conflict**: Global `-v` captures local `--verbose`
   - Affects: `plan task list -v`, `entrypoint execute -v`
   - Impact: Users get wrong output (version instead of verbose)

3. **Future Conflict Risk**: Local `-d` flags would conflict if made global
   - Affects: `plan init`, `session spawn`, `loop start`, `langsmith projects`
   - Impact: Requires careful implementation to avoid ambiguity

4. **Workaround Proliferation**: Code throughout project has workarounds
   - Locations: MCP server, help text, agent examples
   - Impact: Technical debt, maintenance burden

## Expected Behavior After Fix

```bash
# All of these should work
agentic plan list -j
agentic context bootstrap --role build-python -j
agentic plan task current -j
agentic plan task list -v  # Shows verbose output, not version
agentic plan init branch -d "Description"  # Still uses local -d
agentic session spawn -p "test" -d /tmp  # Still uses local -d

# AND these should continue to work
agentic -j plan list
agentic --json context bootstrap --role build-python
agentic --debug plan task list
```

## Files Containing Workarounds

1. `modules/AgenticCLI/src/agenticcli/mcp/orchestration_server.py`
   - Lines 212, 237: `-j` placed before subcommand

2. `modules/AgenticCLI/src/agenticcli/commands/agent_help.py`
   - Lines 318-319, 617-618: Examples show `-j` before subcommand

3. `modules/AgenticCLI/src/agenticcli/commands/plan.py`
   - Line 3369: String parsing to detect `-j` flag position

All these workarounds should become unnecessary after the fix.
