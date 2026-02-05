# Plan: Refactor and Formalize MCP GUI Integration

## Objective
Solidify the MCP GUI integration into the Agentic CLI by refactoring the ad-hoc implementation into a robust, tested, and standardized architecture.

## Context
Initial implementation of the MCP GUI was done as a spike/technical achievement. This plan formalizes that work by moving to a better architectural foundation.

## Phases
1. **P1: Foundation & Asset Management** - Move HTML/CSS to consolidated assets.
2. **P2: Implementation Refactoring** - Clean up `orchestration_server.py` and CLI subcommands.
3. **P3: Testing & Validation** - Add unit and integration tests.
4. **P4: Hardening & Error Handling** - Ensure security and graceful degradation.
5. **P5: UAT & Final Polish** - Full verification in a real Claude Code session.

## Key Files
- `plan_build.yml`: Core build tasks.
- `orchestration_*.mmd`: Orchestration flowchart.

## Success Criteria
- [ ] Subcommand `agentic plan orchestration dashboard` works with both `--browser` and `--mcp`.
- [ ] HTML template is loaded from assets, not hardcoded.
- [ ] At least 80% test coverage for the new dashboard logic.
- [ ] Clear error messages when optional `mcp` dependency is missing.
