# Plan: 260114CL_context_entrypoints

## Status: DECOMMISSIONED

**Decommissioned**: 2026-01-22
**Reason**: Consolidated into 261115CL_agenticcli planning folder

---

## REDIRECT NOTICE

This planning folder has been **DECOMMISSIONED** and its contents have been moved to:

**New Location**: `docs/plans/live/261115CL_agenticcli/`

### Files Moved

| Original File | New Location |
|---------------|--------------|
| `plan.yml` | `261115CL_agenticcli/plan_jit_context.yml` |
| `specification.md` | `261115CL_agenticcli/specification.md` |
| `live/plan_live_build.yml` | `261115CL_agenticcli/live/plan_live_build.yml` |
| `live/plan_live_test.yml` | `261115CL_agenticcli/live/plan_live_test.yml` |
| `live/orchestration_jit_context.mmd` | `261115CL_agenticcli/live/orchestration_jit_context.mmd` |

### Coordination Document

A new coordination file was created at:
`261115CL_agenticcli/live/plan_live_jit_context_entrypoints.yml`

### Rationale

The JIT Context Entrypoints work is fundamentally a CLI feature enhancement. Consolidating it with the AgenticCLI planning folder:

1. Groups related CLI work together
2. Reduces planning folder proliferation
3. Allows tracking alongside other CLI initiatives

---

## Original Overview (Archived)

Implements JIT (Just-In-Time) Pull-based context architecture for agents. Evolves from current "Push" model to a "Pull" model where agents fetch exactly what they need via CLI.

**Key Deliverables:**
1. CLI Context Commands: `agentic context bootstrap|role|task|inputs`
2. CLI Plan Tools: `agentic plan task status|update|current`
3. Main-First Plan Resolution
4. Thin-Client Agent Migration

---

**This folder can be safely removed after confirming all references are updated.**
