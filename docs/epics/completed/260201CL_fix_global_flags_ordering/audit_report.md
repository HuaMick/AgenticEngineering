# Phase P1 Audit Report: Global Flags Ordering

**Date**: 2026-02-01
**Plan**: 260201CL_fix_global_flags_ordering
**Phase**: P1 - Audit
**Worktree**: /home/code/AgenticEngineering

## Executive Summary

This audit confirms that global flags (`-j`, `-d`, `-v`) only work when placed BEFORE subcommands, causing friction for automated agents that append flags to the end of commands. Multiple flag conflicts exist where subcommands define local flags with the same short forms as global flags.

## Task 01: Flag Usage Audit

### Global Flags Defined (cli.py lines 154-173)

1. `--json` / `-j` (line 162-163)
   - Purpose: Output in JSON format for scripting/automation
   - Defined on: Top-level parser only

2. `--debug` / `-d` (line 169-170)
   - Purpose: Enable debug logging to console
   - Defined on: Top-level parser only

3. `--version` / `-v` (line 155-156)
   - Purpose: Show version information
   - Defined on: Top-level parser only

### Flag Conflicts Found

#### Conflict 1: `-j` (--json)
**Status**: NO CONFLICTS
- The `-j` short flag is ONLY used for global `--json`
- Local usage in langsmith commands (lines 1133, 1160) uses long form `--json` only
- No subcommands redefine `-j` for local purposes

#### Conflict 2: `-d` (--debug vs --description vs --directory vs --detail)
**Status**: MULTIPLE CONFLICTS

**Local `-d` definitions:**
1. Line 387: `plan init --description` / `-d`
   - Used for plan description in folder naming
   - Example: `agentic plan init branch -d "Description"`

2. Line 1050: `langsmith projects --detail` / `-d`
   - Used to show additional project details
   - Example: `agentic langsmith projects -d`

3. Line 1590: `session spawn --directory` / `-d`
   - Working directory for Claude Code session
   - Example: `agentic session spawn -p "prompt" -d /path`

4. Line 1782: `loop start --directory` / `-d`
   - Working directory for Ralph Loop
   - Example: `agentic loop start -p "prompt" -d /path`

**Conflict Analysis:**
- These commands will NEVER receive the global `--debug` flag when `-d` is used
- Currently works because flags must be placed before subcommand
- WILL BREAK if we make `-d` work at the end (would be ambiguous)

#### Conflict 3: `-v` (--version vs --verbose vs --vars)
**Status**: MULTIPLE CONFLICTS

**Local `-v` definitions:**
1. Line 502: `plan task list --verbose` / `-v`
   - Show full task details including guidance
   - Example: `agentic plan task list -v`

2. Line 2133: `entrypoint execute --vars` / `-v`
   - Variable substitution for entrypoints
   - Example: `agentic entrypoint execute name --vars KEY=VALUE`

**Conflict Analysis:**
- `agentic plan task list -v` currently shows VERSION, not verbose output (BROKEN)
- Global `-v` captures the flag before subparser sees it
- Confirmed broken behavior in testing

### Flag Usage in Code

#### `-j` / `--json` usage locations:
1. cli.py:136 - Help text documentation
2. cli.py:162-163 - Global flag definition
3. cli.py:1133 - langsmith friction `--json` (long form only)
4. cli.py:1160 - langsmith sessions `--json` (long form only)
5. plan.py:3369 - Detection of JSON output mode in command strings
6. agent_help.py:318-319, 617-618 - Example commands in help text
7. mcp/orchestration_server.py:212, 237 - MCP server using `-j` BEFORE subcommand
8. entry.py:36 - Detection of JSON mode for agent bootstrap

#### `-d` usage locations:
1. cli.py:137 - Help text documentation for `--debug`
2. cli.py:169-170 - Global `--debug` / `-d` definition
3. cli.py:387 - Local `plan init --description` / `-d`
4. cli.py:1050 - Local `langsmith projects --detail` / `-d`
5. cli.py:1590 - Local `session spawn --directory` / `-d`
6. cli.py:1782 - Local `loop start --directory` / `-d`

#### `-v` usage locations:
1. cli.py:138 - Help text documentation for `--version`
2. cli.py:155-156 - Global `--version` / `-v` definition
3. cli.py:502 - Local `plan task list --verbose` / `-v`
4. cli.py:2133 - Local `entrypoint execute --vars` / `-v`
5. entry.py:18 - Early version detection

## Task 02: Flag Parsing Behavior Verification

### Test Results

#### Test 1: `-j` flag positioning
```bash
# FAILS - flag at end
$ agentic plan list -j
agentic: error: unrecognized arguments: -j

# WORKS - flag before subcommand
$ agentic -j plan list
{"plans": [...]}
```
**Status**: CONFIRMED BROKEN - Global flags not accepted at end

#### Test 2: Deep nesting with `-j`
```bash
# FAILS - deep nested command
$ agentic context bootstrap --role build-python -j
agentic: error: unrecognized arguments: -j

# WORKS - flag at beginning
$ agentic -j context bootstrap --role build-python
{"role": "build-python", ...}
```
**Status**: CONFIRMED BROKEN - Deep nesting fails with flags at end

#### Test 3: `-v` conflict with --verbose
```bash
# BROKEN - shows version instead of verbose task list
$ agentic plan task list -v
agentic 0.1.0

# WORKS - long form works correctly
$ agentic plan task list --verbose
Tasks in 260201CL_fix_global_flags_ordering
...
```
**Status**: CONFIRMED CONFLICT - Global `-v` captures flag before subparser

#### Test 4: `-d` conflict testing
```bash
# WORKS - local -d for --description
$ agentic plan init test-branch -d "Test description"
Plan initialized: 260201BR_test_description

# WORKS - local -d for --directory
$ agentic session spawn -p "test" -d /tmp
Command running in background with ID: b289281
```
**Status**: Currently works because flags before subcommand, but WILL CONFLICT if made global

## Findings Summary

### Confirmed Issues

1. **Global flags only work before subcommands**
   - `agentic -j plan list` ✓ works
   - `agentic plan list -j` ✗ fails
   - Affects all global flags: `-j`, `-d`, `-v`

2. **Flag conflicts prevent straightforward solution**
   - `-d` used by 4 different subcommands for local purposes
   - `-v` used by 2 different subcommands for local purposes
   - `-j` has NO conflicts (clean to fix)

3. **Current broken behavior**
   - `agentic plan task list -v` shows version, not verbose output
   - This is a bug caused by global flag capture

### Impact on Agents

Automated agents frequently append flags to commands:
- `agentic context bootstrap --role orchestration-executor -j` FAILS
- `agentic plan task current -j` FAILS
- `agentic plan task list -v` shows VERSION (wrong!)

This causes friction in:
- MCP orchestration server (works around by placing -j first)
- Agent bootstrap commands
- Test automation
- Scripted workflows

## Recommendations for Phase P2 (Implementation)

### Strategy 1: Shared Parent Parser (Preferred)
Create a parent parser with global flags and pass to all subparsers.

**Pros:**
- Standard argparse pattern
- Clean implementation
- Flags work at any position

**Cons:**
- Must handle conflicts explicitly
- Requires updating all `add_parser()` calls

### Strategy 2: Conflict Resolution Approaches

For `-j` (--json):
- NO conflicts - can add to all subparsers safely
- Implement via parent parser

For `-d` (--debug):
- CONFLICTS with: --description, --directory, --detail
- Options:
  1. Only allow long form `--debug` (remove `-d` globally)
  2. Only add `-d` to subparsers that don't conflict
  3. Let local flags take precedence (argparse default)

For `-v` (--version):
- CONFLICTS with: --verbose, --vars
- Options:
  1. Only allow long form `--version` (remove `-v` globally)
  2. Fix broken behavior: don't add to conflicting subparsers
  3. Change local flags to use different short forms

### Recommended Approach

1. **Implement parent parser with long-form-only global flags:**
   - `--json` (keep `-j`)
   - `--debug` (remove `-d`, long form only)
   - `--version` (remove `-v`, long form only)

2. **Update subparser creation:**
   - Create wrapper function for `add_parser()`
   - Auto-inject parent parser
   - Preserve existing local `-d` and `-v` flags

3. **Fix existing conflicts:**
   - Allow `agentic plan task list -v` to show verbose (not version)
   - Preserve all existing local flag behavior

## Files to Modify (Phase P2)

1. `/home/code/AgenticEngineering/modules/AgenticCLI/src/agenticcli/cli.py`
   - Create parent parser (new function)
   - Update all `add_parser()` calls to use parent
   - Remove `-d` and `-v` short forms from global flags

2. Testing required for:
   - `plan init -d` (should use local --description)
   - `session spawn -d` (should use local --directory)
   - `plan task list -v` (should use local --verbose)
   - All commands with `-j` at end (should work)

## Metrics

- Total subparsers in cli.py: ~70+
- Global flag definitions: 3 (`-j`, `-d`, `-v`)
- Flag conflicts found: 6 (4 for `-d`, 2 for `-v`)
- Commands tested: 5
- Confirmed failures: 2 (global flags at end)
- Confirmed conflicts: 1 (global `-v` capturing local `--verbose`)

## Conclusion

The audit confirms the issue and identifies a clear path forward:
1. `-j` can be safely propagated (no conflicts)
2. `-d` and `-v` have conflicts that require removing short forms globally
3. Implementation should use parent parser pattern
4. All existing local flags must be preserved
