# Cleanup Execution Guide

**Quick Reference**: Step-by-step commands for executing the cleanup

## Pre-flight Checks

Before executing cleanup:

```bash
# 1. Verify you're on the main branch
git status

# 2. Ensure no uncommitted changes in plan folders
git diff docs/plans/live/

# 3. Review violations
cat docs/plans/live/260206PC_plan_cleanup/VIOLATIONS_SUMMARY.md

# 4. Optional: Create backup branch
git checkout -b backup-before-plan-cleanup
git checkout main
```

## Phase 2: Archive Operations (2 plans)

### Step 1: Archive 260205BO_bootstrap_test to completed/

```bash
# Move completed plan to completed folder
git mv docs/plans/live/260205BO_bootstrap_test docs/plans/completed/

# Verify
ls docs/plans/completed/260205BO_bootstrap_test/plan_completed.yml
```

**Expected Result**: Plan moved to `docs/plans/completed/`

### Step 2: Archive 260203AV_agenticvoice_async to deferred/

```bash
# Move replaced plan to deferred folder
git mv docs/plans/live/260203AV_agenticvoice_async docs/plans/deferred/

# Verify
ls docs/plans/deferred/260203AV_agenticvoice_async/README.md
```

**Expected Result**: Plan moved to `docs/plans/deferred/`

**Note**: 260203VP_voice_personaplex references 260203AV only as historical context, no action needed.

## Phase 3: Flatten Operations (3 plans)

### Step 3: Flatten 260203TS_task_service

```bash
cd docs/plans/live/260203TS_task_service

# Check if nested orchestration differs from root version
diff orchestration_task_service.mmd live/orchestration_task_service_implementation.mmd || true

# If they differ significantly, decide which to keep
# Then move plan files to root
git mv live/plan_build.yml .

# If nested orchestration is preferred (newer), move it too
# git mv live/orchestration_task_service_implementation.mmd .

# Remove empty nested folder
git rm -r live/

cd /home/code/AgenticEngineering
```

**Expected Result**: Plan files at root, no `live/` subdirectory

### Step 4: Flatten 260205IM_cli_hardening

```bash
cd docs/plans/live/260205IM_cli_hardening

# Move plan files to root
git mv live/plan_build.yml .
git mv live/plan_test.yml .

# Remove empty nested folder
git rm -r live/

cd /home/code/AgenticEngineering
```

**Expected Result**: Plan files at root, `analysis/` folder preserved, no `live/` subdirectory

### Step 5: Flatten 260205LB_cli_loading_bar

```bash
cd docs/plans/live/260205LB_cli_loading_bar

# Move plan files to root
git mv live/plan_build.yml .
git mv live/plan_test.yml .

# Remove empty nested folder
git rm -r live/

cd /home/code/AgenticEngineering
```

**Expected Result**: Plan files at root, no `live/` subdirectory

## Phase 4: Validation

### Step 6: Run validation checks

```bash
# Check 1: No nested live/ folders remain
find docs/plans/live -type d -name "live" | grep -v "^docs/plans/live$"
# Expected: No output (empty)

# Check 2: Archived plans exist
ls docs/plans/completed/260205BO_bootstrap_test
ls docs/plans/deferred/260203AV_agenticvoice_async
# Expected: Directories exist

# Check 3: Flattened plans have files at root
ls docs/plans/live/260203TS_task_service/plan_build.yml
ls docs/plans/live/260205IM_cli_hardening/plan_build.yml
ls docs/plans/live/260205IM_cli_hardening/plan_test.yml
ls docs/plans/live/260205LB_cli_loading_bar/plan_build.yml
ls docs/plans/live/260205LB_cli_loading_bar/plan_test.yml
# Expected: All files exist

# Check 4: No broken references (optional)
grep -r "260205BO_bootstrap_test" docs/plans/live/ 2>/dev/null | grep -v "260206PC_plan_cleanup"
# Expected: No output (only this cleanup plan mentions it)
```

## Commit Changes

```bash
# Review all changes
git status

# Review specific changes
git diff --cached

# Commit with descriptive message
git commit -m "$(cat <<'EOF'
chore(plans): clean up plan folder structure violations

ARCHIVE:
- 260205BO_bootstrap_test → completed/ (plan_completed.yml present)
- 260203AV_agenticvoice_async → deferred/ (replaced by 260203VP)

FLATTEN:
- 260203TS_task_service: move plan files to root, remove nested live/
- 260205IM_cli_hardening: move plan files to root, remove nested live/
- 260205LB_cli_loading_bar: move plan files to root, remove nested live/

All plans now follow flat structure per plan_example.yml.
No nested live/ subdirectories remain.

Plan: docs/plans/live/260206PC_plan_cleanup/

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"

# View commit
git show --stat
```

## Rollback (if needed)

If something goes wrong:

```bash
# If not committed yet
git reset --hard HEAD

# If already committed
git log --oneline -5  # Find commit hash
git revert <commit-hash>

# Or restore from backup branch
git checkout backup-before-plan-cleanup
git branch -m main main-broken
git branch -m backup-before-plan-cleanup main
```

## Post-cleanup

```bash
# Optional: Delete backup branch
git branch -d backup-before-plan-cleanup

# Optional: Clean up this cleanup plan (after completion)
# git mv docs/plans/live/260206PC_plan_cleanup docs/plans/completed/
```

## Troubleshooting

### Issue: "fatal: bad source" when moving files

**Cause**: File doesn't exist at specified path
**Fix**: Check exact file path with `ls -la docs/plans/live/PLANID/live/`

### Issue: "fatal: destination exists"

**Cause**: File already exists at destination
**Fix**: Compare files with `diff`, decide which to keep

### Issue: Plan references still point to old location

**Cause**: Hard-coded paths in other plans
**Fix**: Search and update: `grep -r "old/path" docs/plans/live/`

## Timeline

- **Phase 2**: ~2 minutes (2 git mv commands)
- **Phase 3**: ~5 minutes (3 plans × ~1-2 minutes each)
- **Phase 4**: ~2 minutes (validation checks)
- **Commit**: ~1 minute

**Total**: ~10 minutes

## Success Indicators

After execution, you should see:

```
docs/plans/
├── live/
│   ├── 260203PS_plan_service/          ✓ Already correct
│   ├── 260203QC_question_cli/          ✓ Already correct
│   ├── 260203QG_question_guidance/     ✓ Already correct
│   ├── 260203QT_question_tmux/         ✓ Already correct
│   ├── 260203TS_task_service/          ✓ Fixed (flattened)
│   ├── 260203VP_voice_personaplex/     ✓ Already correct
│   ├── 260205IM_cli_hardening/         ✓ Fixed (flattened)
│   ├── 260205LB_cli_loading_bar/       ✓ Fixed (flattened)
│   ├── 260205TY_migrate_cli_to_typer/  ✓ Already correct
│   └── 260206PC_plan_cleanup/          ✓ This cleanup plan
├── completed/
│   └── 260205BO_bootstrap_test/        ✓ Archived
└── deferred/
    └── 260203AV_agenticvoice_async/    ✓ Archived
```

## Agent Execution

For automated execution via agents:

```bash
# Bootstrap context
agentic context bootstrap --role cleaner

# Execute Phase 2 tasks
agentic plan task update archive_001 --status in_progress
# ... run git mv commands ...
agentic plan task update archive_001 --status completed

# Execute Phase 3 tasks
agentic plan task update flatten_001 --status in_progress
# ... run git mv commands ...
agentic plan task update flatten_001 --status completed

# And so on...
```

## References

- Full plan: `plan_cleanup.yml`
- Action details: `cleanup_actions.yml`
- Structure guide: `STRUCTURE_REFERENCE.md`
- Violation analysis: `VIOLATIONS_SUMMARY.md`
