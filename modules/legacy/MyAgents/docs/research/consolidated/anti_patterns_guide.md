# Anti-Patterns Guide for Multi-Agent Systems

**Created:** 2025-10-24
**Purpose:** Catalog of common mistakes when building LangGraph-based multi-agent systems
**Audience:** Developers building production multi-agent systems
**Scope:** Detection, remediation, and prevention of anti-patterns

---

## Introduction

### Why Agents Fail Differently Than Traditional Software

Multi-agent systems introduce failure modes that don't exist in traditional software:

**Non-Deterministic Behavior:** LLMs produce variable outputs for the same input, making failures difficult to reproduce.

**Error Amplification:** Unlike human collaboration where errors get filtered, LLM agents propagate hallucinations through agent chains, amplifying rather than correcting mistakes.

**State Management Complexity:** Agent state grows unbounded across conversations, leading to context window overflow and token limit errors that crash the system.

**Coordination Failures:** Multiple agents can deadlock, create infinite loops, or fail to coordinate, causing silent failures that are hard to debug.

**Cascading Failures:** One agent's error impacts all downstream agents, with no natural circuit breaker to prevent cascade.

### Common Failure Modes

**Silent Failures:** Agent produces wrong output but execution continues, discovered only by user feedback.

**Context Overflow:** Message history exceeds LLM token limits, causing API errors mid-conversation.

**Hallucination Propagation:** Agent generates false information that downstream agents treat as fact.

**Routing Errors:** Supervisor agent routes tasks to wrong worker, causing capability mismatches.

**State Corruption:** Concurrent updates overwrite state, losing critical conversation context.

**Infinite Loops:** Conditional routing logic creates cycles, consuming resources until timeout.

**Memory Leaks:** State accumulates without cleanup, eventually exhausting memory.

### How to Use This Guide

**For Each Anti-Pattern:**
1. Read the description to understand the problem
2. Check detection methods against your system
3. Apply remediation strategies with code examples
4. Use prevention checklist to avoid the issue

**When Debugging:**
1. Identify symptoms in your system
2. Search this guide for matching anti-patterns
3. Follow LangSmith trace analysis section
4. Apply remediation and validate fix

**Before Production:**
1. Review prevention checklist (Section 10)
2. Audit code against all anti-patterns
3. Add detection monitoring
4. Test error paths explicitly

### Prevention Mindset

**Design for Failure:** Assume every LLM call can fail, every agent can hallucinate, every state update can conflict.

**Observable First:** If you can't trace it, you can't debug it. Instrument before building complexity.

**State Hygiene:** State should be minimal, explicit, and validated. Never assume state consistency.

**Explicit is Better:** Implicit coordination leads to bugs. Make agent handoffs, routing decisions, and error handling explicit.

---

## 1. State Management Anti-Patterns

### Anti-Pattern 1.1: Monolithic State (Severity: HIGH)

**Description:** Putting everything in one giant state object with no organization or boundaries.

**Example:**
```python
# BAD: Everything in one state
class AgentState(TypedDict):
    messages: list  # Conversation history
    user_profile: dict  # User info
    search_results: list  # From research agent
    code_files: list  # From coding agent
    analysis_data: dict  # From analysis agent
    temp_calculations: list  # Temporary data
    llm_client: Any  # Services
    database_connection: Any  # Infrastructure
    config: dict  # Configuration
    logs: list  # Debugging data
```

**Why It's Bad:**
- Context window overflow as state grows unbounded
- Hard to debug - which field caused the error?
- No separation of concerns - agents see everything
- State serialization fails with non-serializable objects (llm_client, database_connection)
- Checkpointing fails or becomes extremely slow

**Detection Methods:**
- State size grows beyond 50KB in checkpoints
- Token limit errors (context length exceeded)
- Serialization errors when checkpointing
- Slow workflow execution as state is passed between nodes
- Multiple agents modifying same fields causing conflicts

**Remediation:**

```python
# GOOD: Organized state with layers
from typing import Annotated
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages

# Layer 1: Shared conversation state
class ConversationState(TypedDict):
    messages: Annotated[list, add_messages]
    conversation_id: str
    conversation_summary: str  # Periodic summary to prevent overflow

# Layer 2: Task-specific state (separate channels)
class TaskState(TypedDict):
    current_task: str
    task_results: dict
    next_agent: str

# Layer 3: Private channels for agent-specific data
# (not visible in main state, passed only between specific nodes)

# Layer 4: Runtime context for infrastructure (not in state)
from langgraph.types import StreamMode

workflow = StateGraph(ConversationState)

# Pass services via runtime context, not state
def create_workflow(llm_client, db_connection):
    def node_with_context(state):
        # Access via closure, not state
        result = llm_client.generate(...)
        return {"messages": [result]}

    workflow.add_node("process", node_with_context)
    return workflow.compile()
```

**Prevention:**
- Use MessagesState as foundation, extend with minimal fields
- Keep infrastructure (clients, connections) in runtime context
- Use private channels for agent-specific data
- Implement state size monitoring and alerting

---

### Anti-Pattern 1.2: Missing Reducers (Severity: MEDIUM)

**Description:** Not using reducer functions for list/dict fields that should accumulate values.

**Example:**
```python
# BAD: No reducer - last write wins
class AgentState(TypedDict):
    messages: list  # Gets overwritten, not accumulated
    search_results: list  # Same message appears multiple times
```

**Why It's Bad:**
- State overwrites instead of merging
- Duplicate entries when multiple nodes update same field
- Lost data from previous agent executions
- Inconsistent state across workflow

**Detection Methods:**
- Same message appears multiple times in state
- Lost conversation history between agent calls
- State fields reset to empty unexpectedly
- Echo agent pattern works but multi-agent coordination breaks

**Remediation:**

```python
# GOOD: Explicit reducers for accumulation
from typing import Annotated
from langgraph.graph.message import add_messages
import operator

class AgentState(TypedDict):
    # Built-in reducer for messages
    messages: Annotated[list, add_messages]

    # Custom reducer for search results (deduplicate by ID)
    search_results: Annotated[list, lambda x, y: list({r['id']: r for r in x + y}.values())]

    # Use operator.add for simple list concatenation
    task_history: Annotated[list, operator.add]

    # Dict merging reducer
    agent_metrics: Annotated[dict, lambda x, y: {**x, **y}]
```

**Echo Agent Reference:**
The echo agent correctly uses `add_messages` reducer (echo_agent.py:136):
```python
messages: Annotated[list, add_messages]
```

**Prevention:**
- Always use `Annotated[list, add_messages]` for message fields
- Define custom reducers for any accumulating fields
- Test state merging with multiple sequential updates
- Review state definition for any bare list/dict types

---

### Anti-Pattern 1.3: Context Window Overflow (Severity: HIGH)

**Description:** Not managing message history size, leading to token limit errors.

**Example:**
```python
# BAD: Unlimited message accumulation
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    # No trimming, no summarization
```

**Why It's Bad:**
- LLM calls fail with "context length exceeded" errors
- Exponentially increasing costs as conversation grows
- System becomes unusable after 20-50 message exchanges
- Production outages during long user sessions

**Detection Methods:**
- Token limit errors in LangSmith traces
- Response times increasing over conversation length
- LLM API errors: "This model's maximum context length is X tokens"
- Costs growing superlinearly with conversation length

**Remediation:**

```python
# GOOD: Message trimming with summarization
from langgraph.graph import StateGraph
from langchain_core.messages import trim_messages, SystemMessage

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    conversation_summary: str
    message_count: int

def create_workflow():
    workflow = StateGraph(AgentState)

    def trim_and_summarize(state: AgentState) -> AgentState:
        """Trim messages and create summary when threshold reached."""
        messages = state["messages"]
        message_count = len(messages)

        # Threshold: summarize every 40 messages
        if message_count > 40 and message_count % 40 == 0:
            # Create summary of older messages
            old_messages = messages[:-20]  # Keep last 20
            summary = llm.generate(f"Summarize this conversation: {old_messages}")

            # Trim to recent + summary
            trimmed = [SystemMessage(content=f"Previous conversation: {summary}")] + messages[-20:]

            return {
                "messages": trimmed,
                "conversation_summary": summary,
                "message_count": len(trimmed)
            }

        return {"message_count": message_count}

    workflow.add_node("trim", trim_and_summarize)
    return workflow
```

**Alternative: Built-in Trimming**
```python
from langchain_core.messages import trim_messages

def generate_with_trimming(state: AgentState):
    """Generate response with automatic message trimming."""
    messages = state["messages"]

    # Trim to fit token budget
    trimmed = trim_messages(
        messages,
        max_tokens=4000,  # Leave room for response
        strategy="last",  # Keep most recent
        include_system=True  # Preserve system message
    )

    response = llm.invoke(trimmed)
    return {"messages": [response]}
```

**Prevention:**
- Monitor message count and token usage per conversation
- Implement automatic trimming at 80% of model's limit
- Add periodic summarization every 20-40 messages
- Test with long conversations (100+ messages)

---

### Anti-Pattern 1.4: No State Validation (Severity: MEDIUM)

**Description:** Using TypedDict without runtime validation, allowing invalid state.

**Example:**
```python
# BAD: No validation
class AgentState(TypedDict):
    messages: list
    temperature: float  # No bounds checking
    agent_name: str  # No enum validation
```

**Why It's Bad:**
- Wrong types pass through silently
- Invalid values cause cryptic errors later
- Hard to debug - error far from source
- No guarantees about state consistency

**Detection Methods:**
- Cryptic type errors in LLM calls
- "NoneType has no attribute..." errors
- Unexpected state values in logs
- Different behavior in prod vs dev (bad data in prod state)

**Remediation:**

```python
# GOOD: Pydantic validation
from pydantic import BaseModel, Field, validator
from typing import Literal

class AgentState(BaseModel):
    messages: list[dict] = Field(default_factory=list)
    temperature: float = Field(ge=0.0, le=2.0)  # 0.0 to 2.0
    agent_name: Literal["supervisor", "research", "coding", "analysis"]
    conversation_id: str = Field(min_length=1)

    @validator("messages")
    def validate_messages(cls, v):
        """Ensure messages have required fields."""
        for msg in v:
            if "content" not in msg:
                raise ValueError("Message missing 'content' field")
        return v

    @validator("temperature")
    def validate_temperature(cls, v):
        """Warn about extreme temperatures."""
        if v > 1.5:
            print(f"Warning: High temperature {v} may produce erratic results")
        return v

# Use in workflow
workflow = StateGraph(AgentState)
```

**Prevention:**
- Use Pydantic BaseModel for production state
- Add Field constraints for numeric values
- Use Literal types for enums
- Add custom validators for complex rules

---

### Anti-Pattern 1.5: State in Database Connections (Severity: HIGH)

**Description:** Storing non-serializable objects like database connections or LLM clients in state.

**Example:**
```python
# BAD: Services in state
class AgentState(TypedDict):
    messages: list
    llm_client: genai.GenerativeModel  # Non-serializable
    db_connection: psycopg2.connection  # Cannot checkpoint
```

**Why It's Bad:**
- Checkpointing fails (cannot serialize connections)
- State restoration fails (connections invalid after restore)
- Memory leaks (connections not properly closed)
- Concurrency issues (connections not thread-safe)

**Detection Methods:**
- "Cannot pickle object" errors when checkpointing enabled
- Checkpoint writes fail silently
- Restored state missing fields
- Database connection errors after workflow resume

**Remediation:**

```python
# GOOD: Services via closure or dependency injection
import google.generativeai as genai
from backend.services.agents.src.domains.secrets import get_secret

def create_workflow():
    """Create workflow with services in closure."""
    # Initialize services once
    gemini_key = get_secret("GEMINI_API_KEY")
    genai.configure(api_key=gemini_key)
    llm = genai.GenerativeModel("gemini-2.5-flash")

    # State only contains data
    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]
        user_input: str
        response: str

    # Nodes access services via closure
    def generate_response(state: AgentState) -> AgentState:
        # llm available in closure, not state
        response = llm.generate_content(state["user_input"])
        return {"response": response.text}

    workflow = StateGraph(AgentState)
    workflow.add_node("generate", generate_response)
    return workflow.compile()
```

**Prevention:**
- Never put clients, connections, or services in state
- Use closures for service access
- Keep state purely data (serializable)
- Test checkpointing early in development

---

## 2. Coordination Anti-Patterns

### Anti-Pattern 2.1: Supervisor Bottleneck (Severity: HIGH)

**Description:** Routing all decisions through one supervisor agent, causing performance degradation.

**Example:**
```python
# BAD: Single supervisor for 15+ agents
supervisor → agent1 → supervisor → agent2 → supervisor → agent3 ...
```

**Why It's Bad:**
- Performance bottleneck - supervisor must process every step
- Single point of failure - supervisor error halts all work
- High token usage - supervisor in every LangSmith trace
- Slow response times - sequential routing adds latency
- Scaling ceiling - supervisor complexity grows with agent count

**Detection Methods:**
- LangSmith traces show supervisor in 80%+ of steps
- Supervisor node has highest token usage
- Response time increases linearly with workflow complexity
- Supervisor system prompt becomes massive (>2000 tokens)
- Adding agents decreases overall throughput

**Remediation:**

```python
# GOOD: Hierarchical teams for 8+ agents
from langgraph.graph import StateGraph

def create_hierarchical_workflow():
    """Create multi-level supervision for scalability."""

    # Team 1: Research Team (specialized supervisor)
    research_team = StateGraph(AgentState)
    research_team.add_node("research_supervisor", research_supervisor_node)
    research_team.add_node("web_search_agent", web_search_node)
    research_team.add_node("data_agent", data_analysis_node)
    research_team_graph = research_team.compile()

    # Team 2: Development Team (specialized supervisor)
    dev_team = StateGraph(AgentState)
    dev_team.add_node("dev_supervisor", dev_supervisor_node)
    dev_team.add_node("coding_agent", coding_node)
    dev_team.add_node("testing_agent", testing_node)
    dev_team_graph = dev_team.compile()

    # Top-level workflow: Coordinates teams, not individual agents
    top_workflow = StateGraph(AgentState)
    top_workflow.add_node("top_supervisor", top_supervisor_node)
    top_workflow.add_node("research_team", research_team_graph)  # Team as node
    top_workflow.add_node("dev_team", dev_team_graph)  # Team as node

    # Top supervisor only routes between teams
    def route_to_team(state):
        if "research" in state["current_task"]:
            return "research_team"
        elif "coding" in state["current_task"]:
            return "dev_team"
        return END

    top_workflow.add_conditional_edges("top_supervisor", route_to_team)
    return top_workflow.compile()
```

**When to Scale:**
- 3-7 agents: Use simple supervisor pattern
- 8-15 agents: Move to hierarchical teams
- 15+ agents: Add more hierarchy levels or network pattern

**Prevention:**
- Monitor supervisor token usage ratio (should be <30%)
- Add hierarchy at 8+ agents
- Test performance with agent count increases
- Use network pattern for specialized domains

---

### Anti-Pattern 2.2: Unclear Agent Specialization (Severity: MEDIUM)

**Description:** Agents with overlapping or vague responsibilities, causing routing confusion.

**Example:**
```python
# BAD: Overlapping responsibilities
agent1 = "You are a helpful assistant that answers questions."
agent2 = "You are an AI that helps users with their queries."
agent3 = "You provide information to users."
```

**Why It's Bad:**
- Supervisor cannot distinguish between agents
- Routing errors - task sent to wrong agent
- Redundant work - multiple agents attempt same task
- Inconsistent results - different agents, different approaches
- Hard to debug - which agent should have handled this?

**Detection Methods:**
- Routing errors in logs ("wrong agent for task")
- Multiple agents producing similar outputs
- Supervisor frequently reroutes tasks
- Low confidence in routing decisions
- User complaints about inconsistent behavior

**Remediation:**

```python
# GOOD: Clear, distinct specializations
from langchain_core.tools import tool

# Research Agent: Web search and data gathering
research_agent_prompt = """
You are a research specialist. Your ONLY job is:
- Web searches using search tools
- Data gathering from external sources
- Fact-checking information
- Summarizing research findings

You DO NOT:
- Write code
- Perform data analysis
- Make decisions about task execution

When asked to do something outside your role, say:
"That requires the [appropriate agent]. I can only handle research tasks."
"""

# Coding Agent: File operations and code generation
coding_agent_prompt = """
You are a coding specialist. Your ONLY job is:
- Writing code in Python, JavaScript, etc.
- File operations (read, write, edit)
- Code review and refactoring
- Running bash commands

You DO NOT:
- Perform web searches
- Analyze data for insights
- Make high-level decisions

When asked to do something outside your role, escalate to supervisor.
"""

# Analysis Agent: Data analysis and synthesis
analysis_agent_prompt = """
You are a data analysis specialist. Your ONLY job is:
- Statistical analysis of data
- Data visualization
- Pattern identification
- Insight generation

You DO NOT:
- Gather new data (use research agent)
- Write production code (use coding agent)
- Make final decisions (escalate to supervisor)
"""

# Create agents with tools matching their specialization
@tool
def web_search(query: str) -> str:
    """Search the web for information."""
    # Only give this tool to research agent
    pass

research_agent = create_react_agent(
    llm,
    tools=[web_search, read_file],
    state_modifier=research_agent_prompt
)

coding_agent = create_react_agent(
    llm,
    tools=[write_file, run_bash, read_file],
    state_modifier=coding_agent_prompt
)
```

**Prevention:**
- Define agent responsibilities in writing before coding
- Give each agent distinct, non-overlapping tools
- Test routing with edge cases
- Document agent specializations in system prompts
- Monitor routing accuracy in production

---

### Anti-Pattern 2.3: Circular Dependencies (Severity: HIGH)

**Description:** Agent A calls Agent B which calls Agent A, creating infinite loops.

**Example:**
```python
# BAD: Circular routing
def supervisor(state):
    return Command(goto="research_agent")

def research_agent(state):
    return Command(goto="supervisor")

def supervisor(state):
    return Command(goto="research_agent")  # Infinite loop!
```

**Why It's Bad:**
- Infinite loops consume resources until timeout
- Wasted tokens and API costs
- System becomes unresponsive
- Hard to detect - appears as slow execution
- Checkpoints grow unbounded

**Detection Methods:**
- Workflow never reaches END node
- Same agents appearing repeatedly in trace
- Token usage grows linearly with time
- Timeouts or max_iterations errors
- LangSmith trace shows repeated pattern

**Remediation:**

```python
# GOOD: Acyclic workflow with cycle detection
from langgraph.graph import StateGraph, START, END

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    current_task: str
    agent_history: list[str]  # Track agent execution
    iteration_count: int

def create_safe_workflow():
    workflow = StateGraph(AgentState)

    def supervisor_with_cycle_detection(state: AgentState) -> Command:
        """Supervisor with cycle detection."""
        agent_history = state.get("agent_history", [])
        iteration = state.get("iteration_count", 0)

        # Check for cycles (same agent 3x in last 6 steps)
        if len(agent_history) >= 6:
            recent = agent_history[-6:]
            for agent in set(recent):
                if recent.count(agent) >= 3:
                    print(f"CYCLE DETECTED: {agent} called 3x in last 6 steps")
                    return Command(goto="error_handler")

        # Check max iterations
        if iteration >= 50:
            print(f"MAX ITERATIONS: Reached {iteration} iterations")
            return Command(goto="error_handler")

        # Decide next agent
        next_agent = decide_next_agent(state)

        # Update tracking
        return Command(
            goto=next_agent,
            update={
                "agent_history": agent_history + ["supervisor"],
                "iteration_count": iteration + 1
            }
        )

    # Add error handler node
    def error_handler(state: AgentState):
        """Handle cycles and errors."""
        return {
            "messages": [AIMessage(content="Error: Workflow reached max iterations or detected cycle")],
            "response": "Error occurred, please try again"
        }

    workflow.add_node("supervisor", supervisor_with_cycle_detection)
    workflow.add_node("error_handler", error_handler)
    workflow.add_edge("error_handler", END)

    return workflow.compile()
```

**Graph Visualization for Cycle Detection:**
```python
# Visualize workflow to spot cycles
def visualize_workflow(workflow):
    """Generate graph visualization to identify cycles."""
    from IPython.display import Image, display

    graph_image = workflow.get_graph().draw_mermaid_png()
    display(Image(graph_image))

    # Check for cycles programmatically
    graph = workflow.get_graph()
    # Use topological sort - if it fails, there's a cycle
```

**Prevention:**
- Design workflow as DAG (directed acyclic graph) upfront
- Add max_iterations to workflow config
- Track agent history in state
- Visualize graph to identify cycles before runtime
- Add cycle detection in supervisor logic

---

### Anti-Pattern 2.4: No Agent Capability Registry (Severity: MEDIUM)

**Description:** Supervisor doesn't know what each agent can do, leading to routing errors.

**Example:**
```python
# BAD: Supervisor guesses agent capabilities
def supervisor(state):
    task = state["current_task"]
    # Hardcoded, error-prone routing
    if "search" in task:
        return "agent1"  # Hope agent1 can search?
    elif "code" in task:
        return "agent2"  # Hope agent2 can code?
```

**Why It's Bad:**
- Tasks routed to incapable agents
- Agents fail or produce wrong results
- No visibility into agent capabilities
- Hard to add new agents (update routing logic everywhere)
- Can't optimize task allocation

**Detection Methods:**
- Agents responding "I can't do that"
- Tasks rerouted multiple times
- High failure rate on certain task types
- New agents not used even when appropriate

**Remediation:**

```python
# GOOD: Explicit capability registry
from dataclasses import dataclass
from typing import Literal

@dataclass
class AgentCapabilities:
    agent_name: str
    capabilities: list[str]
    tools: list[str]
    specialization: str
    max_load: int
    current_load: int = 0

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    current_task: str
    agent_registry: dict[str, AgentCapabilities]  # Capability registry

def create_agent_registry() -> dict[str, AgentCapabilities]:
    """Create registry of agent capabilities."""
    return {
        "research_agent": AgentCapabilities(
            agent_name="research_agent",
            capabilities=["web_search", "data_gathering", "fact_checking"],
            tools=["search_tool", "read_file"],
            specialization="research",
            max_load=5
        ),
        "coding_agent": AgentCapabilities(
            agent_name="coding_agent",
            capabilities=["code_generation", "file_operations", "bash_commands"],
            tools=["write_file", "run_bash", "read_file"],
            specialization="coding",
            max_load=3
        ),
        "analysis_agent": AgentCapabilities(
            agent_name="analysis_agent",
            capabilities=["data_analysis", "visualization", "pattern_detection"],
            tools=["analyze_data", "create_chart"],
            specialization="analysis",
            max_load=4
        )
    }

def supervisor_with_registry(state: AgentState) -> Command:
    """Supervisor uses registry for intelligent routing."""
    task = state["current_task"]
    registry = state["agent_registry"]

    # Analyze task to determine required capabilities
    required_capabilities = analyze_task_requirements(task)

    # Find agents matching capabilities
    capable_agents = [
        agent for agent in registry.values()
        if any(cap in agent.capabilities for cap in required_capabilities)
        and agent.current_load < agent.max_load
    ]

    if not capable_agents:
        return Command(goto="error_handler", update={
            "error": f"No agent available with capabilities: {required_capabilities}"
        })

    # Select best agent (e.g., lowest load)
    best_agent = min(capable_agents, key=lambda a: a.current_load)

    # Update load
    registry[best_agent.agent_name].current_load += 1

    return Command(
        goto=best_agent.agent_name,
        update={"agent_registry": registry}
    )
```

**Prevention:**
- Create capability registry at workflow initialization
- Update registry when adding/removing agents
- Use registry for all routing decisions
- Monitor capability match rate
- Test routing with all task types

---

## 3. Prompting Anti-Patterns

### Anti-Pattern 3.1: Vague System Prompts (Severity: MEDIUM)

**Description:** System prompts that don't clearly define agent role, responsibilities, or behavior.

**Example:**
```python
# BAD: Vague prompt
system_prompt = "You are a helpful assistant. Answer questions."
```

**Why It's Bad:**
- Agent behavior unpredictable
- No clear boundaries on what agent should/shouldn't do
- Routing ambiguity
- Inconsistent responses to similar queries

**Detection Methods:**
- Agent attempts tasks outside its specialization
- Inconsistent responses to same query
- Supervisor routing errors
- User complaints about off-topic responses

**Remediation:**

```python
# GOOD: Explicit, structured prompt
research_agent_prompt = """
# ROLE
You are a research specialist in a multi-agent system.

# RESPONSIBILITIES
- Perform web searches for information
- Gather data from external sources
- Fact-check claims against reliable sources
- Summarize research findings concisely

# CONSTRAINTS
- DO NOT write code or perform coding tasks
- DO NOT analyze data for insights (use analysis agent)
- DO NOT make decisions about task execution
- If asked to do something outside your role, respond: "That requires [appropriate agent]. I can only handle research tasks."

# TOOLS AVAILABLE
- web_search(query: str): Search the web
- read_file(path: str): Read file contents
- fact_check(claim: str): Verify factual claims

# OUTPUT FORMAT
Provide research findings as:
1. Summary (2-3 sentences)
2. Key findings (bullet points)
3. Sources (list of URLs)
4. Confidence level (High/Medium/Low)

# EXAMPLE
User: "Find information about LangGraph"
Output:
Summary: LangGraph is a framework for building multi-agent systems...
Key Findings:
- Built on top of LangChain
- Uses graph-based orchestration
- Supports checkpointing
Sources:
- https://langchain.com/langgraph
Confidence: High
"""

research_agent = create_react_agent(
    llm,
    tools=[web_search, read_file, fact_check],
    state_modifier=research_agent_prompt
)
```

**Prevention:**
- Use template for all system prompts (role, responsibilities, constraints, tools, format)
- Include examples in prompts
- Test prompts with edge cases
- Version control prompts and A/B test changes

---

### Anti-Pattern 3.2: Missing Few-Shot Examples (Severity: LOW)

**Description:** Not providing examples of desired behavior in system prompts.

**Example:**
```python
# BAD: No examples
prompt = "Extract key information from text."
```

**Why It's Bad:**
- Agent interprets task differently than intended
- Inconsistent output format
- Higher error rate on edge cases

**Detection Methods:**
- Output format varies across runs
- Agent misinterprets task requirements
- High rework rate (outputs need correction)

**Remediation:**

```python
# GOOD: Few-shot examples
prompt = """
Extract key information from text and format as JSON.

# EXAMPLES

Input: "John Smith, age 35, lives in New York and works as an engineer."
Output:
{
  "name": "John Smith",
  "age": 35,
  "location": "New York",
  "occupation": "engineer"
}

Input: "The project deadline is March 15, 2025. Budget: $50,000."
Output:
{
  "deadline": "2025-03-15",
  "budget": 50000,
  "currency": "USD"
}

Input: "No specific information provided."
Output:
{
  "error": "Insufficient information"
}

# YOUR TASK
Extract information from the following text:
{user_input}
"""
```

**Prevention:**
- Include 2-3 examples for each task type
- Cover edge cases in examples
- Show both success and error cases
- Update examples based on observed failures

---

### Anti-Pattern 3.3: Hallucination Propagation (Severity: HIGH)

**Description:** Agent generates false information that downstream agents treat as fact.

**Example:**
```python
# BAD: No verification
research_agent → generates hallucinated fact
  ↓
coding_agent → uses hallucinated fact in code
  ↓
analysis_agent → analyzes based on wrong assumption
```

**Why It's Bad:**
- Errors amplify through agent chain
- Wrong results delivered to user
- Hard to trace error source
- User trust eroded

**Detection Methods:**
- Fact-checking finds contradictions
- User reports incorrect information
- Internal inconsistencies in outputs
- Failed tool calls based on hallucinated data

**Remediation:**

```python
# GOOD: Verification agent pattern
from langchain_core.tools import tool

@tool
def verify_facts(claim: str, sources: list[str]) -> dict:
    """Verify factual claims against sources."""
    # Implementation: Check claim against sources
    return {
        "verified": True/False,
        "confidence": 0.0-1.0,
        "contradictions": []
    }

def create_verification_workflow():
    workflow = StateGraph(AgentState)

    # Primary agent
    workflow.add_node("research_agent", research_node)

    # Verification agent
    def verification_node(state: AgentState):
        """Verify outputs before passing downstream."""
        last_message = state["messages"][-1]
        claims = extract_claims(last_message.content)

        verification_results = []
        for claim in claims:
            result = verify_facts(claim, sources=state.get("sources", []))
            verification_results.append(result)

        # Calculate overall confidence
        avg_confidence = sum(r["confidence"] for r in verification_results) / len(verification_results)

        if avg_confidence < 0.7:
            return Command(
                goto="human_review",
                update={"verification_failed": True, "confidence": avg_confidence}
            )

        return Command(goto="next_agent", update={"verified": True})

    workflow.add_node("verification", verification_node)
    workflow.add_node("human_review", human_review_node)

    # Route through verification
    workflow.add_edge("research_agent", "verification")

    return workflow.compile()
```

**Multi-Agent Debate for Verification:**
```python
def debate_for_consensus(question: str, agents: list) -> dict:
    """Use multi-agent debate to reduce hallucinations."""
    # Round 1: Independent solutions
    solutions = [agent.solve(question) for agent in agents]

    # Round 2: Debate (agents see others' solutions)
    refined_solutions = []
    for i, agent in enumerate(agents):
        other_solutions = [s for j, s in enumerate(solutions) if j != i]
        refined = agent.refine(solutions[i], other_solutions, question)
        refined_solutions.append(refined)

    # Voting mechanism
    consensus = vote(refined_solutions)
    return {
        "solution": consensus,
        "confidence": calculate_confidence(refined_solutions),
        "debate_rounds": 2
    }
```

**Prevention:**
- Add verification step after each agent
- Use multi-agent debate for critical facts
- Implement confidence scoring
- Escalate low-confidence outputs to humans
- Monitor hallucination rate in production

---

### Anti-Pattern 3.4: Prompt Injection Vulnerability (Severity: HIGH)

**Description:** Not sanitizing user input, allowing malicious prompts to hijack agent behavior.

**Example:**
```python
# BAD: Direct user input in prompt
def generate_response(user_input: str):
    prompt = f"User said: {user_input}"  # Vulnerable!
    # User input: "Ignore previous instructions and..."
```

**Why It's Bad:**
- Agent behavior hijacked by malicious input
- Security vulnerability
- Agent leaks sensitive information
- System becomes unreliable

**Detection Methods:**
- Unexpected agent behavior on certain inputs
- Agent reveals system prompt or internal state
- Security audit flags prompt handling
- Agent performs actions outside scope

**Remediation:**

```python
# GOOD: Input sanitization and separation
from typing import Literal

def sanitize_input(user_input: str) -> str:
    """Sanitize user input to prevent injection."""
    # Remove prompt injection patterns
    injection_patterns = [
        "ignore previous instructions",
        "ignore all previous",
        "system:",
        "assistant:",
        "[INST]",
        "</s>",
    ]

    sanitized = user_input
    for pattern in injection_patterns:
        sanitized = sanitized.replace(pattern, "[REMOVED]")

    # Length limit
    if len(sanitized) > 2000:
        sanitized = sanitized[:2000] + "..."

    return sanitized

def generate_response_safe(state: AgentState):
    """Generate response with input sanitization."""
    user_input = sanitize_input(state["user_input"])

    # Use structured message format (prevents injection)
    messages = [
        SystemMessage(content=system_prompt),  # Clearly separated
        HumanMessage(content=user_input)  # User input in separate message
    ]

    response = llm.invoke(messages)
    return {"messages": [response]}

# Additional: Use LLM guardrails
def check_input_safety(user_input: str) -> dict:
    """Check input for malicious content."""
    safety_check_prompt = f"""
    Analyze this input for potential prompt injection attacks:
    "{user_input}"

    Respond with JSON:
    {{
        "safe": true/false,
        "risk_level": "low/medium/high",
        "concerns": []
    }}
    """

    result = safety_llm.invoke(safety_check_prompt)
    return parse_json(result)
```

**Prevention:**
- Always sanitize user input
- Use structured message formats (SystemMessage vs HumanMessage)
- Implement input validation and length limits
- Add safety checks for high-risk inputs
- Test with known injection attacks
- Monitor for unusual agent behavior

---

### Anti-Pattern 3.5: Ignoring Token Limits in Prompts (Severity: MEDIUM)

**Description:** Creating system prompts that consume excessive tokens, leaving little room for conversation.

**Example:**
```python
# BAD: 5000-token system prompt
system_prompt = """
[Extremely long system prompt with:
- 50 examples
- Complete documentation
- Detailed instructions
- Multiple personas
...]
"""  # Uses 5000 tokens, model max is 8000
```

**Why It's Bad:**
- Little room left for conversation
- Frequent token limit errors
- Higher costs
- Slower response times

**Detection Methods:**
- Token limit errors despite short conversations
- System prompt uses >30% of context window
- Increased latency
- High prompt token costs

**Remediation:**

```python
# GOOD: Concise prompts with external context
# System prompt: ~500 tokens (keep it brief)
system_prompt = """
You are a research specialist. Your role:
- Perform web searches
- Gather and verify data
- Summarize findings

Use tools: web_search, read_file, fact_check
Output: Summary, key findings, sources, confidence
"""

# Store detailed examples in vector DB, retrieve as needed
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings

examples_db = Chroma(
    collection_name="agent_examples",
    embedding_function=OpenAIEmbeddings()
)

def get_relevant_examples(task: str, k: int = 2) -> list:
    """Retrieve relevant examples for task."""
    return examples_db.similarity_search(task, k=k)

def generate_with_context(state: AgentState):
    """Generate response with dynamic context."""
    task = state["current_task"]

    # Retrieve only relevant examples
    examples = get_relevant_examples(task, k=2)

    # Build prompt with minimal context
    prompt = f"""
    {system_prompt}

    # RELEVANT EXAMPLES
    {format_examples(examples)}

    # TASK
    {task}
    """

    response = llm.invoke(prompt)
    return {"messages": [response]}
```

**Prevention:**
- Keep system prompts <1000 tokens
- Use RAG for examples and documentation
- Monitor token usage per prompt component
- Test with max token budgets

---

## 4. Error Handling Anti-Patterns

### Anti-Pattern 4.1: Silent Failures (Severity: HIGH)

**Description:** Catching all exceptions without proper handling, causing silent failures.

**Echo Agent Example (echo_agent.py:288-292):**
```python
# BAD: Silent failure in echo agent
except Exception as e:
    error_msg = f"ERROR in echo agent: {str(e)}"
    log_decision(error_msg)
    # Logs error but loses stack trace, hard to debug
    raise  # Re-raises but without context
```

**Why It's Bad:**
- Lost error context and stack traces
- Hard to debug production issues
- Errors discovered late or by users
- No visibility into failure patterns

**Detection Methods:**
- Logs show errors but no stack traces
- User reports issues that don't appear in logs
- LangSmith traces show "no error" but wrong output
- Error rates unknown (failures not counted)

**Remediation:**

```python
# GOOD: Explicit error handling with context
import logging
import traceback
from typing import Optional

logger = logging.getLogger(__name__)

class AgentError(Exception):
    """Base exception for agent errors."""
    pass

class LLMError(AgentError):
    """LLM API errors."""
    pass

class ToolError(AgentError):
    """Tool execution errors."""
    pass

def generate_response_with_error_handling(state: AgentState):
    """Generate response with proper error handling."""
    try:
        messages = state["messages"]
        response = llm.generate_content(messages)
        return {"messages": [AIMessage(content=response.text)]}

    except TimeoutError as e:
        # Specific handling for timeouts
        logger.error(f"LLM timeout after 30s: {e}", exc_info=True)
        raise LLMError(f"LLM request timed out: {e}") from e

    except ValueError as e:
        # Input validation errors
        logger.error(f"Invalid input: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content="Error: Invalid input")],
            "error": str(e)
        }

    except Exception as e:
        # Unexpected errors - log full context
        logger.error(
            f"Unexpected error in generate_response",
            extra={
                "state": state,
                "error_type": type(e).__name__,
                "stack_trace": traceback.format_exc()
            },
            exc_info=True
        )
        raise AgentError(f"Agent failed: {e}") from e

# Add error metrics
from dataclasses import dataclass

@dataclass
class ErrorMetrics:
    error_type: str
    count: int
    last_occurrence: str
    affected_agent: str

error_tracker = {}

def track_error(error: Exception, agent: str):
    """Track error occurrences for monitoring."""
    error_type = type(error).__name__
    if error_type not in error_tracker:
        error_tracker[error_type] = ErrorMetrics(
            error_type=error_type,
            count=0,
            last_occurrence="",
            affected_agent=agent
        )

    error_tracker[error_type].count += 1
    error_tracker[error_type].last_occurrence = datetime.now().isoformat()
```

**Prevention:**
- Catch specific exceptions, not broad Exception
- Always log with exc_info=True for stack traces
- Track error metrics and patterns
- Alert on high error rates
- Test error paths explicitly

---

### Anti-Pattern 4.2: No Retry Strategy (Severity: MEDIUM)

**Description:** Not retrying transient failures, causing unnecessary failures.

**Echo Agent Gap:** No RetryPolicy configured (echo_agent.py:213)

**Example:**
```python
# BAD: No retry
workflow.add_node("generate_response", generate_response_node)
# Network blip → failure, no retry
```

**Why It's Bad:**
- Transient errors cause permanent failures
- Lower reliability than necessary
- User frustration from intermittent issues
- Wasted work (no recovery attempt)

**Detection Methods:**
- Errors that work on second manual attempt
- Network timeout errors
- Rate limit errors
- Intermittent failures at specific times

**Remediation:**

```python
# GOOD: RetryPolicy with exponential backoff
from langgraph.types import RetryPolicy

workflow = StateGraph(AgentState)

# LLM calls - retry transient errors
workflow.add_node(
    "generate_response",
    generate_response_node,
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_interval=1.0,  # Start with 1 second
        backoff_factor=2.0,  # Double each retry
        max_interval=30.0,  # Cap at 30 seconds
        jitter=True,  # Add randomness to prevent thundering herd
        retry_on=Exception  # Or specific exceptions
    )
)

# Critical operations - more aggressive retry
workflow.add_node(
    "validate_output",
    validation_node,
    retry_policy=RetryPolicy(
        max_attempts=5,
        initial_interval=0.5,
        backoff_factor=2.0
    )
)

# Specific exception filtering
def should_retry(exception: Exception) -> bool:
    """Determine if error is retryable."""
    retryable_errors = (
        TimeoutError,
        ConnectionError,
        # Add API-specific errors
    )
    return isinstance(exception, retryable_errors)

workflow.add_node(
    "api_call",
    api_node,
    retry_policy=RetryPolicy(
        max_attempts=3,
        retry_on=should_retry  # Custom retry logic
    )
)
```

**When NOT to Retry:**
```python
# Don't retry on permanent errors
non_retryable_errors = (
    ValueError,  # Invalid input
    PermissionError,  # Auth failure
    KeyError,  # Missing data
)

def should_not_retry(exception: Exception) -> bool:
    return isinstance(exception, non_retryable_errors)
```

**Prevention:**
- Add RetryPolicy to all LLM-calling nodes
- Use exponential backoff with jitter
- Distinguish transient vs permanent errors
- Monitor retry rates
- Test with injected transient failures

---

### Anti-Pattern 4.3: Missing Checkpointing (Severity: HIGH)

**Description:** Running production without state persistence, losing all work on failures.

**Echo Agent Gap:** No checkpointing enabled (echo_agent.py:221)
```python
# BAD: No checkpointing
app = workflow.compile()  # No checkpointer parameter
```

**Why It's Bad:**
- No fault tolerance - failures lose all work
- Cannot resume from interruption
- No human-in-the-loop capability
- Cannot debug state at failure point

**Detection Methods:**
- Workflows restart from beginning after any error
- Long-running workflows vulnerable to timeouts
- Cannot inspect state at failure
- No way to recover partial work

**Remediation:**

```python
# GOOD: PostgreSQL checkpointing for production
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg2.pool import SimpleConnectionPool

# Create connection pool
pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    dsn="postgresql://user:password@localhost:5432/myagents"
)

# Create checkpointer
checkpointer = PostgresSaver(pool)

# Compile with checkpointing
app = workflow.compile(checkpointer=checkpointer)

# Run with thread_id for resumable execution
config = {"configurable": {"thread_id": "conversation-123"}}
result = app.invoke(initial_state, config=config)

# Resume from checkpoint after failure
# Automatically resumes from last successful checkpoint
result = app.invoke({"messages": [HumanMessage("continue")]}, config=config)
```

**Development: SQLite Checkpointing**
```python
# For local development
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
app = workflow.compile(checkpointer=checkpointer)
```

**Checkpoint Inspection:**
```python
# Debug by inspecting checkpoints
def inspect_checkpoint(thread_id: str):
    """Inspect checkpoint state for debugging."""
    config = {"configurable": {"thread_id": thread_id}}

    # Get checkpoint history
    checkpoints = checkpointer.list(config)

    for checkpoint in checkpoints:
        print(f"Checkpoint at step {checkpoint.step}")
        print(f"State: {checkpoint.state}")
        print(f"Next nodes: {checkpoint.next_nodes}")
        if checkpoint.error:
            print(f"Error: {checkpoint.error}")
```

**Prevention:**
- Always enable checkpointing in production
- Use PostgreSQL for production, SQLite for dev
- Test checkpoint resume with injected failures
- Monitor checkpoint write latency
- Use thread_id for all conversations

---

### Anti-Pattern 4.4: Ignoring Pending Writes (Severity: MEDIUM)

**Description:** Not leveraging pending writes feature, causing redundant re-execution.

**Example:**
```python
# BAD: Without checkpointing, all work lost on node failure
supervisor → agent1 ✓ → agent2 ✓ → agent3 ✗ (fails)
# Re-run: supervisor → agent1 (redundant) → agent2 (redundant) → agent3
```

**Why It's Bad:**
- Redundant work on retry (wasted tokens and time)
- Duplicate side effects (if agents call external APIs)
- Higher costs and latency

**Detection Methods:**
- Same agents re-execute after failures
- Increased token usage on retries
- Duplicate external API calls
- Longer recovery times

**Remediation:**

```python
# GOOD: Checkpointing with pending writes (automatic)
from langgraph.checkpoint.postgres import PostgresSaver

# Enable checkpointing
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
app = workflow.compile(checkpointer=checkpointer)

# When node fails, successful siblings preserved automatically
# Example:
# Initial: supervisor → [agent1, agent2, agent3] (parallel)
# agent1 ✓, agent2 ✓, agent3 ✗
# Retry: Only agent3 re-executes, agent1 and agent2 results preserved

# This is automatic when checkpointing is enabled!
```

**Verification:**
```python
def verify_pending_writes():
    """Verify pending writes are preserved."""
    # Inject failure in one node
    def failing_node(state):
        raise Exception("Simulated failure")

    workflow.add_node("failing_node", failing_node)

    # Run workflow
    try:
        result = app.invoke(initial_state, config=config)
    except Exception:
        pass

    # Check checkpoint - pending writes should be present
    checkpoint = checkpointer.get(config)
    assert checkpoint.pending_writes  # Preserved from successful nodes

    # Retry - pending writes applied automatically
    result = app.invoke({"messages": []}, config=config)
```

**Prevention:**
- Enable checkpointing (pending writes automatic)
- Test with injected failures in parallel nodes
- Monitor for redundant executions
- Verify pending writes in checkpoints

---

## 5. Observability Anti-Patterns

### Anti-Pattern 5.1: Unverified LangSmith Setup (Severity: MEDIUM)

**Echo Agent Status:** Basic setup present but "unverified" (echo_agent.py:50-127)

**Example:**
```python
# BAD: Silent failure in LangSmith setup
def setup_langsmith():
    try:
        os.environ["LANGSMITH_API_KEY"] = get_secret("LANGSMITH_API_KEY")
        os.environ["LANGSMITH_TRACING"] = "true"
        # Doesn't verify it actually works
    except:
        pass  # Silent failure, no traces
```

**Why It's Bad:**
- Think you have tracing but you don't
- Production issues can't be debugged
- No visibility into agent behavior
- Waste time looking at empty LangSmith project

**Detection Methods:**
- LangSmith UI shows no traces for recent runs
- LANGSMITH_TRACING environment variable set but no traces
- Errors mentioning "invalid API key" in logs
- Traces appear locally but not in CI/CD

**Remediation:**

```python
# GOOD: Verified LangSmith setup (from echo_agent.py with improvements)
from langsmith import Client
import logging

logger = logging.getLogger(__name__)

def setup_langsmith_verified(strict_mode: bool = False):
    """
    Set up LangSmith with validation and connectivity test.

    Args:
        strict_mode: If True, raise errors. If False, warn and continue.
    """
    try:
        langsmith_key = get_secret("LANGSMITH_API_KEY")

        # Step 1: Validate API key format
        valid_prefixes = ("ls__", "lsv2_")
        is_valid = langsmith_key.startswith(valid_prefixes)

        if not is_valid:
            error_msg = (
                f"Invalid LangSmith API key format. "
                f"Must start with {valid_prefixes}. "
                f"Got: '{langsmith_key[:10]}...'"
            )
            if strict_mode:
                logger.error(f"LANGSMITH SETUP FAILED: {error_msg}")
                raise ValueError(error_msg)
            else:
                logger.warning(f"LANGSMITH WARNING: {error_msg}")
                return False

        # Step 2: Test connectivity
        try:
            client = Client(api_key=langsmith_key)
            _ = client.info  # Test API connection
            logger.info("LANGSMITH: Successfully connected to API")
        except Exception as conn_error:
            error_msg = f"Failed to connect to LangSmith API: {conn_error}"
            if strict_mode:
                logger.error(f"LANGSMITH CONNECTIVITY FAILED: {error_msg}")
                raise
            else:
                logger.warning(f"LANGSMITH CONNECTIVITY WARNING: {error_msg}")
                return False

        # Step 3: Configure environment
        os.environ["LANGSMITH_API_KEY"] = langsmith_key
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_PROJECT"] = "myagents"

        # Step 4: Verify tracing works with test run
        from langsmith import traceable

        @traceable(name="langsmith_test")
        def test_trace():
            return "LangSmith tracing operational"

        test_trace()

        logger.info(
            "LANGSMITH SETUP SUCCESS: "
            f"Tracing enabled for project 'myagents'"
        )
        return True

    except Exception as e:
        error_msg = f"LangSmith setup failed: {e}"
        if strict_mode:
            logger.error(f"LANGSMITH SETUP FAILED: {error_msg}")
            raise
        else:
            logger.warning(f"LANGSMITH SETUP WARNING: {error_msg}")
            return False

# Use in initialization
langsmith_enabled = setup_langsmith_verified(strict_mode=False)
if not langsmith_enabled:
    print("Warning: Running without LangSmith tracing")
```

**Manual Verification:**
1. Run workflow
2. Check LangSmith UI (https://smith.langchain.com)
3. Verify traces appear within 30 seconds
4. Check trace includes all nodes

**Prevention:**
- Test LangSmith setup in CI/CD
- Add connectivity check to health endpoint
- Monitor "traces per hour" metric
- Alert on zero traces for extended period

---

### Anti-Pattern 5.2: Missing Structured Logging (Severity: LOW)

**Echo Agent Issue:** File-based logging without structure (echo_agent.py:28-47)

**Example:**
```python
# BAD: Unstructured logging
def log_decision(message: str):
    with open(log_file, "a") as f:
        f.write(f"{timestamp} | {message}\n")
    # Hard to search, no metadata, no context
```

**Why It's Bad:**
- Can't search by agent, task, or error type
- No correlation IDs for debugging
- Hard to aggregate metrics
- Poor production debugging experience

**Detection Methods:**
- Grep through logs to find issues
- Can't filter by specific agent or task
- No metrics dashboards
- Slow incident response

**Remediation:**

```python
# GOOD: Structured logging with metadata
import structlog
from datetime import datetime

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory()
)

logger = structlog.get_logger()

def log_agent_decision(
    agent_name: str,
    decision: str,
    context: dict,
    level: str = "info"
):
    """
    Log agent decisions with structured metadata.

    Args:
        agent_name: Which agent made decision
        decision: What decision was made
        context: Relevant state and context
        level: Log level (info, warning, error)
    """
    log_func = getattr(logger, level)
    log_func(
        "agent_decision",
        agent_name=agent_name,
        decision=decision,
        context=context,
        timestamp=datetime.now().isoformat()
    )

# Usage in nodes
def supervisor_node(state: AgentState) -> Command:
    selected_agent = decide_next_agent(state)

    log_agent_decision(
        agent_name="supervisor",
        decision=f"route_to_{selected_agent}",
        context={
            "current_task": state["current_task"],
            "available_agents": list(state["agent_registry"].keys()),
            "routing_confidence": 0.85
        }
    )

    return Command(goto=selected_agent)

# Logs output as JSON for easy parsing:
# {
#   "event": "agent_decision",
#   "agent_name": "supervisor",
#   "decision": "route_to_research_agent",
#   "context": {"current_task": "...", ...},
#   "timestamp": "2025-10-24T10:30:00",
#   "level": "info"
# }
```

**Searchable Logs:**
```bash
# Find all supervisor decisions
cat logs.json | jq 'select(.agent_name == "supervisor")'

# Find routing errors
cat logs.json | jq 'select(.event == "agent_decision" and .context.routing_confidence < 0.5)'

# Find errors in last hour
cat logs.json | jq 'select(.level == "error" and .timestamp > "2025-10-24T09:00:00")'
```

**Prevention:**
- Use structlog or python-json-logger
- Log all agent decisions with context
- Include correlation IDs for multi-step workflows
- Send logs to centralized system (ELK, Datadog)

---

### Anti-Pattern 5.3: No Cost Tracking (Severity: MEDIUM)

**Echo Agent Gap:** No token usage or cost tracking (echo_agent.py:196-199)

**Example:**
```python
# BAD: No cost tracking
response = llm.generate_content(conversation)
# Don't know how many tokens used or what it cost
```

**Why It's Bad:**
- Budget overruns discovered too late
- Can't optimize expensive workflows
- No visibility into cost per agent/task
- Can't predict scaling costs

**Detection Methods:**
- Surprise bills from LLM providers
- Don't know which agents/tasks are expensive
- Can't set cost budgets or alerts
- No data for cost optimization

**Remediation:**

```python
# GOOD: Comprehensive cost tracking
from dataclasses import dataclass
from typing import Optional

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class CostMetrics:
    agent_name: str
    task_type: str
    token_usage: TokenUsage
    estimated_cost: float
    timestamp: str

# Pricing (update with actual rates)
GEMINI_PRICING = {
    "gemini-2.5-flash": {
        "input_per_1k": 0.00015,
        "output_per_1k": 0.0006
    }
}

class CostTracker:
    def __init__(self):
        self.metrics: list[CostMetrics] = []

    def calculate_cost(self, model: str, usage: TokenUsage) -> float:
        """Calculate cost for token usage."""
        pricing = GEMINI_PRICING.get(model, {})
        input_cost = (usage.prompt_tokens / 1000) * pricing.get("input_per_1k", 0)
        output_cost = (usage.completion_tokens / 1000) * pricing.get("output_per_1k", 0)
        return input_cost + output_cost

    def track_call(
        self,
        agent_name: str,
        task_type: str,
        model: str,
        usage: TokenUsage
    ):
        """Track individual LLM call cost."""
        cost = self.calculate_cost(model, usage)

        metric = CostMetrics(
            agent_name=agent_name,
            task_type=task_type,
            token_usage=usage,
            estimated_cost=cost,
            timestamp=datetime.now().isoformat()
        )

        self.metrics.append(metric)

        # Log for monitoring
        logger.info(
            "llm_call_cost",
            agent=agent_name,
            task=task_type,
            tokens=usage.total_tokens,
            cost=cost
        )

    def get_summary(self) -> dict:
        """Get cost summary."""
        total_cost = sum(m.estimated_cost for m in self.metrics)
        total_tokens = sum(m.token_usage.total_tokens for m in self.metrics)

        # Cost by agent
        agent_costs = {}
        for metric in self.metrics:
            if metric.agent_name not in agent_costs:
                agent_costs[metric.agent_name] = 0
            agent_costs[metric.agent_name] += metric.estimated_cost

        return {
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "cost_by_agent": agent_costs,
            "call_count": len(self.metrics)
        }

# Use in nodes
cost_tracker = CostTracker()

def generate_response_with_tracking(state: AgentState):
    """Generate response with cost tracking."""
    messages = state["messages"]

    # Count input tokens (approximate)
    input_text = "\n".join(m.content for m in messages)
    prompt_tokens = len(input_text) // 4  # Rough estimate

    response = llm.generate_content(input_text)

    # Count output tokens
    completion_tokens = len(response.text) // 4

    usage = TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens
    )

    # Track cost
    cost_tracker.track_call(
        agent_name="research_agent",
        task_type=state.get("current_task", "unknown"),
        model="gemini-2.5-flash",
        usage=usage
    )

    return {"messages": [AIMessage(content=response.text)]}

# Cost reporting
def report_costs(workflow_id: str):
    """Generate cost report."""
    summary = cost_tracker.get_summary()

    print(f"Workflow {workflow_id} Cost Summary:")
    print(f"Total Cost: ${summary['total_cost']:.4f}")
    print(f"Total Tokens: {summary['total_tokens']}")
    print("\nCost by Agent:")
    for agent, cost in summary['cost_by_agent'].items():
        print(f"  {agent}: ${cost:.4f}")
```

**Budget Alerts:**
```python
def check_budget_alert(threshold: float = 1.0):
    """Alert if cost exceeds threshold."""
    summary = cost_tracker.get_summary()
    if summary["total_cost"] > threshold:
        logger.warning(
            "budget_exceeded",
            total_cost=summary["total_cost"],
            threshold=threshold,
            over_budget=summary["total_cost"] - threshold
        )
        # Trigger alert (email, Slack, PagerDuty, etc.)
```

**Prevention:**
- Track token usage on every LLM call
- Calculate costs using current pricing
- Set budget alerts at 80% and 100%
- Monitor cost trends over time
- Optimize high-cost workflows

---

### Anti-Pattern 5.4: Ignoring Trace Analysis (Severity: HIGH)

**Description:** Not reviewing LangSmith traces to identify bottlenecks and errors.

**Example:**
- LangSmith configured but traces never reviewed
- Production issues with no trace investigation
- Slow workflows without performance analysis

**Why It's Bad:**
- Miss obvious performance bottlenecks
- Can't debug complex multi-agent failures
- No visibility into agent behavior
- Waste observability investment

**Detection Methods:**
- Don't know which agents are slow
- Can't explain why workflows fail
- Performance problems discovered by users
- No data for optimization

**How to Use LangSmith for Debugging:**

**1. Identify Slow Agents:**
```
LangSmith UI → Project → Traces → Sort by duration
- Look for agents with >5 second execution time
- Check if time spent in LLM call or logic
- Identify bottleneck agents
```

**2. Find Routing Errors:**
```
LangSmith UI → Filters → Add "tags:routing_error"
- Look for unexpected agent sequences
- Check supervisor routing decisions
- Identify capability mismatches
```

**3. Analyze Token Usage:**
```
LangSmith UI → Traces → Metrics view
- Total tokens per trace
- Tokens per agent
- Identify expensive agents
- Compare input vs output tokens
```

**4. Debug State Issues:**
```
LangSmith UI → Trace → State tab
- Inspect state at each step
- Verify state updates applied
- Check for missing or corrupted fields
```

**5. Cost Analysis:**
```
LangSmith UI → Project → Usage
- Cost per trace
- Cost trends over time
- Cost by agent type
```

**Common Trace Patterns Indicating Problems:**

**Pattern: Repeated Agent Calls**
```
supervisor → research → supervisor → research → supervisor
```
**Problem:** Circular routing or unclear termination
**Solution:** Add cycle detection, clarify agent responsibilities

**Pattern: High Token Usage**
```
Trace shows 50,000 tokens but task is simple
```
**Problem:** Message history not trimmed
**Solution:** Implement message trimming (see Anti-Pattern 1.3)

**Pattern: Long Execution Time**
```
Trace shows 45 seconds for simple task
```
**Problem:** Sequential execution or slow agent
**Solution:** Parallelize independent tasks, optimize slow agent

**Prevention:**
- Review traces daily for production systems
- Set up dashboards for key metrics
- Alert on anomalous trace patterns
- Use trace data for optimization decisions

---

## 6. Performance Anti-Patterns

### Anti-Pattern 6.1: Sequential When Parallel Works (Severity: MEDIUM)

**Description:** Running independent tasks sequentially instead of in parallel.

**Example:**
```python
# BAD: Sequential execution
supervisor → research_agent (10s) → supervisor → coding_agent (8s) → supervisor
# Total: 18+ seconds
```

**Why It's Bad:**
- Slower execution than necessary
- Poor resource utilization
- User perceives system as slow
- Can't scale to handle load

**Detection Methods:**
- Workflow duration = sum of agent durations
- CPU/GPU underutilized during execution
- Tasks have no dependencies but run sequentially

**Remediation:**

```python
# GOOD: Parallel execution for independent tasks
from langgraph.graph import StateGraph, END

def create_parallel_workflow():
    workflow = StateGraph(AgentState)

    def supervisor_parallel(state: AgentState) -> Command:
        """Route to multiple agents in parallel."""
        task = state["current_task"]

        # Identify independent subtasks
        if requires_both_research_and_coding(task):
            # Fan out to both agents simultaneously
            return [
                Command(goto="research_agent"),
                Command(goto="coding_agent")
            ]

        return Command(goto="single_agent")

    workflow.add_node("supervisor", supervisor_parallel)
    workflow.add_node("research_agent", research_node)
    workflow.add_node("coding_agent", coding_node)
    workflow.add_node("aggregator", aggregate_results)

    # Both agents route to aggregator
    workflow.add_edge("research_agent", "aggregator")
    workflow.add_edge("coding_agent", "aggregator")
    workflow.add_edge("aggregator", END)

    return workflow.compile()

# Aggregator combines parallel results
def aggregate_results(state: AgentState) -> AgentState:
    """Combine results from parallel agents."""
    messages = state["messages"]

    # Last two messages are from parallel agents
    research_result = messages[-2] if len(messages) >= 2 else None
    coding_result = messages[-1] if len(messages) >= 1 else None

    combined = f"""
    Research Findings:
    {research_result.content if research_result else 'N/A'}

    Code Implementation:
    {coding_result.content if coding_result else 'N/A'}
    """

    return {"messages": [AIMessage(content=combined)]}
```

**When to Parallelize:**
- Tasks have no dependencies
- Order of execution doesn't matter
- Results can be aggregated afterward
- Agents don't share mutable state

**Prevention:**
- Analyze task dependencies upfront
- Use parallel edges for independent work
- Monitor agent utilization rates
- Test with parallel execution

---

### Anti-Pattern 6.2: Redundant LLM Calls (Severity: HIGH)

**Description:** Calling LLM multiple times for identical or similar queries.

**Example:**
```python
# BAD: Same query called 3 times
agent1: llm.invoke("What is LangGraph?")  # Response A
agent2: llm.invoke("What is LangGraph?")  # Response A again (wasted)
agent3: llm.invoke("What is LangGraph?")  # Response A again (wasted)
```

**Why It's Bad:**
- Wasted tokens and money
- Slower execution
- Unnecessary API load

**Detection Methods:**
- Cost higher than expected
- Same prompts in multiple traces
- High token usage for simple tasks
- Multiple agents producing identical outputs

**Remediation:**

```python
# GOOD: Caching LLM responses
from functools import lru_cache
import hashlib

class LLMCache:
    def __init__(self, max_size: int = 1000):
        self.cache: dict[str, str] = {}
        self.max_size = max_size

    def _hash_key(self, prompt: str, model: str) -> str:
        """Create cache key from prompt and model."""
        content = f"{model}:{prompt}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, prompt: str, model: str) -> Optional[str]:
        """Get cached response."""
        key = self._hash_key(prompt, model)
        return self.cache.get(key)

    def set(self, prompt: str, model: str, response: str):
        """Cache response."""
        key = self._hash_key(prompt, model)

        # Evict oldest if at capacity
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]

        self.cache[key] = response

# Global cache
llm_cache = LLMCache(max_size=1000)

def generate_with_cache(prompt: str, model: str = "gemini-2.5-flash") -> str:
    """Generate response with caching."""
    # Check cache first
    cached = llm_cache.get(prompt, model)
    if cached:
        logger.info("cache_hit", prompt_hash=hashlib.md5(prompt.encode()).hexdigest()[:8])
        return cached

    # Cache miss - call LLM
    logger.info("cache_miss", prompt_hash=hashlib.md5(prompt.encode()).hexdigest()[:8])
    response = llm.generate_content(prompt)

    # Cache response
    llm_cache.set(prompt, model, response.text)

    return response.text

# Use in nodes
def research_with_cache(state: AgentState):
    """Research with caching."""
    query = state["query"]

    # Check if we've answered this before
    response = generate_with_cache(
        prompt=f"Research: {query}",
        model="gemini-2.5-flash"
    )

    return {"messages": [AIMessage(content=response)]}
```

**Semantic Caching for Similar Queries:**
```python
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma

class SemanticCache:
    def __init__(self, similarity_threshold: float = 0.95):
        self.embeddings = OpenAIEmbeddings()
        self.vectorstore = Chroma(
            collection_name="llm_cache",
            embedding_function=self.embeddings
        )
        self.threshold = similarity_threshold

    def get(self, prompt: str) -> Optional[str]:
        """Get cached response for similar prompt."""
        results = self.vectorstore.similarity_search_with_score(prompt, k=1)

        if results and results[0][1] >= self.threshold:
            cached_doc = results[0][0]
            logger.info(
                "semantic_cache_hit",
                similarity=results[0][1],
                cached_prompt=cached_doc.metadata["prompt"][:50]
            )
            return cached_doc.page_content

        return None

    def set(self, prompt: str, response: str):
        """Cache response with embedding."""
        self.vectorstore.add_texts(
            texts=[response],
            metadatas=[{"prompt": prompt}]
        )
```

**Prevention:**
- Implement caching for common queries
- Use semantic cache for similar queries
- Monitor cache hit rate (target >30%)
- Set appropriate cache TTL
- Clear cache when model updated

---

### Anti-Pattern 6.3: Not Caching Expensive Operations (Severity: MEDIUM)

**Description:** Repeating expensive operations (DB queries, API calls) instead of caching.

**Example:**
```python
# BAD: Query database on every agent call
def research_agent(state):
    # Query DB every time
    data = db.query("SELECT * FROM knowledge_base")
    # ... use data
```

**Why It's Bad:**
- Wasted database resources
- Slower execution
- Unnecessary API calls
- Higher costs

**Remediation:**

```python
# GOOD: Cache expensive operations
from functools import lru_cache
import time

@lru_cache(maxsize=100)
def get_knowledge_base(cache_key: str) -> list:
    """Cache knowledge base queries."""
    logger.info("knowledge_base_query", cache_key=cache_key)
    return db.query("SELECT * FROM knowledge_base")

def research_agent_cached(state):
    """Research with cached DB access."""
    # Cache key based on relevant state
    cache_key = f"kb_{datetime.now().strftime('%Y%m%d')}"  # Daily cache

    knowledge_base = get_knowledge_base(cache_key)
    # ... use cached data

# Time-based cache invalidation
class TTLCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> Optional[any]:
        """Get cached value if not expired."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]  # Expired
        return None

    def set(self, key: str, value: any):
        """Cache value with timestamp."""
        self.cache[key] = (value, time.time())

# Usage
api_cache = TTLCache(ttl_seconds=3600)  # 1 hour TTL

def call_external_api(query: str):
    """Call API with caching."""
    cached = api_cache.get(query)
    if cached:
        return cached

    # Cache miss - call API
    result = external_api.query(query)
    api_cache.set(query, result)
    return result
```

**Prevention:**
- Cache database queries with daily/hourly TTL
- Cache external API calls
- Monitor cache hit rates
- Invalidate cache when data changes

---

### Anti-Pattern 6.4: Over-Prompting (Severity: MEDIUM)

**Description:** Including unnecessary information in prompts, increasing token usage.

**Example:**
```python
# BAD: Massive prompt for simple task
prompt = f"""
{entire_codebase}  # 50,000 tokens

{complete_documentation}  # 10,000 tokens

{full_conversation_history}  # 5,000 tokens

Now answer this simple question: {user_question}
"""
```

**Why It's Bad:**
- Excessive token costs
- Slower execution
- Hit token limits faster
- No accuracy improvement

**Detection Methods:**
- High token usage for simple tasks
- Prompt tokens >> completion tokens
- Slow response times
- Frequent token limit errors

**Remediation:**

```python
# GOOD: Minimal, relevant prompts
def generate_minimal_prompt(query: str, context_limit: int = 2000) -> str:
    """Generate prompt with only relevant context."""

    # Retrieve only relevant docs (RAG)
    relevant_docs = vectorstore.similarity_search(query, k=3)

    # Trim to token limit
    context = ""
    for doc in relevant_docs:
        if len(context) + len(doc.page_content) < context_limit:
            context += doc.page_content + "\n\n"
        else:
            break

    prompt = f"""
    Relevant Context:
    {context}

    Question: {query}

    Answer concisely based on the context above.
    """

    return prompt

# Use RAG instead of full context
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings

# Index codebase/docs once
vectorstore = Chroma.from_documents(
    documents=documents,
    embedding=OpenAIEmbeddings(),
    collection_name="codebase"
)

def answer_with_rag(query: str):
    """Answer query with RAG (not full context)."""
    # Retrieve only relevant chunks
    relevant = vectorstore.similarity_search(query, k=3)

    prompt = f"""
    Context: {relevant[0].page_content}

    Question: {query}
    """

    # Much smaller prompt, same accuracy
    return llm.invoke(prompt)
```

**Prevention:**
- Use RAG to retrieve only relevant context
- Set prompt token budgets
- Monitor prompt/completion token ratio
- Remove redundant information from prompts

---

## 7. How to Debug Using LangSmith

### Setting Up LangSmith for Your Project

**Step 1: Get API Key**
```bash
# Sign up at https://smith.langchain.com
# Create API key: Settings → API Keys → Create API Key
```

**Step 2: Configure Environment**
```python
import os
from langsmith import Client

os.environ["LANGSMITH_API_KEY"] = "ls__your_key_here"
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "myagents"

# Verify connection
client = Client()
print(client.info)  # Should succeed
```

**Step 3: Add Tracing to Workflow**
```python
from langsmith import traceable

@traceable(name="workflow_run")
def run_workflow(user_input: str):
    result = workflow.invoke({"user_input": user_input})
    return result
```

### Reading Trace Analysis

**Trace Overview:**
- Duration: Total time from start to end
- Token Usage: Input/output tokens per node
- Cost: Estimated cost based on token usage
- Status: Success/error
- Metadata: Model, temperature, etc.

**Trace Timeline:**
1. Click on trace to open detail view
2. Timeline shows node execution order
3. Hover over nodes for duration
4. Click nodes to see input/output

**State Inspection:**
1. Click "State" tab in trace
2. See state at each step
3. Verify state updates
4. Check for corrupted fields

### Identifying Bottlenecks from Traces

**Performance Bottlenecks:**

**1. Slow Nodes**
```
LangSmith → Traces → Sort by duration
Look for: Nodes with >5s execution time
Action: Optimize slow node or parallelize
```

**2. Sequential Execution**
```
Timeline shows: agent1 → agent2 → agent3 (sequential)
Check if: Tasks are independent
Action: Use parallel edges
```

**3. Large State**
```
State tab shows: State size >50KB
Look for: Unbounded lists, large objects
Action: Implement state trimming
```

**4. Token Bloat**
```
Metrics show: 50,000 prompt tokens for simple task
Look for: Full conversation history in every call
Action: Implement message trimming (Anti-Pattern 1.3)
```

### Cost Analysis Per Agent

**View Costs:**
```
LangSmith → Project → Usage
- Cost per trace
- Cost by date range
- Cost trends
```

**Agent Cost Breakdown:**
```python
# In trace detail view
# Click "Metrics" tab
# See breakdown:
# - supervisor_node: $0.05
# - research_agent: $0.15
# - coding_agent: $0.10
# Total: $0.30
```

**Optimize High-Cost Agents:**
1. Identify most expensive agent
2. Check token usage (prompt vs completion)
3. Reduce prompt size with RAG
4. Implement caching for common queries

### Example: Debugging echo_agent.py with Traces

**Scenario:** Echo agent slow for some inputs

**Step 1: Find Slow Traces**
```
LangSmith → Project "myagents" → Filter by duration >5s
```

**Step 2: Examine Slow Trace**
```
- Click on slow trace
- Timeline shows:
  - process_input_node: 0.1s ✓
  - generate_response_node: 8.5s ✗ (BOTTLENECK)
```

**Step 3: Inspect Node**
```
- Click generate_response_node
- Check input:
  - Prompt tokens: 4,500 (high)
  - Conversation history: 30 messages (not trimmed)
```

**Step 4: Fix**
```python
# Add message trimming before LLM call
from langchain_core.messages import trim_messages

def generate_response(state: AgentState):
    messages = state["messages"]

    # Trim to last 10 messages
    trimmed = trim_messages(messages, max_tokens=2000, strategy="last")

    response = llm.generate_content(trimmed)
    return {"messages": [response]}
```

**Step 5: Verify Fix**
```
- Run workflow again
- Check new trace:
  - generate_response_node: 1.2s ✓ (7x faster)
  - Prompt tokens: 800 (5.6x reduction)
```

### Common Trace Patterns That Indicate Problems

**Pattern 1: Repeated Agent in Sequence**
```
Trace shows: supervisor → research → supervisor → research → supervisor
Problem: Circular routing or unclear termination
Fix: Add cycle detection, clarify END condition
```

**Pattern 2: High Token Low Output**
```
Trace shows: 10,000 prompt tokens, 50 completion tokens
Problem: Over-prompting (Anti-Pattern 6.4)
Fix: Use RAG, trim context
```

**Pattern 3: Same Node Multiple Times**
```
Trace shows: validation_node called 5 times
Problem: Failing validation, retry loop
Fix: Check validation logic, add max retries
```

**Pattern 4: Long Gaps Between Nodes**
```
Timeline shows: 3s gap between node completion and next start
Problem: State serialization overhead or checkpointing latency
Fix: Optimize state size, check checkpoint backend
```

**Pattern 5: No Traces for Failed Run**
```
User reports error but no trace in LangSmith
Problem: Tracing not enabled or setup failed
Fix: Verify LangSmith setup (Anti-Pattern 5.1)
```

---

## 8. How to Debug Using Logs

### Structured Logging Best Practices

**Use Structured Logging Library:**
```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory()
)

logger = structlog.get_logger()
```

**Log Structure:**
```python
logger.info(
    "event_name",
    # Required fields
    agent_name="supervisor",
    event_type="routing_decision",
    timestamp="2025-10-24T10:30:00",

    # Context fields
    conversation_id="conv-123",
    user_id="user-456",

    # Event-specific fields
    selected_agent="research_agent",
    confidence=0.85,
    reasoning="Task requires web search capability"
)
```

### What to Log (State Transitions, Decisions, Errors)

**1. State Transitions**
```python
def supervisor_node(state: AgentState) -> Command:
    logger.info(
        "state_transition",
        from_node="supervisor",
        to_node="research_agent",
        current_state=state["current_task"],
        state_size=len(str(state))
    )
    return Command(goto="research_agent")
```

**2. Agent Decisions**
```python
def decide_next_agent(state: AgentState) -> str:
    decision = make_routing_decision(state)

    logger.info(
        "routing_decision",
        agent="supervisor",
        selected_agent=decision["agent"],
        confidence=decision["confidence"],
        task=state["current_task"],
        alternatives=decision["other_options"]
    )

    return decision["agent"]
```

**3. Errors**
```python
try:
    result = llm.invoke(prompt)
except Exception as e:
    logger.error(
        "llm_call_failed",
        agent="research_agent",
        error_type=type(e).__name__,
        error_message=str(e),
        prompt_length=len(prompt),
        retry_count=retry_count,
        exc_info=True  # Include stack trace
    )
    raise
```

**4. Performance Metrics**
```python
import time

start = time.time()
result = expensive_operation()
duration = time.time() - start

logger.info(
    "operation_completed",
    operation="vector_search",
    duration_seconds=duration,
    result_count=len(result),
    query=query
)

if duration > 5.0:
    logger.warning(
        "slow_operation",
        operation="vector_search",
        duration_seconds=duration,
        threshold=5.0
    )
```

### What NOT to Log (Sensitive Data, Full Prompts)

**DON'T Log:**

**1. User Sensitive Data**
```python
# BAD
logger.info("user_query", email=user.email, ssn=user.ssn)

# GOOD
logger.info("user_query", user_id=hash(user.id))
```

**2. Full Prompts (Too Large)**
```python
# BAD
logger.info("llm_call", prompt=full_prompt)  # 5000 tokens

# GOOD
logger.info("llm_call", prompt_length=len(full_prompt), prompt_preview=full_prompt[:100])
```

**3. API Keys or Secrets**
```python
# BAD
logger.info("api_call", api_key=api_key)

# GOOD
logger.info("api_call", api_key_hash=hash(api_key))
```

**4. Full State Objects**
```python
# BAD
logger.info("state_update", state=state)  # Massive object

# GOOD
logger.info("state_update", state_keys=list(state.keys()), message_count=len(state["messages"]))
```

### Log Analysis Techniques

**1. Grep for Specific Events**
```bash
# Find all routing decisions
cat logs.json | jq 'select(.event == "routing_decision")'

# Find errors
cat logs.json | jq 'select(.level == "error")'

# Find slow operations
cat logs.json | jq 'select(.duration_seconds > 5.0)'
```

**2. Count Event Frequencies**
```bash
# Most common errors
cat logs.json | jq -r 'select(.level == "error") | .error_type' | sort | uniq -c | sort -rn

# Most used agents
cat logs.json | jq -r 'select(.event == "routing_decision") | .selected_agent' | sort | uniq -c | sort -rn
```

**3. Trace Conversation Flow**
```bash
# All events for conversation
cat logs.json | jq 'select(.conversation_id == "conv-123")' | jq -r '[.timestamp, .event, .agent_name] | @tsv'
```

**4. Performance Analysis**
```bash
# Average duration by operation
cat logs.json | jq -r 'select(.operation) | [.operation, .duration_seconds] | @tsv' | awk '{sum[$1]+=$2; count[$1]++} END {for (op in sum) print op, sum[op]/count[op]}'
```

**5. Error Rate Over Time**
```bash
# Error count per hour
cat logs.json | jq -r 'select(.level == "error") | .timestamp[:13]' | sort | uniq -c
```

### Example from echo_agent.py:50-127

**Current Logging in echo_agent.py:**
```python
def log_decision(message: str):
    """Log agent decisions to file with timestamp."""
    timestamp = datetime.now().isoformat()
    with open(log_path, "a") as f:
        f.write(f"{timestamp} | {message}\n")
```

**Problems:**
- Unstructured (hard to parse)
- No event types or metadata
- Can't filter by agent or error type
- File-based (not scalable)

**Improved Logging:**
```python
import structlog

logger = structlog.get_logger()

# Replace log_decision calls:

# Before:
log_decision(f"Processing input: {user_input[:50]}...")

# After:
logger.info(
    "input_processing",
    user_input_length=len(user_input),
    user_input_preview=user_input[:50]
)

# Before:
log_decision(f"LANGSMITH SETUP FAILED: {error_msg}")

# After:
logger.error(
    "langsmith_setup_failed",
    error_message=error_msg,
    strict_mode=LANGSMITH_STRICT_MODE
)

# Before:
log_decision(f"Generating response using LLM (message count: {len(messages)})")

# After:
logger.info(
    "llm_generation_start",
    agent="echo_agent",
    message_count=len(messages),
    model=GEMINI_MODEL
)
```

**Benefit:**
- Structured JSON logs
- Easy to parse and analyze
- Filterable by event type
- Includes relevant context
- Can send to log aggregation service

---

## 9. Prevention Checklist

### Pre-Development

**Clear Agent Specializations Defined**
- [ ] Each agent has written role description
- [ ] Agent responsibilities don't overlap
- [ ] Agent tools match their specialization
- [ ] Routing criteria defined upfront

**State Schema Designed with Reducers**
- [ ] State uses MessagesState as foundation
- [ ] All list fields have reducers (add_messages, operator.add)
- [ ] No non-serializable objects in state (clients, connections)
- [ ] State size estimated (target <50KB)

**Error Handling Strategy Planned**
- [ ] RetryPolicy planned for each node
- [ ] Checkpointing backend selected (PostgreSQL for prod)
- [ ] Error escalation thresholds defined
- [ ] Human-in-the-loop triggers identified

**Observability Setup Verified**
- [ ] LangSmith API key validated
- [ ] Connectivity test passed
- [ ] Traces visible in UI
- [ ] Structured logging library configured (structlog)

### During Development

**System Prompts Tested with Examples**
- [ ] Each prompt includes role, responsibilities, constraints
- [ ] Prompts include 2-3 few-shot examples
- [ ] Prompts tested with edge cases
- [ ] Prompt token budget set (<1000 tokens)

**State Size Monitored**
- [ ] Message trimming implemented (every 40 messages)
- [ ] State size logged on each update
- [ ] Alert set for state >50KB
- [ ] Tested with long conversations (100+ messages)

**RetryPolicy Configured**
- [ ] All LLM-calling nodes have RetryPolicy
- [ ] Exponential backoff with jitter enabled
- [ ] Transient vs permanent errors distinguished
- [ ] Max attempts set appropriately (3-5)

**LangSmith Traces Reviewed**
- [ ] Traces visible for all test runs
- [ ] Agent execution order verified
- [ ] Token usage per agent checked
- [ ] No silent failures in traces

### Pre-Production

**All Error Paths Tested**
- [ ] Injected LLM API failures
- [ ] Injected network timeouts
- [ ] Tested checkpoint resume from failure
- [ ] Verified error messages to users

**Cost Projections Calculated**
- [ ] Token usage measured for typical workflows
- [ ] Cost per conversation estimated
- [ ] Budget alerts configured (80% and 100%)
- [ ] Cost tracking implemented in code

**Checkpointing Tested**
- [ ] Checkpoint write/read verified
- [ ] Resume from failure tested
- [ ] Pending writes preserved on node failure
- [ ] Checkpoint backend performance acceptable (<100ms writes)

**Load Testing Completed**
- [ ] Tested with 10+ concurrent conversations
- [ ] Verified performance at scale (15+ agents)
- [ ] Measured throughput (target >10 requests/min)
- [ ] Identified bottlenecks and optimized

**Monitoring Alerts Configured**
- [ ] Error rate alert (>5% in 5 min)
- [ ] Latency alert (>10s avg in 5 min)
- [ ] Cost alert (80% of budget)
- [ ] Zero traces alert (>30 min without trace)

---

## Conclusion

This anti-patterns guide catalogs 40+ common mistakes in multi-agent systems with detection methods and remediation strategies. Key themes:

**State Management:** Keep state minimal, use reducers, trim messages, never store services in state.

**Coordination:** Start simple (supervisor), scale to hierarchical, avoid circular routing, maintain capability registry.

**Prompting:** Be explicit, include examples, verify facts, sanitize input, keep prompts concise.

**Error Handling:** Retry transient failures, use checkpointing, never fail silently, escalate to humans.

**Observability:** Verify LangSmith works, use structured logging, track costs, analyze traces regularly.

**Performance:** Parallelize independent work, cache expensive operations, minimize prompt tokens, monitor bottlenecks.

**Prevention:** Use the checklists in Section 9 at each stage of development. Review this guide during code reviews and when debugging production issues.

**Next Steps:**
1. Audit your current codebase against this guide
2. Fix high-severity anti-patterns first
3. Add detection monitoring for common issues
4. Use prevention checklist for new features
5. Share this guide with your team

**Resources:**
- LangGraph Documentation: https://langchain.com/langgraph
- LangSmith Tracing: https://smith.langchain.com
- Recommendations Report: /docs/research/recommendations_report.md
- Implementation Patterns: /docs/research/consolidated/langgraph_implementation_patterns.md
