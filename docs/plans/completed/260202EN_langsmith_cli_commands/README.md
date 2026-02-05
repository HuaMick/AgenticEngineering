# LangSmith CLI Commands Enhancement Plan

**Status:** PENDING
**Branch:** feature/langsmith-cli-enhancements
**Worktree:** /home/code/AgenticEngineering-feature/langsmith-cli-enhancements
**Created:** 2026-02-02

## Summary

Formalize temporary forensic scripts into permanent CLI commands for LangSmith trace analysis and friction pattern detection. This is a lightweight enhancement to the existing LangSmith CLI integration.

## Background

Temporary forensic scripts were created to analyze LangSmith traces for friction patterns during orchestration enforcement investigations. These ad-hoc scripts proved valuable for debugging and should be formalized as CLI commands for regular use.

## Existing Implementation

The `agentic langsmith` command group already exists with:
- `runs` - List recent runs with filtering
- `run <id>` - Show detailed run information
- `projects` - List all projects
- `stats` - Show project statistics
- `friction` - Analyze traces for friction patterns
- `sessions` - List recent sessions with run counts

Implementation: `modules/AgenticCLI/src/agenticcli/commands/langsmith.py`

## Proposed Enhancements

Add or enhance these commands to match the capabilities of the temporary forensic scripts:

1. **session-analyze** - Analyze session runs in detail
   - Group runs by session_id
   - Show session timeline
   - Identify session patterns
   - Export session data for further analysis

2. **batch-search** - Search traces for patterns across multiple sessions
   - Pattern matching across runs
   - Batch filtering by criteria
   - CSV/JSON export of results
   - Support for regex patterns

3. **run-inspect** - Enhanced detailed run inspection
   - Expand existing `run` command capabilities
   - Show parent/child run relationships
   - Display full trace hierarchy
   - Include timing breakdown

4. **friction-report** - Generate comprehensive friction report
   - Build on existing `friction` command
   - Export to markdown/JSON formats
   - Include resolution recommendations
   - Link to RLM patterns where applicable

## RLM Integration

The friction analysis entrypoint (`modules/AgenticGuidance/entrypoints/_analyze_friction.yml`) references RLM (Recursive Language Model) patterns. RLM specifications exist in:
- `modules/AgenticGuidance/assets/specifications/rlm-context-accessor.yml`
- `modules/AgenticGuidance/assets/definitions/rlm-patterns.yml`

**This plan includes implementing CLI support for RLM patterns** to enable:
- Context accumulation across sessions (ACCUMULATOR_* variables)
- Named context storage (CONTEXT_* variables)
- RLM validation for large trace datasets (100+ traces)
- Bounded recursion enforcement (max_depth limits)

Reference: https://lnkd.in/gDXVnFm7

## Scope

IN SCOPE:
- Enhance existing LangSmith CLI commands
- Add new forensic analysis commands
- Improve output formatting and export options
- Better session-based filtering and analysis
- RLM context accessor CLI implementation
- RLM variable support (ACCUMULATOR_*, CONTEXT_*)

OUT OF SCOPE:
- Backend service changes (AgenticLangSmith module)
- New friction pattern detection algorithms
- LangSmith API changes

## Success Criteria

1. All proposed commands implemented and tested
2. Commands produce useful output for debugging
3. Export options work correctly (JSON/CSV/Markdown)
4. Documentation updated with new command usage
5. Backward compatibility maintained with existing commands

## Folder Structure

```
260202EN_langsmith_cli_commands/
├── README.md                      # This file
├── orchestration.mmd              # Simple orchestration flowchart
└── plan_build.yml                 # Build plan with tasks
```

## Next Steps

1. Review existing langsmith.py implementation
2. Define command signatures and options
3. Implement enhanced commands
4. Add tests for new functionality
5. Update CLI documentation
