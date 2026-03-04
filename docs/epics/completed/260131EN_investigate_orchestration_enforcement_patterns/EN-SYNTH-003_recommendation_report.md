# Orchestration Enforcement Investigation: Final Recommendations

**Investigation ID:** 260131EN_investigate_orchestration_enforcement_patterns
**Report Date:** 2026-02-01
**Report Author:** Synthesis Agent (Task: EN-SYNTH-003)
**Status:** Final Recommendation

---

## Executive Summary

This investigation evaluated six proposals for improving orchestration enforcement in the Agentic Engineering framework. After comprehensive analysis of infrastructure readiness, implementation complexity, and value delivery, we recommend a **phased implementation approach** starting with foundational environment-based context injection (P3) and role detection (P4), followed by MMD-based task structure preloading (P2).

### Key Findings

- **All six proposals are technically feasible** with varying levels of complexity and effort
- **Foundational proposals (P3, P4) are critical enablers** for all role-based enforcement
- **High-value, low-risk proposal (P2) provides immediate structure visibility** without enforcement gaps
- **Infrastructure is 55-85% ready** across proposals, with tmux patterns (P5) most ready at 85%
- **Total effort ranges from 400-440 hours (MVP) to 711-886 hours (comprehensive)**

### Primary Recommendation

**Implement P3 + P4 + P2 as Minimum Viable Product (MVP)**
- Phase 1: Environment-based context injection (P3) - 80-100 hours
- Phase 2: Role detection and enforcement (P4) - 280 hours
- Phase 3: MMD-to-tasklist transformation (P2) - 40-60 hours
- **Total MVP effort: 400-440 hours over 10-15 weeks**

### Deferred Proposals

- **P1 (CLI Tasklist Tracking)**: Defer full implementation; implement Quick Wins only (20-32 hours)
- **P5 (Tmux Session Patterns)**: Defer until P3+P4 foundation validated (250-350 hours)
- **P6 (Bootstrap Plan Generation)**: Defer until P2 validated (61-96 hours)

---

## Investigation Overview

### Background and Motivation

The Agentic Engineering framework uses orchestration patterns where a main orchestrator agent spawns specialized subagents to complete tasks. Current enforcement relies on agent discipline and process guidance, with no hard boundaries to prevent:
- Subagents spawning additional orchestrators
- Subagents archiving or moving plan folders
- Agents claiming unassigned tasks
- Sessions operating without orchestration context

This investigation was initiated to evaluate systematic enforcement mechanisms that provide graduated boundaries (advisory, warning, blocking) while maintaining backward compatibility and minimizing implementation complexity.

### Scope

Six proposals were investigated over 18 detailed analysis tasks:

1. **P1: CLI Tasklist Orchestration Tracking** - Extend CLI task commands for gate validation, dependencies, and enforcement
2. **P2: Preloaded Tasklists at Plan Start** - Parse orchestration MMD files to generate structured tasklists
3. **P3: Session Spawn Context Injection** - Inject orchestration context via environment variables at session spawn
4. **P4: Main Session Detection/Identification** - Detect session roles and enforce role-appropriate behaviors
5. **P5: Tmux Session Management Patterns** - Leverage tmux infrastructure for session hierarchy enforcement
6. **P6: Bootstrap-time Plan Auto-generation** - Generate agent-specific task files from process.yml

### Investigation Methodology

Each proposal underwent three-phase analysis:
1. **Infrastructure Audit**: Assess readiness and integration points
2. **Pattern Analysis**: Review existing implementations and validate approach
3. **Design and Estimation**: Detailed implementation plan with effort estimates

Investigation deliverables:
- 18 detailed analysis documents (EN-P1-002 through EN-P6-003)
- Proposal comparison matrix (EN-SYNTH-001)
- Quick wins and immediate actions analysis (EN-SYNTH-002)
- This final recommendation report (EN-SYNTH-003)

---

## Key Findings

### P1: CLI Tasklist Orchestration Tracking

**Complexity:** MEDIUM | **Effort:** 80-100 hours | **Risk:** MEDIUM | **Value:** MEDIUM-HIGH

**Summary:** Extends existing CLI tasklist commands with gate validation, enforced dependencies, and completion hooks. Builds on 70% ready infrastructure.

**Strengths:**
- Builds on existing CLI infrastructure (task commands already exist)
- File-based state persists across session restarts
- Human-readable and debuggable (YAML files)
- Incremental implementation provides immediate value

**Weaknesses:**
- **Critical enforcement gap**: Agents can bypass via direct YAML edits
- Enforcement depends on agent discipline (opt-in, not hard boundaries)
- CLI overhead affects context efficiency
- 7 gaps identified requiring ~100 hours to address

**Verdict:** Defer full implementation. **Implement Quick Wins only** (simplified commands, event logging) for 20-32 hours of effort with immediate value.

---

### P2: Preloaded Tasklists at Plan Start

**Complexity:** MEDIUM | **Effort:** 40-60 hours | **Risk:** LOW | **Value:** HIGH

**Summary:** Parses orchestration MMD files at plan start to generate structured tasklists that are preloaded into orchestrator and agent contexts.

**Strengths:**
- **High value, low risk** - best effort-to-value ratio
- 75% infrastructure ready (entrypoint execute exists, MMD format 90% consistent)
- Natural extension point at `entrypoint execute --compile`
- Provides immediate plan structure visibility
- Enables progress reporting (X of Y tasks complete)
- Foundation for other proposals (P1 can consume these tasklists, P6 can extend)

**Weaknesses:**
- MMD format variations from manual editing (mitigated with schema validation)
- Circular dependencies in edge parsing (detection included)
- Agent routing mismatch potential (validation against KNOWN_AGENTS)

**Implementation Approach:**
- 5-stage transformation pipeline: metadata → phases → tasks → dependencies → tasklist
- Integration at `_compile_context()` in entrypoint.py
- Agent-specific filtering by AGENT_ROUTING metadata
- Validation command for MMD-to-YAML consistency

**Verdict:** **Implement in Phase 2** (after P3, parallel with P4). Provides structure visibility that complements enforcement foundation.

---

### P3: Session Spawn Context Injection

**Complexity:** LOW-MEDIUM | **Effort:** 80-100 hours | **Risk:** LOW | **Value:** HIGH

**Summary:** Inject orchestration context (role, task, plan, parent session) into spawned Claude Code sessions via environment variables and optional prompt prefixes.

**Strengths:**
- **FOUNDATIONAL** - all role-based enforcement proposals depend on this
- Industry-validated approach (environment variables standard practice)
- Zero-latency role detection
- Propagates to all subprocess tools
- Works for both LLM and tool scripts
- No file I/O overhead

**Weaknesses:**
- Environment variables can be overwritten by agent (mitigated: session registry is authoritative)
- Token overhead from prompt prefix (mitigated: opt-in via --inject-context, 50-100 tokens)

**Implementation Approach:**
- Add CLI arguments: --role, --task, --plan, --parent-session, --phase
- Build spawn_env dict with AGENTIC_* variables
- Update session record schema with orchestration fields
- Optional prompt prefix injection for redundancy

**Environment Variables:**
- AGENTIC_SESSION_ID: Unique identifier
- AGENTIC_SESSION_ROLE: orchestrator | subagent
- AGENTIC_TASK_ID: Assigned task identifier
- AGENTIC_PLAN_FOLDER: Plan folder path
- AGENTIC_PARENT_SESSION: Parent session UUID
- AGENTIC_PHASE: Current orchestration phase

**Verdict:** **Implement in Phase 1** (critical path). This is the foundational enabler for all role-based proposals.

---

### P4: Main Session Detection/Identification

**Complexity:** MEDIUM | **Effort:** 280 hours | **Risk:** MEDIUM | **Value:** HIGH

**Summary:** Detect session roles (orchestrator vs subagent) and enforce role-appropriate behaviors through CLI command restrictions and guidance.

**Strengths:**
- Provides **enforcement layer** for orchestration boundaries
- Multi-layer detection (environment vars → session registry → heuristics)
- Graduated enforcement levels (advisory, warning, blocking)
- Clear error messages guide agents to correct behaviors
- Builds on P3's context injection

**Weaknesses:**
- Environment variable tampering possible (mitigated: session registry authoritative, defense-in-depth)
- Subagent escape via --force (mitigated: only overrides WARNING, not BLOCKING)

**Implementation Approach:**
- Create `orchestration/enforcement.py` module with RoleEnforcer class
- Implement 3-layer detection strategy (env vars → registry → inference)
- Add enforcement hooks to CLI commands (spawn, archive/move, task complete)
- Graduated enforcement levels with --force override for warnings

**Role Permissions Matrix:**

| Operation | Orchestrator | Subagent |
|-----------|--------------|----------|
| Spawn sessions | ALLOW | WARNING (--force override) |
| Archive/move plans | ALLOW | BLOCKING (no override) |
| Complete assigned task | ALLOW | ALLOW |
| Complete unassigned task | ADVISORY | ADVISORY |

**Verdict:** **Implement in Phase 1** (immediately after P3). This completes the enforcement foundation.

---

### P5: Tmux Session Management Patterns

**Complexity:** MEDIUM-HIGH | **Effort:** 250-350 hours | **Risk:** MEDIUM | **Value:** HIGH

**Summary:** Leverage tmux session infrastructure for role-based orchestration enforcement with session hierarchy tracking and quality gate integration.

**Strengths:**
- **85% infrastructure ready** (SessionService and AgenticTmux fully implemented)
- Session-level enforcement with tmux session hierarchy
- Quality gate integration (phase approval workflows)
- Environment variable persistence in tmux sessions
- Audit trail for all orchestration events

**Weaknesses:**
- Tmux-specific (graceful fallback needed for standalone mode)
- Session name collision potential (validation required)
- Orphan sessions when parent killed (detection and cleanup needed)
- Substantial effort (3.5 development cycles)

**Implementation Approach:**
- Wrap SessionService with OrchestrationEnforcementService
- Add OrchestrationRole enum and OrchestrationContext dataclass
- Session hierarchy management with parent-child tracking
- CLI orchestration command group (init, spawn, status, hierarchy)

**Verdict:** **Defer to Phase 3** (after P3+P4 foundation validated). Session hierarchy tracking (IA-004) provides most value without tmux complexity. Implement full P5 only if tmux-specific features prove necessary.

---

### P6: Bootstrap-time Plan Auto-generation

**Complexity:** LOW-MEDIUM | **Effort:** 61-96 hours | **Risk:** LOW | **Value:** MEDIUM-HIGH

**Summary:** Generate agent-specific task files from process.yml at bootstrap time, providing granular step-by-step guidance.

**Strengths:**
- 80% infrastructure ready (agent_help.py already parses process.yml)
- Process.yml schema is consistent (54 files reviewed)
- Complements P2 (plan-level structure) with agent-level steps
- Low technical risk (straightforward extraction)

**Weaknesses:**
- Stale task files if process.yml changes (mitigated: timestamp checks, refresh command)
- Agent type inference requires explicit mapping
- Value unclear until P2 validates that auto-generated task files are useful

**Implementation Approach:**
- Create AgentTaskGenerator service to extract steps from process.yml
- Task file schema at `.claude/task-lists/<role>.yml`
- CLI command: `agentic context generate-agent`
- Bootstrap integration: `agentic context bootstrap --generate-task-file`
- Lifecycle management (create, archive, cleanup, restore)

**Verdict:** **Defer to Phase 4** (after P2 validated). P6 adds agent-level granularity that complements P2's plan-level structure. Implement only if P2 proves that auto-generated task files deliver value.

---

## Recommendations

### Primary Recommendation: Phased Implementation

We recommend a **phased implementation approach** that prioritizes foundational work, validates patterns with quick wins, and defers large efforts until foundation proves effective.

#### Phase 0: Quick Wins Sprint (1-2 weeks, 20-32 hours)

Immediate value from low-complexity improvements. Validates patterns before committing to larger efforts.

**Quick Wins:**
- QW-001: Simplified task status commands (`agentic task done`, `agentic task next`) - 3-5 hours
- QW-002: Event-based logging infrastructure - 4-6 hours
- QW-003: Session whoami command - 4-6 hours
- QW-004: MMD metadata extraction utility - 2-4 hours
- QW-005: Session registry query utilities - 3-5 hours

**Value:** Makes task tracking simpler than manual YAML edits, provides audit trail, enables role introspection.

#### Phase 1: Foundation (8-12 weeks, 360-380 hours)

**CRITICAL PATH** - Enables all role-based enforcement.

**IA-001: Environment Variable Injection (P3 Core) - 20-30 hours**
- Add CLI arguments: --role, --task, --plan, --parent-session, --phase
- Inject AGENTIC_* environment variables at session spawn
- Update session registry schema with orchestration fields
- Integration point: `cmd_spawn()` in session.py

**IA-002: Role Detection Logic (P4 Core) - 30-40 hours**
- Create `orchestration/enforcement.py` module
- Implement RoleEnforcer class with 3-layer detection
- Define graduated enforcement levels (advisory, warning, blocking)
- Role permissions matrix

**IA-004: Session Hierarchy Tracking - 12-18 hours**
- Store parent_session_id in session records
- Update parent's child_sessions list when spawning
- Add `agentic session hierarchy` command

**IA-007: Enforcement Hooks in CLI Commands - 16-24 hours**
- Add enforcement checks to session spawn
- Block subagent archive/move operations
- Warn on unassigned task completions

**Deliverables:**
- Environment-based context injection working
- Role detection and enforcement functional
- Session hierarchy tracking and display
- CLI enforcement hooks preventing boundary violations

#### Phase 2: Structure Visibility (2-3 weeks, 40-60 hours)

**PARALLEL WITH PHASE 1** - Can develop independently.

**IA-003: MMD Parsing Service (P2 Core) - 25-40 hours**
- Implement MMDParserService with 5-stage transformation pipeline
- Metadata → Phases → Tasks → Dependencies → Tasklist generation
- Integration point: New service in `services/mmd_parser_service.py`

**IA-006: Entrypoint Execute Tasklist Integration - 8-12 hours**
- Wire MMD parsing into `entrypoint execute --compile`
- Include tasklist in compiled context bundle
- Filter tasklist by agent role using AGENT_ROUTING

**Deliverables:**
- MMD files automatically parsed to structured tasklists
- Orchestrators see plan structure at bootstrap
- Agents see assigned tasks without manual tracking
- Progress reporting enabled (X of Y tasks complete)

#### Phase 3: Optional Enhancements (3-4 weeks, 12-18 hours)

**IA-005: Gate Validation Commands (P1 Subset) - 12-18 hours**
- Add CLI commands: `agentic plan gate check/require/list`
- Gate definition schema in plan YAML
- Gate types: file_exists, phase_complete, review_approved

**Deliverables:**
- Orchestrators can enforce phase transitions
- Gate validation provides quality control points
- Foundation for orchestration state machine

#### Phase 4: Evaluation and Next Steps (1-2 weeks)

**Activities:**
- Deploy Phase 0-3 deliverables to production
- Collect feedback from orchestrator usage
- Measure adoption of role-based enforcement
- Decide on P5 (tmux patterns) implementation
- Decide on P6 (bootstrap generation) implementation
- Decide on full P1 (tasklist tracking) implementation

**Decision Points:**
- If P2 tasklists are valuable → Consider P6 for agent-level granularity
- If session hierarchy proves valuable → Consider P5 for tmux-specific features
- If task tracking needs emerge → Consider full P1 implementation

### Alternative Approaches Considered

**Alternative 1: Implement P1 First (CLI Tasklist Tracking)**

**Rejected because:**
- P1 has critical enforcement gap (agents can bypass via YAML edits)
- P2 provides similar structure visibility without enforcement weaknesses
- Quick Wins from P1 (QW-001, QW-002) provide immediate value without full P1 commitment
- P2 is higher value-to-effort ratio (40-60h vs 80-100h)

**Alternative 2: Implement P2 Before P3+P4**

**Rejected because:**
- P2 is valuable but not foundational
- P3+P4 enable all role-based enforcement (more strategic)
- Better to establish enforcement foundation first, then add structure
- Can parallelize P2 with P4 if resources available

**Alternative 3: Implement All Proposals in Parallel**

**Rejected because:**
- Resource constraints and dependencies between proposals
- Risk of over-engineering before validating patterns
- Phased approach validates foundation before committing to full implementation
- Total effort (711-886 hours) too large to commit without validation

### Trade-offs Analyzed

**Enforcement vs Flexibility:**
- **P1, P4**: More enforcement, less flexibility
- **P2, P6**: More structure, agents retain flexibility
- **Decision**: Start with graduated enforcement (P4) that includes advisory levels, preserving flexibility while establishing boundaries

**Complexity vs Value:**
- **P3, P4**: Higher complexity, foundational value
- **P2**: Lower complexity, immediate value
- **P5**: Highest complexity, incremental value over P3+P4
- **Decision**: Prioritize P3+P4 for foundation, P2 for quick value, defer P5 until foundation validated

**Infrastructure Readiness vs Strategic Value:**
- **P5**: 85% infrastructure ready but substantial effort (250-350h)
- **P3**: 60% infrastructure ready but foundational (80-100h)
- **Decision**: Strategic value (P3 foundational) outweighs infrastructure readiness (P5 ready but incremental)

---

## Implementation Roadmap

### Timeline and Milestones

```
Week 0-2:   Phase 0 - Quick Wins Sprint
            └─> Deliverables: Simplified commands, event logging, whoami, utils

Week 3-6:   Phase 1A - Environment Injection (IA-001)
            └─> Deliverables: AGENTIC_* env vars, session registry schema

Week 3-8:   Phase 2 - MMD Parsing (IA-003, IA-006) [PARALLEL]
            └─> Deliverables: MMDParserService, entrypoint integration

Week 7-14:  Phase 1B - Role Detection (IA-002, IA-004, IA-007)
            └─> Deliverables: RoleEnforcer, hierarchy tracking, enforcement hooks

Week 15-17: Phase 3 - Gate Validation (IA-005)
            └─> Deliverables: Gate commands, validation logic

Week 18-19: Phase 4 - Evaluation
            └─> Activities: Deploy, measure, decide on P5/P6/P1
```

**Total Timeline: 19 weeks (4.5 months) with parallelization**

### Resource Requirements

**Development Effort:**
- Phase 0: 20-32 hours (1 developer, 1-2 weeks)
- Phase 1: 78-112 hours (1 developer, 8-12 weeks or 2 developers, 4-6 weeks)
- Phase 2: 33-52 hours (1 developer, 2-3 weeks, parallel with Phase 1B)
- Phase 3: 12-18 hours (1 developer, 3-4 weeks)
- **Total: 143-214 hours**

**Testing Effort:**
- Unit tests: 20% of development (29-43 hours)
- Integration tests: 15% of development (21-32 hours)
- **Total: 50-75 hours**

**Documentation Effort:**
- CLI command documentation: 8-12 hours
- Process.yml updates for agents: 8-12 hours
- Architecture documentation: 8-12 hours
- **Total: 24-36 hours**

**Grand Total: 217-325 hours**

### Phased Deliverables

**MVP (Phases 0-2): 10-15 weeks, 143-214 hours**
- Environment-based context injection
- Role detection and enforcement
- Preloaded tasklists from MMD
- Session hierarchy tracking
- CLI enforcement hooks

**Complete Foundation (Phases 0-3): 19 weeks, 217-325 hours**
- All MVP deliverables
- Gate validation commands
- Event logging and audit trail
- Comprehensive testing and documentation

### Quick Wins Timeline

Quick wins can be implemented **immediately** and provide value within 1-2 weeks:

| Week | Quick Win | Effort | Value |
|------|-----------|--------|-------|
| 1 | QW-001: Simplified commands | 3-5h | Immediate adoption boost |
| 1 | QW-004: MMD metadata utility | 2-4h | Foundation for P2 |
| 1 | QW-005: Session registry utils | 3-5h | Foundation for hierarchy |
| 2 | QW-002: Event logging | 4-6h | Audit trail from day 1 |
| 2 | QW-003: Whoami command | 4-6h | Role introspection ready |

**Total: 16-26 hours over 2 weeks**

### Foundation Work Sequence

Foundation work (P3+P4) follows **critical path dependencies**:

```
QW-003 (whoami) ──┐
                  ├──> IA-001 (env injection) ──> IA-002 (role detection) ──> IA-007 (enforcement hooks)
QW-005 (utils) ───┘                                      └──> IA-004 (hierarchy)
```

**Parallelization Opportunity:**
- IA-003 (MMD parsing) can run **parallel** to IA-002/IA-004/IA-007
- This saves 4-6 weeks on the timeline

### Long-term Vision (Deferred)

**Phase 5: Tmux Patterns (P5) - IF VALIDATED**
- Duration: 6-8 weeks
- Effort: 250-350 hours
- Prerequisite: P3+P4 deployed and valuable
- Deliverables: OrchestrationEnforcementService, quality gates, tmux hierarchy

**Phase 6: Agent Granularity (P6) - IF VALIDATED**
- Duration: 3-4 weeks
- Effort: 61-96 hours
- Prerequisite: P2 deployed and valuable
- Deliverables: Agent task file generation, bootstrap integration

**Phase 7: Enhanced Tracking (P1) - IF NEEDED**
- Duration: 2-3 weeks
- Effort: 60-68 hours (deferred items only)
- Prerequisite: P2 proves insufficient
- Deliverables: Enforced task dependencies, completion hooks

---

## Risks and Mitigations

### Technical Risks

**Risk 1: Environment Variable Injection Breaks Existing Workflows**
- **Likelihood:** LOW
- **Impact:** HIGH
- **Mitigation:**
  - All new env vars are opt-in (only set if --role etc provided)
  - Backward compatibility tested with existing plans
  - Gradual rollout with monitoring
  - Legacy sessions continue to work without orchestration context

**Risk 2: MMD Parsing Fails on Legacy/Manually-Edited Files**
- **Likelihood:** MEDIUM
- **Impact:** MEDIUM
- **Mitigation:**
  - Graceful fallbacks for missing metadata
  - Schema validation with clear error messages
  - Test with 50+ real MMD files before deployment
  - Manual MMD files still work (just no auto-generated tasklist)

**Risk 3: Role Enforcement Blocks Legitimate Operations**
- **Likelihood:** LOW
- **Impact:** MEDIUM
- **Mitigation:**
  - Graduated enforcement (advisory → warning → blocking)
  - --force override for warning-level blocks
  - Clear error messages guide users to correct approach
  - Advisory level for ambiguous cases

**Risk 4: Session Hierarchy Tracking Has Race Conditions**
- **Likelihood:** LOW
- **Impact:** MEDIUM
- **Mitigation:**
  - Session registry uses file locks for atomic updates
  - Parent update happens synchronously at spawn
  - Orphan detection handles missing parent gracefully

### Schedule Risks

**Risk 5: Implementation Takes Longer Than Estimated**
- **Likelihood:** MEDIUM
- **Impact:** MEDIUM
- **Mitigation:**
  - Estimates include buffer (ranges rather than point estimates)
  - Phased approach allows course correction
  - Quick wins validate patterns before large commitments
  - Can defer Phase 3 (gate validation) if timeline slips

**Risk 6: Testing Reveals Fundamental Design Issues**
- **Likelihood:** LOW
- **Impact:** HIGH
- **Mitigation:**
  - P3 and P4 use industry-validated patterns (environment variables)
  - Quick wins provide early validation
  - Integration testing planned throughout (not just at end)
  - Can pivot to alternative approaches if needed

### Adoption Risks

**Risk 7: Agents Don't Use New CLI Commands (Stick to Manual YAML Edits)**
- **Likelihood:** MEDIUM
- **Impact:** MEDIUM
- **Mitigation:**
  - Make CLI commands **simpler** than alternatives (e.g., `task done` vs manual YAML edit)
  - Update agent process.yml to reference new commands
  - Event logging tracks adoption rates
  - Enforcement hooks make CLI commands the path of least resistance

**Risk 8: Orchestrators Bypass Role-Based Enforcement**
- **Likelihood:** LOW
- **Impact:** HIGH
- **Mitigation:**
  - Audit trail (event logging) detects bypasses
  - Enforcement hooks cover all sensitive operations
  - Session registry is authoritative (can't be easily tampered)
  - Graduated enforcement respects orchestrator autonomy while guiding behavior

### Value Risks

**Risk 9: Quick Wins Don't Provide Enough Value to Justify Larger Efforts**
- **Likelihood:** LOW
- **Impact:** MEDIUM
- **Mitigation:**
  - Quick wins are independently valuable (not just prototypes)
  - Evaluation phase (Phase 4) before committing to P5/P6/P1
  - Defer large efforts until foundation proves value
  - Can stop after MVP if enforcement proves sufficient

**Risk 10: P3+P4 Foundation Insufficient for Orchestration Needs**
- **Likelihood:** LOW
- **Impact:** HIGH
- **Mitigation:**
  - P3+P4 are industry-validated patterns
  - Session hierarchy tracking (IA-004) complements foundation
  - P5 (tmux) available as enhancement if needed
  - Evaluation phase identifies gaps before deferring P5/P6

---

## Success Criteria

### Functional Criteria

**FC-1: Role Identification**
- Sessions can identify their role (orchestrator vs subagent)
- Validation: `agentic session whoami` shows role correctly
- Target: 95%+ of sessions correctly identify role

**FC-2: Context Propagation**
- Orchestrators can spawn subagent sessions with context
- Validation: Spawned session sees `AGENTIC_SESSION_ROLE=subagent`
- Target: 100% of spawned sessions receive orchestration context

**FC-3: Enforcement Boundaries**
- Subagents are blocked from orchestrator-only operations
- Validation: Subagent cannot archive plan; receives blocking error
- Target: Zero subagent archive/move attempts succeed

**FC-4: Plan Structure Visibility**
- Plans have preloaded tasklists from MMD
- Validation: `entrypoint execute --compile` includes tasklist
- Target: 100% of plans with MMD have tasklists in context

**FC-5: Session Hierarchy**
- Session hierarchy is tracked and queryable
- Validation: `agentic session hierarchy` shows parent-child tree
- Target: 100% of spawned sessions record parent_session

**FC-6: Gate Enforcement**
- Gate validation prevents phase transitions when requirements not met
- Validation: `agentic plan gate require` fails if gate not met
- Target: 100% of gate checks return correct pass/fail

### Non-Functional Criteria

**NFC-1: Performance**
- Session spawn adds < 100ms overhead
- MMD parsing completes in < 500ms for typical files
- Target: 95th percentile latency within thresholds

**NFC-2: Backward Compatibility**
- No breaking changes to existing CLI commands
- Sessions without orchestration context continue to work
- Target: 100% of existing plans work without modification

**NFC-3: Usability**
- Clear error messages for enforcement violations
- CLI commands are simpler than manual alternatives
- Target: 80%+ of agents prefer CLI commands over manual edits

**NFC-4: Reliability**
- < 5% of enforcement operations fail with errors
- Event logging captures 100% of orchestration actions
- Target: 99%+ success rate for enforcement operations

### Measurement Approach

**Instrumentation:**
- Event logging infrastructure (QW-002) provides audit trail
- Log all orchestration actions: task status, session spawn, plan lifecycle
- JSONL format for easy analysis

**Metrics Collection:**
- Count CLI command executions vs manual YAML edits
- Measure enforcement effectiveness (blocks, warnings, advisory)
- Track adoption rates (% of sessions using --role flag)
- Monitor performance (spawn latency, MMD parsing time)

**Validation:**
- Unit tests for all enforcement logic (95%+ coverage target)
- Integration tests with real plan folders
- Manual validation of session hierarchy display
- Regression tests for backward compatibility

**Reporting:**
- Weekly metrics dashboard during rollout
- Monthly adoption and value reports
- Quarterly evaluation against success criteria

---

## Next Steps

### Immediate Actions (Week 1-2)

1. **Approve this recommendation report**
   - Review findings and recommendations
   - Confirm phased approach and priorities
   - Approve resource allocation

2. **Create implementation plans**
   - Spawn planner-build agent for Phase 0 (Quick Wins)
   - Create detailed task breakdown for IA-001, IA-002, IA-003
   - Estimate resource needs and timeline

3. **Begin Quick Wins Sprint**
   - QW-001: Implement simplified task commands (3-5 hours)
   - QW-004: Create MMD metadata extraction utility (2-4 hours)
   - QW-005: Build session registry query utilities (3-5 hours)

### Short-term Actions (Week 3-6)

4. **Phase 1A: Environment Injection**
   - IA-001: Implement environment variable injection (20-30 hours)
   - Add CLI arguments: --role, --task, --plan, --parent-session, --phase
   - Update session registry schema
   - Test with spawned sessions

5. **Phase 2: MMD Parsing (Parallel)**
   - IA-003: Build MMDParserService (25-40 hours)
   - Implement 5-stage transformation pipeline
   - Test with 50+ real MMD files

### Medium-term Actions (Week 7-14)

6. **Phase 1B: Role Detection and Enforcement**
   - IA-002: Create RoleEnforcer service (30-40 hours)
   - IA-004: Implement session hierarchy tracking (12-18 hours)
   - IA-007: Add enforcement hooks to CLI commands (16-24 hours)
   - IA-006: Wire MMD parsing into entrypoint execute (8-12 hours)

### Long-term Actions (Week 15-19)

7. **Phase 3: Gate Validation**
   - IA-005: Implement gate validation commands (12-18 hours)
   - Test with multi-phase plans

8. **Phase 4: Evaluation**
   - Deploy all deliverables to production
   - Collect metrics and feedback
   - Decide on P5/P6/P1 implementation

### Decision Gates

**Gate 1: After Quick Wins Sprint (Week 2)**
- Are quick wins delivering value?
- Are patterns validating as expected?
- Proceed to Phase 1 or adjust?

**Gate 2: After Phase 1A (Week 6)**
- Is environment injection working correctly?
- Are sessions receiving orchestration context?
- Proceed to Phase 1B or debug?

**Gate 3: After Phase 1B and 2 (Week 14)**
- Is role enforcement effective?
- Are tasklists providing value?
- Is session hierarchy useful?
- Proceed to Phase 3 or iterate?

**Gate 4: After Phase 3 (Week 17)**
- Is gate validation working?
- Is the complete foundation delivering value?
- Proceed to evaluation or enhance?

**Gate 5: After Evaluation (Week 19)**
- What is the adoption rate?
- What is the value delivered?
- Implement P5 (tmux patterns)?
- Implement P6 (bootstrap generation)?
- Implement full P1 (tasklist tracking)?

---

## Conclusion

This investigation has produced a clear, actionable roadmap for orchestration enforcement in the Agentic Engineering framework. The recommended approach balances foundational work (P3+P4) with immediate value delivery (Quick Wins, P2), while deferring large efforts (P5, P6, full P1) until the foundation proves effective.

### Why This Approach Works

1. **Foundational First**: P3 and P4 enable all role-based enforcement. Without environment-based context injection, sessions cannot identify their role. Without role detection, there are no enforcement boundaries.

2. **Quick Wins Validate**: 20-32 hours of quick wins provide immediate value and validate patterns before committing to 360-380 hours of foundation work.

3. **High Value, Low Risk**: P2 (MMD parsing) delivers high value (plan structure visibility) with low risk and moderate effort (40-60 hours). It complements P3+P4 without adding enforcement complexity.

4. **Graduated Enforcement**: Advisory, warning, and blocking levels respect agent autonomy while establishing clear boundaries. This is more effective than binary allow/deny.

5. **Defer Large Efforts**: P5 (250-350h), P6 (61-96h), and full P1 (80-100h) are deferred until foundation validates. This avoids over-engineering and preserves resources.

6. **Industry-Validated Patterns**: P3 (environment variables) and P4 (role-based access control) are standard practices. This reduces technical risk.

### Expected Outcomes

**Immediate (Weeks 1-6):**
- Simplified task commands reduce friction
- Event logging provides audit trail
- Environment injection enables role detection
- MMD parsing provides plan structure

**Short-term (Weeks 7-14):**
- Role-based enforcement establishes orchestration boundaries
- Session hierarchy enables orchestrator oversight
- Tasklists provide progress visibility

**Medium-term (Weeks 15-19):**
- Gate validation enables quality control
- Complete foundation deployed and validated
- Metrics guide decisions on P5/P6/P1

**Long-term (6+ months):**
- If validated: Tmux patterns (P5) add session-level orchestration
- If validated: Bootstrap generation (P6) adds agent-level granularity
- If needed: Enhanced tracking (P1) provides task dependencies

### Final Recommendation

**Approve and proceed with phased implementation:**
- Phase 0: Quick Wins Sprint (1-2 weeks)
- Phase 1: Foundation (P3+P4, 8-12 weeks)
- Phase 2: Structure (P2, parallel with Phase 1B, 2-3 weeks)
- Phase 3: Gates (P1 subset, 3-4 weeks)
- Phase 4: Evaluation (1-2 weeks)

**Total timeline: 19 weeks (4.5 months)**
**Total effort: 217-325 hours**
**Expected value: High (foundational orchestration enforcement)**

This approach delivers orchestration enforcement in manageable increments, validates patterns early, and defers large efforts until foundation proves effective.

---

## References

### Investigation Documents

**Synthesis:**
- EN-SYNTH-001: Proposal Comparison Matrix
- EN-SYNTH-002: Quick Wins and Immediate Actions

**P1 Analysis:**
- proposal_1_gaps_analysis.yml
- proposal_1_complexity_assessment.yml

**P2 Analysis:**
- EN-P2-001: Plan Start Analysis
- EN-P2-002: MMD Format Analysis (50 files)
- EN-P2-003: MMD Transformation Design

**P3 Analysis:**
- EN-P3-001: Session Spawn Audit
- EN-P3-002: Session Context Flow Lifecycle
- EN-P3-003: Context Injection Design

**P4 Analysis:**
- EN-P4-001: Session Metadata Audit
- EN-P4-002: Environment Session Identification
- EN-P4-003: Role Detection Enforcement Design

**P5 Analysis:**
- EN-P5-001: AgenticTmux Audit
- EN-P5-002: Tmux Patterns Review (3 plans)
- EN-P5-003: Tmux Orchestration Enforcement Design

**P6 Analysis:**
- EN-P6-001: Process.yml Audit (54 files)
- EN-P6-002: MMD Task Transformation Prototype
- EN-P6-003: Agent Plan Generation Design

### Plan Documents

- orchestration_orchestration_enforcement.mmd
- plan_teach.yml
- friction_analysis.yml

### Related Work

- Claude Code feature request #17188: Environment variable injection
- SessionService implementation (modules/AgenticGuidance/src/agenticguidance/services/session.py)
- AgenticTmux implementation (modules/AgenticGuidance/src/agenticguidance/services/agentic_tmux.py)
- Plan YAML schema (docs/plans/plan_example.yml)

---

**Report Status:** Final Recommendation
**Next Action:** Human approval and Phase 0 implementation planning
