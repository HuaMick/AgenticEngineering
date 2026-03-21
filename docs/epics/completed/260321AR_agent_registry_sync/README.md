# 260321AR: Sync KNOWN_AGENTS Registry with Disk Agents

## Problem

`KNOWN_AGENTS` in `modules/AgenticCLI/src/agenticcli/commands/agent_help.py` (lines 19-46) lists only 20 agents, but 28 agents exist on disk. The `AGENT_CATEGORIES` dict (lines 49-70) has the same gap. This means `is_agent_name()` returns False and `agentic agent help <name>` fails for 8 valid agents.

## Missing Agents (exist on disk, not in registry)

| Agent | Category | Disk path |
|-------|----------|-----------|
| `build-agentic-docs` | build | `agents/build/build-agentic-docs/` |
| `epic-creator` | planner | `agents/planner/epic-creator/` |
| `orchestration-loop` | orchestration | `agents/orchestration/orchestration-loop/` |
| `planner-explore` | planner | `agents/planner/planner-explore/` |
| `planner-orchestration` | planner | `agents/planner/planner-orchestration/` |
| `planner-sdk` | planner | `agents/planner/planner-sdk/` |
| `story-writer` | planner | `agents/planner/story-writer/` |
| `test-cleaner` | test | `agents/test/test-cleaner/` |

## Scope

1. Add all 8 missing agents to `KNOWN_AGENTS` list
2. Add all 8 to `AGENT_CATEGORIES` dict under correct categories
3. Update `test_all_agents_registered` count assertion
4. Update category count assertions in `test_agent_help.py`
5. Consider: auto-discover agents from disk instead of hardcoding

## Files

- `modules/AgenticCLI/src/agenticcli/commands/agent_help.py` (lines 19-70)
- `modules/AgenticCLI/tests/test_agent_help.py`
