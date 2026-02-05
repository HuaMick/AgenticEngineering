# CLI Remediation Plan

## Overview

This plan addresses two critical CLI issues discovered during execution of plan `260201CL_fix_global_flags_ordering`:

1. **Global Flags Regression**: The implementation broke the ability to use global flags before subcommands
2. **Task ID Disambiguation**: CLI cannot distinguish duplicate task IDs across different phases

## Issues Discovered

### Issue 1: Global Flags Regression

**Before the fix:**
- `agentic --json plan list` worked correctly
- `agentic -j plan list` worked correctly

**After the fix:**
- `agentic --json plan list` fails with "unrecognized arguments: --json"
- `agentic plan list -j` now works (intended behavior)

**Problem:** The implementation removed the original behavior while adding new behavior. This is a REGRESSION that breaks existing scripts and documentation.

**Required Fix:** Support global flags in BOTH positions:
- `agentic --json plan list` (original behavior)
- `agentic plan list --json` (new behavior)

### Issue 2: Task ID Disambiguation

**Current behavior:**
When multiple phases have tasks with the same ID (e.g., P1 has task "01", P2 has task "01"):
- `agentic plan task complete 01` completes the FIRST matching task (from P1)
- There is no way to specify which phase's task to complete

**Attempted solutions that failed:**
- `agentic plan task update P2.01 --status completed` - "Task not found"
- `agentic plan task update P2-01 --status completed` - "Task not found"

**Required Fix:** Support phase-qualified task IDs:
- `agentic plan task start P2-01` should target task "01" in phase P2
- `agentic plan task complete P2-01` should target task "01" in phase P2
- Backward compatibility: `agentic plan task complete 01` still completes first match

## Plan Structure

### Phase 1: Teach (plan_teach.yml)
Document requirements and design technical approach:
- Issue documentation with specific examples
- Requirements analysis
- Technical approach design for both fixes

### Phase 2: Build (plan_build.yml)
Implement the fixes:
- Investigation of current implementation
- Fix global flags regression (pre-parse approach)
- Fix task ID disambiguation (phase-qualified IDs)
- Update documentation

### Phase 3: Test (plan_test.yml)
Validate both fixes:
- Test global flags in all positions
- Test phase-qualified task IDs
- Integration testing
- Regression testing

### Phase 4: Audit & Cleanup (plan_audit_clean.yml)
Code quality and documentation:
- Code quality audit
- Update related documentation
- Remove obsolete comments and technical debt

## Execution

To execute this plan:

```bash
# 1. Start with teaching phase
agentic entrypoint execute _plan_teach --compile

# 2. Proceed to build phase
agentic entrypoint execute _plan_build --compile

# 3. Validate with test phase
agentic entrypoint execute _plan_test --compile

# 4. Final audit and cleanup
agentic entrypoint execute _plan_audit_clean --compile
```

## Success Criteria

- `agentic --json plan list` works (regression fixed)
- `agentic plan list --json` works (original fix preserved)
- `agentic plan task complete P2-01` updates correct task
- `agentic plan task complete 01` updates first match (backward compat)
- No new argparse conflicts introduced
- All tests pass
- Documentation updated

## Target Files

- `modules/AgenticCLI/src/agenticcli/cli.py` - Global flags parsing
- `modules/AgenticCLI/src/agenticcli/commands/plan.py` - Task ID handling

## Technical Notes

### Global Flags Pre-Parsing Approach

The fix should extract global flags from any position in `sys.argv` before passing to argparse:

1. Parse `sys.argv` to find `--json`, `-j`, `--debug`
2. Remove these flags from argv
3. Pass cleaned argv to argparse
4. Merge extracted flags with argparse results

### Phase-Qualified Task ID Format

Support these formats:
- `P2-01` (preferred, dash separator)
- `P2.01` (optional, dot separator)
- `01` (unqualified, backward compatible)

Parsing regex: `r'^(P\d+)[-.](.+)$'`

## Related Plans

- `260201CL_fix_global_flags_ordering` - Original plan that introduced Issue 1
