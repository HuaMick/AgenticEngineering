# Agent Offload Opportunities

## Summary
Analysis of planner and deploy agents to identify work that can be offloaded to CLI.

## High Priority Automation (No Reasoning Required)

### 1. Planning Folder Scaffolding
**Current Agent**: deploy-worktree

**Manual Steps**:
1. Generate folder name (YYMMDDRepo_Branch)
2. Create directory structure (live/, completed/)
3. Create 4 placeholder YAML files
4. Populate metadata in plan_live_teach.yml

**CLI Command**: `agentic worktree create` or `agentic plan scaffold`

**Friction Reduction**: 5-10 manual steps eliminated

### 2. Git Worktree Operations
**Current Agent**: deploy-worktree

**Manual Steps**:
1. Determine repository root
2. Create worktree: `git worktree add -b <branch> <path>`
3. Verify creation
4. Update VS Code workspace file

**CLI Command**: `agentic worktree create`

**Friction Reduction**: Git commands + JSON manipulation eliminated

### 3. Plan File Generation from Templates
**Current Agents**: planner-build, planner-test, planner-cleaning

**Manual Steps**:
1. Read example plan files
2. Copy structure
3. Update for specific domain
4. Create properly formatted YAML

**CLI Command**: `agentic template generate <type>`

**Friction Reduction**: Template copying + manual editing eliminated

### 4. Plan Folder Validation
**Current Agents**: All planners

**Manual Steps**:
1. Check folder has live/ and completed/
2. Verify required files exist
3. Validate YAML syntax
4. Check input references

**CLI Command**: `agentic plan validate`

**Friction Reduction**: Validation logic centralized

## Medium Priority Automation

### 5. Input File Resolution
**Current Agents**: All agents

**Manual Steps**:
1. Check if referenced files exist
2. Resolve paths across bases
3. Validate YAML syntax
4. Report discrepancies

**CLI Command**: `agentic inputs validate/resolve`

### 6. Planning State Management
**Current Agents**: planner-cleaning

**Manual Steps**:
1. Read phase files
2. Identify completed items
3. Move to plan_completed.yml
4. Track lifecycle state

**CLI Command**: `agentic plan task complete`

### 7. User Story Integration
**Current Agents**: planner-test, planner-cleaning

**Manual Steps**:
1. Scan userstories directory
2. Parse and categorize
3. Map to test phases
4. Reference in success criteria

**CLI Command**: `agentic stories find`

## Expected CLI Commands Summary

```bash
# Worktree management
agentic worktree create <branch>
agentic worktree list
agentic worktree remove <branch>

# Plan management
agentic plan scaffold <name>
agentic plan status
agentic plan validate <path>
agentic plan task start/complete <id>
agentic plan archive

# Input validation
agentic inputs validate <file>
agentic inputs resolve <file>

# Templates
agentic template generate build|test|cleanup

# User stories
agentic stories find [--project <p>]

# CI/CD
agentic cicd audit
```

## Impact by Agent

| Agent | CLI Commands to Use | Work Eliminated |
|-------|---------------------|-----------------|
| deploy-worktree | worktree create, plan scaffold | Git + folder + file creation |
| planner-build | template generate, inputs validate | Template copying, validation |
| planner-test | stories find, template generate | Story scanning, templates |
| planner-cleaning | plan task complete, plan archive | YAML editing, folder copying |
| planner-reviewer | plan validate, inputs validate | Structure validation |
| deploy-cicd | cicd audit | Manual file comparison |
