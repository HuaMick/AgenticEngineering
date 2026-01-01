# Secrets Workflow Testing Guide

This directory contains tests for the secrets workflow, which manages API keys and secrets via GCP Secret Manager.

## Test Structure

Tests for secrets workflow are integrated into other workflow tests. This directory serves as a placeholder for dedicated secrets workflow tests.

## Testing Guidance

### Secrets Workflow Testing Pattern

When testing the secrets workflow, follow this sequence:

1. **Verify Secret Retrieval**
   - Test retrieval of valid secrets
   - Verify secrets are correctly fetched from GCP Secret Manager
   - Verify fallback behavior (if applicable)

2. **Test Error Handling**
   - Test with missing secrets
   - Test with invalid secret names
   - Verify error messages are clear
   - Test recovery scenarios

3. **Test Secret Usage**
   - Verify secrets are correctly injected into workflows
   - Test that workflows can use retrieved secrets
   - Verify secrets are not exposed in logs

### Integration with Other Workflows

Secrets workflow is typically tested as part of other workflows:

- **Coding Agent**: Uses `get_secret("GEMINI_API_KEY")` for API access
- **Echo Agent**: Uses `get_secret("GEMINI_API_KEY")` for API access
- **Studio Service**: Uses `get_secret("LANGSMITH_API_KEY")` for tracing

Test secrets workflow indirectly by:

1. Running workflows that depend on secrets
2. Verifying workflows succeed when secrets are available
3. Verifying workflows fail gracefully when secrets are missing
4. Checking that error messages guide users to configure secrets

## Running Tests

```bash
# Run workflow tests that use secrets
pytest tests/workflows/agent_chat/ -v

# Run infrastructure tests that use secrets
pytest tests/workflows/infrastructure/test_studio_service.py -v
```

## Prerequisites

- GCP Secret Manager configured
- Required secrets available:
  - `GEMINI_API_KEY` - For AI model access
  - `LANGSMITH_API_KEY` - For observability
- GCP project credentials configured
- Service account with Secret Manager access

## Test Scenarios

### Secret Retrieval

1. **Valid Secret**
   - Request secret that exists
   - Verify secret is returned
   - Verify secret format is correct

2. **Missing Secret**
   - Request secret that doesn't exist
   - Verify appropriate error is raised
   - Verify error message guides user

3. **Invalid Secret Name**
   - Request secret with invalid name
   - Verify error handling
   - Verify clear error message

### Integration Testing

Test secrets workflow through dependent workflows:

1. **Workflow Success**
   - Ensure secrets are configured
   - Run dependent workflow
   - Verify workflow succeeds

2. **Workflow Failure (Missing Secrets)**
   - Remove or invalidate secret
   - Run dependent workflow
   - Verify workflow fails gracefully
   - Verify error message is helpful

## Notes

- Secrets workflow is typically tested indirectly through other workflows
- Direct unit tests can be added here if needed
- Focus on integration testing with workflows that use secrets
- Ensure secrets are never logged or exposed in test output

