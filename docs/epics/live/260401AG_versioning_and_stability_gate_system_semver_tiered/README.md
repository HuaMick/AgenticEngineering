# Epic: Versioning and Stability Gate System

## Objective

Implement a comprehensive versioning and stability gate system for the AgenticEngineering monorepo. Currently all modules are hardcoded at `0.1.0` with no semantic versioning, no automated version management, minimal stability gate enforcement (only 4 commands marked EXPERIMENTAL), no container-based E2E testing, and no rollback mechanism. This epic delivers:

1. **Semantic versioning (semver)** — single source of truth, automated bumping, git tags
2. **Tiered stability gates** — formalized ALPHA/BETA/EXPERIMENTAL/STABLE enforcement with promotion workflows
3. **Container sandbox E2E** — Docker-based isolated testing that validates CLI in a clean environment
4. **Rollback mechanism** — simple git-based version rollback using tags, with post-rollback validation

## Affected User Stories

| Story ID | Title | Impact |
|----------|-------|--------|
| US-GDN-007 | Agent Versioning | Core — versioning system applies to all agents |
| US-GDN-089 | CI/CD Pipeline Configuration | Container E2E is the first CI/CD gate |
| US-GDN-090 | CI/CD Infrastructure Status Check | Health check extensions for gate status |
| US-GDN-091 | CI/CD Validation Phase | Tiered gates validate in CI/CD context |
| US-GDN-092 | Python Build and Packaging | Version sync with pyproject.toml build files |
| US-GDN-093 | Python Dependency Management | Version pinning and dependency safety for rollback |
| US-GDN-094 | Python Installation Verification | Container E2E verifies clean install |
| US-GDN-097 | Build Phase in Orchestration | Pre-release gate integrates with build phase |
| US-GDN-098 | Deploy Phase in Orchestration | Rollback mechanism for deployment failures |
| US-GDN-101 | Environment Validation | Container validates clean environment |
| US-GDN-102 | DevOps Pipeline Audit | Stability audit command for pipeline compliance |
| US-PLN-062 | Validation Gates | Core — tiered gates concept and enforcement |
| US-SET-002 | Update and Rebuild CLI | Rollback requires rebuild capability |
| US-SET-004 | Health Check | Extended health with version/gate checks |
| US-SET-025 | Git Safety Checks | Git tag safety during versioning operations |

## Phases Overview

### Phase 1: Semver Version Management (`P1_semver`)
Build the core version management infrastructure. Create a `VersionService` in AgenticGuidance following Domain -> Workflow -> Entrypoint pattern. Implement version parsing/validation/bumping (semver), synchronization across all version sources (`pyproject.toml`, `__init__.py`), CLI commands (`agentic version show|bump|history`), and git tag integration.

### Phase 2: Tiered Stability Gates + Coverage Tracking (`P2_stability_gates`)
Formalize the existing `StabilityLevel` enum into an enforceable gate framework with **usage-driven stability tracking** — a novel system that derives stability levels from actual command usage data rather than manual promotion.

**2A: Gate Registry & Enforcement**
Create a `StabilityGateRegistry` service with per-command and per-feature gate configuration. Add gate enforcement policies to CLI dispatch (warn, block, require-flag modes). Stability levels are set via code decorators (Option A from claw-code analysis: promotion is a code change, not a runtime operation).

**2B: Coverage Tracking System**
Build a `CoverageService` that records every CLI command invocation with its normalized signature, commit hash, success/fail, and actor (human vs UAT agent). This creates a **content-addressable coverage table** in TinyDB where each unique (command_signature + commit_hash) pair tracks aggregate usage stats. Stability levels become derivable from data:
- `ALPHA`: < 3 successful uses at current commit, or only 1 runner type
- `BETA`: >= 3 uses at current commit, tested by UAT agent, 0 recent fails  
- `STABLE`: >= 10 uses across >= 2 commits, both human + UAT, 0 fails in last N runs

**2C: Story-to-Signature Mapping**
Link user story success criteria to command signatures. Each ticket's `success_criteria` maps to one or more `command_sig` values. When coverage shows a sig is tested at HEAD, the linked success criterion is marked as "covered by usage data." This closes the loop between user stories and actual command usage.

**2D: Failure Feedback Loop**
On command failure: record in coverage table, demote stability level, check if an active ticket owns the failed signature (enrich that ticket with failure context), and surface in `agentic stability audit --regressions`. Never auto-create epics — planners consume the regression report and decide whether to propose new tickets. Uses error fingerprinting (hash of error type + message + command sig) to deduplicate.

**2E: CLI Post-Invocation Hook**
A lightweight hook (~1ms overhead) that fires after every `agentic` CLI command, recording the normalized command signature, commit hash, success/fail, actor identity, and timestamp to the coverage table. This is the data collection backbone for the entire coverage tracking system.

Add `agentic stability audit` command with `--regressions` and `--untested` flags.

### Phase 3: Container Sandbox E2E (`P3_container_e2e`)
Build a Docker-based isolated E2E testing environment. Create a Dockerfile that installs AgenticCLI from source in a clean Python environment. Implement a test runner that orchestrates container lifecycle and executes CLI smoke tests against the real installed binary. Integrate E2E pass/fail results into stability gate promotion criteria.

### Phase 4: Rollback Mechanism (`P4_rollback`)
Implement simple git-based version rollback. Leverage git tags created in Phase 1 as version markers. Rollback = `git revert` to a tagged version + re-run version sync across all files + health check validation. No custom RollbackService, no tar.gz state snapshots. The `agentic version rollback <version>` CLI command finds the git tag, reverts to it, re-syncs version files (`pyproject.toml`, `__init__.py`), and runs a post-rollback health check.

### Phase 5: Integration & Pre-Release Gates (`P5_integration`)
Wire all components into a unified pre-release validation pipeline. Extend `agentic health` with version alignment and gate status checks. Create `agentic release preflight` command that runs all gates (tests, E2E, stability audit, health) before allowing a version bump. Add integration tests covering the full workflow.

### Phase 6: UAT (`P6_uat`)
User acceptance testing against all affected user stories. Validates complete user journeys for version management, stability gate enforcement, container E2E execution, rollback safety, and health check integration.

## Dependencies and Prerequisites

- **TinyDB is sole data store** — no YAML/MMD fallback needed
- **Hatchling build system** — already configured in pyproject.toml, ready for version management
- **UV package manager** — used for dependency resolution and installation
- **StabilityLevel enum** — exists in `agenticcli/decorators.py` with ALPHA/BETA/EXPERIMENTAL/STABLE
- **Health check command** — exists in `agenticcli/commands/health.py` with extensible check pattern
- **Docker must be available** — container E2E requires Docker engine on development machine
- **Git** — required for tag management and rollback tracking
- **Python 3.11+** — minimum version for AgenticCLI

## Architecture

Follows **Domain -> Workflow -> Entrypoint** pattern:

### Version Management
- **Domain**: `VersionService` in `agenticguidance/services/version.py` (parse, validate, bump, compare)
- **Workflow**: `VersionSyncWorkflow` in `agenticcli/workflows/version.py` (bump + sync files + create tag)
- **Entrypoint**: CLI commands in `agenticcli/commands/version.py`

### Stability Gates & Coverage Tracking
- **Domain**: `StabilityGateRegistry` in `agenticguidance/services/stability_gate.py` (gate config, enforcement levels)
- **Domain**: `CoverageService` in `agenticguidance/services/coverage.py` (record usage, query coverage, derive stability, failure handling)
- **Workflow**: `GateEnforcementWorkflow` integrated into CLI dispatch
- **Hook**: Post-invocation CLI hook in `agenticcli/hooks/coverage_hook.py` (records every command invocation)
- **Entrypoint**: Updated `decorators.py` + `agenticcli/commands/stability.py`

### Coverage Tracking Data Model

**Coverage Table** (TinyDB `coverage` table in `~/.agentic/epics.db`):
```python
{
    "sig": "a3f2b1c9d4e5",                           # sha256(canonical_command)[:12]
    "canonical": "epic ticket list --epic=STR --json", # human-readable normalized form
    "commit": "e37338e",                               # git commit hash (code version)
    "count": 5,                                        # successful invocations at this commit
    "fails": 0,                                        # failed invocations at this commit
    "last_run": "2026-04-01T14:30:00Z",                # most recent invocation
    "runners": ["human", "uat-agent"],                 # who has exercised this combination
    "last_error": null,                                # most recent error message (if any)
    "error_fingerprint": null                          # hash(error_type + message + sig) for dedup
}
```

**Command Signature Normalization**:
- Sort flags alphabetically
- Replace values with type tokens: `--epic <folder>` → `--epic=STR`, `--limit 10` → `--limit=INT`
- Strip positional args to types: `agentic epic ticket start T01` → `epic ticket start ID`
- Hash the canonical string: `sha256("epic ticket list --epic=STR --json")[:12]`
- Pairwise coverage: track individual flags AND flag-pairs, not the full power set (per pairwise testing research — most bugs come from 2-factor interactions)

**Story-Signature Mapping** (on ticket records in TinyDB):
```python
# Added field on ticket records
{
    "id": "US-CLI-042",
    "story_sigs": [                                    # command signatures this story covers
        "epic ticket list --epic=STR",
        "epic ticket list --epic=STR --json"
    ]
}
```

**Stability Derivation Logic**:
```python
def derive_stability(sig: str, commit: str) -> StabilityLevel:
    records = coverage.search(sig=sig)
    at_head = [r for r in records if r["commit"] == commit]
    
    if not at_head or at_head[0]["count"] < 3:
        return StabilityLevel.ALPHA
    
    head_rec = at_head[0]
    if head_rec["fails"] > 0:
        return StabilityLevel.ALPHA  # any failure at HEAD = ALPHA
    
    all_commits = {r["commit"] for r in records if r["count"] > 0}
    all_runners = set()
    for r in records:
        all_runners.update(r["runners"])
    total_success = sum(r["count"] for r in records)
    
    if (total_success >= 10 
        and len(all_commits) >= 2 
        and "human" in all_runners 
        and "uat-agent" in all_runners):
        return StabilityLevel.STABLE
    
    if head_rec["count"] >= 3 and "uat-agent" in head_rec["runners"]:
        return StabilityLevel.BETA
    
    return StabilityLevel.ALPHA
```

**Failure Handling Flow**:
```
CLI command fails
  → CoverageService.record_failure(sig, commit, error, actor)
  → Increment fails count, store error_fingerprint
  → Stability auto-demotes to ALPHA (any failure at HEAD = ALPHA)
  → Check: does any active ticket have this sig in story_sigs?
    ├── YES → Enrich ticket metadata with failure context
    │         (error message, timestamp, commit, how many times)
    └── NO  → Record only — surfaced via `stability audit --regressions`
  → Planner agents consume regression report on next run
  → Planner decides: new ticket, annotate existing, or ignore
  → Human approves or rejects planner proposal
  
  NEVER auto-create epics or tickets on failure.
  Use error_fingerprint for deduplication (same root cause = same fingerprint).
```

**UAT Agent Integration**:
```
UAT agent runs → agentic stability audit --untested
  → Returns commands with 0 coverage at HEAD
  → Each untested sig shows linked user stories
  → UAT agent knows exactly what to test and why
  
UAT agent completes test → coverage hook records success
  → sig coverage count increments
  → If thresholds met, stability auto-promotes
  → agentic stability audit shows updated levels
```

**Planner Agent Integration**:
```
Planner runs → reads stability audit --regressions
  → Sees which commands are demoted and why
  → Sees which user stories are affected
  → Proposes tickets with full failure context
  → Does NOT duplicate — checks error_fingerprint against existing tickets
```

**Build Agent Integration**:
```
Build agent picks up ticket → agentic epic ticket current -j
  → Ticket includes coverage data for its story_sigs:
    { "epic ticket list --epic=STR": {"status": "ALPHA", "fails": 1, "last_error": "KeyError"} }
  → Agent knows exactly what's broken and what's working
  → After fix: coverage hook records new successes at new commit
```

### Container E2E
- **Infrastructure**: `docker/Dockerfile`, `docker/docker-compose.e2e.yml`
- **Runner**: `scripts/e2e_runner.py` (container lifecycle + test execution)
- **Tests**: `tests/e2e/` directory with container smoke tests

### Rollback
- **Mechanism**: `git revert` to tagged version + version file sync (reuses `VersionSyncWorkflow` from Phase 1)
- **Entrypoint**: CLI command in `agenticcli/commands/version.py` (rollback subcommand)
- **No new services** — rollback logic lives in the existing version workflow and CLI command

## Key Design Decisions

1. **Single version source of truth** — `VersionService` reads/writes version, all other files sync from it
2. **Version stored in `__init__.py`** — remains the canonical Python source; `pyproject.toml` synced via tool
3. **Gate enforcement is configurable** — three modes: `warn` (banner only), `block` (exit with error), `require-flag` (allow with `--unstable` flag)
4. **Container E2E uses multi-stage Docker build** — slim runtime image for fast test execution
5. **Rollback uses git** — `git revert` to tagged version, no custom state snapshots needed (git is the state manager)
6. **Rollback is version-granular** — rolls back to a specific prior tagged version, then re-syncs version files
7. **Pre-release gate is composable** — each check is independent, can be run individually or as suite
8. **Promotion is a code change, not a runtime operation** (Option A) — developers change `@stability(StabilityLevel.BETA)` decorators in code. The `stability audit` command is advisory: it reports what SHOULD be promoted based on usage data, but doesn't auto-promote. This is validated by claw-code's approach where `CommandSource::FeatureGated` → `CommandSource::Builtin` is a source code change.
9. **Coverage tracking uses content-addressable signatures** — command invocations are normalized and hashed into 12-char signatures. Coverage table stores aggregates per (sig, commit), not individual invocation history. ~500 rows max for 100 commands × 5 flag combos. TinyDB is sufficient (no SQLite needed).
10. **Stability is derivable from usage data** — ALPHA/BETA/STABLE thresholds are computed from the coverage table, not manually set. Commit hash is the granularity for "code changed" (not function/file hash — too fragile).
11. **Failures enrich existing work, never auto-create tickets** — error fingerprinting (hash of error type + message + sig) prevents duplicates. Planner agents consume regression reports and decide whether to propose tickets. This follows the industry-standard "dedup + enrich + escalate-on-threshold" pattern from SRE/PagerDuty/chaos engineering.
12. **User stories link to command signatures** — `story_sigs` field on ticket records maps success criteria to specific command signatures. When coverage shows a sig is tested at HEAD, the linked criterion is "covered by usage data." This is our version of test impact analysis (inspired by Microsoft/Google/Meta patterns but applied at CLI command level rather than code line level).
13. **Pairwise coverage, not exhaustive** — based on combinatorial testing research, track individual flags and flag-pairs, not the full power set. Most bugs surface from 2-factor interactions.

## Impacted Artifacts

| Artifact | Type | Change |
|----------|------|--------|
| `agenticguidance/services/version.py` | Service (NEW) | VersionService — semver parse, validate, bump, compare |
| `agenticguidance/services/stability_gate.py` | Service (NEW) | StabilityGateRegistry — gate config, enforcement levels |
| `agenticguidance/services/coverage.py` | Service (NEW) | CoverageService — record usage, query coverage, derive stability, failure handling |
| `agenticcli/commands/version.py` | CLI (NEW) | `agentic version show\|bump\|history\|rollback` commands |
| `agenticcli/commands/stability.py` | CLI (NEW) | `agentic stability audit` command with `--regressions` and `--untested` flags |
| `agenticcli/commands/release.py` | CLI (NEW) | `agentic release preflight` command |
| `agenticcli/workflows/version.py` | Workflow (NEW) | Version bump + sync + tag + rollback-to-tag workflow |
| `agenticcli/hooks/coverage_hook.py` | Hook (NEW) | Post-invocation hook — records command sig, commit, success/fail, actor to coverage table |
| `agenticcli/decorators.py` | CLI | Extended gate enforcement (warn/block/require-flag) |
| `agenticcli/commands/health.py` | CLI | Add version alignment + gate status checks |
| `agenticcli/__init__.py` | Module | Version managed by VersionService |
| `agenticguidance/__init__.py` | Module | Version managed by VersionService |
| `modules/AgenticCLI/pyproject.toml` | Config | Version synced by VersionService |
| `modules/AgenticGuidance/pyproject.toml` | Config | Version synced by VersionService |
| `docker/Dockerfile` | Infrastructure (NEW) | E2E test sandbox container |
| `docker/docker-compose.e2e.yml` | Infrastructure (NEW) | E2E test orchestration |
| `scripts/e2e_runner.py` | Script (NEW) | Container E2E test runner |
| `tests/e2e/` | Tests (NEW) | Container-based E2E smoke tests |

## Success Criteria

**Version Management (P1)**
1. `agentic version show` displays current semver version for all modules
2. `agentic version bump patch|minor|major` bumps version, syncs all files, creates git tag
3. `agentic version history` shows version history from git tags
4. All version sources (`__init__.py`, `pyproject.toml`) stay synchronized after any bump

**Stability Gates & Coverage (P2)**
5. `StabilityGateRegistry` enforces gate levels with configurable policies (warn/block/require-flag)
6. `agentic stability audit` reports all commands with their gate levels, coverage stats, and derived stability
7. `agentic stability audit --untested` shows commands with 0 coverage at HEAD, with linked user stories
8. `agentic stability audit --regressions` shows demoted commands with failure details and affected stories
9. CLI post-invocation hook records every command to coverage table with < 2ms overhead
10. Coverage table correctly normalizes command signatures (sorted flags, type tokens, pairwise tracking)
11. Stability levels are correctly derived from coverage data (ALPHA/BETA/STABLE thresholds)
12. On failure: coverage table updated, stability demoted, active tickets enriched with failure context
13. Error fingerprinting prevents duplicate failure records for the same root cause
14. `story_sigs` mapping on tickets links user stories to command signatures
15. `agentic epic ticket current -j` includes coverage data for the ticket's `story_sigs`

**Container E2E (P3)**
16. `docker-compose -f docker/docker-compose.e2e.yml up` runs full E2E suite in isolated container
17. Container E2E executes real `agentic` binary smoke tests (not mocked) in clean environment

**Rollback (P4)**
18. `agentic version rollback <version>` finds the git tag, reverts via `git revert`, re-syncs version files, and runs health check
19. Post-rollback health checks validate system integrity (version alignment, tests pass)

**Integration (P5)**
20. `agentic health` includes version alignment check and stability gate status
21. `agentic release preflight` runs all gates and blocks version bump on failure

**Cross-Cutting**
22. All existing tests continue to pass (no regressions)
23. UAT validates affected user stories: US-GDN-007, US-PLN-062, US-SET-004, US-GDN-089

## Decisions (formerly Open Questions)

1. **Module version independence vs. lockstep?** — DECIDED: shared monorepo version for simplicity. Independent versions deferred to future epic if needed.
2. **Docker availability requirement** — DECIDED: yes, fallback to local subprocess E2E with reduced isolation when Docker unavailable.
3. **Promotion mechanism** — DECIDED: Option A (code-change promotion). Developer changes `@stability()` decorator in code. `stability audit` is advisory only — reports what should be promoted based on coverage data. Validated by claw-code analysis where tier changes are source code changes.
4. **Rollback mechanism** — DECIDED: git-based only. `git revert` to tagged version + version sync. No custom RollbackService or tar.gz state snapshots. Validated by claw-code analysis where rollback is implicit state capture, not a custom service.
5. **Coverage storage** — DECIDED: TinyDB `coverage` table in existing `~/.agentic/epics.db`. Content-addressable signatures (sha256[:12]). ~500 rows max. No need for SQLite, bloom filters, or bitmaps at single-user CLI scale.
6. **Failure handling** — DECIDED: dedup + enrich + surface pattern. Never auto-create epics/tickets. Error fingerprinting for dedup. Planners consume regression reports and propose tickets. Human approves. Validated by SRE/PagerDuty/chaos engineering research.

## Research Context

This epic's design was informed by analysis of the claw-code (Claude Code) codebase and industry research:

**Claw-code patterns adopted:**
- Three-tier command classification (`CommandSource { Builtin, InternalOnly, FeatureGated }`) → validates our `StabilityLevel` enum approach
- `PermissionPolicy` with per-tool requirements map → model for `StabilityGateRegistry`
- Trust-gated deferred initialization → ALPHA features require explicit opt-in
- `unsafe_code = "forbid"` workspace quality gates → build-time enforcement model

**Industry research:**
- **Combinatorial testing** (Microsoft PICT, pairwise testing) → track flag-pairs not full power set
- **Coverage bitmaps** (AFL fuzzing) → content-addressable signatures for efficient storage
- **Test impact analysis** (Microsoft Azure DevOps, Google TAP, Meta predictive test selection) → inverted index from code unit to tests; our version maps command signatures to user stories
- **Progressive delivery** (Netflix Kayenta, Spinnaker) → statistical canary analysis for promotion decisions
- **Feature flag auto-demotion** (LaunchDarkly measured rollouts, Envoy outlier detection) → metric-based kill switches
- **Failure feedback** (SRE error budgets, PagerDuty dedup keys, chaos engineering known-failure catalogs) → dedup + enrich + escalate-on-threshold

**Novel contribution:** No existing tool applies usage-driven stability tracking at the CLI command level. This system combines progressive delivery + test impact analysis + observability into a CLI-native stability gate framework.
