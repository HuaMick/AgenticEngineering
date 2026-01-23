# Planner-Audit Guidance Remediation Plan
**Reviewer**: planner-audit (self-review)
**Date**: 2026-01-23
**Status**: Recommended for next session
**Effort**: 15-20 minutes

---

## Problem Statement

The planner-audit agent guidance exceeds the recommended 2000-token maximum by 8 tokens (2008 total). This triggers the context-bloat criterion (NAT-006), resulting in a NEEDS_ATTENTION verdict.

**Root Cause**: Steps 1-2 in process.yml contain verbose explanations that could be condensed through references to shared guidelines.

---

## Remediation Actions

### Action 1: Condense JIT CLI Bootstrap Step

**Target File**: `modules/AgenticGuidance/agents/planner/planner-audit/process.yml`
**Section**: Step 1
**Current Size**: ~100 tokens

**Current Content**:
```yaml
- |
  JIT CLI BOOTSTRAP (Run FIRST before any file exploration):
  Execute these commands to get structured context efficiently:

  ```bash
  # Get seed context (objective, process summary, inputs)
  agentic context bootstrap --role planner-audit -j

  # Get current task if working from a plan
  agentic plan task current -j
  ```

  CLI output provides:
  - Your objective and process summary
  - Input file paths to read
  - Current task details (if plan exists)

  ONLY use Glob/Grep/Read if CLI output indicates specific files to examine.
  DO NOT explore the codebase before running these commands.
```

**Proposed Change**:
```yaml
- |
  JIT CLI BOOTSTRAP (Run FIRST - see context-minimisation.yml):

  ```bash
  agentic context bootstrap --role planner-audit -j
  agentic plan task current -j
  ```

  This provides seed context (objective, process summary, inputs) efficiently.
  Only use Glob/Grep/Read if CLI output indicates specific files to examine.
```

**Expected Reduction**: 30-40 tokens

---

### Action 2: Restructure Required Inputs Validation

**Target File**: `modules/AgenticGuidance/agents/planner/planner-audit/process.yml`
**Section**: Step 2
**Current Size**: ~80 tokens

**Current Content**:
```yaml
- |
  VALIDATE REQUIRED INPUTS:
  The following inputs MUST be provided by the orchestrator or user:

  1. plan_folder_path (string, required)
     - Path to the plan folder to audit
     - Example: "docs/plans/live/260106MyProject_feature_auth/"
     - ERROR if missing: "STOP: No plan_folder_path provided. Cannot audit without a target folder."

  2. target_project_path (string, required)
     - Absolute path to target project root
     - Example: "/home/code/MyProject"
     - ERROR if missing: "STOP: No target_project_path provided. Cannot resolve plan folder location."

  If ANY required input is missing, report the specific error and STOP.
```

**Proposed Change**:
```yaml
- |
  VALIDATE REQUIRED INPUTS (see inputs.yml required_inputs section):

  CHECKLIST:
  - [ ] plan_folder_path provided? (e.g., docs/plans/live/260106MyProject_feature_auth/)
  - [ ] target_project_path provided? (e.g., /home/code/MyProject)

  If ANY missing: "STOP: Cannot proceed without required inputs."
```

**Expected Reduction**: 20-30 tokens

---

### Action 3: Verify Final Size

**Validation Command**:
```bash
# After making edits, verify final token count
wc -w modules/AgenticGuidance/agents/planner/planner-audit/inputs.yml \
    modules/AgenticGuidance/agents/planner/planner-audit/process.yml | tail -1
# Expected output: ~1900-1950 tokens
```

**Success Criteria**: Final size < 1950 tokens

---

## Implementation Steps

1. **Edit process.yml** (10 minutes)
   - Condense Step 1 to 2-3 lines with reference
   - Convert Step 2 to structured checklist format
   - Validate YAML syntax

2. **Verify References** (2 minutes)
   - Confirm context-minimisation.yml and inputs.yml still exist
   - Check that condensed references are valid

3. **Token Count Verification** (2 minutes)
   - Run token counting command above
   - Confirm total is now < 1950 tokens

4. **Self-Review Revalidation** (1 minute)
   - Re-run self-review to confirm PASS verdict
   - Document in 260123_planner_audit_selfreview_v2.yml

---

## Expected Outcomes

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Total tokens | 2008 | <1950 | ✓ Achievable |
| Step 1 tokens | ~100 | ~60 | ✓ 40-token reduction |
| Step 2 tokens | ~80 | ~50 | ✓ 30-token reduction |
| NAT-006 triggered | YES | NO | ✓ Expected |
| Self-review result | NEEDS_ATTENTION | PASS | ✓ Expected |
| Guidance quality | 9/10 | 9/10 | ✓ Maintained |

---

## Risk Assessment

**Risk Level**: MINIMAL

**Potential Issues**:
1. Condensation might make steps less clear?
   - Mitigated by keeping reference pointers to fuller documentation
   - Agent can read referenced files if needed

2. YAML syntax errors after edits?
   - Mitigated by validating with `yamllint` or `python -m yaml`
   - Only changing existing steps, not restructuring

3. Reducing essential information?
   - Mitigated by condensing VERBOSE explanations, not critical content
   - All essential constraints (required inputs, error conditions) retained

---

## Approval Criteria

✓ Token count < 1950
✓ All YAML syntax valid
✓ All file references still resolve
✓ Self-review result = PASS
✓ No guidance quality degradation (maintain 9/10 clarity)

---

## Deferral Rationale (if needed)

This remediation can be safely deferred because:
1. **Marginal violation**: Only 0.4% over limit (8 tokens)
2. **Low practical impact**: Agent functions effectively despite bloat
3. **Easy to batch**: Can be combined with other agents exceeding thresholds
4. **No critical issues**: No broken references, duplicates, or deprecations
5. **High quality baseline**: Guidance is excellent with minimal issues

---

## Alternative Approaches

### Option A: Defer to Batch Optimization (RECOMMENDED)
- Group with other agents > 1500 tokens
- Batch condense all agents together
- Run once per planning cycle
- **Effort**: 15-20 minutes as part of larger session

### Option B: Immediate Fix
- Fix in isolation this session
- Allows immediate PASS verdict
- **Effort**: 15-20 minutes standalone

---

## Related Guidance Files

- `modules/AgenticGuidance/assets/guidelines/context-minimisation.yml` - Referenced for JIT CLI best practices
- `modules/AgenticGuidance/agents/planner/planner-audit/inputs.yml` - Required inputs definition
- `modules/AgenticGuidance/assets/definitions/self-review-criteria.yml` - NAT-006 specification

---

## Sign-Off

**Reviewer**: planner-audit agent
**Review Date**: 2026-01-23
**Remediation Status**: Recommended for implementation in next session

This remediation plan is straightforward, low-risk, and addresses the marginal context-bloat violation while maintaining the excellent quality of the planner-audit guidance.
