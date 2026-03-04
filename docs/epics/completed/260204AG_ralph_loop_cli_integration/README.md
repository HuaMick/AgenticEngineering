# Ralph Loop CLI Integration

**Plan ID:** 260204AG
**Status:** Active
**Branch:** main
**Worktree:** /home/code/AgenticEngineering

## Objective

Implement a native, plan-aware Ralph Loop system in the agentic CLI that integrates with planning folder management, uses tmux for session spawning, and verifies completion by checking actual plan state rather than trusting agent claims.

## Problem Statement

### Current State
- Ralph Loop is a Claude Code plugin/hook that feeds the same prompt back to the agent
- Problem: Agent can "lie" about completion - claims tasks are done without actually finishing them
- No integration with plan task management system
- No verification that work is actually complete

### Target State
- CLI-native loop that spawns Claude Code sessions in tmux
- Plan-aware: Queries `agentic plan task current` to verify real completion
- File-based state tracking in `~/.agentic/ralph/{plan_folder}/`
- Terminal capture for iteration logging
- Graceful handling of crashes and max iterations

## Architecture

### Components

1. **RalphLoopService** (Domain Layer)
   - Location: `modules/AgenticGuidance/src/agenticguidance/services/ralph_loop.py`
   - Responsibilities:
     - Loop state management
     - Iteration tracking
     - Plan completion detection
     - Tmux session lifecycle

2. **Ralph CLI Commands** (Entrypoint Layer)
   - Location: `modules/AgenticCLI/src/agenticcli/commands/ralph.py`
   - Commands:
     - `agentic ralph start --plan <folder> --prompt-file <file>`
     - `agentic ralph stop --plan <folder>`
     - `agentic ralph status --plan <folder>`
     - `agentic ralph history [--plan <folder>]`

3. **State Storage**
   - Location: `~/.agentic/ralph/{plan_folder}/`
   - Structure:
     ```
     ~/.agentic/ralph/260204AG_ralph_loop_cli_integration/
     ├── state.json              # Current loop state
     ├── ralph.log               # Debug logging
     └── iterations/
         ├── 1/
         │   ├── output.txt      # Terminal capture
         │   └── metadata.json   # Timestamp, completion check
         ├── 2/
         └── 3/
     ```

### Key Patterns

1. **Plan-Aware Completion Detection**
   ```python
   result = subprocess.run(['agentic', 'plan', 'task', 'current', '-j'])
   data = json.loads(result.stdout)
   is_complete = data.get('all_complete', False)
   ```

2. **Tmux Session Spawning**
   ```bash
   tmux new-session -d -s ralph-{plan_folder}-{iteration}
   tmux send-keys -t ralph-{plan_folder}-{iteration} "claude --print --prompt @prompt.txt" C-m
   ```

3. **Terminal Capture**
   ```bash
   tmux capture-pane -p -J -t ralph-{plan_folder}-{iteration}
   ```

## Reference Implementation

This implementation draws patterns from:

- **Existing Infrastructure:**
  - `modules/AgenticCLI/src/agenticcli/commands/loop.py` - Basic loop tracking
  - `modules/AgenticCLI/src/agenticcli/commands/session.py` - Session spawning
  - `modules/AgenticGuidance/src/agenticguidance/services/session.py` - SessionService

- **Deferred Plan:**
  - `260130MA_multi_agent_tmux_coordination` - Tmux patterns, inbox messaging

## Dependencies

| Component | Status | Purpose |
|-----------|--------|---------|
| AgenticCLI/commands/loop.py | Exists | Loop tracking patterns |
| AgenticCLI/commands/plan.py | Exists | Plan task status queries |
| AgenticCLI/commands/session.py | Exists | Session spawning patterns |
| AgenticGuidance/services/session.py | Exists | SessionService for tmux |

## Success Criteria

### Functional
- Ralph Loop starts with: `agentic ralph start --plan <folder> --prompt-file <file>`
- Loop queries actual plan task status via `agentic plan task current`
- Loop exits when `all_complete` is True (not when agent claims completion)
- Iteration logs captured to `~/.agentic/ralph/{plan_folder}/iterations/`
- Loop can be stopped gracefully
- Status shows current iteration and completion check results
- History lists all loops with filtering

### Quality
- Unit tests pass with 80%+ coverage for RalphLoopService
- Integration tests validate all CLI commands
- Manual test plan covers end-to-end scenarios
- Graceful handling of crashes and max iterations

### User Experience
- Clear output showing progress and next steps
- JSON mode for scripting/automation
- Helpful error messages
- Status command shows actionable information

## Phases

### Phase 1: Core Service Implementation
Create RalphLoopService with state management, iteration logging, and lifecycle management.

**Tasks:** AG_001, AG_002, AG_003

### Phase 2: CLI Command Integration
Create ralph CLI commands that use RalphLoopService.

**Tasks:** AG_004, AG_005, AG_006, AG_007, AG_008, AG_009

### Phase 3: Loop Execution Engine
Implement the main loop that runs iterations and checks completion.

**Tasks:** AG_010, AG_011, AG_012

### Phase 4: Integration and Testing
Validate Ralph Loop works end-to-end with real plans.

**Tasks:** AG_013, AG_014, AG_015

## Test Strategy

### Unit Tests
- Location: `modules/AgenticGuidance/tests/test_services_ralph_loop.py`
- Coverage: RalphLoopService core logic
- Target: 80%+ coverage

### Integration Tests
- Location: `modules/AgenticCLI/tests/integration/test_ralph_cli.py`
- Coverage: CLI commands end-to-end
- Strategy: Mock RalphLoopService to avoid external dependencies

### Manual Testing
- Location: `docs/plans/live/260204AG_ralph_loop_cli_integration/test_plan.md`
- Coverage: Real plan execution, crash recovery, false completion detection

## Related Plans

- **260130MA** (Deferred): Multi-Agent tmux Coordination - Reference for tmux patterns
- **260203QF** (Live): Question Foundation - May benefit from Ralph Loop integration
- **260203PS** (Live): Plan Service - Related planning infrastructure

## Usage Examples

### Start a Ralph Loop
```bash
agentic ralph start \
  --plan 260204AG_ralph_loop_cli_integration \
  --prompt-file prompt.txt \
  --max-iterations 10
```

### Check Status
```bash
agentic ralph status --plan 260204AG_ralph_loop_cli_integration
```

### Stop Loop
```bash
agentic ralph stop --plan 260204AG_ralph_loop_cli_integration
```

### List All Loops
```bash
agentic ralph history --status running
```

## Implementation Notes

### False Completion Protection
The key innovation is **verification over trust**:
- Don't trust agent output claiming "All tasks complete"
- Always query actual plan state: `agentic plan task current -j`
- Check `all_complete` field in JSON output
- Log completion check results to iteration metadata

### Crash Recovery
- Detect if Claude Code crashes mid-iteration
- Log crash to iteration metadata
- Don't lose iteration count
- State.json always reflects current state

### Background Execution
- Loop runs in background (tmux session)
- User can detach and check status later
- Main CLI process returns immediately
- Child process handles iteration loop

## Timeline Estimate

- Phase 1: 2-3 hours (service implementation)
- Phase 2: 2-3 hours (CLI commands)
- Phase 3: 2-3 hours (execution engine)
- Phase 4: 2-3 hours (testing)
- **Total: 8-12 hours**

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Tmux dependency | Document tmux requirement, provide fallback error |
| Claude CLI not found | Check for claude command, clear error message |
| Infinite loop | Max iterations limit, manual stop command |
| State corruption | Atomic writes, backup on update |
| Plan query errors | Retry once, don't treat errors as completion |

## Questions

None currently - design is well-defined from existing patterns.
