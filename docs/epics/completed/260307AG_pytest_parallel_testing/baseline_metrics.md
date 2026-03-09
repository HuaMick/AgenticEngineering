# Test Execution Metrics

Captured: 2026-03-07

## Sequential Baselines (Before Parallelization)

### AgenticCLI (Sequential, no testmon)

| Run | Tests | Passed | Skipped | Deselected | Wall-clock |
|-----|-------|--------|---------|------------|------------|
| 1   | 1554  | 1512   | 10      | 32         | 138.18s    |
| 2   | 1554  | 1512   | 10      | 32         | 134.76s    |
| 3   | 1554  | 1512   | 10      | 32         | 136.59s    |

**Average: 136.51s (2m17s)**

### AgenticGuidance (Sequential)

| Run | Tests | Passed | Failed | Skipped | Wall-clock |
|-----|-------|--------|--------|---------|------------|
| 1   | 648   | 640    | 3*     | 5       | 4.95s      |
| 2   | 648   | 639    | 4**    | 5       | 4.86s      |
| 3   | 648   | 640    | 3*     | 5       | 4.68s      |

**Average: 4.83s**

## Parallel Results (After Parallelization)

### AgenticCLI (Parallel, -n auto --dist loadgroup)

| Run | Tests | Passed | Skipped | Wall-clock |
|-----|-------|--------|---------|------------|
| 1   | 1554  | 1512   | 10      | 49.53s     |
| 2   | 1554  | 1512   | 10      | 52.44s     |
| 3   | 1554  | 1512   | 10      | 52.26s     |

**Average: 51.41s**

### AgenticGuidance (Parallel, -n auto --dist loadgroup)

| Run | Tests | Passed | Failed | Skipped | Wall-clock |
|-----|-------|--------|--------|---------|------------|
| 1   | 648   | 640    | 3*     | 5       | 1.95s      |
| 2   | 648   | 640    | 3*     | 5       | 1.87s      |

**Average: 1.91s**

## Speedup Summary

| Module | Sequential | Parallel | Reduction | Speedup |
|--------|-----------|----------|-----------|---------|
| AgenticCLI | 136.51s | 51.41s | **62.3%** | **2.65x** |
| AgenticGuidance | 4.83s | 1.91s | **60.5%** | **2.53x** |

Both modules exceed the ≥30% wall-clock reduction target.

## Pre-existing Failures

These failures exist before any parallelization changes:
- `tests/test_plan_resurrection.py::TestFindPlanFolderLivePreference::test_tinydb_completed_path_resolved_to_live`
- `tests/test_plan_resurrection.py::TestFindPlanFolderLivePreference::test_only_live_exists_returns_live`
- `tests/test_plan_resurrection.py::TestFindPlanFolderLivePreference::test_only_completed_returns_nothing`

*3 pre-existing failures in test_plan_resurrection.py (ModuleNotFoundError: agenticcli)
**Run 2 baseline had 1 additional flaky failure in test_plan_repository_filelock.py

## Notes

- Platform: Linux WSL2, CPU count determines `-n auto` worker allocation
- Integration tests grouped via `xdist_group("integration")` to prevent tmux conflicts
- `--dist loadgroup` ensures xdist_group markers are respected
- testmon + xdist combination verified working
