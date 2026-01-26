# JIT Context Retrieval Specification

## Goal
To evolve the project's guidance system from a "Push" model (pre-loading large flattened files) to a "Pull" model (agents fetching exactly what they need via the CLI). This makes the Agentic CLI a first-class citizen for context engineering.

## Core Concept
Instead of Claude loading thousands of tokens of static Markdown files in the `.claude/agents/` directory, agents are given a "Bootstrap Context" that instructs them to run specific `agentic context` commands to retrieve their operational parameters.

## Architecture

### 1. The Bootstrap Agent (Thin Client)
The agent definition in `.claude/agents/` becomes minimal:
- **Role Identifier:** "You are the [Project Manager/Planner/Builder] agent."
- **Bootstrap Command:** "Before taking action, you MUST run `agentic context bootstrap` to receive your task objective and role-specific constraints."

### 2. The Context Command Group (`agentic context ...`)
A new CLI module that serves as the JIT context provider:
- **`agentic context bootstrap`**: An aggregator that returns the core "Seed Context" (Active Task + Primary Role Guidance).
- **`agentic context role <role-id>`**: Returns the standardized process and "Ways of Working" for a specific role.
- **`agentic context task`**: Specifically crawls the **Main Worktree's** `docs/plans/live/` directory to identify and extract the active task for the current worktree/branch.
- **`agentic context inputs`**: Provides a JIT manifest of relevant project files, replacing static `inputs.yml` references with dynamic discovery.

### 3. Main-First Resolution
Since planning now happens exclusively in the `main` branch/worktree, the CLI (running in a feature worktree) must:
1. Detect the main worktree location.
2. Resolve paths to `docs/plans/live/` within that main worktree.
3. Extract the `objective` and `status` from the YML plan files that match the current branch/feature index.

## Benefits
-   **Minimal Initial Token Usage:** Reduces the "context tax" paid on every single turn.
-   **Zero Stale Guidance:** Agents always pull the latest rules from the CLI logic, ensuring policy updates are immediate across all active sessions.
-   **Main-First Harmony:** Solves the challenge of agents losing track of plans in feature worktrees by delegating plan-hunting to the CLI.
-   **Traceability:** Context retrieval is logged in the terminal, making it visible to the user.
