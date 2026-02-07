# Interactive Wizard CLI - Hybrid Approach
**Plan ID:** 260207IW  
**Created:** 2026-02-07  
**Status:** Deferred  

## Objective

Implement a hybrid CLI interaction model that combines the token efficiency of args-based commands with the agent constraint benefits of interactive/wizard-style prompts.

## Background

Research indicates trade-offs between two CLI interaction patterns for AI agents:

| Aspect | Single Command + Args | Interactive/Wizard Style |
|--------|----------------------|--------------------------|
| **Token Efficiency** | ✅ Lower - one call, minimal overhead | ❌ Higher - multiple turns, prompts, confirmations |
| **Agent Constraint** | ❌ Agent must know all args upfront | ✅ Drip-feeds context, constrained choices |
| **Error Recovery** | ❌ Fail at end if wrong args | ✅ Can clarify/correct mid-flow |
| **Automation** | ✅ Easy to script/reproduce | ❌ Harder to automate |
| **Thinking Iterations** | ✅ One decision point | ❌ Many decision points |

## Proposed Solution

A hybrid approach that:
1. **Keeps args-based commands** as the default for automation efficiency
2. **Adds `--interactive` flag** for guided mode when agents need exploration
3. **Provides `--options --json`** to let agents discover valid choices before calling

Example flow:
```bash
# Agent queries what options exist
agentic plan spawn --options --json
# Returns: {"types": ["guidance-update", "build", "bugfix"], "required": ["plan_id"]}

# Agent then makes informed single call
agentic plan spawn --type guidance-update --plan 260207XX
```

## Plan Files

| File | Description |
|------|-------------|
| `plan_userstories.yml` | **First Step** - Map all user stories for CLI command combinations |
| `plan_research.yml` | Document research findings on agent CLI interaction patterns |
| `plan_build.yml` | Implementation tasks for hybrid CLI features |
| `plan_test.yml` | Testing plan including UAT against user stories |

## Dependencies

- Existing user stories in `docs/userstories/MyAgents/`
- CLI implementation in `modules/AgenticCLI/`
- Understanding of current command structure

## Deferred Reason

Not prioritized for current iteration. To be picked up when CLI interaction patterns need optimization based on observed agent behavior.
