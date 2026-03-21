# 260321DC: Clean Up Deferred Epic MMD Files

## Problem

4 orphaned `.mmd` files remain in `docs/epics/deferred/`:

```
docs/epics/deferred/260203AV_agenticvoice_async/orchestration_agenticvoice_async.mmd
docs/epics/deferred/260203AV_agenticvoice_async/live/orchestration_agenticvoice_async.mmd
docs/epics/deferred/260126AV_agenticvoice/orchestration_agenticvoice.mmd
docs/epics/deferred/260203VP_voice_personaplex/orchestration_voice_personaplex.mmd
```

These are legacy artefacts from before TinyDB migration. While they don't affect runtime (deferred epics aren't scanned), they create noise in searches and contradict the TinyDB-only architecture.

Note: `260203AV_agenticvoice_async` has an MMD both at root and inside `live/` subdirectory — incomplete migration state before deferral.

## Scope

1. Delete all 4 `.mmd` files from deferred epics
2. Verify no code references these specific files
3. Consider archiving the deferred voice epics entirely if they're abandoned
