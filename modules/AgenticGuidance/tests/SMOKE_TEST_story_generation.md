# Smoke Test: Story Generation in Planner Agents

## Test SMOKE_001: Automatic Story Generation

### Objective
Verify that planner-build automatically generates user stories when none exist for a new feature.

### Prerequisites
- AgenticEngineering environment set up
- CLI installed: `agentic` command available
- Clean test environment (no existing stories for test objective)

### Test Procedure

#### Step 1: Create New Test Plan
```bash
# Create a plan with an objective that has no existing stories
agentic entrypoint _ticket_build.yml --input "Add health check endpoint to API"
```

Expected output:
- orchestration-planning spawns planner-build
- planner-build executes

#### Step 2: Observe planner-build Behavior
Monitor the planner-build agent output for:

**Expected behaviors:**
- [ ] Agent runs `agentic stories find` command
- [ ] Agent detects no stories found
- [ ] Agent generates 3-8 user stories for health check feature
- [ ] Agent creates story file at `docs/userstories/AgenticBackend/NN_health.yml`
- [ ] Agent outputs story IDs (e.g., US-API-HEALTH-001, US-API-HEALTH-002)

#### Step 3: Verify Story Content
Inspect the generated story file:
```bash
# Find the generated story file
find docs/userstories -name "*health*.yml" -type f

# Read the story content
cat docs/userstories/AgenticBackend/NN_health.yml
```

**Verification checklist:**
- [ ] Stories have `id` field (format: US-<PROJECT>-<NNN>)
- [ ] Stories have `name` field (brief description)
- [ ] Stories have `journey` field (step-by-step user actions)
- [ ] Stories have `success_criteria` field (list of measurable criteria)
- [ ] Stories have `testing` field (local and docker instructions)
- [ ] Acceptance criteria are specific (e.g., "returns 200 OK") not vague (e.g., "works")
- [ ] Journey includes step-by-step user actions with expected outcomes

#### Step 4: Verify Plan Output
Check the generated build plan:
```bash
# Find the plan folder
ls docs/epics/live/

# Read the build plan
cat docs/epics/live/260214XX_add_health_check_endpoint/ticket_build.yml
```

**Verification checklist:**
- [ ] `affected_stories` field populated with story IDs
- [ ] `story_creation_tasks` field present (tasks for teach phase)
- [ ] Story IDs match the generated story file
- [ ] Task inputs reference story files for context

#### Step 5: Continue to Test Phase
Allow orchestration to proceed to test planning:

**Expected behaviors:**
- [ ] orchestration-planning spawns planner-test
- [ ] planner-test validates story content exists (FENCE)
- [ ] planner-test validation passes (stories complete)
- [ ] planner-test creates test plan with UAT phase

#### Step 6: Verify Test Plan UAT Phase
Check the test plan:
```bash
cat docs/epics/live/260214XX_add_health_check_endpoint/ticket_test.yml
```

**Verification checklist:**
- [ ] Test plan has UAT phase
- [ ] UAT phase has tasks referencing story IDs
- [ ] UAT tasks include acceptance criteria from stories
- [ ] Each UAT task has `story_id` field
- [ ] Each UAT task has `acceptance_criteria` list (copied from story)
- [ ] Each UAT task has `verification_method` field

### Expected Outcome
✅ **PASS Criteria:**
- Stories generated automatically when missing
- Story content is complete and measurable
- UAT phase references the generated stories
- Acceptance criteria are specific and actionable

❌ **FAIL Criteria:**
- planner-build does not generate stories
- Generated stories missing required fields
- Acceptance criteria are vague or generic
- UAT phase does not reference generated stories

---

## Test SMOKE_002: Story Validation Fence

### Objective
Verify that planner-test blocks planning when story content is incomplete.

### Prerequisites
- AgenticEngineering environment set up
- Ability to create/modify story files
- Test plan with affected_stories

### Test Procedure

#### Step 1: Create Incomplete Story File
Manually create a story file with missing `success_criteria` field:

```bash
# Create incomplete story file
cat > docs/userstories/AgenticCLI/99_test_incomplete.yml << EOF
stories:
- id: US-CLI-TEST-INCOMPLETE-001
  name: Incomplete test story
  category: test
  persona: Test user
  priority: low
  starting_state:
    - Test environment ready
  journey:
    - User runs test command
    - Command executes
  # Missing success_criteria field
  testing:
    local: "Run test locally"
EOF
```

#### Step 2: Create Plan Referencing Incomplete Story
Create a test build plan that references this story:

```bash
cat > /tmp/test_ticket_build.yml << EOF
name: test-incomplete-story-validation
affected_stories:
  - US-CLI-TEST-INCOMPLETE-001
phases: []
EOF
```

#### Step 3: Run planner-test
Attempt to run planner-test with this incomplete story:

```bash
# This would normally be spawned by orchestration
# Manual simulation of planner-test validation
```

**Expected behaviors:**
- [ ] planner-test reads `affected_stories` from plan
- [ ] planner-test checks if story file exists (PASS - file exists)
- [ ] planner-test validates story content (FAIL - missing success_criteria)
- [ ] planner-test STOPS with fence violation error

#### Step 4: Observe Fence Trigger
Verify the error message:

**Expected error output:**
```
FENCE VIOLATION: Story content missing for UAT planning

The following stories have incomplete content:
- US-CLI-TEST-INCOMPLETE-001: missing success_criteria

REQUIRED ACTION:
Stories must be generated before test planning. Fix story content to include
success_criteria, journey, and testing fields.
```

**Verification checklist:**
- [ ] Error message clearly states "FENCE VIOLATION"
- [ ] Error message identifies which story has issues
- [ ] Error message specifies missing field (success_criteria)
- [ ] Error message provides remediation steps
- [ ] Planning does NOT continue (no UAT tasks created)

#### Step 5: Fix Story File
Add the missing `success_criteria` field:

```bash
# Edit the story file
cat > docs/userstories/AgenticCLI/99_test_incomplete.yml << EOF
stories:
- id: US-CLI-TEST-INCOMPLETE-001
  name: Complete test story
  category: test
  persona: Test user
  priority: low
  starting_state:
    - Test environment ready
  journey:
    - User runs test command
    - Command executes
  success_criteria:
    - Command exits with code 0
    - Output contains expected result
  testing:
    local: "Run test locally"
EOF
```

#### Step 6: Retry planner-test
Re-run planner-test with the fixed story:

**Expected behaviors:**
- [ ] planner-test validates story content
- [ ] Validation passes (all required fields present)
- [ ] Planning continues normally
- [ ] UAT tasks created with story criteria

### Expected Outcome
✅ **PASS Criteria:**
- Fence catches incomplete stories before UAT creation
- Clear error message indicates which field is missing
- Planning can continue after fixing story content
- Complete stories pass validation successfully

❌ **FAIL Criteria:**
- Fence does not detect missing fields
- Error message is unclear or generic
- Planning continues despite incomplete stories
- Fixed stories still fail validation

---

## Smoke Test Execution Log

### SMOKE_001 Execution
**Date:** _____________
**Tester:** _____________
**Result:** ☐ PASS ☐ FAIL
**Notes:**


**Issues Found:**


---

### SMOKE_002 Execution
**Date:** _____________
**Tester:** _____________
**Result:** ☐ PASS ☐ FAIL
**Notes:**


**Issues Found:**


---

## Summary
These smoke tests validate the core functionality of user story generation and validation in the planner agents. Both tests should PASS before proceeding to UAT.
