# Test Examples: Tests That Should NOT Be Skipped

This directory contains example test files demonstrating tests that should **NOT** be skipped and why.

## Purpose

These examples guide test agents on:
1. Which tests should NOT be skipped
2. How to handle setup requirements (install tools, start services)
3. When skipping is acceptable vs when setup should be performed

## Key Principles

### 1. Credential-Based Tests Should NOT Be Skipped

**Principle**: If credentials or authentication are available through tooling or infrastructure, tests should use them rather than skip.

- Tests requiring credentials should use available authentication mechanisms
- If authentication helpers are missing, install them rather than skip
- If authentication fails, it's a bug to investigate, not a reason to skip

**Example**: Tests requiring GCP authentication should use available service account credentials and GCP tooling rather than skip.

### 2. Service-Based Tests Should NOT Be Skipped

**Principle**: If a service can be started before tests run, tests should NOT be skipped.

- Test agents should start required services before running tests
- Wait for services to be ready before executing tests
- Stop services after tests complete
- If a service fails to start, that's a bug to investigate

**Example**: Studio service tests should start the LangGraph Studio service before running tests, not skip when service is not running.

### 3. Setup Requirements Should Be Met, Not Skipped

**Principle**: Most setup can be automated (install tools, start services, clone repos).

- If a tool is missing, install it
- If a service is not running, start it
- If a repository is missing, clone it or find it
- If a package is missing, install it
- Only skip for truly unfabricatable conditions

**Example**: Tests requiring Agent-GCPtoolkit should locate the repository in parent directories or sibling worktrees rather than skip.

## When Skipping IS Acceptable

Only skip tests when:
1. **Truly unfabricatable conditions**: Production infrastructure failures that cannot be simulated
2. **Explicitly documented acceptable skips**: See project-specific documentation
3. **User explicitly requests skip**: For specific test scenarios

## Test Agent Responsibilities

When encountering a test that might be skipped:

1. **Check if setup can be performed**:
   - Install missing tools
   - Start required services
   - Clone missing repositories
   - Install missing packages
   - Configure missing dependencies

2. **Use available credentials and authentication**:
   - Use available authentication mechanisms
   - Install authentication helpers if needed
   - Don't skip due to "missing credentials" if credentials are available through tooling

3. **Start services before tests**:
   - Start required services before test execution
   - Wait for services to be ready
   - Stop services after tests complete

4. **Only skip if truly necessary**:
   - After attempting setup
   - After checking alternative locations
   - After verifying the condition cannot be fabricated

## Files in This Directory

- `README.md`: This file - Guidelines and examples for tests that should NOT be skipped
- `final_outcome_report.yml`: Example format for final summary reports produced by the audit agent
- `critical_questions.yml`: Examples of skeptical questions the audit agent should ask when reviewing execution data

## Critical Questions for Final Output Audit

The `critical_questions.yml` file provides examples of red flags and skeptical questions for the final output audit agent. Key patterns to watch for:

### Red Flags That Indicate Workarounds (Not Fixes)

1. **Wrapper scripts instead of proper installation**
   - Question: "Why is a wrapper script needed? Shouldn't `uv pip install -e .` be sufficient?"
   
2. **Test/production environment divergence**
   - Question: "Testing with code may use different execution paths than Agent UAT which tests installed CLI via subagents - are these testing the same thing?"
   - Note: Agent UAT uses subagents; Human UAT uses actual humans (not what agents perform)
   
3. **Hardcoded paths to specific worktrees**
   - Question: "What happens when this runs on a different machine without this exact path?"

4. **Manual file creation instead of automated setup**
   - Question: "Shouldn't `myagents setup` create this file automatically?"

5. **Skipped tests hidden in passed summaries**
   - Question: "Which specific tests were skipped and why?"

The audit agent should challenge workarounds and ask: "Why can't we fix the root cause instead?"

## Integration with Test Agents

These examples are included as inputs to test agent processes. Test agents should reference these examples when:
- Deciding whether to skip a test
- Determining what setup to perform
- Understanding acceptable vs unacceptable skips
- Reviewing final output from orchestration agents (critical_questions.yml)
