# Question TUI - Detailed UI Design

## Overview

The Question TUI replaces ntfy push notifications with a persistent tmux window
that the user can switch to from any pane. It works over SSH and Termux on
Android.

The core interaction model is a **navigable list** - the user moves a cursor
through pending questions with arrow keys or Tab, presses Enter to answer,
and the cursor auto-advances to the next question. This minimises friction:
answering 5 questions feels like a flow, not 5 separate command invocations.

The TUI also supports **iterative Q&A**: the user can reply "need more info"
which signals the agent to provide clarification, and new follow-up questions
that arrive during the session appear automatically in the list.

**Rendering**: Uses `tty.setcbreak()` for single-keypress reading and Rich
Console for output. No Rich Live, no Textual, no curses, no external deps
beyond Rich (already installed). Works on any ANSI terminal.

---

## 1. Tmux Window Lifecycle

### Launch: `agentic question dashboard`

```
User is in any tmux pane (e.g. orchestrator main pane)
  |
  v
Runs: agentic question dashboard
  |
  v
Is there already a tmux window named "questions"?
  YES --> tmux select-window -t questions  (focus it)
  NO  --> tmux new-window -n questions \
            "agentic question dashboard --no-tmux-window"
          (creates window, runs TUI inside it)
```

If NOT in tmux at all, the TUI runs directly in the current terminal.

### Notification: agent asks a question

```
Agent runs: agentic agent question ask "Should we use approach A or B?"
  |
  v
Question persisted to YAML (unchanged)
  |
  v
notify_question_window() called:
  - tmux display-message "1 new question - switch to [questions] window"
  - If questions window exists: tmux set-option -t questions \
      monitor-activity on  (causes window name to highlight in status bar)
```

The user sees the status bar flash and switches to the `questions` window
with `Ctrl-B w` (window list) or `Ctrl-B <number>`.

### Exit

Pressing `q` or `Ctrl-C` in the TUI exits cleanly. The tmux window closes
(process exits, window auto-closes). No daemon process stays behind.

---

## 2. Main Screen: Navigable Question List

The default view. A cursor (highlighted row) shows which question is
selected. Auto-refreshes every 5s between keypresses.

### Layout (80-column terminal)

```
 PENDING QUESTIONS (3)                        Auto-refresh: 5s

 Plan           Severity  Question
 ─────────────────────────────────────────────────────────────
 260221TU_re..  BLOCKING  Should we use Rich Live or Textual
 260220MI_mi..  HIGH      Which migration strategy for TinyDB   <-- cursor
 260221NE_fi..  MEDIUM    Should we keep backward-compat alias

 ─────────────────────────────────────────────────────────────
 ↑↓/Tab navigate  Enter answer  m more info  d defer  q quit
```

The **cursor row** is rendered with an inverted/highlighted background
(Rich `[reverse]` style or `[on white]` for the row). Everything else
is normal.

### Column layout

No `#` column needed - the cursor replaces numbered selection.

| Column   | Width | Notes                            |
|----------|-------|----------------------------------|
| Plan     | 14    | Truncated with `..`              |
| Severity | 8     | Color-coded                      |
| Question | rest  | Truncated to fit, single line    |

### Severity color coding

| Severity | Normal row          | Cursor row (inverted bg)    |
|----------|---------------------|-----------------------------|
| BLOCKING | `[red bold]`        | `[red bold reverse]`        |
| HIGH     | `[red]`             | `[red reverse]`             |
| MEDIUM   | `[yellow]`          | `[yellow reverse]`          |
| LOW      | `[dim]`             | `[reverse]`                 |

### Empty state

```
 PENDING QUESTIONS (0)                        Auto-refresh: 5s

 No pending questions. All clear.

 Waiting for new questions...
 Press q to quit.
```

### New question arrives (auto-refresh)

When the list refreshes and a new question appears, the status line briefly
shows:

```
 ─────────────────────────────────────────────────────────────
 NEW: 1 question added                    ↑↓ Tab Enter d m q
```

The cursor stays on the same question (matched by ID), or moves to the
first question if the previously-selected one was answered/removed.

---

## 3. Keyboard Controls

All input is single-keypress (cbreak mode). No Enter required for
navigation.

| Key          | Action                                          |
|--------------|-------------------------------------------------|
| `↑` / `k`   | Move cursor up                                  |
| `↓` / `j`   | Move cursor down                                |
| `Tab`        | Move cursor to next question (wraps to top)     |
| `Enter`      | Open answer flow for selected question          |
| `m`          | Request more info (iterative flow)              |
| `d`          | Defer selected question                         |
| `s`          | Show full detail (read-only)                    |
| `q`          | Quit TUI                                        |
| `Ctrl-C`     | Quit TUI                                        |

Arrow keys are detected via escape sequences:
- `ESC [ A` = Up
- `ESC [ B` = Down

The `j`/`k` vim bindings are a fallback for terminals that don't send
proper arrow escape sequences (rare, but possible on some Termux configs).

---

## 4. Interaction Flow: Answering a Question (Enter)

### Step 1: Press Enter on highlighted row

The list screen clears. Full question detail is shown:

```
 ─────────────────────────────────────────────────────────────
 QUESTION                                   Plan: 260220MI_mi..
 Severity: HIGH        Asked by: build-python
 Time: 2026-02-21 14:32:05
 ─────────────────────────────────────────────────────────────

 Which migration strategy should we use for TinyDB? Options
 are incremental migration (migrate on read) or bulk migration
 (one-time script that converts all records).

 Context:
 The PlanService currently uses YAML files with FileLock. We
 need to move to TinyDB for better query support. There are
 ~50 plan files in production.

 ─────────────────────────────────────────────────────────────
```

### Step 2a: Suggested answers (if present)

```
 Select an answer:
   ↑↓ to select, Enter to confirm, c custom, Esc back

   Incremental migration (migrate on read)           <-- cursor
   Bulk migration (one-time script)

 ─────────────────────────────────────────────────────────────
```

Suggested answers are also navigable with ↑↓. Enter confirms.
`c` switches to custom freeform input. `Esc` goes back to list
without answering.

### Step 2b: Freeform answer (no suggestions)

```
 Your answer (Esc to cancel):
 > _
```

This is the one place where we switch back to line-buffered input
(restore terminal, use `input()`, then re-enter cbreak). The user
types freely and presses Enter.

### Step 3: Confirmation

```
 Your answer: Incremental migration (migrate on read)

 Submit? [Y/n/e]   Y=submit  n=cancel  e=edit
```

Single keypress: `y`/Enter submits, `n` cancels, `e` re-opens the
answer input.

### Step 4: Auto-advance

```
 ✓ Answer submitted.
```

Brief flash (0.5s), then the list redraws with:
- The answered question removed
- Cursor auto-advanced to the next pending question
- If no more questions: shows empty state

This means answering 5 questions is: Enter, type, Enter, y,
Enter, type, Enter, y, Enter, type, Enter, y... — a smooth flow.

---

## 5. Interaction Flow: Request More Info (m)

This is the **iterative Q&A** feature. Sometimes the user needs more
context before they can answer.

### Step 1: Press `m` on highlighted row

```
 ─────────────────────────────────────────────────────────────
 REQUEST MORE INFO                          Plan: 260220MI_mi..

 Which migration strategy should we use for TinyDB?...

 What info do you need? (Esc to cancel):
 > _
```

### Step 2: User types their request

```
 > How many concurrent readers do we expect? And what's the
   current read latency?
```

### Step 3: Submitted as a special answer

The response is submitted as an answer with a `need_more_info` flag:

```yaml
status: answered
answer: "Need more info: How many concurrent readers do we expect?..."
answered_by: human
confidence: null
need_more_info: true
```

The agent sees `need_more_info: true` in the answer file, provides
clarification, and creates a new follow-up question. The TUI auto-
refreshes and the follow-up appears in the list.

### Step 4: Back to list

```
 → Info requested. Waiting for agent follow-up...
```

Cursor stays in position. When the follow-up question arrives (next
auto-refresh), it appears in the list (possibly at the top if it's
higher severity).

---

## 6. Interaction Flow: Defer (d)

### Press `d` on highlighted row

```
 Defer this question?
 "Which migration strategy for TinyDB..."

 [Y/n]
```

Single keypress. `y`/Enter defers, `n` cancels.

On defer: question disappears from list, cursor moves to next.

---

## 7. Interaction Flow: Show Detail (s)

### Press `s` on highlighted row

Same detail view as the answer flow (Section 4, Step 1) but read-only:

```
 (full question detail)

 Press any key to return...
```

Any keypress returns to the list. Useful for reading long context
before deciding to answer.

---

## 8. Rendering: Cbreak + Rich Pattern

### Why cbreak mode?

The navigable list requires single-keypress input (arrow keys, Enter,
q, d, m) without waiting for the user to press Enter after each key.
Python's `tty.setcbreak()` enables this on any Unix terminal.

### Render loop pseudocode

```python
import sys
import tty
import termios
import time
from rich.console import Console

class QuestionTUI:
    def __init__(self, repo_root, refresh_seconds=5):
        self.console = Console()
        self.repo_root = repo_root
        self.refresh = refresh_seconds
        self.cursor = 0
        self.questions = []   # list of (question_data, plan_path)

    def run(self):
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            while True:
                self._refresh_questions()
                self._render()
                key = self._read_key_with_timeout(self.refresh)

                if key is None:
                    continue  # timeout => re-render (auto-refresh)
                elif key == 'q' or key == '\x03':  # q or Ctrl-C
                    break
                elif key == '\x1b[A' or key == 'k':  # Up
                    self.cursor = max(0, self.cursor - 1)
                elif key == '\x1b[B' or key == 'j':  # Down
                    self.cursor = min(len(self.questions) - 1, self.cursor + 1)
                elif key == '\t':  # Tab
                    self.cursor = (self.cursor + 1) % max(1, len(self.questions))
                elif key == '\r':  # Enter
                    self._handle_answer()
                elif key == 'd':
                    self._handle_defer()
                elif key == 'm':
                    self._handle_more_info()
                elif key == 's':
                    self._handle_show()
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    def _read_key_with_timeout(self, timeout):
        """Read a keypress, or return None after timeout.

        Uses select.select() for the timeout. Reads escape sequences
        for arrow keys (ESC [ A/B/C/D) as a single logical key.
        """
        import select
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            return None
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            # Possible escape sequence - read more
            ready2, _, _ = select.select([sys.stdin], [], [], 0.05)
            if ready2:
                ch += sys.stdin.read(1)
                if ch[-1] == '[':
                    ready3, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if ready3:
                        ch += sys.stdin.read(1)
        return ch

    def _render(self):
        """Clear screen and print the question table with cursor highlight."""
        self.console.clear()
        # ... build and print Rich Table with cursor row highlighted ...

    def _handle_answer(self):
        """Switch to line mode for answer input, then back to cbreak."""
        # Restore terminal for input()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
        try:
            # Show full question, get answer via interactive_answer_wizard
            # Submit answer
            pass
        finally:
            # Re-enter cbreak mode
            tty.setcbreak(sys.stdin.fileno())
```

### Terminal mode switching

The TUI runs in **cbreak mode** for the list navigation, but **restores
normal line mode** for freeform text input (answer typing). The switch
is:

```
cbreak mode (navigation)
  --> Enter pressed
  --> termios restore (line mode)
  --> input() for answer text
  --> tty.setcbreak() again
  --> back to navigation
```

This is clean and well-tested on Termux and SSH. The `termios` save/
restore ensures we never leave the terminal in a broken state, even if
the process crashes (wrapped in try/finally).

---

## 9. Screen Adaptations

### Termux Portrait (60 cols x 30 rows)

- Plan column shrinks to 10 chars
- Question column shrinks accordingly
- Severity shows abbreviated: `BLK`, `HI`, `MED`, `LO`
- Status bar: shorter keybinding hints

Detection: `console.width` from Rich Console.

### Termux Landscape / SSH (80+ cols)

- Full layout as shown in Section 2

### Large terminal (120+ cols)

- Question column gets more space
- Shows `Asked By` as an extra column

---

## 10. Notification Flow (replacing ntfy)

### When an agent asks a question

```
Agent                          Filesystem                    tmux
  |                               |                            |
  |-- agentic agent question ask ->                            |
  |                               |-- write pending/*.yml      |
  |                               |                            |
  |-- notify_question_window() ---|--------------------------->|
  |                               |     display-message:       |
  |                               |     "New question pending" |
  |                               |     + highlight questions  |
  |                               |       window in status bar |
```

### When user answers in TUI

```
User (in questions window)     Filesystem                    Agent
  |                               |                            |
  |-- Enter, answers ------------>|                            |
  |   (cursor auto-advances)      |-- move to answered/*.yml   |
  |                               |                            |
  |-- list auto-refreshes         |                            |
  |   (answered q disappears)     |                            |
  |                               |                            |
  |                               |<-- agent watches fs -------|
  |                               |    (existing watcher)      |
  |                               |                            |
  |                               |--- agent reads answer ---->|
```

### Iterative Q&A flow

```
User                            Filesystem                   Agent
  |                               |                            |
  |-- m (more info) ------------>|                             |
  |                               |-- answered/*.yml           |
  |                               |   (need_more_info: true)   |
  |                               |                            |
  |                               |<-- agent reads answer ---->|
  |                               |    sees need_more_info     |
  |                               |                            |
  |                               |<-- agent asks follow-up ---|
  |                               |    pending/new_q.yml       |
  |                               |                            |
  |<-- TUI auto-refreshes -------|                             |
  |   (new question appears)     |                             |
  |                               |                            |
  |-- Enter, answers follow-up -->|                            |
```

---

## 11. Command Summary After Redesign

### User-facing (unchanged names, new behavior)

| Command | Behavior |
|---------|----------|
| `agentic question dashboard` | Opens/focuses `questions` tmux window with navigable TUI |
| `agentic question list` | CLI table output (unchanged) |
| `agentic question show <id>` | CLI detail output (unchanged) |
| `agentic question answer <id>` | CLI answer (unchanged, for scripting) |

### Agent-facing (unchanged)

| Command | Behavior |
|---------|----------|
| `agentic agent question ask` | Create question + `notify_question_window()` |
| `agentic agent question defer` | Defer question (unchanged) |
| `agentic agent question watch` | Filesystem watcher (ntfy removed) |
| `agentic agent question watch-daemon` | Background watcher (ntfy removed) |
| `agentic agent question watch-stop` | Stop watcher (unchanged) |

### Removed

| What | Why |
|------|-----|
| ntfy push notifications | Replaced by tmux window notification |
| NtfyReplyPoller | Replaced by direct TUI answering |
| NtfyQuestionAgent | No longer needed |
| ntfy preferences config | No longer read |

---

## 12. File Changes Summary

| File | Change |
|------|--------|
| `tui/question_tui.py` | **NEW** - QuestionTUI class (cbreak + Rich) |
| `tui/__init__.py` | **NEW** - package marker |
| `commands/question.py` | Modify `cmd_dashboard` to launch TUI; remove ntfy code |
| `utils/tmux_notify.py` | Add `notify_question_window()`; deprecate old functions |
| `services/question_watcher.py` | Remove NtfyReplyPoller class |
| `models/question.py` | Add `need_more_info` field to Question dataclass |
| `utils/ntfy.py` | **DELETE** |
| `services/ntfy_question_agent.py` | **DELETE** |

---

## 13. Answer Flow Timing (Friction Analysis)

Goal: answering a simple question with suggested answers should take
**under 3 seconds** of user interaction.

| Step | Keys | Time |
|------|------|------|
| Navigate to question | ↓ or Tab (0-3 presses) | ~1s |
| Open answer | Enter | instant |
| Select suggested answer | ↓ then Enter | ~0.5s |
| Confirm | y or Enter | instant |
| Auto-advance | automatic | 0s |

Total: ~1.5s per question with suggestions, ~3-5s for freeform.

Compare to current CLI flow:
1. Read notification (switch context)
2. Type `agentic question list --plan X`
3. Read question IDs
4. Type `agentic question answer <long-id> --text "..."`
5. Repeat for each question

Current: ~30s per question. New: ~3s per question.
