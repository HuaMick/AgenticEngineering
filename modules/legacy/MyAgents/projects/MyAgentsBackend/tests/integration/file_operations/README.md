# File Operations - Integration Test Suite

This directory contains the comprehensive integration test suite for file operations.

> **Note (2025-11-27)**: Tests have been consolidated from four separate files into two files for better maintainability:
> - `test_core.py` - Core functionality (domain + tool tests)
> - `test_integration.py` - Workflow integration tests

## Test Structure

The test suite is organized into two main files:

### 1. Core Functionality Tests (`test_core.py`)
Consolidates domain-level and tool-level tests using parametrization.

**Coverage:**
- **Path Validation**: Relative paths, absolute paths, directory traversal, symlinks
- **File Operations**: Read, list, edit with various scenarios and error cases
- **Search Operations**: Pattern matching, glob patterns, path validation for search
- **Tool Registry**: Tool registration, lookup, delegation to domain
- **Tool Delegation**: Tools delegate to domain correctly and propagate errors
- **LLM Binding**: Tool schemas, parameters, and compatibility

**Purpose:** Verify core file operations and tool layer work correctly in isolation.

### 2. Workflow Integration Tests (`test_integration.py`)
Tests the coding agent workflow's integration with file operation tools.

**Coverage:**
- **Tool Binding**: Tools bind correctly to LLM
- **Tool Execution**: Tool calls execute from LLM responses
- **Error Handling**: FileNotFoundError, validation errors handled gracefully
- **State Management**: Iteration count, message history preserved
- **Multi-tool Workflows**: Chaining multiple operations

**Purpose:** Verify workflow layer can use tools via LLM binding without full E2E execution.

## Running Tests

### Run All Integration Tests
```bash
pytest tests/integration/file_operations/ -v
```

### Run Specific Test Files
```bash
# Core functionality tests (domain + tool tests consolidated)
pytest tests/integration/file_operations/test_core.py -v

# Integration tests (workflow integration)
pytest tests/integration/file_operations/test_integration.py -v
```

### Run by Test Markers
```bash
# Run only integration tests
pytest -m integration tests/integration/file_operations/ -v
```

### Run Specific Test Classes
```bash
# Path validation tests
pytest tests/integration/file_operations/test_core.py::TestPathValidation -v

# File operations tests
pytest tests/integration/file_operations/test_core.py::TestFileOperations -v

# Tool registry tests
pytest tests/integration/file_operations/test_core.py::TestToolRegistry -v
```

## Test Markers

- `@pytest.mark.integration` - Integration tests (all tests in this suite)

## Prerequisites

### For Domain and Tool Tests
- No external dependencies (use temp directories)
- Fast execution (< 1 second)

### For Workflow Integration Tests
- Mock LLM and API keys (no real API calls)
- Fast execution (< 1 second)

### For E2E Tests
- GEMINI_API_KEY available via Secret Manager
- Test directory accessible: `/home/code/myagents/test_data/`
- Real LLM calls (slower execution, ~5-10 seconds per test)

## Test Fixtures

### Common Fixtures
- `temp_dir` - Creates temporary directory for testing (auto-cleanup)
- `file_ops` - FileOperations instance with temp directory
- `setup_test_env` - Monkeypatches _file_ops for tool testing

## Success Criteria Validation

This test suite validates the following success criteria:

1. **All tool operations covered by tests** ✓
   - `test_core.py` covers read_file, list_files, edit_file, search_in_files, find_files
   - Tests delegation, error handling, and LLM binding

2. **Domain operations covered by tests** ✓
   - `test_core.py` covers all FileOperations methods
   - Tests validation, reading, listing, editing, searching

3. **Integration tests validate complete workflows** ✓
   - `test_integration.py` validates LLM-tool-domain flow
   - Tests workflow integration with tools

4. **Tests validate backward compatibility** ✓
   - Tool tests verify import paths and interfaces
   - State management tests ensure workflow compatibility

## Test Coverage

The test suite uses parametrized tests for efficiency while maintaining comprehensive coverage:

### Core Tests (`test_core.py`)
- **Path Validation**: Relative paths, absolute paths, directory traversal, symlinks
- **File Operations**: Read, list, edit with success and error cases
- **Search Operations**: Pattern matching, glob patterns, path validation
- **Tool Registry**: Registration, lookup, error handling
- **Tool Delegation**: Correct delegation to domain, error propagation
- **LLM Binding**: Schema validation, parameter checking

### Integration Tests (`test_integration.py`)
- **Tool Binding**: Tools bind correctly to LLM
- **Tool Execution**: Execution from LLM responses
- **Error Handling**: Various error scenarios
- **State Management**: Iteration tracking, message history
- **Multi-tool Workflows**: Chaining operations
- **Total: 6 integration tests**

### End-to-End Workflows
- File reading: 3 tests
- Directory listing: 2 tests
- File editing: 2 tests
- Security validation: 2 tests
- Multi-tool workflows: 2 tests
- Backward compatibility: 2 tests
- **Total: 13 E2E tests**

### Overall: 54 tests covering all layers

## Notes

- Domain and tool tests use temporary directories (no cleanup issues)
- E2E tests create files in `/home/code/myagents/test_data/` (auto-cleanup)
- Some tests may skip if dependencies are not available
- E2E tests use real workflows (no mocks) for true validation
- All tests are independent and can run in any order
