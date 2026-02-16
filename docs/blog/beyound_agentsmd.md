How do you go beyond agents.md?

When you code with AI everyone starts with agents.md.

Agent doesnt know something -> add instructions to agents.md -> agent gets smarter.

This works well until it doesn’t.

The instructions you give your agents are made up of two things:

Signal: The useful part of the instructions

Noise: Everything else

As you add to your agents.md you will add more and more situational context, stuff they may or may not use depending on what you have tasked them to do. The problem here is when they don’t use it, it becomes noise.

Noise gives you context rot. Context rot makes your agent dumber.

For example, in earlier projects, I often shoved everything into a single `CLAUDE.md`. It looked like this:

```markdown
# CLAUDE.md
## Project Overview
This project is a Python framework for...

## Development Commands
uv sync --extra dev
make format
docker-compose up

## Code Architecture
- Core Library: core/
- Server: server/
- MCP Server: mcp_server/

## Testing
- Unit Tests: tests/
- Integration Tests: Tests marked with _int
```

As you can see, development commands, architecture, and testing rules are all fighting for attention in context window.

The next evolution is to break up your agents.md into multiple files or even folders of files.

Then you give your agents an index file and treat the system like an encyclopedia.

Your agent uses the index to understand what each file contains and only looks up and reads the full file if it needs to. This works well but you still front loading your agent with a lot up front. Your index will need descriptions against each file and the descriptions that aren’t used become noise.

In later projects, I moved to a manifest pattern. The agent reads this map first to find what it needs:

```markdown
# index.md (Manifest)

## Backend Services
- **Location**: `/services/backend/`
- **Components**:
  - `validator`: [Validation Rules](/services/backend/validator.md)
  - `registry`: [Model Definitions](/services/backend/registry.md)

## Frontend Services
- **Location**: `/services/frontend/`
- **Components**:
  - `cli`: [Command Interface](/services/frontend/cli.md)
  - `automation`: [Process Workflows](/services/frontend/automation.md)
```

This works well but you still front loading your agent with a lot up front. Your index will need descriptions against each file which can get very lengthy on abstract decision points:

```markdown
# index.md (Decision Overload)

- [Strategy_UserSimulation.md]: Use when you need full user journey validation. Spawns test-user-simulator agents to execute end-to-end flows. Verifiable but slow.
- [Strategy_BlindTest.md]: Use when validating documentation completeness. Spawns agents without prior context to test if docs are sufficient.
- [Strategy_ManualValidation.md]: Use for complex scenarios requiring human judgment or where automation is too costly...
```

This leads to the **Entrypoint Pattern**.

Rather than giving the agent a map of *everything*, you give it a specific prompt that acts as the entry key to a single, focused adventure.

For example, instead of a general `agents.md`, you might have a dedicated prompt file for starting a feature:

```markdown
# prompts/start-feature.md

You are now in Feature Mode. 
1. Read `@processes/start_feature.md` to understand your next steps.
2. Do not deviate from the process.
```

When you paste this prompt into the agent, it follows the single link to `@processes/start_feature.md`. That file then links to *only* the specific context needed for that step (e.g. "read user story"), keeping context rot to near zero.

The challenge changes here from limiting noise to task decomposition. You can route all you want but a complex task often has to be broken down into simpler steps. If you have the same agent session working across steps, the other steps become noise to each other.

Research is different from planning, planning is different to implementation, implementation is different to testing - they all become noise to each other.

Now it's time to introduce subagents.

Subagents are just separate agent sessions. The key is they all get their own context window. In theory you could just restart your session before each task, but who wants to do such grunt work. Most off the shelf agent harnesses (claude code) give you the ability to define subagent profiles. For the different types of tasks you can define a subagent, the standard ones are researcher, planner, builder, and tester. Now you can route to a subagent with a fresh context window,

and the instructions for the agent doing research don’t become noise for the agent who is doing planning - you get a hard reset on hand off.

The current approach strictly follows this. We define specialized roles in a markdown table:

```markdown
| Task Type | Assigned Agent | Flags |
|-----------|----------------|-------|
| Python Implementation | `build-python` | `--role build-python` |
| Test Execution | `test-runner` | `--role test-runner` |
```

When I need code built, I don't ask the current agent to switch context. I spawn a fresh one:

```bash
claude "Refactor the user model" --profile build-python
```

The `build-python` agent wakes up with a clean brain, 0% context usage, and only the instructions relevant to coding—no noise from the planning or research phases.

If you’ve gotten this far, congrats you’re doing agent orchestration and context engineering. It's not to be taken lightly this is hard to get right.

You probably feel pretty powerful now, you're a leader of a small army. But your minions still get stuff wrong. Sometimes the wrong subagent is spawned, sometimes the agent ignores a file its meant to read or just doesn’t do what it’s told.

The game shifts again here, you now need to build some fences to keep your sheep in the pen. But I’ll stop here and talk about how I do that in my next post.

If you're keen please like and subscribe (the free one is fine), it will tell me that people are actually reading and getting value from my ramblings and hopefully motivate me to write more.