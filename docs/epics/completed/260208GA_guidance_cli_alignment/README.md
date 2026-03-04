# Guidance-CLI Alignment

## Problem
Multiple agent guidance files reference CLI commands with wrong signatures, missing parameters, or behaviors that aren't enforced. This causes agents to generate commands that fail at runtime.

## Gaps Found

### Critical
1. **`agentic loop start <loop-type>`** - Guidance says positional loop-type arg + `--plan` flag. CLI actually takes `--prompt`/`--entrypoint`/`--prompt-file`. No positional arg, no `--plan`.
   - Files: cli-commands.yml:333, orchestration-executor/process.yml:80
   - CLI: cli.py:733-754

2. **`agentic session spawn --worktree`** - Guidance documents `--worktree` flag. CLI has `--directory` instead.
   - Files: cli-commands.yml:267,276,293

3. **`agentic loop status [<loop-id>]`** - Guidance says loop-id is optional. CLI requires it.
   - Files: cli-commands.yml:373, cli.py:766-769

4. **`agentic loop history [<loop-id>]`** - Guidance says optional positional arg. CLI has no positional arg, has undocumented `--active` and `--status` flags.
   - Files: cli-commands.yml:387-395, cli.py:772-783

### Medium
5. **Short-name resolution** - plans.yml says "NOT supported", but CLI actually implements partial folder name matching via startswith().
   - Files: plans.yml:80-90, plan.py:186-244

6. **Agent-routing validation** - plan-mmd-schema.yml requires AGENT_ROUTING validation as HARD FAIL. `agentic plan validate` doesn't check it.

7. **Loop type validation** - agent-loops.yml defines valid loop types. CLI doesn't validate against this list.

8. **Parallel task execution** - orchestration-executor-specification.yml describes target_files overlap grouping. Not implemented.

## Open Questions
- Q1: Should we fix guidance to match CLI, or fix CLI to match guidance? (Per-gap decision needed)
- Q2: For the loop command, should we add the structured loop-type pattern or keep the generic prompt-based approach?
- Q3: Should `--worktree` be added as an alias for `--directory` in session spawn, or just update docs?
- Q4: Is parallel task execution a priority, or can we defer it?

## Scope
- Audit every CLI command referenced in guidance files
- Fix either guidance or CLI for each gap (direction TBD per open question)
- Update all process.yml files that reference wrong signatures
- Add integration tests for corrected commands
