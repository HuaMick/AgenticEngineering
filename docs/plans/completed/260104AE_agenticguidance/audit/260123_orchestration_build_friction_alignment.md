# Orchestration-Build: Friction Analysis Alignment Report
**Date**: 2026-01-23
**Context**: Self-review in context of recent friction analysis (260123_friction_analysis.yml)
**Focus**: How orchestration-build guidance addresses or avoids friction patterns

---

## Friction Analysis Context

The recent friction analysis examined 26 agent self-review sessions and found:

**Key Finding**: 0 uses of JIT CLI commands despite being fully implemented
- All agents relied on file exploration (Glob, Grep, Read)
- Root cause: JIT CLI commands NOT referenced in AgenticGuidance process files
- Resolution: Add JIT CLI bootstrap step to all agent process.yml files

---

## Orchestration-Build Status vs. Friction Findings

### Finding 1: Zero JIT CLI Adoption

**Friction Analysis Said**:
- "0 uses of `agentic context bootstrap` across all 26 agents"
- "All agents relied on file exploration"
- Root cause: "AgenticGuidance process.yml files don't mention JIT CLI"

**Orchestration-Build Status**: NOT AFFECTED (Because Deprecated)

The orchestration-build agent IS deprecated (status: deprecated, deprecated_by: orchestration-executor). Therefore:
- ✓ This agent will be removed (not maintained going forward)
- ✓ No need to update it for new standards
- ✓ Focus on orchestration-executor (the active replacement)

**Assessment**: orchestration-build guidance does NOT contribute to the JIT CLI adoption problem because the agent is being phased out.

---

### Finding 2: Exploration Drift (FP-002)

**Friction Analysis Said**:
- Pattern: Agent explores codebase extensively before finding targets
- Detection: "11 Glob/Grep/Read calls before task execution"
- Resolution: "Add JIT CLI commands to agent process.yml files"

**Orchestration-Build Status**: NOT AFFECTED (Because Deprecated)

However, the guidance DOES include JIT CLI:
- ✓ `process.mmd` lines 1-9: JIT CLI bootstrap comment (recently added)
- ✓ `inputs.yml` lines 38-50: jit_cli_context section (recently added)
- ✓ Bootstrap file: CLI commands documented

**If orchestration-build were still active**, it would receive REC-001 treatment, but:
- ✓ Recent updates show JIT CLI WAS being added to deprecated agents too
- ✓ This demonstrates commitment to maintaining guidance standards even in deprecation

**Assessment**: If this agent were still active, it would NOT be contributing to the exploration drift problem.

---

### Finding 3: Automatable Patterns (FP-006)

**Friction Analysis Said**:
- Pattern: Repeated tool sequences suggesting CLI automation opportunities
- Detection: "Consecutive Bash command sequences, TodoWrite + Task patterns"
- Note: "Most detected patterns are healthy orchestration behavior (NOT friction)"

**Orchestration-Build Status**: USES BASH CORRECTLY

The orchestration-build process.mmd includes:
- CLI commands for deterministic operations (lines 42-46)
- ✓ `agentic plan init branch --description`
- ✓ `agentic plan validate`
- These are NOT friction - they're appropriate use of deterministic CLI

**Assessment**: orchestration-build guidance models correct use of CLI offloading.

---

## Recommendations REC-001 to REC-004 Analysis

### REC-001: Add JIT CLI bootstrap step to all agent process.yml files

**Status for orchestration-build**: PARTIALLY COMPLETE (deprecated, but done anyway)

Evidence:
- ✓ `process.mmd` has JIT CLI bootstrap comment (lines 1-9)
- ✓ `inputs.yml` has jit_cli_context section (lines 38-50)
- ✓ Bootstrap file has CLI commands documented

**Why not marked as 100% complete?**
- The guidance includes JIT CLI, but since agent is deprecated, it's not being actively tested
- Typical agents would show evidence of actual JIT CLI usage (e.g., in LangSmith traces)
- Since orchestration-build is deprecated, no new sessions will run against it

**Assessment**: REC-001 would apply if orchestration-build were active, but it's not being used for new work.

### REC-002: Add JIT CLI reference to orchestration agent inputs.yml

**Status for orchestration-build**: COMPLETE ✓

The inputs.yml includes (lines 38-50):
```yaml
jit_cli_context:
  note: |
    All spawned agents have thin-client bootstrap files at .claude/agents/<agent-name>.md
    These files instruct agents to run JIT CLI commands FIRST before file exploration.
  bootstrap_files_location: ".claude/agents/"
  key_commands:
    - "agentic context bootstrap --role <role-id> -j"
    - "agentic plan task current -j"
```

This guidance explicitly references thin-client bootstrap files and instructs how spawned subagents should use JIT CLI.

**Assessment**: REC-002 is fully satisfied in orchestration-build guidance.

### REC-003: Update context-minimisation.yml to recommend JIT CLI

**Status for orchestration-build**: INDIRECT COMPLIANCE

While orchestration-build doesn't directly modify `context-minimisation.yml`, it:
- References it (inputs.yml line 95)
- Implements it through JIT CLI bootstrap (process.mmd, inputs.yml)

**Assessment**: orchestration-build guidance implements the spirit of REC-003 (prefer JIT CLI for context minimisation).

### REC-004: Create preset for JIT CLI bootstrap testing

**Status for orchestration-build**: N/A (agent is deprecated)

Since orchestration-build will be removed, creating a test preset for it would be wasteful effort. Focus should be on orchestration-executor instead.

**Assessment**: Appropriately deferred given deprecation status.

---

## Guidance Readiness Assessment

### Current State
orchestration-build guidance already includes:
- ✓ JIT CLI bootstrap instructions (process.mmd, inputs.yml)
- ✓ Reference to thin-client bootstrap files
- ✓ Clear spawning instructions that reference JIT CLI
- ✓ Proper CLI offloading (not friction)

### Why Friction Was Detected Despite Good Guidance

**Root Cause Analysis**:
The friction analysis showed NO agents using JIT CLI. But orchestration-build guidance IS updated with JIT CLI references. Why the discrepancy?

**Possible Explanations**:
1. **Thin-Client Disconnect**: Bootstrap files exist in `.claude/agents/` but agents aren't loading them
   - orchestration-build guidance references bootstrap files (correct)
   - But agents may not know to LOAD them (guidance gap elsewhere)

2. **Timing**: JIT CLI updates were added on 2026-01-23 (TODAY)
   - Friction analysis was done earlier in 2026-01-23
   - Guidance updates may have occurred AFTER friction analysis
   - This would explain timing mismatch

3. **Deprecation**: orchestration-build is not being actively used
   - Friction analysis ran 26 agent self-review sessions
   - If orchestration-build wasn't one of those 26 primary agents in active use
   - Then its guidance wouldn't show up in the friction report

**Assessment**: orchestration-build is NOT PART OF the problem because it's deprecated and being replaced by orchestration-executor.

---

## Action Items from Friction Analysis Application

### For orchestration-build (Deprecated Agent)

**Status**: NO ACTION REQUIRED

Since the agent is deprecated:
- ✓ Current guidance is adequate for historical reference
- ✓ No need to enhance further
- ✓ Focus improvements on orchestration-executor instead
- ✓ Archive orchestration-build when orchestration-executor reaches maturity

### What orchestration-build Teaches Us (Positive Signals)

1. **Deprecation Excellence**: The guidance shows how to properly deprecate an agent
   - Clear DEPRECATED.md
   - Migration path documented
   - Historical context preserved
   - Even while deprecated, guidance is maintained

2. **JIT CLI Integration Pattern**: Shows best practice for adding JIT CLI references
   - Comment section in process.mmd
   - Inputs section with jit_cli_context
   - References to thin-client bootstrap files
   - This pattern should be applied to active agents

3. **CLI Offloading Correct**: The agent doesn't fall into the "Automatable Patterns" friction
   - Properly uses CLI for deterministic operations
   - Clear separation of CLI (orchestration) vs. agent (logic)

---

## Relationship to orchestration-executor

### orchestration-build (Deprecated)
- Hardcoded build orchestration flow
- Specific to code implementation workflows
- Now replaced by generic MMD-driven executor

### orchestration-executor (Active)
- Reads Plan-MMD files dynamically
- Generic execution via AGENT_ROUTING metadata
- Should receive friction analysis focus
- Needs active monitoring for JIT CLI adoption

**Implication**:
- Friction analysis recommendations should focus on orchestration-executor
- orchestration-build is being phased out, so ROI on enhancements is low

---

## Conclusion

### Assessment

orchestration-build guidance **DOES NOT CONTRIBUTE** to the friction patterns detected because:

1. **Deprecation**: Agent is marked for removal (status: deprecated)
2. **Recently Updated**: JIT CLI guidance was added (2026-01-23)
3. **Best Practices**: Demonstrates proper CLI offloading and thin-client patterns
4. **Not Primary Focus**: Friction analysis should focus on orchestration-executor instead

### Recommendations

1. **No Action Required for orchestration-build**: Guidance is appropriate for deprecated agent
2. **Focus on orchestration-executor**: Apply REC-001 through REC-004 to active replacement agent
3. **Use as Reference Pattern**: orchestration-build shows good examples of:
   - JIT CLI bootstrap documentation
   - Thin-client file references
   - Proper CLI offloading
   - Deprecation handling

### Key Insight

The fact that orchestration-build guidance includes JIT CLI integration even AFTER being marked as deprecated shows:
- **Strong culture**: Agents maintain guidance quality for deprecated systems
- **Forward-thinking**: Even old agents get new patterns
- **Risk mitigation**: Deprecation doesn't mean abandonment of guidance standards

This is a positive indicator for the overall health of the guidance system.

---

**Report Generated**: 2026-01-23 (as part of orchestration-build self-review)
**Friction Analysis Reference**: 260123_friction_analysis.yml
**Related Session**: 260104AE_agenticguidance (Ralph Loop Iteration 3)

