# Entrypoints

Entrypoints are high-level process shortcuts designed for the user to quickly inject specific context into an agent's context window.

## 🚀 Purpose
These files act as the starting point for a "choose your own adventure" style workflow. By injecting an entrypoint (e.g., using `@_plan.yml`), you provide the agent with a clear goal and the initial map it needs to navigate through multiple layers of definitions, guidelines, and specialized process files.

## 🔍 The `_` Prefix
The underscore prefix (`_`) is used for rapid discovery. When typing `@` in the chat or task interface, the `_` allows you to instantly filter for the core orchestration and execution processes.

## 📖 How They Work
Agents do not just follow the entrypoint; they use it as a root node to:
1.  **Understand the Goal**: Each entrypoint defines a clear `goal`.
2.  **Locate Core Inputs**: They point to mandatory guidelines (`context-minimisation.yml`, `response-audit.yml`, etc.).
3.  **Navigate the Guidance Tree**: Agents follow paths from the entrypoint to specialized sub-agents and assets to gather the exact context required for the current step.

## 🛠 Available Entrypoints

| Entrypoint | Purpose |
| :--- | :--- |
| `_plan.yml` | Dedicated planning phase for implementation or teaching. |
| `_teach.yml` | Execution phase for an existing teaching plan. Uses orchestration-guidance. |
| `Diagnostics.yml` | Investigation and system state verification. |
| `Explore.yml` | High-level codebase exploration and discovery. |

## 🔧 Orchestration Processes

For implementation execution, use the specialized mermaid-driven orchestrators directly:

| Orchestrator | Purpose |
| :--- | :--- |
| `agents/orchestration/orchestration-build/process.mmd` | Build/Implementation orchestration for code changes and features. |
| `agents/orchestration/orchestration-guidance/process.mmd` | Context engineering orchestration for guidance system updates. |
