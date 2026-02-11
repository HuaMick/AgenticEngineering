# Trace Capture Investigation

## Problem
A 45-minute orchestration session that executed 5 plans with 48+ tasks only generated **5 traces** in LangSmith. This suggests significant gaps in trace capture for spawned sessions.

## Symptoms
- `agentic session list --all` shows 105 total sessions
- LangSmith shows only 5 traces from the last 24 hours
- The orchestration session was clearly successful (all plans completed)
- Stop hooks should be capturing session data but traces are missing

## Investigation Areas
1. **Stop hook execution**: Is `stop_hook.sh` running for background sessions?
2. **Session spawning**: Are spawned sub-sessions getting proper trace initialization?
3. **LangSmith API errors**: Are there failed POST requests to LangSmith?
4. **Environment variables**: Is `CC_LANGSMITH_PROJECT` inherited by spawned sessions?
5. **Trace ID propagation**: Are parent trace IDs being passed to child sessions?

## Key Files
- `modules/AgenticCLI/src/agenticcli/hooks/stop_hook.sh` - trace generation
- `modules/AgenticCLI/src/agenticcli/commands/session.py` - session spawning
- `modules/AgenticLangSmith/` - LangSmith integration

## Open Questions
- Q1: Are background sessions (-b flag) running stop hooks?
- Q2: Is there a race condition between session completion and trace capture?
- Q3: Should we add trace capture validation to session health checks?

## Expected Outcome
- All spawned sessions generate LangSmith traces
- Trace capture rate matches session count
- Stop hooks reliably execute for all completion scenarios
