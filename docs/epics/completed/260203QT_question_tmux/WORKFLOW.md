# Tmux HITL Workflow Guide

**Plan ID**: 260203QT
**Purpose**: Human-in-the-loop question answering for remote/SSH scenarios
**Last Updated**: 2026-02-06

## Overview

The Tmux HITL (Human-in-the-Loop) workflow enables remote operators to review and answer agent questions through a dedicated tmux notification pane. This is ideal for scenarios where:

- You're working over SSH without voice interface
- You want visual separation between agent execution and question notifications
- You need persistent notifications that survive terminal disconnection
- You're running multiple agents and need to monitor questions centrally

### How It Works

When an agent encounters a blocker and needs human input:

1. Agent generates a question YAML file in `questions/pending/`
2. Tmux notification pane automatically updates with question details
3. Human operator reviews the question in the dedicated pane
4. Operator answers via CLI command: `agentic question answer <id>`
5. Agent detects the answer and automatically resumes work

### Visual Layout

```
┌────────────────────────────────────────────────────────────────────┐
│  Tmux Session: my-work                                              │
│  ┌──────────────────────────────┬────────────────────────────────┐ │
│  │ Main Pane (70%)              │ Questions Pane (30%)           │ │
│  │                               │                                │ │
│  │ $ agentic ralph start        │ PENDING QUESTIONS (2)          │ │
│  │                               │ ────────────────────────────   │ │
│  │ Running task QT-010...       │                                │ │
│  │ Generated question Q-...     │ [1] Q-20260203-143022-a1b2     │ │
│  │ Waiting for answer...        │     Severity: blocking         │ │
│  │                               │     Asked: 14:30:22            │ │
│  │                               │     "Should we proceed with    │ │
│  │                               │      deployment to prod?"      │ │
│  │                               │                                │ │
│  │                               │ [2] Q-20260203-150945-c3d4     │ │
│  │                               │     Severity: high             │ │
│  │                               │     Asked: 15:09:45            │ │
│  │                               │     "Which testing framework   │ │
│  │                               │      should we use?"           │ │
│  │                               │                                │ │
│  │                               │ TO ANSWER:                     │ │
│  │                               │ agentic question answer        │ │
│  │                               │   Q-20260203-143022-a1b2       │ │
│  │                               │                                │ │
│  │                               │ TO LIST ALL:                   │ │
│  │                               │ agentic question list          │ │
│  └──────────────────────────────┴────────────────────────────────┘ │
│  [Ctrl+B, Arrow Keys to navigate between panes]                    │
└────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Required Software

- **tmux** installed and available in PATH
  ```bash
  # Ubuntu/Debian
  sudo apt install tmux

  # macOS
  brew install tmux
  ```

- **AgenticCLI** installed with question support
  ```bash
  cd modules/AgenticCLI
  uv pip install -e .
  ```

- **watchdog** library for file watching (optional, but recommended)
  ```bash
  pip install watchdog>=3.0
  ```

### Environment Check

Verify your environment is ready:

```bash
# Check tmux is installed
which tmux

# Check agentic CLI is available
agentic --version

# Test question commands are available
agentic question --help
```

## Setup Instructions

### Step 1: Start Tmux Session

Create a new tmux session for your work:

```bash
tmux new -s my-work
```

Or attach to an existing session:

```bash
tmux attach -t my-work
```

### Step 2: Start Question Watcher Daemon

The watcher daemon monitors the `questions/pending/` directory and automatically updates the tmux notification pane when questions appear or change.

```bash
agentic question watch-daemon
```

**Expected output:**
```
✓ Question watcher started in background (PID: 12345)
Plan: /home/code/AgenticEngineering/docs/plans/live/260203QT_question_tmux
Use 'agentic question watch-stop' to stop the watcher
```

### Step 3: Verify Notification Pane

After starting the watcher, you should see a new pane appear on the right side of your tmux window (30% width). This pane shows:

- Count of pending questions
- List of questions with severity and timestamps
- CLI commands to answer questions

If the pane doesn't appear immediately:
- It will be created automatically when the first question is generated
- You can manually trigger pane creation by running: `agentic question list --tmux-refresh`

### Step 4: Start Your Agent Work

With the watcher running, start your agent tasks as normal:

```bash
# Example: Start Ralph orchestration loop
agentic ralph start

# Or run specific tasks
agentic plan task execute QT-010
```

## Agent Workflow

When an agent encounters a situation requiring human input:

### 1. Agent Generates Question

The agent creates a question using the QuestionQueue service:

```python
from agenticguidance.services.question import QuestionQueue
from pathlib import Path

queue = QuestionQueue(Path("docs/plans/live/260203QT_question_tmux"))
question = queue.create_question(
    text="Should we proceed with production deployment?",
    context="All tests passed. Ready to deploy version 2.1.0",
    severity="blocking",
    asked_by="agent"
)
```

This creates a file: `questions/pending/Q-YYYYMMDD-HHMMSS-XXXX.yml`

### 2. Notification Pane Updates

The file watcher detects the new question file and:
- Updates the notification pane with formatted question details
- Displays a tmux status message: "1 pending question - check pane"
- Highlights blocking questions in red/bold

### 3. Agent Waits for Answer

The agent enters a polling loop, checking for an answer file:

```python
# Agent waits for answer (blocks until human responds)
while True:
    question = queue.get_question(question_id)
    if question and question.status == "answered":
        answer_text = question.answer
        break
    time.sleep(5)  # Poll every 5 seconds
```

## Human Operator Workflow

### 1. Notice Question Notification

You'll see the notification in two ways:

1. **Tmux status message** (bottom of screen):
   ```
   [tmux] 1 pending question - check pane
   ```

2. **Notification pane** (right side) updates with question details

### 2. Switch to Notification Pane

Navigate to the notification pane to review questions:

- Press `Ctrl+B` (tmux prefix key)
- Then press `→` (right arrow) to move to the notification pane
- Scroll with `Ctrl+B` then `[` (enter copy mode), use arrow keys, press `q` to exit

### 3. Review Question Details

The notification pane shows:
- Question ID (needed for answering)
- Severity level (blocking, high, medium, low)
- Timestamp when question was created
- Full question text
- Context information
- CLI command to answer

Example display:
```
PENDING QUESTIONS (1)
────────────────────────────────

[1] Q-20260203-143022-a1b2
    Severity: blocking
    Asked: 14:30:22
    "Should we proceed with production deployment?"

    Context: All tests passed. Ready to deploy version 2.1.0

TO ANSWER:
agentic question answer Q-20260203-143022-a1b2
```

### 4. Answer the Question

Switch back to the main pane or open a new terminal, then run:

```bash
# Answer with inline text
agentic question answer Q-20260203-143022-a1b2 \
  --text "Yes, proceed with deployment" \
  --confidence high

# Or answer interactively (prompts for text)
agentic question answer Q-20260203-143022-a1b2
```

**Expected output:**
```
✓ Question answered: Q-20260203-143022-a1b2
Answer moved to: .../questions/answered/
```

### 5. Agent Resumes Automatically

Once you provide the answer:
- The question file moves from `pending/` to `answered/`
- The notification pane updates (question disappears from list)
- The agent detects the answer and resumes execution
- Agent continues with the provided answer

## Commands Reference

### Watch Commands

| Command | Description | Use Case |
|---------|-------------|----------|
| `agentic question watch` | Watch questions in foreground | Development/debugging |
| `agentic question watch-daemon` | Watch questions in background | Production use in tmux |
| `agentic question watch-stop` | Stop all running watchers | Cleanup before exit |

**Examples:**

```bash
# Start watcher daemon (recommended for tmux)
agentic question watch-daemon

# Start watcher in foreground (for debugging)
agentic question watch

# Stop all watchers
agentic question watch-stop
```

### Question Management Commands

| Command | Description | Options |
|---------|-------------|---------|
| `agentic question list` | List questions | `--status pending\|answered\|all` |
| `agentic question show <id>` | Show question details | - |
| `agentic question answer <id>` | Answer a question | `--text`, `--confidence` |
| `agentic question defer <id>` | Defer a question | - |
| `agentic question ask <text>` | Create new question | `--severity`, `--context` |

**Examples:**

```bash
# List only pending questions (default)
agentic question list

# List all questions (pending + answered)
agentic question list --status all

# Show details for specific question
agentic question show Q-20260203-143022-a1b2

# Answer with high confidence
agentic question answer Q-20260203-143022-a1b2 \
  --text "Yes, approved for production" \
  --confidence high

# Defer a non-urgent question
agentic question defer Q-20260203-150945-c3d4

# Create a new question manually
agentic question ask "Should we refactor the auth module?" \
  --severity medium \
  --context "Current code has high complexity"
```

### Tmux Navigation

| Key Combination | Action |
|-----------------|--------|
| `Ctrl+B` then `←` | Switch to left pane |
| `Ctrl+B` then `→` | Switch to right pane |
| `Ctrl+B` then `↑` | Switch to upper pane |
| `Ctrl+B` then `↓` | Switch to lower pane |
| `Ctrl+B` then `[` | Enter copy mode (scroll) |
| `q` | Exit copy mode |
| `Ctrl+B` then `d` | Detach from session |

**Tmux Cheat Sheet:**

```bash
# Create new session
tmux new -s session-name

# List sessions
tmux ls

# Attach to session
tmux attach -t session-name

# Detach from session (inside tmux)
Ctrl+B, d

# Kill session (from outside)
tmux kill-session -t session-name

# Rename session (inside tmux)
Ctrl+B, $
```

## Troubleshooting

### Pane Not Appearing

**Symptom**: After starting watcher, no notification pane appears

**Possible Causes & Solutions**:

1. **Not in a tmux session**
   ```bash
   # Check if in tmux
   echo $TMUX
   # Should output something like: /tmp/tmux-1000/default,12345,0

   # If empty, start tmux first
   tmux new -s my-work
   ```

2. **Watcher not running**
   ```bash
   # Check watcher status
   ps aux | grep question

   # Restart watcher
   agentic question watch-stop
   agentic question watch-daemon
   ```

3. **No questions pending yet**
   - Pane is created on-demand when first question appears
   - Create a test question to trigger pane creation:
     ```bash
     agentic question ask "Test question" --severity low
     ```

### Watcher Not Updating

**Symptom**: Pane exists but doesn't update when questions change

**Solutions**:

1. **Verify watcher is running**
   ```bash
   ps aux | grep "question.*watch"

   # Should see a Python process
   ```

2. **Check file permissions**
   ```bash
   # Ensure questions directory is writable
   ls -la docs/plans/live/260203QT_question_tmux/questions/
   ```

3. **Manually refresh pane**
   ```bash
   agentic question list --tmux-refresh
   ```

4. **Restart watcher with logging**
   ```bash
   agentic question watch-stop

   # Run in foreground to see debug output
   agentic question watch
   ```

### Tmux Not Detected

**Symptom**: Commands work but tmux features not activating

**Solutions**:

1. **Verify TMUX environment variable**
   ```bash
   env | grep TMUX

   # Should output TMUX=/tmp/tmux-...
   ```

2. **Check tmux is in PATH**
   ```bash
   which tmux
   # Should output: /usr/bin/tmux or similar
   ```

3. **Reinstall tmux if needed**
   ```bash
   sudo apt update
   sudo apt install --reinstall tmux
   ```

### Questions Not Appearing

**Symptom**: Agent creates questions but they don't show in pane

**Solutions**:

1. **Check plan path resolution**
   ```bash
   # Verify plan detection
   agentic context bootstrap --role build-python

   # Or manually specify plan
   agentic question list --plan /full/path/to/plan/folder
   ```

2. **Verify file structure**
   ```bash
   # Check questions directory exists
   ls -la docs/plans/live/*/questions/pending/

   # Create if missing
   mkdir -p docs/plans/live/260203QT_question_tmux/questions/pending
   ```

3. **Check YAML file format**
   ```bash
   # View a question file directly
   cat questions/pending/Q-*.yml

   # Should be valid YAML with required fields
   ```

### Pane Shows "No Pending Questions" But Agent Is Waiting

**Symptom**: Agent blocks waiting for answer, but pane shows no questions

**Solutions**:

1. **Different plan paths**
   - Agent and watcher may be monitoring different plan folders
   - Verify both use the same plan path:
     ```bash
     # In agent logs, check plan path
     # In CLI, specify explicit path
     agentic question watch-daemon --plan /path/to/plan
     ```

2. **Question in wrong directory**
   ```bash
   # Check all question directories
   find . -name "Q-*.yml" -type f

   # Move to correct location if needed
   mv questions/Q-*.yml questions/pending/
   ```

3. **Corrupted question file**
   ```bash
   # Validate YAML syntax
   python3 -c "import yaml; yaml.safe_load(open('questions/pending/Q-*.yml'))"
   ```

### Watcher Daemon Won't Stop

**Symptom**: `watch-stop` command fails or daemon keeps running

**Solutions**:

1. **Force kill the process**
   ```bash
   # Find the PID
   ps aux | grep "question.*watch"

   # Kill by PID
   kill -9 <PID>
   ```

2. **Clean up state files**
   ```bash
   # Remove state tracking files
   rm ~/.agentic/state/question_watcher_*
   ```

3. **Check for multiple watchers**
   ```bash
   # List all question watcher processes
   ps aux | grep question

   # Kill all at once
   pkill -f "question.*watch"
   ```

## Best Practices

### For Remote Work

1. **Use persistent tmux sessions**
   - Name your sessions meaningfully: `tmux new -s project-name`
   - Detach instead of closing: `Ctrl+B, d`
   - Reattach after network disconnection: `tmux attach -t project-name`

2. **Start watcher in daemon mode**
   - Always use `watch-daemon` for background operation
   - Avoid `watch` (foreground) unless debugging

3. **Monitor multiple plans**
   - Start separate watcher for each active plan
   - Use different tmux windows for each plan
   - Example multi-plan setup:
     ```bash
     # Window 1: Plan QT
     cd /path/to/QT_plan
     agentic question watch-daemon

     # Window 2: Plan QC
     cd /path/to/QC_plan
     agentic question watch-daemon
     ```

### For Agent Development

1. **Test question flow before production**
   ```bash
   # Create test question
   agentic question ask "Test" --severity low

   # Verify pane updates
   # Answer the question
   agentic question answer <id> --text "Test answer"

   # Verify pane clears
   ```

2. **Use appropriate severity levels**
   - `blocking`: Agent cannot proceed (requires immediate answer)
   - `high`: Important for workflow (answer soon)
   - `medium`: Normal priority (can wait)
   - `low`: Optional feedback (can be deferred)

3. **Provide context in questions**
   - Include relevant background information
   - Explain why the question matters
   - Suggest options if applicable

### For Production Use

1. **Set up session restoration**
   - Use tmux session management tools (tmuxinator, tmuxp)
   - Save session layouts for quick restoration
   - Document session setup in project README

2. **Monitor watcher health**
   ```bash
   # Add to cron or monitoring script
   ps aux | grep "question.*watch" || agentic question watch-daemon
   ```

3. **Clean up answered questions periodically**
   ```bash
   # Archive old answered questions
   find questions/answered -mtime +30 -name "*.yml" -exec mv {} archive/ \;
   ```

## Advanced Usage

### Custom Notification Format

The notification pane content is generated by `agenticcli.utils.question_formatter.format_question_notification()`. To customize the display format, modify this function in your fork or create a plugin.

### Integration with Voice Interface

For hybrid workflows combining tmux and voice:

1. Run tmux watcher for visual notifications
2. Use voice interface for answering (when available)
3. Both interfaces monitor the same `questions/` directory

See related plan: [260203VP - Voice PersonaPlex](../260203VP_voice_personaplex/)

### Multi-Session Orchestration

For complex multi-agent scenarios:

```bash
# Terminal 1: Orchestrator
tmux new -s orchestrator
agentic ralph start

# Terminal 2: Monitor
tmux new -s monitor
agentic question watch-daemon --plan /path/to/all/plans
watch -n 2 'agentic question list --status pending'

# Terminal 3: Answer
# Use for manual question answering
agentic question list
agentic question answer <id>
```

## Related Documentation

- [Question CLI README](../../../../modules/AgenticCLI/README.md#question---question-queue-management)
- [Question Service Implementation](../../../../modules/AgenticGuidance/src/agenticguidance/services/question.py)
- [Tmux Utilities](../../../../modules/AgenticCLI/src/agenticcli/utils/tmux.py)
- [Plan Overview](./README.md)

## Support

For issues, questions, or feature requests:

1. Check this troubleshooting guide
2. Review agent guidance documentation
3. Test with minimal reproduction case
4. Report issues with full context (logs, environment, steps)

## Changelog

- **2026-02-06**: Initial documentation created for QT-010
- Future updates will be tracked here
