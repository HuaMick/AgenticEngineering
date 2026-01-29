# CLI Documentation Update Plan

**Plan ID:** 260128UP_update_cli_readme_and_help_documentation
**Created:** 2026-01-28
**Status:** Planning
**Worktree:** `/home/code/AgenticEngineering-cli-docs-update`
**Branch:** `cli-docs-update`

## Objective

Update the AgenticCLI documentation to ensure accuracy and completeness for all current commands. This includes:

1. **README.md Updates** - Add missing command documentation and update existing sections
2. **Help String Updates** - Improve --help output consistency and helpfulness
3. **Validation** - Ensure documentation matches actual CLI behavior

## Background

The AgenticCLI has grown to include many new commands that are not fully documented in the README:
- `context` (CCI - CLI Context Injection) - bootstrap, role, task, inputs, generate-agent
- `entrypoint` - list, show, execute with --compile
- `session` - spawn, list, stop, status
- `loop` - start, stop, status, history
- `plan task` - new subcommands: prefill, list, status, add, update, current

Additionally, existing documentation may have outdated syntax or missing options.

## Plan Structure

| File | Phase | Description |
|------|-------|-------------|
| `plan_teach.yml` | TEACH | Update README.md documentation |
| `plan_build.yml` | BUILD | Update --help strings in CLI source |
| `plan_test.yml` | TEST | Validate documentation accuracy |
| `plan_audit_clean.yml` | AUDIT | Final review and cleanup |

## Key Tasks

### TEACH Phase (README Updates)
- Add context command documentation
- Add entrypoint command documentation
- Add session command documentation
- Add loop command documentation
- Update plan task subcommands
- Update command categories table
- Add langsmith sessions subcommand

### BUILD Phase (Help String Updates)
- Audit current --help output
- Update main parser epilog
- Improve subcommand descriptions
- Add examples to complex commands

### TEST Phase (Validation)
- Compare --help to README
- Test documented examples
- Verify command categories (Global vs Project)

## Commands Covered

### Documented (needs review)
- `plan` - init, scaffold, status, validate, task, archive, list, move
- `worktree` (wt) - create, list, remove, status
- `config` (cfg) - show, init, get, set, list, delete, show-path, set-path, clear
- `langsmith` (ls) - runs, run, projects, stats, friction, sessions
- `manifest` (mf) - show, list, validate
- `template` (tpl) - generate, list
- `stories` (st) - find
- `inputs` - validate, resolve
- `cicd` - audit, list, show
- `state` - list, show, clear, cleanup
- `env` - show, export, run
- `preferences` (prefs) - get, set, list, delete, clear
- `setup`, `health`, `update`, `rebuild`

### Missing from README (priority)
- `context` (ctx) - bootstrap, role, task, inputs, generate-agent
- `entrypoint` (ep) - list, show, execute
- `session` - spawn, list, stop, status
- `loop` - start, stop, status, history

## Success Criteria

1. README.md accurately documents all CLI commands
2. All --help output is clear and consistent
3. README examples work correctly when executed
4. Command categories (Global vs Project) are accurate
5. No broken or outdated references

## Notes

- Focus on documentation accuracy, not CLI implementation changes
- Coordinate between TEACH and BUILD phases for consistency
- Test in both git and non-git contexts for category validation
