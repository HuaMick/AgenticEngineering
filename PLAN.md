# Plan: Story-Writer UAT-First Restructure

## Epic: 260406AG_story_writer_uat_first_restructure

## Story Discovery (FENCE: STORY-FIRST PLANNING ✅)

Affected stories:
- **US-STR-001**: Story Discovery and Coverage — story format changes affect `find`, `health`, `coverage` commands
- **US-GDN-074**: User Story UAT — UAT process directly impacted by story format changes
- **US-GDN-081**: Test Phase Planning Architecture — planner-test reads stories to create UAT tasks
- **US-PLN-046**: Orchestration Workflow — planning pipeline spawns story-writer and parses output

## Objective

Restructure the `build-story-writer` agent output to embed **UAT verification metadata** directly into stories at generation time. Today, stories describe observable behavior (when/then steps) but lack concrete verification instructions, forcing test-uat agents to independently discover how to validate each step. This leads to inconsistent UAT and false passes/fails.

**Key changes:**
1. Add `verify` and `verify_type` fields per story step — explicit verification commands
2. Add `uat_context` at story level — smoke commands, expected artifacts, environment requirements
3. Update story-writer guidance to generate these fields
4. Update planner-test and test-uat to consume verification metadata
5. Update pipeline validation and CLI health output

## Phases and Tickets (7 phases, 20 tickets)

### P1: Initial Research and Planning (1 ticket — seed)
| ID | Description |
|----|-------------|
| IM_001 | Analyze the codebase to understand how to implement the objective |

### P2: Story Schema Extension (2 tickets)
| ID | Description | Agent | Stories |
|----|-------------|-------|---------|
| P2_001 | Add verify and verify_type fields to user-stories step schema | build-python | US-GDN-074, US-GDN-081 |
| P2_002 | Add uat_context section to story-level schema | build-python | US-STR-001 |

### P3: Story Service Updates (3 tickets)
| ID | Description | Agent | Stories |
|----|-------------|-------|---------|
| P3_001 | Update StoryService data models for verify and uat_context fields | build-python | US-STR-001, US-GDN-074 |
| P3_002 | Add verification extraction helpers to StoryService | build-python | US-GDN-074, US-GDN-081 |
| P3_003 | Add verification coverage computation to story health | build-python | US-STR-001, US-STR-020 |

### P4: Story-Writer Guidance Update (4 tickets)
| ID | Description | Agent | Stories |
|----|-------------|-------|---------|
| P4_001 | Update build-story-writer process.yml with verification generation instructions | teacher-update-guidance | US-GDN-074, US-GDN-081 |
| P4_002 | Update build-story-writer manifest.yml output description | teacher-update-guidance | US-GDN-074 |
| P4_003 | Update planner-test guidance to consume verification fields from stories | teacher-update-guidance | US-GDN-074, US-GDN-081 |
| P4_004 | Update test-uat guidance to prefer verify fields over blind discovery | teacher-update-guidance | US-GDN-074 |

### P5: Pipeline Integration (2 tickets)
| ID | Description | Agent | Stories |
|----|-------------|-------|---------|
| P5_001 | Update planner_loop.py validation to check verification coverage | build-python | US-PLN-046 |
| P5_002 | Update stories health CLI to show verification coverage | build-python | US-STR-001 |

### P6: Test and Validation (4 tickets, test-fix-loop ×3)
| ID | Description | Agent | Stories |
|----|-------------|-------|---------|
| P6_001 | Unit tests for StoryService verify fields and helpers | test-builder | US-GDN-074, US-STR-001 |
| P6_002 | Unit tests for planner_loop.py verification coverage validation | test-builder | US-PLN-046 |
| P6_003 | Integration test for story verification pipeline end-to-end | test-builder | US-GDN-074, US-GDN-081 |
| P6_004 | Tests for stories health verification coverage output | test-builder | US-STR-001 |

### P7: UAT (4 tickets, test-fix-loop ×3) — FENCE: UAT IS MANDATORY ✅
| ID | Description | Agent | Stories |
|----|-------------|-------|---------|
| P7_001 | UAT: Story Discovery and Coverage | test-uat | US-STR-001 |
| P7_002 | UAT: User Story UAT process with verification fields | test-uat | US-GDN-074 |
| P7_003 | UAT: Test Phase Planning reads verification fields | test-uat | US-GDN-081 |
| P7_004 | UAT: Orchestration pipeline handles verification fields | test-uat | US-PLN-046 |

## FENCE Compliance

| Fence | Status | Evidence |
|-------|--------|----------|
| STORY-FIRST PLANNING | ✅ | `agentic stories find` ran first, 4 affected stories identified |
| UAT IS MANDATORY | ✅ | P7 phase with 4 UAT tickets |
| UAT USER STORY ANCHORING | ✅ | Each P7 ticket anchored to specific story ID |
| CLI SMOKE TEST REQUIREMENT | ✅ | P7_001 and P7_004 use real CLI commands |

## Dependencies

- P2 → P3 (service needs schema to be defined first)
- P3 → P4 (guidance references the schema and service helpers)
- P3 → P5 (pipeline integration uses service helpers)
- P2+P3+P4+P5 → P6 (tests validate all preceding work)
- P6 → P7 (UAT runs after tests pass)

## Open Questions

1. Should `verify` be a single string or a list? **Recommendation**: Single string initially
2. Should existing stories be backfilled? **Recommendation**: New stories only; existing gain verify when re-generated
3. Should verify_type include `composite`? **Recommendation**: Start simple, extend later
