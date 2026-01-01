# Pre-Release Checklist

This checklist must be completed before any release to prevent testing gaps and ensure the system works for end users.

**Purpose**: Ensure automated tests passing = system actually works for end users

**Context**: Created based on lessons learned from GCPTOOLKIT-CONFIG-GAP-001, where 98% automated test pass rate did not prevent critical production failure.

---

## Phase 1: Automated Testing

### Unit and Integration Tests
- [ ] All automated tests pass (100% pass rate)
- [ ] No skipped or disabled tests
- [ ] Test coverage meets requirements
- [ ] No test warnings or deprecation notices

### Build Validation
- [ ] Clean build completes successfully
- [ ] No compilation warnings or errors
- [ ] All dependencies resolve correctly
- [ ] Package installation works (`pip install -e .` or `uv sync`)

---

## Phase 2: Fresh Environment Testing

### Clean Environment Setup
- [ ] Remove all configuration: `rm -rf ~/.config/myagents/ ~/.config/agent-gcptoolkit/`
- [ ] Verify clean state: `ls ~/.config/` (should not show myagents or agent-gcptoolkit)
- [ ] Document starting environment (OS, Python version, installed packages)

### Fresh Installation Test
- [ ] Install from scratch in clean environment
- [ ] No pre-existing configuration
- [ ] No environment variables set
- [ ] Installation completes without errors

### First-Run Experience
- [ ] Run primary command without setup (e.g., `myagents chat`)
- [ ] Error message displayed is clear and actionable
- [ ] Error message shows exact file paths
- [ ] Error message shows exact commands to run
- [ ] Auto-setup prompt appears (if interactive terminal)
- [ ] Error message includes troubleshooting steps

### Configuration Setup
- [ ] Run configuration wizard (`myagents config init`)
- [ ] Wizard prompts for all required information
- [ ] Configuration file created at correct path
- [ ] Configuration file has all required sections
- [ ] Configuration validation passes (`myagents config verify`)

### Post-Setup Functionality
- [ ] Primary commands work after setup
- [ ] No additional configuration required
- [ ] Auto-generated files created correctly (e.g., .env files)
- [ ] All documented features accessible

---

## Phase 3: Manual Verification

### Manual Test Execution
- [ ] Execute manual test checklist (see Phase 6 in plan)
- [ ] All checklist items completed successfully
- [ ] No unexpected errors encountered
- [ ] No undocumented steps required

### User Workflow Testing
- [ ] Test complete user workflows from start to finish
- [ ] Test error recovery scenarios
- [ ] Test configuration modification scenarios
- [ ] Test upgrade/migration scenarios (if applicable)

### Cross-Platform Testing (if applicable)
- [ ] Test on Linux
- [ ] Test on macOS
- [ ] Test on Windows (if supported)
- [ ] Document platform-specific issues

---

## Phase 4: Documentation Validation

### Follow-Docs-Exactly Test
- [ ] Fresh environment prepared
- [ ] Follow SETUP.md from line 1 with no prior knowledge
- [ ] Every step works exactly as documented
- [ ] No missing steps identified
- [ ] No incorrect steps identified
- [ ] No ambiguous instructions

### Documentation Completeness
- [ ] All setup steps documented
- [ ] All configuration options documented
- [ ] All commands documented with examples
- [ ] All error messages documented with recovery steps
- [ ] Troubleshooting section comprehensive
- [ ] Prerequisites clearly stated

### Documentation Accuracy
- [ ] File paths are correct and portable (no hardcoded paths)
- [ ] Command examples are correct and tested
- [ ] Code snippets are accurate
- [ ] Configuration examples are valid
- [ ] Links and references are working
- [ ] Version-specific information is accurate

---

## Phase 5: Blind-Test Validation (Critical Features)

### Blind-Test Setup
- [ ] Create test scenarios for agent with NO prior knowledge
- [ ] Test scenarios cover complete user journey
- [ ] Agent has access ONLY to documentation (SETUP.md, README.md)
- [ ] Agent has NO access to codebase or implementation details

### Blind-Test Execution
- [ ] Agent successfully completes setup using docs only
- [ ] Zero manual file creation/editing required
- [ ] No undocumented steps encountered
- [ ] All documented steps work as described
- [ ] Error recovery possible using docs only

### Blind-Test Results
- [ ] All test scenarios pass
- [ ] Documentation gaps identified and fixed
- [ ] Implementation issues identified and fixed
- [ ] Re-test after fixes confirms resolution

---

## Phase 6: Error Handling and Recovery

### Error Scenario Testing
- [ ] Missing configuration file
- [ ] Invalid configuration file (malformed YAML)
- [ ] Missing required fields in configuration
- [ ] Invalid paths in configuration
- [ ] Missing dependencies
- [ ] Permission errors
- [ ] Network connectivity issues (if applicable)

### Error Message Quality
- [ ] All error messages are clear and specific
- [ ] Error messages show exact paths
- [ ] Error messages show exact commands
- [ ] Error messages include troubleshooting steps
- [ ] No technical jargon without explanation
- [ ] Error messages tested for clarity

### Recovery Path Testing
- [ ] Recovery steps documented for each error scenario
- [ ] Recovery steps tested and verified working
- [ ] Users can recover from errors without manual file editing
- [ ] Auto-repair/auto-setup works correctly

---

## Phase 7: Production Environment Simulation

### Environment Matching
- [ ] Test environment configuration matches production
- [ ] No hidden configuration in test environment
- [ ] No environment variables not available in production
- [ ] No test-specific mocks or stubs that bypass real functionality

### Non-Interactive Mode Testing
- [ ] Test in CI/CD environment (set CI=true)
- [ ] Error messages appropriate for non-interactive mode
- [ ] No interactive prompts in non-interactive mode
- [ ] Exit codes correct (0 for success, non-zero for errors)
- [ ] Logs are clear and actionable

### Performance Validation
- [ ] Startup time acceptable
- [ ] Response time acceptable
- [ ] Resource usage acceptable
- [ ] No memory leaks
- [ ] No performance regressions

---

## Phase 8: Security Validation

### Secrets Management
- [ ] No secrets in code
- [ ] No secrets in configuration files committed to git
- [ ] Secrets properly masked in logs and error messages
- [ ] .gitignore includes all sensitive files
- [ ] Service account files properly secured (chmod 600)

### Dependency Security
- [ ] No known vulnerabilities in dependencies
- [ ] Dependency versions pinned or constrained
- [ ] Security scan completed (if available)
- [ ] License compliance verified

---

## Phase 9: Regression Testing

### Existing Functionality
- [ ] All existing features still work
- [ ] No breaking changes to public API
- [ ] No performance regressions
- [ ] No security regressions

### Backward Compatibility
- [ ] Existing configurations still work
- [ ] Migration path documented (if breaking changes)
- [ ] Deprecation warnings in place (if applicable)
- [ ] Compatibility matrix updated

---

## Phase 10: Release Artifacts

### Documentation
- [ ] CHANGELOG.md updated with all changes
- [ ] Version number updated in all locations
- [ ] Release notes prepared
- [ ] Migration guide prepared (if needed)

### Build Artifacts
- [ ] Package builds successfully
- [ ] Package metadata correct (version, description, etc.)
- [ ] Package includes all required files
- [ ] Package excludes test files and development artifacts

### Distribution
- [ ] Distribution package tested in clean environment
- [ ] Installation instructions accurate
- [ ] Upgrade instructions accurate (if applicable)
- [ ] Rollback procedure documented

---

## Phase 11: Final Sign-Off

### Stakeholder Review
- [ ] Technical review completed
- [ ] Documentation review completed
- [ ] Security review completed (if required)
- [ ] User acceptance testing completed (if applicable)

### Release Approval
- [ ] All checklist items completed
- [ ] All critical issues resolved
- [ ] All high-priority issues resolved or deferred
- [ ] Release notes approved
- [ ] Go/No-Go decision documented

---

## Critical Reminders

**Remember:**
- Automated tests passing ≠ system works for end users
- Fresh environment testing is mandatory
- Manual verification is required
- Documentation must be tested by following it exactly
- Test environment must match production environment
- No hidden configuration allowed
- Blind-test validation proves documentation completeness

**If in doubt:**
- Run fresh environment test again
- Follow documentation exactly from line 1
- Test error scenarios and recovery paths
- Verify with manual verification checklist

---

## Checklist Completion

**Release Version:** _______________
**Date:** _______________
**Completed By:** _______________

**Overall Status:**
- [ ] All phases completed successfully
- [ ] All critical items checked
- [ ] No blocking issues remaining
- [ ] Ready for release

**Sign-off:**

Technical Lead: _______________ Date: _______________
Documentation Lead: _______________ Date: _______________
QA Lead: _______________ Date: _______________

---

## Appendix: Common Pitfalls

Based on lessons learned from GCPTOOLKIT-CONFIG-GAP-001:

1. **Automated tests passing but system doesn't work**
   - Cause: Test environment ≠ production environment
   - Prevention: Fresh environment testing mandatory

2. **Documentation exists but users can't follow it**
   - Cause: Documentation not tested by following it exactly
   - Prevention: Follow-docs-exactly test mandatory

3. **Documentation is long but incomplete**
   - Cause: Length ≠ quality, missing critical steps
   - Prevention: Blind-test validation

4. **Error messages not actionable**
   - Cause: Generic errors without specific guidance
   - Prevention: Error message quality checks

5. **Hidden configuration in tests**
   - Cause: Test setup creates configuration not available to users
   - Prevention: No hidden configuration allowed

6. **Manual verification skipped**
   - Cause: Assumed automated tests are sufficient
   - Prevention: Manual verification mandatory

7. **Test environment has shortcuts**
   - Cause: Test setup bypasses normal user setup flow
   - Prevention: Test must go through same flow as users

8. **Documentation updated after testing**
   - Cause: Documentation changes not re-tested
   - Prevention: Documentation loop at very end

9. **Recovery paths not tested**
   - Cause: Only happy path tested
   - Prevention: Error scenario testing mandatory

10. **Blind trust in process**
    - Cause: Following process without understanding why
    - Prevention: This checklist documents the "why"
