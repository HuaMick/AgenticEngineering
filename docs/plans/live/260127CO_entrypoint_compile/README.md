# Plan: Entrypoint Compile Flag (260127CO)

## Objective
Add `--compile` flag to `agentic entrypoint execute` that recursively resolves all file references and outputs a complete context bundle.

## Problem
Entrypoints reference other files (orchestration MMD, inputs.yml) which themselves reference 20+ more files. Agents currently must use Read/Glob/Grep tools manually to build their initial context.

## Solution
Single command compiles everything into one output:
```bash
agentic entrypoint execute _plan_teach --compile
```

## Output Format
```
# === ENTRYPOINT: _plan_teach ===
<yaml content>

# === ORCHESTRATION: process.mmd ===
<mmd content>

# === INPUTS: inputs.yml ===
<inputs.yml content>

# === REFERENCED: fix-the-source.yml ===
<content>
...
```

## Files Modified
- `modules/AgenticCLI/src/agenticcli/commands/entrypoint.py`

## Phases
1. **Build Phase** (6 tasks): Add argument, implement helpers, update cmd_execute
2. **Validation Phase** (2 tasks): Manual blind test, unit tests
3. **Cleanup Phase** (2 tasks): Linting, full test suite

## Worktree
- Branch: `feat/entrypoint-compile`
- Path: `/home/code/AgenticEngineering-feat/entrypoint-compile`

## Plan Files
- `plan_build.yml` - Detailed tasks and implementation notes
