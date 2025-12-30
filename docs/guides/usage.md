# Usage Guide

This guide covers how to use MyAgents, including both the Echo Agent and Coding Agent, as well as LangGraph Studio integration.

## Quick Start

```bash
# Run the coding agent (default)
myagents chat

# Run the echo agent
myagents chat --agent echo

# Run the coding agent explicitly
myagents chat --agent coding
```

## Echo Agent Usage

The Echo Agent is a basic conversational agent for simple interactions.

### Starting the Echo Agent

```bash
myagents chat --agent echo
```

### What Happens

1. Your input is processed by the `process_input` node (currently just passes through)
2. Input is sent to `generate_response` node which calls Gemini 2.5-flash
3. Response is printed to console
4. Process exits (no conversation history retained)

### Example Session

```
Enter your message: Explain quantum computing in one sentence

Processing your request...

[Agent response from Gemini appears here]
```

### Limitations

- **Single-shot interaction:** Each run is independent, no follow-up questions
- **No conversation history:** Previous messages are not retained
- **No multi-turn dialogues:** Must restart for each new question
- **No tool-calling:** Agent cannot use any tools

### Use Cases

The Echo Agent is suitable for:
- Quick one-off questions
- Testing LangGraph setup
- Learning LangGraph basics
- Simple Q&A without context

## Coding Agent Usage

The Coding Agent provides file operation capabilities with multi-turn conversation support.

### Starting the Coding Agent

```bash
# Method 1: Default agent
myagents chat

# Method 2: Explicit agent selection
myagents chat --agent coding
```

### Interactive CLI

Once started, you'll see:

```
Coding Agent CLI
Type 'exit' or 'quit' to end the session
You:
```

### Available Commands

**File Operations:**
- List files in a directory
- Read file contents
- Edit existing files
- Search file contents (`search_in_files`)
- Find files by pattern (`find_files`)

**Shell Execution:**
- Execute shell commands within allowed directories
- Run system commands like `pwd`, `ls`, etc.

**Git Operations:**
- Get repository root (`git_repo_root`)
- Check git status (`git_status`)
- View diffs (`git_diff`)
- Get current branch (`git_current_branch`)

**Session Commands:**
- `exit` - End the session
- `quit` - End the session

### Example Sessions

#### Listing Files

```
You: List the files in the current directory

Agent: I'll list the files for you.

[Agent uses list_files tool and displays results]

Files in current directory:
- README.md
- pyproject.toml
- langgraph.json
...
```

#### Reading Files

```
You: Read the README.md file

Agent: I'll read that file for you.

[Agent uses read_file tool and displays contents]

The README.md file contains:
# MyAgents
...
```

#### Editing Files

```
You: Update the version number in pyproject.toml to 1.2.0

Agent: I'll make that change for you.

[Agent uses edit_file tool]

Done! I've updated the version to 1.2.0 in pyproject.toml.
```

#### Searching File Contents

```
You: Search for "TODO" comments in all Python files

Agent: I'll search for that pattern.

[Agent uses search_in_files tool]

Found matches in 5 files:
- src/main.py:42: # TODO: Add error handling
- src/utils.py:15: # TODO: Optimize this function
...
```

#### Finding Files by Pattern

```
You: Find all test files in the project

Agent: I'll find files matching that pattern.

[Agent uses find_files tool with pattern "**/test_*.py"]

Found 12 test files:
- tests/test_main.py
- tests/workflows/test_echo_agent.py
...
```

#### Multi-Turn Conversations

```
You: List all Python files in the backend directory

Agent: [Lists Python files]

You: Now read the contents of the agents.py file

Agent: [Reads and displays agents.py]

You: Change the temperature setting to 0.7

Agent: [Edits the file with new temperature value]
```

#### Shell Execution

```
You: run pwd to check current directory

Agent: I'll check the current directory for you.

[Agent uses execute_shell tool]

Current directory: /home/user/myagents
```

```
You: run git status to see repository state

Agent: I'll check the git status.

[Agent uses execute_shell tool]

On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

```
You: list files in current directory

Agent: I'll list the files for you.

[Agent uses execute_shell tool with 'ls -la']

total 48
drwxr-xr-x  8 user user 4096 Nov 24 10:00 .
drwxr-xr-x  5 user user 4096 Nov 24 09:00 ..
-rw-r--r--  1 user user 1234 Nov 24 10:00 README.md
...
```

#### Shell Execution Security Constraints

The `execute_shell` tool operates with the following security restrictions:

- **Allowed directory restriction:** Commands can only be executed within the allowed directory path. Attempts to access files or directories outside this path will be rejected.
- **30-second timeout:** All shell commands have a maximum execution time of 30 seconds. Long-running commands will be terminated automatically.
- **No interactive commands:** Commands requiring user input are not supported.

### How the Coding Agent Works

1. **You enter a natural language request**
   - Agent analyzes your request
   - Determines if tools are needed

2. **Agent decides on action**
   - If tools needed: Calls appropriate file operations
   - If no tools needed: Generates direct response

3. **Tool execution (if applicable)**
   - read_file: Reads and returns file contents
   - list_files: Lists directory contents
   - edit_file: Makes text replacements
   - search_in_files: Searches file contents with regex patterns
   - find_files: Finds files matching glob patterns
   - execute_shell: Runs shell commands within allowed directory

4. **Agent processes results**
   - Formats tool output
   - Generates user-friendly response
   - Maintains conversation context

5. **Conversation continues**
   - Full context retained throughout session
   - Can reference previous operations
   - Multi-step workflows supported

### Best Practices

**For File Listing:**
- Be specific about the directory path
- Specify if you want recursive listing
- Ask for specific file types if needed

**For File Reading:**
- Use absolute or relative paths
- Agent works best with text files
- Large files may be slow to display

**For File Editing:**
- Be specific about the changes you want
- Provide enough context for the agent to find the right location
- Double-check changes if they're critical
- Remember: No undo functionality exists

**For File Search:**
- Use regex patterns for content search (e.g., `TODO.*fix`)
- Use glob patterns for file finding (e.g., `**/*.py`, `src/**/*.ts`)
- Combine search with read for efficient workflows
- Specify file types when searching large codebases

### Limitations

- **No write operations:** Can edit existing files but not create new ones
- **No undo:** Changes are immediate and permanent
- **Text files only:** Binary files not supported
- **Limited error recovery:** File operation failures may require retry
- **No sandboxing:** No permission controls on file access

### Error Handling

If a file operation fails:
1. Agent will report the error
2. You can retry with corrected information
3. Session continues (not terminated by errors)

Common errors:
- File not found
- Permission denied
- Invalid file format (binary files)
- File too large

## LangGraph Studio

Both agents can be accessed via LangGraph Studio for visual debugging and development.

### Starting Studio

```bash
# Ensure port 2024 is available
uv run langgraph dev

# Studio will start at: http://localhost:2024
```

### Opening Studio

1. Open your browser
2. Navigate to: http://localhost:2024
3. Select an agent:
   - `echo` - Basic conversational agent
   - `coding` - File operations agent

### Studio Features

**Visual Graph:**
- See node execution flow
- Watch state changes in real-time
- Visualize conditional routing

**Step-by-Step Debugging:**
- Pause execution at nodes
- Inspect state at each step
- See tool calls and results

**State Inspection:**
- View complete message history
- See tool call details
- Inspect custom state fields

**Tool Call Visualization:**
- See which tools are called
- View tool inputs
- See tool outputs

### Benefits of Studio

- **Learning:** Understand how agents work internally
- **Debugging:** Identify issues in graph execution
- **Development:** Test changes to agent logic
- **Visualization:** See the graph structure clearly

### Studio Limitations

- **No production use:** Studio is for development only
- **Port requirement:** Needs port 2024 available
- **Local only:** Not designed for remote access
- **Performance:** May be slower than CLI for simple operations

## Tips and Tricks

### For Echo Agent

1. **Keep questions focused:** Single-topic questions work best
2. **Be specific:** Vague prompts may produce vague responses
3. **Test quickly:** Good for rapid experimentation

### For Coding Agent

1. **Use absolute paths:** More reliable than relative paths
2. **Start broad, then narrow:** List directory first, then read specific files
3. **Describe edits clearly:** Provide context and be specific
4. **Verify critical changes:** Ask agent to read file after edits
5. **Use exit command:** Type 'exit' or 'quit' to end session cleanly

### For LangGraph Studio

1. **Use for learning:** Great way to understand agent internals
2. **Debug complex flows:** Especially useful for tool-calling agents
3. **Inspect state:** See exactly what data the agent is working with
4. **Test changes:** Quick iteration on agent modifications

## Next Steps

- **Architecture:** Learn how agents work internally - see [../architecture/architecture.md](../architecture/architecture.md)
- **Testing:** Verify your setup - see [../../tests/README.md](../../tests/README.md)
- **Setup:** Initial setup and configuration - see [../SETUP.md](../SETUP.md)
