# Plan: Add User Story Generation to Planner Agents

**Plan ID:** 260214US_add_user_story_generation_phase_to_planner_agents
**Branch:** 260214US_add_user_story_generation_to_planners
**Status:** Active
**Priority:** Critical

## Problem Statement

The planner agents (planner-build and planner-test) generate implementation plans with tasks and phases, but they do NOT generate user stories. This creates a critical gap in UAT validation:

1. Test phases have no UAT acceptance criteria grounded in real user journeys
2. Manual test tasks are just command checklists ("run X --help") not user story validations
3. The test-runner agent (which only runs existing tests) is routed for verification instead of test-builder (which creates new tests)
4. Plans get marked complete after checking `--help` output without verifying actual functionality

### Evidence from 260214TU_tmux_orchestration_ui

- Phase 5 "Verification" had only 2 tasks: run existing tests + manual checklist
- TU_009 "Manual integration test" was 5 bullet points checking --help flags
- Zero unit tests created for the new tmux_layout.py module
- The agent marked TU_009 complete after confirming `--help` showed new flags
- A critical tmux bug (detached sessions missing -x/-y dimensions) shipped because no test actually created a tmux session

## Root Cause

- `orchestration-planning.mmd` has story **discovery** via `agentic stories find`
- But planner agents don't have a story **generation** step
- Story discovery finds story IDs; story generation creates story content
- Without story content, UAT has no acceptance criteria to validate against

## Solution

Add user story generation to the planning workflow:

1. **planner-build**: Generate 3-8 user stories when discovery finds none
2. **planner-test**: Validate story content exists before creating UAT tasks
3. **orchestration-planning**: Add story content validation gate after discovery
4. **orchestration-executor**: Validate stories before UAT execution
5. **planning-standard.yml**: Clarify discovery vs generation vs validation

## Plan Structure

```
docs/plans/live/260214US_add_user_story_generation_phase_to_planner_agents/
├── README.md (this file)
├── plan_build.yml (implementation phases)
├── plan_test.yml (test and UAT phases)
├── plan_teach.yml (guidance teaching phases)
├── plan_audit_clean.yml (audit and cleanup phases)
├── analysis/ (empty - for future friction analysis)
├── completed/ (empty - for archived tasks)
└── audit/ (empty - for compliance checks)
```

## Key Changes

### 1. planner-build/process.yml
- Add "USER STORY GENERATION" step after line 209
- Generate stories in "As a [user], I [action], so that [outcome]" format
- Each story has: journey, success_criteria, testing, priority
- Story quantity guidance: 3-8 stories (happy/error/edge cases)
- FENCE: Build plans cannot skip story generation (blocked_plan_types)

### 2. planner-test/process.yml
- Add "FENCE: STORY CONTENT MUST EXIST" after line 84
- Validate story files exist with complete content
- Add UAT task generation template at line 286
- One UAT task per story with acceptance criteria

### 3. orchestration-planning/process.mmd
- Add ValidateStoryContent node after RecordStories (line 148)
- Check story files exist and have required fields
- Block if stories missing/incomplete without story_creation_tasks

### 4. orchestration-executor/process.yml
- Add UAT validation gate before executing UAT phases
- Verify stories have success_criteria, journey, testing fields
- Block UAT execution if validation fails

### 5. planning-standard.yml
- Clarify story lifecycle: discovery -> generation -> validation
- Document when each step happens and who's responsible

## Success Criteria

- [ ] planner-build process.yml includes User Story Generation step
- [ ] planner-test process.yml includes Story Content Validation fence
- [ ] orchestration-planning validates story content after discovery
- [ ] orchestration-executor has UAT validation gate
- [ ] planning-standard.yml clarifies discovery vs generation vs validation
- [ ] Test planners output includes user stories with acceptance criteria
- [ ] UAT phases map 1:1 to user stories with explicit validation steps
- [ ] Meta-test: Create a new plan and verify it generates user stories

## Dogfooding

This plan eats its own dogfood by:
1. Creating user stories for itself (US-CLI-PLAN-001, US-CLI-PLAN-002)
2. Including UAT phase that validates against those stories
3. Testing the very guidance changes it implements

## User Stories

Affected stories for this plan:
- **US-CLI-PLAN-001**: Planner creates comprehensive implementation plans with user stories
- **US-CLI-PLAN-002**: Plans include UAT phase with acceptance criteria

Story files: `docs/userstories/AgenticCLI/15_planning.yml`

## Testing Strategy

1. **Unit Tests**: Validate each guidance file has required sections
2. **Integration Tests**: Full planning workflow with story generation
3. **Smoke Tests**: Manual validation with real objectives
4. **UAT**: Validate against US-CLI-PLAN-001 and US-CLI-PLAN-002

## Next Steps

1. Execute build phase (update guidance files)
2. Create user story files (dogfooding)
3. Run test phase to validate changes
4. Execute UAT to confirm stories work end-to-end
5. Archive plan when all tasks complete

## Related Plans

- 260214TU_tmux_orchestration_ui (motivating example - UAT gap)
- Future plans will benefit from automatic story generation
