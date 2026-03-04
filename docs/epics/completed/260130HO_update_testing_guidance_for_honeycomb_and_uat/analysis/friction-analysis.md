# Friction Analysis: Testing Guidance Alignment

## Observed Friction
The user identified a gap in the current testing guidance:
1. **Honeycomb Model Missing**: The repository currently uses a "Three-Layer" or "Multi-Layer" testing model, but the user expects a "Honeycomb Integration First" model.
2. **UAT Core Alignment**: While UAT is already mandatory, the user wants to reinforce that it is the "core" of testing and must be anchored to user stories.

## Root Cause
- The existing `AgenticGuidance` was built with a traditional pyramid-like or multi-layer focus.
- The concept of "Honeycomb" (prioritizing integration tests over unit tests) is not explicitly defined in the assets.
- Although UAT is mandatory, its relationship as the "core" success criterion could be more prominently signaled.

## Target Agents
- `teacher-update-assets`: To implement the changes in the guidance assets.
- `planner-test`: To adopt the honeycomb model for future test planning.

## Proposed Remediation
- Introduce **Testing Honeycomb** definition and guideline.
- Update `testing.yml` to prioritize the Honeycomb model.
- Update `strategy-validation.yml` to make Honeycomb the default choice.
- Update `agent-loops.yml` to ensure the phase ordering reflects the UAT-core reality.
