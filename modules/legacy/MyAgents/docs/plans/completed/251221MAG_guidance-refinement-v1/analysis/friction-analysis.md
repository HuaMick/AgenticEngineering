# Orchestration Workflow Friction Analysis

**Date**: 2025-12-21
**Objective**: Consolidate and verify agent guidance orchestration flow
**Focus**: `/home/code/myagents/MyAgentsGuidance-staging/agents/orchestration/process.mm`

## Executive Summary

The orchestration workflow coordinates planner-teach, planner-reviewer, and teacher agents to improve agent guidance through a recursive planning loop. Analysis reveals several friction points where paths are unclear, signposts are missing, and fences need strengthening.

## Target Agents Involved

1. **orchestration/orchestrator** (meta-agent, coordinates workflow)
2. **planner/planner-teach** (creates guidance improvement plans)
3. **planner/planner-reviewer** (reviews and approves plans)
4. **teacher/teacher-process** (updates process files with paths/fences/signposts)
5. **teacher/teacher-update-assets** (updates shared assets/definitions/examples)
6. **test/test-final-output** (audits final outcome)

## Current State: What Works

### Clear Paths
- **Process discovery**: Agents know where to find process.yml files
- **Input layering**: The transitive loading via inputs.yml layers is well-defined
- **Core concepts**: Path/fence/signpost definitions exist and are referenced
- **Planning loop structure**: The planner-teach → planner-reviewer → teacher flow is explicit in process.mm

### Effective Signposts
- **Agent categories**: `/home/code/myagents/MyAgentsGuidance/assets/definitions/agent-categories.yml` clearly defines boundaries
- **Path/fence/signpost definitions**: Core teaching framework exists
- **Success criteria patterns**: `success-criteria-teacher.yml` provides outcome-based verification guidance

### Working Fences
- **Category boundaries**: Agent categories define clear "do not cross" lines
- **Loop max iterations**: agent-loops.yml specifies maximum iterations (prevents infinite loops)
- **Required inputs check**: Process steps include "Review all inputs. If an input cannot be found, do not proceed."

## Friction Points: Where Agents Struggle

### 1. CRITICAL: Missing Planning Loop Definition in Orchestration Context

**Observed Gap**: The orchestration process.mm references a "Planning-Teach Loop" (line 33) but doesn't explicitly define:
- Maximum iterations for the planner ↔ reviewer loop
- Exit conditions (beyond "Approved?")
- Escalation triggers (what if loop never converges?)

**Impact**: Orchestrator lacks clear fence for when to escalate vs continue iterating.

**Current State**:
```mermaid
PlanningLoop{Planning-Teach Loop}
  SpawnPlanner[Spawn planner-teach Agent]
  SpawnPlanner --> SpawnReviewer[Spawn planner-reviewer Agent]
  SpawnReviewer --> Approved{Approved?}
  Approved -- "No: Refine" --> SpawnPlannerFix[Spawn planner-teach Agent]
```

**Missing Signpost**:
- No reference to `assets/definitions/agent-loops.yml#planner-loop` (defines max 5 iterations)
- No explicit escalation path if max iterations reached

**Recommendation**: Add explicit loop context to orchestration/process.mm or orchestration/inputs.yml referencing the planner-loop definition.

### 2. HIGH: Orchestration Inputs Missing Key Teaching Concepts

**Observed Gap**: `/home/code/myagents/MyAgentsGuidance/agents/orchestration/inputs.yml` lists only 9 inputs. It does NOT reference:
- `assets/definitions/path.yml`
- `assets/definitions/fence.yml`
- `assets/definitions/signpost.yml`
- `assets/definitions/guidance-artifacts.yml`
- `assets/definitions/agent-categories.yml` (critical for routing decisions)

**Impact**: Orchestrator coordinating guidance work doesn't have direct access to the core teaching framework definitions. Must infer from planner-teach behavior.

**Evidence**: Orchestration inputs.yml only includes fix-the-source, experiment-first, context-minimisation, worktree-and-branching, response-audit, iteration, plans, guidance, agent-loops, and test-final-output.

**Recommendation**: Extend orchestration/inputs.yml to include the teaching framework when orchestrating guidance improvement workflows.

### 3. HIGH: Process.mm Format Lacks Explicit Inputs/Steps/Guidelines Structure

**Observed Gap**: The orchestration process.mm uses a mermaid flowchart format which embeds steps, inputs, and guidelines as comments:
```mermaid
%% GOAL: Orchestrate agents...
%% PROFILE: Orchestration-Context-Engineer
%% OUTPUT: Completed plans...
%% GUIDELINE: Strict NO CODE policy...
%% INPUT_PATH: agents/orchestration/inputs.yml
```

**Impact**:
- Format differs from all other agent process files (which use YAML with explicit goal/inputs/steps/guidelines sections)
- Harder to parse and validate systematically
- No explicit step-by-step workflow (steps are embedded in flowchart nodes)

**Current Pattern**: All other agents use `process.yml` with structured YAML. Only orchestration uses `process.mm`.

**Recommendation**: Consider either:
1. Converting process.mm to process.yml with explicit structure + mermaid diagram as supplemental
2. Documenting the .mm format expectations in guidance-artifacts.yml

### 4. MEDIUM: Teacher Planning Process Lacks Concrete Examples

**Observed Gap**: The planner-teach agent references success-criteria-teacher.yml and outcome-verification.yml but doesn't have concrete examples of:
- What a "friction-analysis.md" should contain (structure, depth, format)
- What "plan_live_teach.yml" tasks look like for guidance work
- What "minimal, verifiable plan" means in the teaching context

**Impact**: Planner-teach agents may produce inconsistent planning artifacts.

**Current Signposts**:
- `assets/examples/teacher/concise.yml` exists but focuses on writing style, not planning deliverables
- No example teaching plan in `assets/examples/planner/`

**Recommendation**: Create `assets/examples/planner/teaching-plan-example.yml` showing a complete guidance improvement plan.

### 5. MEDIUM: Worktree Planning Folder Creation Not Explicitly Sequenced

**Observed Gap**: The orchestration process.mm shows "RunNewWorktree" → "VerifyWorktree" → "PlanningLoop" but:
- Doesn't explicitly state that _new_worktree.yml MUST complete before planning starts
- Doesn't specify what happens if worktree already exists
- The verification step lacks defined acceptance criteria

**Impact**: Potential race condition or unclear error handling if worktree setup incomplete.

**Recommendation**: Add explicit fence in orchestration process: "REQUIREMENT: Planning folder at docs/plans/live/YYMMDDRepo_Branch/ must exist with live/ and completed/ subdirectories before spawning planner-teach."

### 6. LOW: Agent Loop Definitions Not Referenced in Process Files

**Observed Gap**: `assets/definitions/agent-loops.yml` defines planner-loop with max 5 iterations, but:
- planner-teach/process.yml doesn't reference this loop definition
- planner-reviewer/process.yml doesn't reference this loop definition
- orchestration/process.mm doesn't explicitly cite max iterations

**Impact**: Loop context exists but isn't discoverable by agents executing within those loops.

**Recommendation**: Add loop_context sections to planner-teach and planner-reviewer process files:
```yaml
loop_context:
  participates_in: ["planner-loop"]
  loop_definition: "assets/definitions/agent-loops.yml#planner-loop"
  max_iterations: 5
```

### 7. LOW: Missing Validation Criteria for "Approved" Decision

**Observed Gap**: planner-reviewer/process.yml states "APPROVE: If all criteria are met" but doesn't enumerate what those criteria are in detail. The guidelines mention:
- Unique plan name and correct worktree path
- File-level inputs for context routing
- Measurable success criteria including user-focused validation
- Proper agent type allocation and operation ordering
- Alignment with Domain → Workflow → Entrypoint patterns

**Impact**: These criteria are guidelines but not formalized as a checklist.

**Recommendation**: Convert approval criteria into a structured checklist in planner-reviewer/inputs.yml or process.yml.

## Mismatches Between Guidance and Repository Reality

### Mismatch 1: Path References Use Two Different Conventions

**Guidance Says**: Various files reference both absolute paths and relative paths inconsistently.

**Repository Reality**:
- Some inputs.yml use relative paths: `"assets/definitions/agent-categories.yml"`
- Some use absolute paths: `"/home/code/myagents/docs/plans/live/YYMMDDRepo_Branch/"`
- folder-structure.yml uses absolute paths

**Impact**: Agents must handle both conventions or may fail to locate files.

**Recommendation**: Standardize on relative paths from repo root for all guidance files. Use absolute paths only for plan folder references (which span worktrees).

### Mismatch 2: Agent Category "Teacher" Special Status Not Reflected in Process

**Guidance Says**: agent-categories.yml includes special note:
```yaml
special_note: "Teacher category has special plan+execute hybrid status -
teacher agents both plan (via planner-teach) and execute (via
teacher-process/teacher-update-assets) guidance improvements"
```

**Repository Reality**:
- teacher-process and teacher-update-assets do NOT participate in planning loops
- They are pure executors, following plans created by planner-teach
- No "hybrid" behavior visible in process files

**Impact**: Special note is misleading. Teacher agents execute guidance changes; planner-teach plans them.

**Recommendation**: Update agent-categories.yml to clarify: "planner-teach plans guidance improvements; teacher agents execute those plans by updating processes and assets."

## Root Cause Patterns

### Pattern 1: Documentation Drift
- Definitions created but not consistently referenced in process files
- Example: agent-loops.yml exists but loop participants don't cite it

### Pattern 2: Format Heterogeneity
- Most agents use process.yml (YAML)
- Orchestration uses process.mm (Mermaid)
- No guidance on when to use which format

### Pattern 3: Implicit vs Explicit Knowledge
- Orchestration assumes agents know to check for worktree setup
- Planner loop max iterations defined but not enforced in process
- Approval criteria exist as prose, not checklists

## Recommended Guidance Updates (Priority Order)

### Phase 1: Critical Path Clarification (HIGH IMPACT)

1. **Add loop context to orchestration process**
   - File: `agents/orchestration/process.mm` or convert to `process.yml`
   - Add explicit reference to planner-loop definition
   - Define escalation path if max iterations reached

2. **Extend orchestration inputs for teaching context**
   - File: `agents/orchestration/inputs.yml`
   - Add path.yml, fence.yml, signpost.yml, agent-categories.yml when orchestrating guidance work
   - OR: Create `orchestration-teach-inputs.yml` variant for guidance workflows

3. **Create planning example for teaching work**
   - File: `assets/examples/planner/teaching-plan-example.yml`
   - Show complete structure: friction-analysis.md, plan_live_teach.yml format
   - Include realistic guidance refinement tasks

### Phase 2: Strengthen Fences (MEDIUM IMPACT)

4. **Formalize planner-reviewer approval checklist**
   - File: `agents/planner/planner-reviewer/inputs.yml`
   - Convert prose criteria into structured checklist
   - Reference from process.yml

5. **Add loop context to planner agents**
   - Files: `agents/planner/planner-teach/process.yml`, `agents/planner/planner-reviewer/process.yml`
   - Add loop_context sections referencing planner-loop

6. **Clarify worktree verification criteria**
   - File: `agents/orchestration/process.mm` or process.yml
   - Define exact checks for "VerifyWorktree" step
   - Specify error handling if verification fails

### Phase 3: Remove Inconsistencies (LOW IMPACT)

7. **Standardize path conventions**
   - Files: All inputs.yml files, folder-structure.yml
   - Use relative paths for repo content, absolute paths for cross-worktree references

8. **Correct teacher category description**
   - File: `assets/definitions/agent-categories.yml`
   - Clarify planner-teach vs teacher-* role separation

9. **Document process file format guidance**
   - File: `assets/definitions/guidance-artifacts.yml`
   - Add when to use .yml vs .mm format
   - OR: Migrate orchestration/process.mm to process.yml

## Success Criteria for This Plan

This plan succeeds when:

1. Orchestrator can execute the guidance improvement loop without ambiguity
2. Planner-teach agents produce consistent, reviewable planning artifacts
3. Planner-reviewer agents have clear, verifiable approval criteria
4. Teacher agents receive well-structured plans with explicit file paths and acceptance criteria
5. All loop participants know their max iterations and escalation triggers
6. No path/fence/signpost references are broken or undiscoverable

## Verifiable Checkpoints

- [ ] Orchestration process explicitly references planner-loop definition
- [ ] Orchestration inputs include teaching framework when coordinating guidance work
- [ ] Concrete example of teaching plan exists in assets/examples/planner/
- [ ] Planner-reviewer has formalized approval checklist
- [ ] All agents participating in loops have loop_context sections in their process files
- [ ] Path conventions documented and consistent across all inputs.yml files
- [ ] Agent categories accurately reflect planner-teach vs teacher-* separation
