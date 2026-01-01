# Fresh Environment Testing Guide

This guide provides step-by-step instructions for testing MyAgents in a fresh environment to ensure it works for new users.

**Purpose**: Catch configuration issues and portability problems before they reach users

**Context**: Created based on GCPTOOLKIT-CONFIG-GAP-001, where automated tests passed but fresh environment testing would have caught the missing configuration file issue.

**Detection Behavior**: MyAgents uses simplified path detection with no fallbacks:
- **Project Root**: Walks up from CWD to find `langgraph.json`, stops at `/tmp` boundary
- **Config Path**: Checks only `~/.config/myagents/config.yml` (home-only, no project-level config)
- **LangGraph Path**: Checks only `~/.config/myagents/langgraph.json` (no auto-creation)
- **Error Guidance**: All errors guide users to run `myagents setup` or `myagents preferences`

---

## Why Fresh Environment Testing Matters

**Lesson Learned**: Automated tests passed with 98% pass rate, but system was unusable for end users due to missing configuration file.

**Root Cause**: Tests ran in environment with hidden/temporary configuration that wasn't documented or persisted.

**Prevention**: Fresh environment testing ensures:
- No hidden configuration
- Test environment = production environment
- Setup process actually works
- Documentation is accurate
- Portability issues caught early

---

## Test Environment Setup

### Prerequisites
- Clean Linux/macOS/Windows machine (or VM)
- Python 3.11+ installed
- Terminal access
- Internet connection (for GCP Secret Manager)
- GCP project with Secret Manager API enabled
- GCP service account with Secret Manager access

### Initial State Verification
Before starting, verify clean state:

```bash
# Check no existing MyAgents configuration
ls -la ~/.config/myagents/
# Should return: No such file or directory

# Check no existing gcptoolkit configuration
ls -la ~/.config/agent-gcptoolkit/
# Should return: No such file or directory

# Document starting environment
python --version
uname -a
pip list | grep -i agent
```

---

## Test Scenario 1: First-Time User (No Configuration)

### Objective
Verify error detection and auto-setup flow for user with zero configuration.

### Steps

1. **Install MyAgents** (follow installation docs exactly):
   ```bash
   # If testing from source
   git clone <repository>
   cd MyAgents
   uv sync
   pip install -e .

   # Verify installation
   myagents --version
   ```

2. **Attempt to run chat without configuration**:
   ```bash
   myagents chat
   ```

   **Expected Result**:
   - Error message displayed
   - Error mentions configuration file path: `~/.config/agent-gcptoolkit/config.yml`
   - Error shows exact commands to run
   - Auto-setup prompt appears (if interactive terminal)
   - Exit code is 1 (failure)

3. **Verify error message quality**:
   - [ ] Error message is clear and specific
   - [ ] Shows exact file path that's missing
   - [ ] Shows exact commands to run (`myagents config init`)
   - [ ] Includes troubleshooting steps
   - [ ] No technical jargon without explanation

4. **Test auto-setup prompt (interactive)**:
   ```bash
   # Run in interactive terminal
   myagents chat
   # Respond to prompt: Y
   ```

   **Expected Result**:
   - Configuration wizard starts
   - Prompts for GCP project ID
   - Prompts for service account path
   - Configuration file created
   - Chat starts immediately after setup

5. **Test non-interactive mode**:
   ```bash
   # Simulate CI/CD environment
   CI=true myagents chat
   ```

   **Expected Result**:
   - No interactive prompt
   - Clear error message with manual instructions
   - Exit code is 1 (failure)

### Success Criteria
- [ ] Error detection works correctly
- [ ] Error message is clear and actionable
- [ ] Auto-setup prompt works in interactive mode
- [ ] Non-interactive mode fails with clear instructions
- [ ] No crashes or stack traces
- [ ] All paths in error messages are portable (no hardcoded paths)

---

## Test Scenario 2: Configuration Setup Flow

### Objective
Verify configuration wizard creates valid configuration.

### Steps

1. **Clean environment**:
   ```bash
   rm -rf ~/.config/myagents/ ~/.config/agent-gcptoolkit/
   ```

2. **Run configuration wizard**:
   ```bash
   myagents config init
   ```

   **Expected Prompts**:
   - GCP project ID
   - Service account key path (or press Enter for ADC)

3. **Verify configuration file created**:
   ```bash
   # Check file exists
   ls -la ~/.config/agent-gcptoolkit/config.yml

   # View contents
   cat ~/.config/agent-gcptoolkit/config.yml
   ```

   **Expected Contents**:
   - `authentication` section
   - `gcp` section
   - `project_id` field
   - Valid YAML syntax

4. **Validate configuration**:
   ```bash
   myagents config verify
   ```

   **Expected Result**:
   - Validation passes
   - No errors or warnings
   - Success message displayed

5. **Test secret retrieval**:
   ```bash
   myagents secrets get GEMINI_API_KEY
   ```

   **Expected Result**:
   - Secret retrieved successfully
   - Secret value displayed (partially masked)
   - No errors

### Success Criteria
- [ ] Configuration wizard completes successfully
- [ ] Configuration file created at correct path
- [ ] Configuration file has all required sections
- [ ] Configuration validation passes
- [ ] Secret retrieval works
- [ ] No manual file editing required

---

## Test Scenario 3: Chat Command (Full Flow)

### Objective
Verify chat command works after configuration setup.

### Steps

1. **Ensure configuration is set up** (from Scenario 2)

2. **Change to project directory**:
   ```bash
   cd /path/to/MyAgents-<worktree>
   ```

3. **Start chat session**:
   ```bash
   myagents chat
   ```

   **Expected Result**:
   - Chat session starts without errors
   - No configuration errors
   - .env file created in worktree root
   - Chat interface appears

4. **Verify .env file creation**:
   ```bash
   cat .env
   ```

   **Expected Contents**:
   - Auto-generated header comment
   - GOOGLE_API_KEY (mapped from GEMINI_API_KEY)
   - LANGSMITH_API_KEY
   - LANGSMITH_TRACING
   - LANGSMITH_PROJECT

5. **Verify .env is ignored by git**:
   ```bash
   git status
   ```

   **Expected Result**:
   - .env should NOT appear in git status output
   - .gitignore contains .env entry

6. **Send test message**:
   ```
   > Hello, can you help me?
   ```

   **Expected Result**:
   - Agent responds appropriately
   - No errors in response
   - Response is coherent

### Success Criteria
- [ ] Chat starts successfully after configuration
- [ ] .env file auto-generated correctly
- [ ] .env contains all required keys
- [ ] .env is ignored by git
- [ ] Agent responds to messages
- [ ] No configuration errors

---

## Test Scenario 4: Studio Command

### Objective
Verify LangGraph Studio starts and works correctly.

### Steps

1. **Ensure configuration is set up** (from Scenario 2)

2. **Start Studio**:
   ```bash
   myagents studio start
   ```

   **Expected Result**:
   - Studio starts without errors
   - No API key errors
   - .env file created/updated
   - Studio accessible at http://localhost:2024

3. **Verify Studio UI**:
   - Open browser: http://localhost:2024
   - Check for API key error messages
   - Verify agents are available
   - Test running an agent

4. **Verify .env file**:
   ```bash
   cat .env
   ```

   **Expected Result**:
   - GOOGLE_API_KEY present
   - LANGSMITH_API_KEY present
   - LANGSMITH_PROJECT=myagents-default (Studio)

5. **Stop Studio**:
   ```bash
   myagents studio stop
   ```

   **Expected Result**:
   - Studio stops gracefully
   - No errors

### Success Criteria
- [ ] Studio starts successfully
- [ ] No API key missing errors
- [ ] .env file auto-generated
- [ ] Studio UI accessible
- [ ] Agents work in Studio
- [ ] Studio stops gracefully

---

## Test Scenario 5: Error Recovery

### Objective
Verify users can recover from error states.

### Steps

1. **Start with working configuration** (from Scenario 2)

2. **Remove configuration file** (simulate error):
   ```bash
   rm ~/.config/agent-gcptoolkit/config.yml
   ```

3. **Attempt to use chat**:
   ```bash
   myagents chat
   ```

   **Expected Result**:
   - Error detected
   - Clear error message
   - Auto-setup prompt (if interactive)
   - Recovery instructions

4. **Follow recovery instructions**:
   - Accept auto-setup prompt OR
   - Run `myagents config init` manually

5. **Verify recovery successful**:
   ```bash
   myagents chat
   ```

   **Expected Result**:
   - Chat works again
   - No lingering errors

6. **Test invalid configuration** (simulate error):
   ```bash
   echo "invalid yaml {{" > ~/.config/agent-gcptoolkit/config.yml
   ```

7. **Run configuration validation**:
   ```bash
   myagents config verify
   ```

   **Expected Result**:
   - Validation fails
   - Clear error message about YAML syntax
   - Recovery instructions

8. **Recover from invalid configuration**:
   ```bash
   myagents config init
   # Confirm overwrite
   ```

   **Expected Result**:
   - New valid configuration created
   - Validation passes

### Success Criteria
- [ ] Missing configuration detected
- [ ] Recovery instructions clear
- [ ] Auto-setup works for recovery
- [ ] Invalid configuration detected
- [ ] Validation provides clear errors
- [ ] Recovery process successful

---

## Test Scenario 6: Documentation Accuracy

### Objective
Verify SETUP.md can be followed exactly from fresh environment.

### Steps

1. **Clean environment**:
   ```bash
   rm -rf ~/.config/myagents/ ~/.config/agent-gcptoolkit/
   ```

2. **Open SETUP.md** and follow from line 1

3. **Execute each step exactly as documented**:
   - Note any missing steps
   - Note any incorrect steps
   - Note any unclear instructions
   - Note any steps that don't work

4. **Document results**:
   - Create test report: `tests/manual/follow_docs_test_report.md`
   - List all issues found
   - Suggest improvements

### Success Criteria
- [ ] Every step in SETUP.md works exactly as documented
- [ ] No missing steps
- [ ] No incorrect steps
- [ ] No ambiguous instructions
- [ ] Setup completes successfully
- [ ] All documented features work

---

## Test Scenario 7: Portability Testing

### Objective
Verify system works across different environments.

### Steps

1. **Test from different directories**:
   ```bash
   # Project commands require langgraph.json in tree
   cd /path/to/project/with/langgraph.json
   myagents chat  # Should work (walks up tree to find langgraph.json)

   # Global commands work from anywhere
   cd ~/Documents
   myagents preferences  # Should work (global command)
   myagents config show  # Should work (global command)

   # Project commands fail outside project
   cd /tmp
   myagents chat  # Should fail with error: "No langgraph.json found. Run from project directory or use 'myagents setup'."
   ```

2. **Test with different configurations**:
   - Service account key file
   - Application Default Credentials (ADC)
   - Different GCP projects

3. **Test on different platforms** (if applicable):
   - Linux
   - macOS
   - Windows (if supported)

4. **Verify no hardcoded paths**:
   ```bash
   # Test from non-project directory
   cd /tmp
   myagents chat 2>&1 | grep -i "MyAgents-<worktree>"
   # Should return nothing (no hardcoded worktree paths)

   # Verify error message is generic and helpful
   myagents chat
   # Should show: "No langgraph.json found. Run from project directory or use 'myagents setup'."
   ```

### Success Criteria
- [ ] Works from any directory
- [ ] No hardcoded paths in error messages
- [ ] Works with different configurations
- [ ] Cross-platform compatibility (if applicable)
- [ ] Portable file paths only

---

## Test Scenario 8: CI/CD Simulation

### Objective
Verify behavior in non-interactive CI/CD environments.

### Steps

1. **Clean environment**:
   ```bash
   rm -rf ~/.config/myagents/ ~/.config/agent-gcptoolkit/
   ```

2. **Simulate CI/CD environment**:
   ```bash
   export CI=true
   export GITHUB_ACTIONS=true  # Optional: simulate GitHub Actions
   ```

3. **Test commands in non-interactive mode**:
   ```bash
   myagents chat
   ```

   **Expected Result**:
   - No interactive prompts
   - Clear error message
   - Manual setup instructions
   - Exit code 1

4. **Set up configuration non-interactively**:
   ```bash
   # Document how to set up configuration in CI/CD
   # This may require manual config file creation or environment variables
   ```

5. **Verify commands work after setup**:
   ```bash
   myagents config show
   myagents secrets get GEMINI_API_KEY
   ```

### Success Criteria
- [ ] No interactive prompts in CI/CD mode
- [ ] Clear error messages for non-interactive mode
- [ ] Manual setup instructions provided
- [ ] Exit codes correct (0 for success, 1 for errors)
- [ ] Configuration can be set up non-interactively

---

## Test Results Template

Use this template to document fresh environment test results:

```markdown
# Fresh Environment Test Results

**Test Date:** YYYY-MM-DD
**Tester:** [Name]
**Environment:**
- OS: [Linux/macOS/Windows]
- OS Version: [Version]
- Python Version: [Version]
- MyAgents Version: [Version]

## Scenario Results

### Scenario 1: First-Time User
- Status: [PASS/FAIL]
- Issues Found: [List issues or "None"]
- Notes: [Additional observations]

### Scenario 2: Configuration Setup
- Status: [PASS/FAIL]
- Issues Found: [List issues or "None"]
- Notes: [Additional observations]

[Continue for all scenarios]

## Overall Assessment
- Total Scenarios: 8
- Passed: [N]
- Failed: [N]
- Pass Rate: [X%]

## Critical Issues
[List any critical issues that block release]

## Recommendations
[List recommendations for improvements]

## Conclusion
[READY FOR RELEASE / NOT READY - FIX ISSUES]
```

---

## Common Issues and Troubleshooting

### Issue: Configuration wizard doesn't start
**Symptoms**: `myagents config init` does nothing or errors
**Diagnosis**: Check Python version, installation
**Resolution**: Reinstall MyAgents, verify Python 3.11+

### Issue: Secrets not found
**Symptoms**: `myagents secrets get` fails
**Diagnosis**: GCP configuration or permissions issue
**Resolution**: Verify GCP project ID, service account access, Secret Manager API enabled

### Issue: .env file not created
**Symptoms**: Chat/Studio starts but .env missing
**Diagnosis**: Permission issues or implementation bug
**Resolution**: Check directory permissions, report bug

### Issue: Error messages show hardcoded paths
**Symptoms**: Error references "MyAgents-<worktree>" or other specific paths
**Diagnosis**: Portability issue
**Resolution**: Update error messages to use generic paths

### Issue: Documentation doesn't match reality
**Symptoms**: Steps in SETUP.md don't work
**Diagnosis**: Documentation out of sync
**Resolution**: Update documentation, re-test

---

## Best Practices

1. **Always start fresh**: Don't skip cleaning configuration
2. **Document everything**: Note all observations, even small ones
3. **Test exactly as users would**: No shortcuts or workarounds
4. **Verify error messages**: Read them as a new user would
5. **Test error recovery**: Don't just test happy path
6. **Check portability**: No hardcoded paths allowed
7. **Simulate CI/CD**: Test non-interactive mode
8. **Follow docs exactly**: Don't use prior knowledge

---

## Integration with Release Process

Fresh environment testing should be performed:
- Before every release (mandatory)
- After major configuration changes
- After documentation updates
- When bugs related to setup are fixed

This is Phase 5 of the pre-release checklist.

---

## References

- Pre-Release Checklist: `/home/code/myagents/MyAgents-<worktree>/docs/testing/pre_release_checklist.md`
- SETUP.md: `/home/code/myagents/MyAgents-<worktree>/SETUP.md`
- GCPTOOLKIT-CONFIG-GAP-001-REVISED plan: Detailed testing strategy
- Live Plan: `/home/code/myagents/docs/plans/live/251105_packaging.yml`
