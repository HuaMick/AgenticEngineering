# Manual Setup Steps for Decentralized GitHub Issues Planning

This document outlines the manual setup steps required before implementing the decentralized GitHub Issues planning system.

## Overview

The goal is to migrate from centralized YAML plan files (`docs/plans/live/*.yml`) to decentralized GitHub Issues where:
- Each agent task becomes its own GitHub Issue
- Agents read their assigned issue to discover all context
- Agents update their issue as they work (checkboxes, comments, Progress section)
- Orchestration agent queries issues to discover work

## Prerequisites

1. **GitHub Repository**: Ensure you have a GitHub repository for this project
2. **GitHub Token**: You'll need a GitHub Personal Access Token (PAT) with `repo` scope
3. **Python Environment**: Python 3.8+ with `uv` package manager

## Step 1: Create GitHub Issue Templates

Create issue templates in `.github/ISSUE_TEMPLATE/` directory:

### 1.1 Epic Template (`.github/ISSUE_TEMPLATE/epic.yml`)

```yaml
name: Plan Epic
description: Create a new plan/epic for agent orchestration
title: "[Plan] "
labels: ["epic", "plan"]
body:
  - type: input
    id: plan_id
    attributes:
      label: Plan ID
      description: Unique identifier for this plan (e.g., FOLDER_RESTRUCTURE_001)
      placeholder: PLAN_ID
  - type: textarea
    id: description
    attributes:
      label: Description
      description: High-level description of what this plan accomplishes
  - type: input
    id: worktree
    attributes:
      label: Worktree Path
      description: Path to the worktree for this plan
      placeholder: /home/code/myagents/MyAgents
  - type: textarea
    id: phases
    attributes:
      label: Phases Overview
      description: List of phases in this plan (will be created as separate issues)
```

### 1.2 Phase Template (`.github/ISSUE_TEMPLATE/phase.yml`)

```yaml
name: Phase
description: Create a phase within a plan
title: "[Phase] "
labels: ["phase"]
body:
  - type: input
    id: plan_id
    attributes:
      label: Plan ID
      description: Parent plan ID (label)
      placeholder: PLAN_ID
  - type: input
    id: phase_name
    attributes:
      label: Phase Name
      description: Name of this phase
      placeholder: Preparation & Analysis
  - type: dropdown
    id: execution_type
    attributes:
      label: Execution Type
      options:
        - sequential
        - parallel
        - test-fix-loop
        - audit-test-fix-loop
  - type: textarea
    id: agent_tasks
    attributes:
      label: Agent Tasks Overview
      description: List of agent tasks in this phase (will be created as separate issues)
```

### 1.3 Agent Task Template (`.github/ISSUE_TEMPLATE/agent_task.yml`)

```yaml
name: Agent Task
description: Create an agent task issue
title: "[Agent] "
labels: ["agent-task"]
body:
  - type: input
    id: plan_id
    attributes:
      label: Plan ID
      description: Parent plan ID (label)
      placeholder: PLAN_ID
  - type: input
    id: phase_name
    attributes:
      label: Phase Name
      description: Parent phase name (label)
      placeholder: Preparation & Analysis
  - type: dropdown
    id: agent_type
    attributes:
      label: Agent Type
      options:
        - planner
        - build
        - test
        - cleaner
        - audit
  - type: textarea
    id: input_files
    attributes:
      label: Input Files
      description: List of file paths (one per line) that this agent needs
      placeholder: |
        /path/to/file1.py
        /path/to/file2.yml
  - type: textarea
    id: guidance
    attributes:
      label: Guidance
      description: Full context and instructions for the agent
      placeholder: |
        Context: ...
        
        Instructions:
        1. ...
        2. ...
        
        Why this matters: ...
  - type: textarea
    id: success_criteria
    attributes:
      label: Success Criteria
      description: List success criteria as checkboxes (one per line)
      placeholder: |
        - [ ] Criterion 1
        - [ ] Criterion 2
  - type: textarea
    id: tasks
    attributes:
      label: Tasks
      description: List tasks as checkboxes (one per line)
      placeholder: |
        - [ ] Task 1
        - [ ] Task 2
  - type: textarea
    id: progress
    attributes:
      label: Progress
      description: Agent will update this section as work progresses
      value: |
        ## Progress
        
        _Agent will update this section with findings and work done._
```

## Step 2: Set Up GitHub Labels

Create the following label structure in your GitHub repository:

### Required Labels

**Plan Labels:**
- `plan_id:<PLAN_ID>` (e.g., `plan_id:FOLDER_RESTRUCTURE_001`) - One per plan
- `epic` - For plan/epic issues
- `phase` - For phase issues
- `agent-task` - For agent task issues

**Status Labels:**
- `status:pending` - Work not started
- `status:in_progress` - Work in progress
- `status:blocked` - Work blocked
- `status:done` - Work complete

**Agent Type Labels:**
- `agent_type:planner`
- `agent_type:build`
- `agent_type:test`
- `agent_type:cleaner`
- `agent_type:audit`

**Worktree Labels:**
- `worktree:<path>` (e.g., `worktree:/home/code/myagents/MyAgents`) - One per worktree

### Label Colors (Recommended)

- Plan labels: Blue (`#0052CC`)
- Status labels: Green (`#0E8A16`) for done, Yellow (`#FBBA00`) for in_progress, Red (`#D93F0B`) for blocked
- Agent type labels: Purple (`#5319E7`)
- Worktree labels: Gray (`#B60205`)

## Step 3: Set Up GitHub Token Secret

Store your GitHub Personal Access Token securely:

1. **Create GitHub PAT:**
   - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate new token with `repo` scope
   - Copy the token

2. **Store Token:**
   - Add to your secrets management (e.g., `secrets/GITHUB_TOKEN`)
   - Or use environment variable: `export GITHUB_TOKEN=your_token_here`
   - **Never commit tokens to git**

## Step 4: Manual Prototype (GH-008)

Before building automation, manually create issues for one plan to validate the approach:

### 4.1 Select a Test Plan

Choose a simple plan from `docs/plans/live/` (e.g., `251122_main.yml` or a small subset of `251124_folder_restructure.yml`)

### 4.2 Create Epic Issue

1. Go to GitHub Issues → New Issue
2. Use Epic template
3. Fill in:
   - Plan ID: `TEST_PLAN_001`
   - Description: Copy from YAML plan
   - Worktree: Copy from YAML plan
   - Phases: List phase names
4. Add labels: `epic`, `plan_id:TEST_PLAN_001`, `worktree:<path>`
5. Create issue and note the issue number (e.g., #123)

### 4.3 Create Phase Issues

For each phase in the plan:

1. Go to GitHub Issues → New Issue
2. Use Phase template
3. Fill in:
   - Plan ID: `TEST_PLAN_001`
   - Phase Name: Copy from YAML
   - Execution Type: Copy from YAML
   - Agent Tasks: List agent task names
4. Add labels: `phase`, `plan_id:TEST_PLAN_001`, `phase:<phase_name>`
5. In issue body, add link to epic: `Parent: #123`
6. Create issue and note the issue number

### 4.4 Create Agent Task Issues

For each agent task in each phase:

1. Go to GitHub Issues → New Issue
2. Use Agent Task template
3. Fill in:
   - Plan ID: `TEST_PLAN_001`
   - Phase Name: Copy from YAML
   - Agent Type: Copy from YAML
   - Input Files: Copy from YAML (one per line)
   - Guidance: Copy full guidance section from YAML
   - Success Criteria: Convert to checkboxes (`- [ ] Criterion`)
   - Tasks: Convert to checkboxes (`- [ ] Task`)
   - Progress: Leave empty (agents will fill)
4. Add labels:
   - `agent-task`
   - `plan_id:TEST_PLAN_001`
   - `phase:<phase_name>`
   - `agent_type:<agent_type>`
   - `status:pending`
   - `worktree:<path>`
5. In issue body, add link to phase: `Parent Phase: #<phase_issue_number>`
6. Create issue and note the issue number

### 4.5 Test Agent Workflow

1. **Test Agent Reading:**
   - Manually assign an agent task issue to yourself
   - Verify you can extract all needed info from issue body:
     * Guidance section
     * Success criteria (checkboxes)
     * Tasks (checkboxes)
     * Input files

2. **Test Agent Updating:**
   - Update a checkbox (`- [ ]` → `- [x]`)
   - Add a comment with progress
   - Update Progress section
   - Change label from `status:pending` to `status:in_progress`

3. **Test Orchestration Querying:**
   - Query issues by label: `plan_id:TEST_PLAN_001`
   - Group by phase label
   - Filter by status: `status:pending`
   - Verify you can discover all work to be done

### 4.6 Document Findings

Create `docs/research/github_issues_prototype_findings.md` with:
- What worked well
- What was difficult
- Any issues discovered
- Recommendations for automation

## Step 5: Repository Structure

Ensure your repository has this structure:

```
.github/
  ISSUE_TEMPLATE/
    epic.yml
    phase.yml
    agent_task.yml
docs/
  plans/
    live/          # YAML plans (will be migrated)
    backlog/       # Backlog plans
    completed/     # Completed plans
  research/
    github_issues_prototype_findings.md
src/               # Or your code structure
  github_issues/   # Future: GitHub Issues API wrapper
    __init__.py
    api.py
    templates.py
secrets/
  GITHUB_TOKEN     # GitHub PAT (gitignored)
```

## Step 6: Next Steps After Manual Setup

Once manual prototype is validated:

1. **Build API Wrapper (GH-001)**
   - Create `src/github_issues/api.py`
   - Implement functions for create, read, update, delete issues
   - Handle checkbox updates in markdown

2. **Update Planner Agent (GH-003)**
   - Modify `frontend/agents/planner/processes/build.yml`
   - Replace YAML creation with GitHub Issues API calls

3. **Update Orchestration Agent (GH-004)**
   - Modify `frontend/agents/orchestration/start.yml`
   - Replace YAML reading with GitHub Issues API queries

4. **Update Build/Test/Cleaner Agents (GH-005)**
   - Modify agent process files
   - Agents receive issue numbers, read via API, update directly

5. **Create Migration Script (GH-006)**
   - Script to convert existing YAML plans to GitHub Issues
   - Run for all plans in `docs/plans/live/`

## Checklist

- [ ] Issue templates created (epic, phase, agent_task)
- [ ] GitHub labels created (plan_id, phase, status, agent_type, worktree)
- [ ] GitHub token stored securely
- [ ] Manual prototype created (one plan → issues)
- [ ] Agent reading workflow tested
- [ ] Agent updating workflow tested
- [ ] Orchestration querying workflow tested
- [ ] Findings documented
- [ ] Repository structure ready

## Notes

- **Start Small**: Begin with one simple plan to validate approach
- **Iterate**: Refine templates and labels based on prototype findings
- **Document**: Keep notes on what works and what doesn't
- **Backward Compatible**: Keep YAML support during transition (flag-based)

## Questions to Answer During Prototype

1. Can agents extract all needed context from issue body alone?
2. Is checkbox updating in markdown reliable?
3. Do labels provide enough filtering/grouping capability?
4. Can orchestration agent discover work effectively via queries?
5. Is the issue hierarchy clear and maintainable?
6. Are there any GitHub API limitations we need to work around?

