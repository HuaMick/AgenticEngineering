# Planning Context Improvements

**Plan ID**: 260204PC (Planning Context)
**Plan Name**: planning-context-improvements
**Branch**: 260204PC-planning-context-improvements
**Worktree**: /home/code/AgenticEngineering-260204PC-planning-context-improvements

## Problem Statement

Current planning files don't adequately scope what files and artifacts will change during implementation. This creates several challenges:

1. **Limited Orchestration Visibility**: Without clear file and artifact scoping, the orchestration layer cannot effectively determine which work items can be parallelized safely.

2. **Ambiguous Impact Analysis**: Teams and agents reviewing plans cannot quickly assess the blast radius of proposed changes.

3. **Inefficient Work Distribution**: The lack of upfront scoping means orchestration must be conservative, potentially missing opportunities for parallel execution.

4. **Incomplete Context**: Planning agents don't have clear guidance on capturing comprehensive scope information during the planning phase.

## Current State

Planning templates and examples include:
- High-level objectives and goals
- Sequential task breakdowns
- Success criteria and validation steps

Planning templates and examples lack:
- Explicit listing of files that will be modified/created
- Clear identification of impacted artifacts (APIs, services, configs)
- Structured metadata for orchestration decision-making

## Proposed Approach

### 1. Schema Enhancement

Add two new sections to planning templates and schemas:

**impacted_files**: A structured list of files expected to change
- Path to file (relative to worktree root)
- Change type (create, modify, delete)
- Change category (implementation, test, config, docs)

**impacted_artifacts**: A structured list of higher-level artifacts affected
- Artifact type (API, service, CLI command, agent, config)
- Artifact identifier (name/path)
- Impact type (interface change, behavior change, new feature)

### 2. Template Updates

Update planning templates in:
- `modules/AgenticGuidance/assets/` - Core planning templates
- `modules/AgenticCLI/src/agenticcli/commands/plan.py` - Template generation logic

### 3. Agent Guidance Updates

Update planner agent process files to include scoping steps:
- `modules/AgenticGuidance/agents/planner-*/process.yml`
- Add explicit steps for file/artifact analysis
- Provide examples of good vs poor scoping

### 4. Example Updates

Update existing planning examples to demonstrate the pattern:
- Show realistic impacted_files sections
- Demonstrate impacted_artifacts usage
- Provide commentary on orchestration benefits

### 5. Orchestration Integration

Enable orchestration to leverage scoping metadata:
- Parse impacted_files and impacted_artifacts
- Use file overlap detection for parallelization decisions
- Provide visibility into cross-plan dependencies

## Objectives

1. Add "impacted_files" section to planning template/schema
2. Add "impacted_artifacts" section for APIs, services, configs, tests
3. Update planning agents to populate these sections during planning
4. Enable orchestration to use this for better parallelization decisions
5. Update existing planning examples to demonstrate the pattern

## Key Files Likely Impacted

### Planner Agent Guidance
- `modules/AgenticGuidance/agents/planner-*/process.yml`
- Planner agent inputs.yml files

### Planning Templates/Assets
- `modules/AgenticGuidance/assets/` (planning templates/examples)

### CLI Template Generation
- `modules/AgenticCLI/src/agenticcli/commands/plan.py`

### Schema/Models (if applicable)
- Any existing planning schema definitions
- Data models for plan parsing

## Success Criteria

1. Planning templates include impacted_files and impacted_artifacts sections
2. Planner agents have clear guidance on populating these sections
3. At least 3 example plans demonstrate the new sections
4. Orchestration can parse and use the scoping metadata
5. Documentation explains the rationale and usage patterns

## Related Plans

- Orchestration parallelization improvements
- Planning agent standardization efforts
- CLI planning command enhancements
