# Epic: Reduce Orchestration Context Overflow

## Objective

Investigate and address the root causes of meta orchestration sessions running out of
context window during plan execution. The orchestration agent sits on top of sub-agent
sessions, managing their lifecycle. When the context fills up, the orchestration session
can no longer function and compaction fails entirely.

## Background

On 2026-03-02, the meta orchestration session `3ee29cd2` (slug: `golden-mapping-kitten`)
ran out of context after 54 turns while executing the `260301RE_remap_plan_task_to_epic_ticket`
epic. The session spawned 22 concurrent sub-agents and exhausted its context window,
resulting in a compaction failure:

```
Error: Error during compaction: Error: Conversation too long.
Press esc twice to go up a few messages and try again.
```

## Diagnostic Findings

### Session Profile

| Metric | Value |
|--------|-------|
| Session ID | `3ee29cd2-72e1-445d-bff8-bca8f59bc787` |
| Slug | `golden-mapping-kitten` |
| JSONL size | 5.7 MB |
| User messages | 72 |
| Assistant messages | 83 |
| Progress events | 34 |
| Sub-agents spawned | 22 |
| Sub-agent data | 5.2 MB |
| LangSmith traced turns | 54 (turns 1-54) |
| Duration | ~12 minutes (09:15–09:27 AEDT) |

### Turn-by-Turn Context Growth (LangSmith trace data)

The orchestration session showed a clear pattern of context accumulation:

- **Turns 1-11**: Plan discovery — reading plan files, task lists, orchestration MMD.
  Input sizes ranged 0.1-45 KB. The session loaded plan manifests (some up to 45 KB).
- **Turns 12-35**: Sub-agent spawning — 22 agents launched sequentially, each returning
  `Async agent launched successfully` confirmations. Tasks marked as `in_progress`.
  Input sizes ~0.8 KB per turn.
- **Turns 36-45**: Poll cycle 1 — task completions start coming in (teach_03, teach_05,
  teach_02, teach_07, teach_08, teach_04). Input sizes 0.1-0.7 KB.
- **Turns 46-54**: Agent retrieval payloads — **each turn injected ~35 KB** of agent
  retrieval data (`<retrieval_status>not_ready</retrieval_status>` or `success` with
  full agent output). This is where context growth accelerated dramatically.

### Key Finding: Agent Retrieval Payload Size

The most significant contributor to context overflow was the **agent retrieval payloads**
returned during sub-agent polling. Each retrieval injected the agent's full output
(~35 KB per retrieval) directly into the orchestration session's context.

With 22 sub-agents being polled, a single poll cycle across all agents adds
approximately **770 KB** (22 × 35 KB) to context. Multiple poll cycles compound this
to megabytes of accumulated retrieval data.

### Context Budget Analysis

| Context Component | Approx. Size | Notes |
|-------------------|-------------|-------|
| System prompt + guidance | ~50 KB | Fixed overhead |
| Plan manifests (6 files) | ~100 KB | Loaded at startup |
| Agent launch messages (22×) | ~20 KB | 22 launch confirmations |
| Task status updates | ~10 KB | Various mark-as-in-progress |
| Agent retrieval payloads | **~770 KB per poll cycle** | 22 agents × ~35 KB each |
| Assistant reasoning | ~50 KB | Claude's responses |

A single complete poll cycle of all 22 agents consumes a significant portion of
the context window. After 2-3 cycles with responses and reasoning, the window is
exhausted.

### Trace Infrastructure Note

The LangSmith stop hook only captures the **newest message per turn** (1 message per
trace), not the cumulative conversation history. The input sizes shown in traces
represent individual message sizes, not total context. The actual context window
includes all accumulated messages from all prior turns.

## Scope

This epic should focus on the agent retrieval payload issue specifically. The findings
above should inform a dedicated planning session to design solutions.

## Status

Status: needs_planning
Created: 2026-03-03
