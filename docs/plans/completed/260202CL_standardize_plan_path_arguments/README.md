# Plan: Standardize Plan Path Arguments

## Problem Statement
The `agentic plan` subcommands are inconsistent in how they accept the path to a plan folder. Some commands use a positional argument `path`, while others use an optional flag `--plan` (or `-p`). This leads to user confusion and errors when switching between commands.

Example:
- `agentic plan status <path>` (positional only)
- `agentic plan task list --plan <path>` (flag only)

The goal is to standardize all `plan` subcommands to support both positional and flag-based path specifications where appropriate, prioritizing the `--plan`/`-p` convention for consistency across the CLI.

## Proposed Changes
1. Audit all `plan` subcommands in `agenticcli/cli.py`.
2. Update `status`, `validate`, `archive`, and any other positional-only commands to support `--plan` and `-p`.
3. Ensure backward compatibility by keeping the positional argument if it already exists, but mark it as optional if `--plan` is provided.
4. Update command handlers in `agenticcli/commands/plan.py` to handle both sources of the plan path.

## Success Criteria
- `agentic plan status --plan <name>` works.
- `agentic plan status <name>` still works.
- `agentic plan validate --plan <name>` works.
- `agentic plan archive --plan <name>` works.
- Help text for all `plan` commands is consistent regarding path arguments.
