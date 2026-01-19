# Audit Report: Worktree-Locality Instructions

**Date**: 2026-01-19
**Auditor**: explore agent
**Status**: Complete

## Executive Summary

Analyzed 4 guidance files for worktree-locality instructions conflicting with Main-First Planning. Found **5 major instruction sets** requiring remediation.

## Files Analyzed

1. `orchestration-planning/process.mmd`
2. `orchestration-planning/inputs.yml`
3. `worktree-and-branching.yml`
4. `plans.yml`

## Findings

### 1. process.mmd (lines 49-68) - CRITICAL
**Issue**: `agentic plan init <branch>` creates worktree FIRST, then plan folder in that worktree.
**Conflict**: Main-First requires plan creation in main before worktree switching.

### 2. plans.yml (lines 1-3, 24-40) - HIGH
**Issue**: Definition states "Plans are organized by worktree" with naming convention embedding worktree suffix.
**Conflict**: Main-First requires plans to live in main initially.

### 3. worktree-and-branching.yml (lines 12-23) - MEDIUM
**Issue**: "Main branch as source of truth" rule not extended to plan creation.
**Conflict**: Inconsistent - guidance syncs from main but plans don't.

### 4. inputs.yml (lines 259-263) - MEDIUM
**Issue**: `agentic plan init <branch>` marked as PREFERRED. No main-branch pathway documented.
**Conflict**: No guidance for creating plans in main first.

## Summary Table

| Location | Severity | Update Needed |
|----------|----------|---------------|
| process.mmd:49-68 | CRITICAL | Add main-first plan creation flow |
| plans.yml:1-3, 24-40 | HIGH | Update definition for main-first org |
| worktree-and-branching.yml:12-23 | MEDIUM | Extend rule to plan creation |
| inputs.yml:259-263 | MEDIUM | Document main-branch plan init |

## Architectural Observation

Current guidance embeds **Feature-First Planning** assumption. Main-First Planning requires architectural inversion where plans are created in main FIRST, then synced to worktrees.
