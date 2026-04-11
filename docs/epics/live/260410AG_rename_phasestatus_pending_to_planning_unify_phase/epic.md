# Rename PhaseStatus.pending → planning

## Motivation

Phase status terminology is currently inconsistent across the codebase. The `PhaseStatus` enum uses `pending`, but `format_status()` in `agenticcli/console.py` has a legacy alias that rewrites `pending → planning` at display time. The result: the TinyDB record says `pending`, the `phase list` table shows `planning`, and the `phase update` warning message says `pending → completed`. Three voices, three words, one lifecycle.

The `EpicStatus` enum already uses `planning`. Unifying `PhaseStatus` on the same term eliminates the display alias hack and gives both epics and phases a consistent vocabulary.

## Scope

Rename `PhaseStatus.PENDING` → `PhaseStatus.PLANNING` (enum value `"planning"`). Remove the display-layer legacy alias. Migrate existing TinyDB records. Update all code, tests, schemas, and documentation that reference phase status `"pending"`.

**Note:** `TicketStatus.PENDING` (for tickets/tasks, not phases) is NOT in scope — tickets legitimately use `pending`. Only phase-level status is being renamed.

## Known touch-points

- `modules/AgenticGuidance/src/agenticguidance/services/epic.py` — `PhaseStatus` enum definition
- `modules/AgenticGuidance/src/agenticguidance/services/epic_repository.py` — `add_phase` default, status validation
- `modules/AgenticCLI/src/agenticcli/commands/epic.py`:
  - `cmd_phase_add` (line ~2243) — `"status": "pending"` default
  - `cmd_phase_update` (line ~2434) — transition map hardcoded "pending"
  - `cmd_phase_list` (line ~2327) — default fallback `phase.status or "pending"`
  - Phase rendering in epic status (line ~913)
- `modules/AgenticCLI/src/agenticcli/console.py` — remove `"pending": "planning"` legacy alias from `format_status` (lines 192–194)
- `modules/AgenticCLI/src/agenticcli/workflows/orchestration.py` — any phase pending checks
- `modules/AgenticGuidance/assets/specifications/plan-schema.yml` — phase status enum
- `modules/AgenticGuidance/assets/specifications/orchestration-executor-specification.yml` — phase status docs
- `modules/AgenticCLI/src/agenticcli/templates/mmd/header.mmd.j2` — legacy template references
- Tests under `modules/AgenticCLI/tests/` and `modules/AgenticGuidance/tests/` that assert phase status `"pending"`
- One-shot TinyDB migration: rewrite any existing phase records with `status == "pending"` → `"planning"`

## Success criteria

1. `PhaseStatus` enum has no `PENDING` member; `PLANNING = "planning"` is present.
2. `agentic epic phase add` creates phases with DB status `"planning"` (verifiable with JSON output).
3. `agentic epic phase list` displays `"planning"` for new phases, and the displayed value matches the DB value exactly (no aliasing).
4. `agentic epic phase update` warning messages use `"planning"` as the prior-status term where applicable.
5. `format_status()` no longer contains the `pending → planning` legacy alias for phase statuses.
6. Existing TinyDB phase records (if any) with `status: "pending"` are migrated to `"planning"` — no orphaned legacy values after upgrade.
7. Full test suite passes: `AgenticGuidance` tests + `AgenticCLI` tests.
8. Story US-PLN-047 `starting_state` and UAT plan wording is updated to match the new canonical terminology.
9. `TicketStatus.pending` is untouched — only phase-level status changed.

## Out of scope

- Renaming `TicketStatus.PENDING` (tickets keep `pending`).
- Adding `--dry-run` to `agentic orchestrate session implement` (separate concern).
- Any changes to `EpicStatus` (already uses `planning`).
