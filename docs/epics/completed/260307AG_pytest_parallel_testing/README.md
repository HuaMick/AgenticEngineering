# Epic 260307AG: Pytest Parallel Testing with xdist + testmon

## Objective

Implement pytest-xdist for parallel test execution across AgenticCLI and AgenticGuidance
modules, and harmonize pytest-testmon for intelligent test selection in both modules.
The goal is to significantly reduce test feedback loop times while maintaining test
isolation and correctness.

## Current State

| Metric | AgenticCLI | AgenticGuidance |
|--------|-----------|-----------------|
| Test files | 76 | 25 |
| Test functions | ~1,568 | ~648 |
| pytest-xdist | ✅ 3.8.0 installed | ✅ 3.8.0 installed |
| pytest-testmon | ✅ 2.2.0 installed | ✅ 2.2.0 installed |
| Parallelization | ✅ `-n auto --dist loadgroup` | ✅ `-n auto --dist loadgroup` |
| addopts | `-m 'not uat' -n auto --dist loadgroup` | `-v --tb=short --testmon -n auto --dist loadgroup` |
| Integration test serialization | ✅ `xdist_group("integration")` in conftest.py | N/A |
| Makefile targets | ✅ test, test-fast, test-seq, test-all | ✅ test, test-fast, test-seq, test-all |
| Markers | unit, integration, experiment, slow, uat, ntfy | None configured |

## Results

All 6 phases complete, all 21 tickets done.

| Module | Passed | Skipped | Failures | Wall Time | Baseline | Speedup |
|--------|--------|---------|----------|-----------|----------|---------|
| AgenticCLI | 1,512 | 10 | 0 | 57s | 136s | 58% |
| AgenticGuidance | 640 | 0 | 3 (pre-existing) | 0.82s | 4.83s | 83% |

### Key Decisions

- AgenticCLI `addopts` omits `--testmon` from default to avoid conflicts with UAT marker
  filtering; testmon is available via `make test-fast`.
- AgenticGuidance `addopts` retains `--testmon` in default run since all tests qualify.
- Integration tests in AgenticCLI serialized via `xdist_group("integration")` in
  `conftest.py` to prevent tmux/CLI binary conflicts across workers.
- `.gitignore` updated to exclude `.testmondata-shm` and `.testmondata-wal` lock files.

## Story Discovery

**Fence: STORY-FIRST PLANNING** — Story discovery completed via `agentic agent stories find`.

### Affected Stories

This is an **infrastructure** epic improving developer test execution speed. It maps to:

- **US-DEV-010**: Run Tests via Agent — test-runner relies on fast pytest execution;
  parallel testing directly reduces agent feedback loop time
- **US-DEV-014**: DevOps Pipeline Audit — parallel testing is a pipeline optimization
- **US-GD-060**: Execute Python Tests — core test execution capability enhanced
- **US-GD-061**: Smoke Test Strategy — fast smoke tests benefit from parallelization
- **US-GD-062**: Test Execution Report — xdist changes output format; reports must handle it

### No Additional Stories Rationale

No new user stories are needed. This epic enhances the speed of an existing capability
(test execution) without changing user-facing behavior. All acceptance criteria from
existing stories remain valid — tests must still pass, reports must still be generated,
and the test-runner agent must still function correctly.

## Phases Overview

### Phase 1: Baseline & Dependencies
Capture sequential test execution times as baseline, install pytest-xdist in both
modules, and validate that the dependency installs cleanly.

### Phase 2: AgenticCLI Parallel Configuration
Configure xdist for AgenticCLI with proper worker count, ensure TinyDB isolation
fixtures work per-worker (each worker gets its own tmp_path), handle integration
test scheduling, and resolve any shared-state conflicts.

### Phase 3: AgenticGuidance Parallel Configuration
Configure xdist for AgenticGuidance, add testmon dependency (currently missing),
and ensure fixture isolation per worker.

### Phase 4: Makefile & Developer Ergonomics
Update Makefile targets for parallel execution, add new targets (test-fast, test-parallel),
create a Makefile for AgenticGuidance, and document usage patterns.

### Phase 5: UAT — Validate Parallel Testing
Execute end-to-end validation: run full suites in parallel mode, verify no test
pollution between workers, confirm testmon+xdist interplay, and measure speedup.

## Dependencies and Prerequisites

- **pytest-xdist>=3.0**: Parallel test execution via `-n auto` or `-n <workers>`
- **pytest-testmon>=2.0**: Already in AgenticCLI; needs adding to AgenticGuidance
- **Python 3.x**: Already available as `python3`
- **uv**: Already used for dependency management

### Key Constraints

1. **TinyDB isolation**: The `_isolate_tinydb` autouse fixture creates per-test
   tmp_path databases. With xdist, each worker gets its own tmp_path — this should
   work naturally but must be verified.
2. **testmon + xdist compatibility**: pytest-testmon v2.x supports xdist but requires
   `--testmon` without `--forked`. Must verify the combination works.
3. **Integration tests**: AgenticCLI's 18 integration tests use real CLI binary and
   tmux sessions — these may need sequential scheduling or grouping.
4. **Autouse fixtures**: Both modules use autouse session-scoped fixtures that must
   be validated for per-worker behavior.

## Success Criteria

1. **pytest-xdist installed** in both AgenticCLI and AgenticGuidance dev dependencies
2. **pytest-testmon installed** in AgenticGuidance (already present in AgenticCLI)
3. **All existing tests pass** with `-n auto` (parallel mode) — zero regressions
4. **Makefile targets updated** with parallel-aware test commands
5. **Measurable speedup**: ≥30% reduction in wall-clock time for full test suite
6. **testmon + xdist interplay verified**: selective test runs work under parallel mode
7. **No test pollution**: parallel workers cannot corrupt each other's state

## Resolved Questions

1. **Worker count strategy**: Using `-n auto` (CPU count) in both modules. Delivers
   the best local speedup (58% and 83% respectively) without configuration overhead.
2. **Integration test grouping**: AgenticCLI integration tests serialized via
   `xdist_group("integration")` in `conftest.py` — this prevents tmux/CLI binary
   conflicts across workers without requiring a separate sequential run.
3. **testmon database location**: Default `.testmondata` location works correctly with
   xdist's merge strategy. Lock files (`.testmondata-shm`, `.testmondata-wal`) added
   to `.gitignore`.
