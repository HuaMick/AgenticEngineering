# Context Compiler Specification

## Goal
To optimize context usage and latency by pre-compiling (AOT) the distributed `inputs.yml` dependency graph into flattened Markdown files for use by Claude Code subagents.

## Core Concept
We treat `inputs.yml` as "Source Code" and `.claude/agents/*.md` as "Build Artifacts".

## Architecture

### 1. The Compiler (`agentic agents compile --lazy`)
A CLI command that ensures `.claude/agents/*.md` files are in sync with their `inputs.yml` sources.
- **Lazy Mode:** Checks file modification timestamps. If `inputs.yml` (and its dependencies) are older than the `.md` artifact, compilation is skipped.
- **Output:** Flattened Markdown files in `.claude/agents/`.

### 2. The Hook (`UserPromptSubmit`)
We utilize Claude Code's shell execution hooks to trigger compilation **Just-In-Time**.

**Configuration (`.claude/settings.json`):**
```json
{
  "hooks": {
    "UserPromptSubmit": {
      "commands": [
        "agentic agents compile --lazy"
      ]
    }
  }
}
```

**Workflow:**
1.  User submits a prompt.
2.  Hook triggers `agentic agents compile --lazy`.
3.  Compiler quickly verifies/updates all agent definition files (~50ms).
4.  Claude receives the prompt and begins execution.
5.  If Claude spawns a subagent, it reads the fresh `.md` file from disk.

## Benefits
-   **Guaranteed Consistency:** The agent context is always in sync with `AgenticGuidance` source files.
-   **Zero Maintenance:** No manual "build" step required by the user.
-   **Performance:** Checksums/Timestamps ensure the hook adds negligible latency to the interactions.
