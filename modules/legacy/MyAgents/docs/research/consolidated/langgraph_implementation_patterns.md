# LangGraph Implementation Patterns: Comprehensive Reference Guide

**Version:** 1.0
**Created:** 2025-10-24
**Purpose:** Definitive reference for implementing LangGraph-based multi-agent systems
**Target Audience:** Developers building production LangGraph applications
**Document Length:** 2000-3000 lines

---

## Table of Contents

1. [Overview](#1-overview)
2. [State Management](#2-state-management)
3. [Agent Coordination Patterns](#3-agent-coordination-patterns)
4. [Error Handling and Reliability](#4-error-handling-and-reliability)
5. [Observability](#5-observability)
6. [Advanced Patterns](#6-advanced-patterns)
7. [Implementation Guide](#7-implementation-guide)
8. [Decision Matrix](#8-decision-matrix)
9. [References](#9-references)

---

## 1. Overview

### 1.1 What is LangGraph?

LangGraph is a framework for building stateful, multi-agent applications using large language models (LLMs). Built on the principles of Google's Pregel framework, LangGraph provides a graph-based architecture where:

- **Nodes do the work** - Execute agent logic, call LLMs, run tools
- **Edges tell what to do next** - Define control flow between nodes
- **State flows through the graph** - Explicit state management with custom reducers

**Key Principle:** Execution proceeds in discrete "super-steps" where nodes process messages and vote to halt when no incoming messages remain.

**Official Documentation:** https://langchain-ai.github.io/langgraph/

### 1.2 Why Use LangGraph?

**Strengths:**
- **Explicit Control Flow:** Graph-based orchestration makes workflows visible and debuggable
- **Sophisticated State Management:** TypedDict/Pydantic schemas with custom reducers
- **Built-in Fault Tolerance:** Checkpoint-driven persistence and pending writes mechanism
- **Production-Ready:** RetryPolicy, breakpoints, LangSmith integration
- **Composability:** Subgraph composition enables complex systems from simple components

**When to Choose LangGraph:**
- Need explicit control over agent coordination
- Require checkpoint-based fault tolerance
- Building production systems with observability requirements
- Want visual debugging and execution tracing
- Need to compose multi-level agent hierarchies

### 1.3 When to Use LangGraph vs Other Frameworks

**LangGraph vs AutoGen:**
- LangGraph: Explicit graph-based control flow, visual debugging
- AutoGen: Conversational patterns, flexible human-in-the-loop modes
- **Choose LangGraph if:** You need explicit control and visual workflows
- **Choose AutoGen if:** Conversation-first patterns fit your use case

**LangGraph vs CrewAI:**
- LangGraph: Low-level control, composable graphs
- CrewAI: High-level crews, YAML configuration
- **Choose LangGraph if:** You need fine-grained control and customization
- **Choose CrewAI if:** Rapid prototyping with role-based teams

**LangGraph vs MetaGPT:**
- LangGraph: General-purpose multi-agent orchestration
- MetaGPT: Software development specific (PRD, design, code)
- **Choose LangGraph if:** General workflows beyond software development
- **Choose MetaGPT if:** Simulating software company processes

**LangGraph vs Semantic Kernel:**
- LangGraph: Python-first, LangChain ecosystem
- Semantic Kernel: C#/.NET, Microsoft ecosystem
- **Choose LangGraph if:** Python development, LangChain integration
- **Choose Semantic Kernel if:** .NET development, Microsoft AI stack

### 1.4 Core Concepts and Terminology

**StateGraph:**
- Primary graph class parameterized by user-defined State objects
- Foundation for all LangGraph workflows
- Supports TypedDict, dataclass, Pydantic BaseModel

**Nodes:**
- Functions that execute work (LLM calls, tool execution, data processing)
- Receive state as input, return state updates
- Signature: `def node_fn(state: StateType) -> StateType | dict`

**Edges:**
- Define control flow between nodes
- Types: Direct edges, conditional edges, normal edges
- Enable sequential, parallel, and conditional execution

**State:**
- Data structure flowing through the graph
- Defined using TypedDict or Pydantic for validation
- Supports custom reducers for sophisticated update semantics

**Reducers:**
- Functions that control how state updates are merged
- Specified via Python's `Annotated` type
- Built-in: `add_messages`, `add`, custom reducers

**Checkpoints:**
- Automatic state snapshots at every super-step
- Enable fault tolerance and resumption
- Store state, configuration, next nodes, error information

**Command Objects:**
- Unified control flow for dynamic routing
- Signature: `Command(goto=target, update=state_updates, graph=Command.PARENT)`
- Enable multi-level graph navigation

**MessagesState:**
- Prebuilt state for message-based workflows
- Includes `add_messages` reducer for conversation history
- Commonly subclassed for domain-specific fields

### 1.5 Official Documentation Links

**Core Documentation:**
- LangGraph Docs: https://langchain-ai.github.io/langgraph/
- Concepts: https://langchain-ai.github.io/langgraph/concepts/
- Tutorials: https://langchain-ai.github.io/langgraph/tutorials/

**Multi-Agent Patterns:**
- Agent Supervisor: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/
- Multi-Agent Collaboration: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/multi-agent-collaboration/
- Hierarchical Teams: https://langchain-ai.github.io/langgraph/concepts/multi_agent/#hierarchical

**State Management:**
- State Concept: https://langchain-ai.github.io/langgraph/concepts/low_level/#state
- Reducers: https://langchain-ai.github.io/langgraph/concepts/low_level/#reducers
- MessagesState: https://langchain-ai.github.io/langgraph/reference/graphs/#messagesstate

**Error Handling:**
- RetryPolicy: https://langchain-ai.github.io/langgraph/reference/types/#retrypolicy
- Checkpointing: https://langchain-ai.github.io/langgraph/concepts/persistence/
- Breakpoints: https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/

**Advanced:**
- Subgraphs: https://langchain-ai.github.io/langgraph/concepts/multi_agent/#hierarchical
- LangSmith: https://docs.smith.langchain.com/

---

## 2. State Management

### 2.1 StateGraph Basics

**Core Concept:** StateGraph is parameterized by a user-defined State object that defines the data flowing through your workflow.

**State Definition Options:**

**Option 1: TypedDict (Lightweight)**
```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, add_messages

class AgentState(TypedDict):
    """Lightweight state using TypedDict."""
    messages: Annotated[list, add_messages]
    user_input: str
    response: str
```

**When to use:**
- Rapid prototyping
- Simple state structures
- No validation requirements

**Option 2: Pydantic BaseModel (Validated)**
```python
from pydantic import BaseModel, Field
from typing import Annotated
from langgraph.graph import add_messages

class AgentState(BaseModel):
    """Validated state using Pydantic."""
    messages: Annotated[list, add_messages] = Field(default_factory=list)
    user_input: str = Field(..., min_length=1, max_length=10000)
    response: str = Field(default="")
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
```

**When to use:**
- Production applications
- Need runtime validation
- Complex state with constraints
- API integration requiring validated schemas

**Option 3: Dataclass (Standard Python)**
```python
from dataclasses import dataclass, field
from typing import Annotated
from langgraph.graph import add_messages

@dataclass
class AgentState:
    """State using Python dataclass."""
    messages: Annotated[list, add_messages] = field(default_factory=list)
    user_input: str = ""
    response: str = ""
```

**When to use:**
- Standard Python approach
- Simple defaults
- No external dependencies (Pydantic)

**Echo Agent Example:**
```python
# From echo_agent.py:134-138
class AgentState(TypedDict):
    """State structure for the echo agent."""
    messages: Annotated[list, add_messages]
    user_input: str
    response: str
```

### 2.2 Annotated Types and Reducers

**Core Concept:** Reducers control how state updates are merged when multiple nodes update the same field.

**Default Behavior (No Reducer):**
```python
class State(TypedDict):
    count: int  # Updates override existing value

# Node 1 returns {"count": 5}
# Node 2 returns {"count": 10}
# Result: {"count": 10}  # Overwritten
```

**Built-in Reducers:**

**`add_messages` - Message History**
```python
from langgraph.graph import add_messages
from typing import Annotated

class State(TypedDict):
    messages: Annotated[list, add_messages]

# Automatically:
# - Serializes/deserializes between dict and Message objects
# - Tracks message IDs for proper updates
# - Deduplicates messages
# - Appends new messages to existing list
```

**`add` - List Concatenation**
```python
from langgraph.graph import add
from typing import Annotated

class State(TypedDict):
    items: Annotated[list[str], add]

# Node 1 returns {"items": ["a", "b"]}
# Node 2 returns {"items": ["c", "d"]}
# Result: {"items": ["a", "b", "c", "d"]}  # Concatenated
```

**`operator.add` - Numeric Addition**
```python
import operator
from typing import Annotated

class State(TypedDict):
    total: Annotated[int, operator.add]

# Node 1 returns {"total": 5}
# Node 2 returns {"total": 10}
# Result: {"total": 15}  # Added together
```

**Custom Reducers:**
```python
def merge_dicts(existing: dict, new: dict) -> dict:
    """Custom reducer that deep merges dictionaries."""
    result = existing.copy()
    for key, value in new.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result

class State(TypedDict):
    config: Annotated[dict, merge_dicts]
```

**Reducer Best Practices:**
1. **Use `add_messages` for conversation history** - Standard pattern for chat agents
2. **Use `add` for accumulating lists** - Task results, logs, events
3. **Use `operator.add` for counters** - Metrics, token counts
4. **Create custom reducers for complex merge logic** - Configuration, nested structures

**Echo Agent Example:**
```python
# From echo_agent.py:136
messages: Annotated[list, add_messages]

# This enables:
# - Automatic message accumulation
# - Proper HumanMessage/AIMessage handling
# - Message ID tracking
```

### 2.3 MessagesState Pattern

**Core Concept:** MessagesState is a prebuilt state designed for message-based workflows, commonly used as a foundation for multi-agent coordination.

**Definition:**
```python
from langgraph.graph import MessagesState

class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]
```

**Subclassing for Domain-Specific Fields:**
```python
from langgraph.graph import MessagesState

class CustomAgentState(MessagesState):
    """Extend MessagesState with domain fields."""
    user_input: str
    response: str
    current_task: str
    agent_capabilities: dict[str, list[str]]
    task_results: list[dict]
```

**Common Pattern in Multi-Agent Systems:**
```python
from langgraph.graph import MessagesState
from typing import Annotated

class SupervisorState(MessagesState):
    """State for supervisor coordinating multiple agents."""
    # Inherited: messages

    # Supervisor-specific fields
    current_agent: str
    task_queue: list[str]
    completed_tasks: list[dict]
    agent_capabilities: dict[str, list[str]]
```

**Why MessagesState is Important:**
- **Standardized communication** - All agents use same message format
- **Automatic history** - Conversation accumulates without manual tracking
- **LangChain compatibility** - Works with LangChain message types
- **Visibility** - Complete reasoning history visible to supervisor

**Trade-offs:**
- **Context bloat** - Full history sharing can create large context
- **No privacy** - All agents see all messages
- **Token costs** - Large message history consumes tokens

**Solutions:**
- Use ChatHistoryReducer for summarization
- Implement private channels for sensitive data
- Periodic message history compression

### 2.4 Checkpointing and Persistence

**Core Concept:** LangGraph saves a checkpoint of the graph state at every super-step, enabling fault tolerance and resumption.

**Checkpoint Contents:**
- Current state values
- Configuration metadata
- Information about next nodes to execute
- Task details including error states

**Supported Backends:**

**In-Memory (Development/Testing)**
```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# Pros: Fast, no dependencies
# Cons: Lost on process restart
# Use for: Testing, development
```

**SQLite (Local Persistence)**
```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
app = workflow.compile(checkpointer=checkpointer)

# Pros: Persistent, file-based, no server
# Cons: Single-process, not for production scale
# Use for: Local development, demos
```

**PostgreSQL (Production)**
```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:password@host:5432/dbname"
)
app = workflow.compile(checkpointer=checkpointer)

# Pros: Production-ready, multi-process, durable
# Cons: Requires PostgreSQL server
# Use for: Production deployments
```

**Checkpoint Benefits:**
1. **Fault Tolerance** - Resume from last successful step
2. **State Inspection** - Debug execution at any point
3. **Time Travel** - Replay execution from checkpoints
4. **Error Recovery** - Graceful handling of partial failures

**Example: Resume After Failure**
```python
# Initial run fails at step 3
initial_state = {"messages": [], "user_input": "complex task"}
config = {"configurable": {"thread_id": "user-123"}}

try:
    result = app.invoke(initial_state, config=config)
except Exception as e:
    print(f"Failed: {e}")

# Fix issue and resume from last checkpoint
result = app.invoke(None, config=config)  # Resumes from checkpoint
```

**Echo Agent Gap:**
```python
# From echo_agent.py:221
app = workflow.compile()  # No checkpointer

# Should be:
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))
app = workflow.compile(checkpointer=checkpointer)
```

### 2.5 Pending Writes and Interrupts

**Core Concept:** When a graph node fails mid-execution at a given superstep, LangGraph stores pending checkpoint writes from any other nodes that completed successfully.

**How Pending Writes Work:**

```python
# Workflow with 3 parallel nodes
workflow.add_node("research", research_node)
workflow.add_node("analysis", analysis_node)
workflow.add_node("synthesis", synthesis_node)

# Execution scenario:
# 1. research_node completes successfully ✓
# 2. analysis_node completes successfully ✓
# 3. synthesis_node fails ✗

# LangGraph behavior:
# - Stores "pending writes" from research and analysis
# - On retry, only re-executes synthesis_node
# - research and analysis outputs are preserved
```

**Benefits:**
- **Efficiency** - No redundant re-execution of successful nodes
- **Cost Savings** - Avoid re-running expensive LLM calls
- **Consistency** - Partial progress preserved

**Interrupts for Human-in-the-Loop:**
```python
# Set breakpoint before critical operation
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["critical_decision", "file_modification"]
)

# Execution pauses at breakpoint
result = app.invoke(initial_state, config=config)

# Inspect state
current_state = app.get_state(config)
print(current_state.values)

# Modify state if needed
app.update_state(config, {"confidence": 0.9})

# Resume execution
result = app.invoke(None, config=config)
```

**Use Cases:**
- Manual approval workflows
- Low-confidence decision review
- Debugging complex failures
- Compliance requirements (human oversight)

### 2.6 State Schema Patterns

**Pattern 1: Internal State Channels (Full Visibility)**
```python
class AgentState(TypedDict):
    """All fields visible to all nodes."""
    messages: Annotated[list, add_messages]
    user_input: str
    intermediate_results: list[dict]
    final_response: str
```

**When to use:** Simple workflows, no privacy requirements

**Pattern 2: Private Channels (Node-to-Node)**
```python
from langgraph.graph import StateGraph

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

class PrivateResearchState(TypedDict):
    research_notes: str  # Only visible to research nodes
    sources: list[str]

# Add nodes with private channels
# (Note: Example pattern, check docs for latest API)
```

**When to use:** Sensitive data, isolated subsystems

**Pattern 3: Input/Output Schemas (External Interface)**
```python
class InternalState(TypedDict):
    messages: Annotated[list, add_messages]
    internal_metrics: dict
    debug_info: str

class InputSchema(TypedDict):
    user_input: str

class OutputSchema(TypedDict):
    response: str

# Subset state for external interfaces
# (Expose only InputSchema and OutputSchema to API)
```

**When to use:** API boundaries, client-server separation

**Pattern 4: Runtime Context (Dependencies)**
```python
class RuntimeContext(TypedDict):
    llm_client: Any
    database: Any
    config: dict

# Pass via context_schema parameter
app = workflow.compile(
    checkpointer=checkpointer,
    # context_schema=RuntimeContext  # Check docs for latest API
)

# Access in nodes via runtime.context
def node_fn(state: AgentState, *, runtime):
    llm = runtime.context["llm_client"]
    # ...
```

**When to use:** Dependencies (LLM clients, databases), avoid serialization issues

### 2.7 Code Examples from Echo Agent

**State Definition:**
```python
# From echo_agent.py:134-138
class AgentState(TypedDict):
    """State structure for the echo agent."""
    messages: Annotated[list, add_messages]
    user_input: str
    response: str
```

**State Initialization:**
```python
# From echo_agent.py:270-274
initial_state = {
    "messages": [],
    "user_input": user_input,
    "response": ""
}
```

**State Updates in Nodes:**
```python
# From echo_agent.py:169
return {"messages": [HumanMessage(content=user_input)]}

# From echo_agent.py:203-206
return {
    "messages": [AIMessage(content=response_text)],
    "response": response_text
}
```

**Improvements Needed:**
1. Add checkpointing with PostgreSQL
2. Add conversation_id for multi-turn tracking
3. Add task context fields for multi-agent coordination
4. Consider Pydantic for validation in production

---

## 3. Agent Coordination Patterns

### 3.1 Supervisor Pattern

**Architecture:** Centralized coordinator makes all routing decisions and controls communication flow.

**Flow Diagram:**
```
User Input
    |
    v
[Supervisor]
    |
    +----> [Research Agent]
    |           |
    |           v (returns to supervisor)
    +----> [Coding Agent]
    |           |
    |           v (returns to supervisor)
    +----> [Analysis Agent]
    |           |
    |           v (returns to supervisor)
    +----> [Validation Agent]
    |
    v
[Finalize] --> Response
```

**When to Use:**
- **Team Size:** 3-7 agents
- **Task Characteristics:** Clear task boundaries, sequential dependencies
- **Control Requirements:** Need centralized oversight and validation
- **Example Use Cases:** Research + analysis workflows, code generation + testing, multi-step data processing

**State Management:**
```python
from langgraph.graph import MessagesState

class SupervisorState(MessagesState):
    """State for supervisor pattern."""
    # Inherited: messages (full conversation history)

    current_task: str
    selected_agent: str
    task_results: dict[str, Any]
    agent_capabilities: dict[str, list[str]]
```

**Implementation - Supervisor Node:**
```python
from langgraph.types import Command
from typing import Literal

def supervisor_node(state: SupervisorState) -> Command[Literal["research", "coding", "analysis", "validation", END]]:
    """Supervisor decides which agent to route to next."""

    messages = state["messages"]
    current_task = state["current_task"]

    # Use LLM to decide routing
    system_prompt = """You are a supervisor coordinating specialized agents.

Available agents:
- research: Web search, data gathering, information retrieval
- coding: Code generation, file operations, script writing
- analysis: Data analysis, pattern recognition, insights
- validation: Output verification, fact-checking, quality control

Based on the conversation history and current task, decide which agent should handle the next step.
Return JSON: {"next_agent": "agent_name", "reasoning": "why this agent"}
"""

    routing_decision = llm.invoke(
        [{"role": "system", "content": system_prompt}] + messages,
        response_format={"type": "json_object"}
    )

    decision = json.loads(routing_decision.content)
    next_agent = decision["next_agent"]

    # Log decision
    log_decision(f"Supervisor routing to {next_agent}: {decision['reasoning']}")

    return Command(
        goto=next_agent,
        update={"selected_agent": next_agent}
    )
```

**Implementation - Worker Agent:**
```python
from langgraph.prebuilt import create_react_agent

# Create specialized agent with tools
research_tools = [web_search, read_file, extract_data]
research_agent = create_react_agent(
    model=llm,
    tools=research_tools,
    state_schema=SupervisorState,
    state_modifier="You are a research specialist. Focus only on information gathering."
)

# Add to graph
workflow.add_node("research", research_agent)
workflow.add_edge("research", "supervisor")  # Always return to supervisor
```

**Implementation - Handoff Tools:**
```python
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState, InjectedToolCallId

@tool
def transfer_to_research(
    state: Annotated[dict, InjectedState],
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId]
):
    """Transfer task to research agent for information gathering."""
    return Command(
        goto="research",
        update={
            "messages": [AIMessage(
                content=f"Transferring to research agent: {query}",
                tool_calls=[{"id": tool_call_id, "name": "transfer_to_research"}]
            )],
            "current_task": query
        },
        graph=Command.PARENT
    )

@tool
def transfer_to_coding(
    state: Annotated[dict, InjectedState],
    task: str,
    tool_call_id: Annotated[str, InjectedToolCallId]
):
    """Transfer task to coding agent for code generation."""
    return Command(
        goto="coding",
        update={
            "messages": [AIMessage(
                content=f"Transferring to coding agent: {task}",
                tool_calls=[{"id": tool_call_id, "name": "transfer_to_coding"}]
            )],
            "current_task": task
        },
        graph=Command.PARENT
    )

# Supervisor has access to handoff tools
supervisor_tools = [transfer_to_research, transfer_to_coding, ...]
```

**Complete Workflow:**
```python
from langgraph.graph import StateGraph, START, END

# Build graph
workflow = StateGraph(SupervisorState)

# Add supervisor
workflow.add_node("supervisor", supervisor_node)

# Add worker agents
workflow.add_node("research", research_agent)
workflow.add_node("coding", coding_agent)
workflow.add_node("analysis", analysis_agent)
workflow.add_node("validation", validation_agent)

# Define edges
workflow.add_edge(START, "supervisor")

# Workers return to supervisor
workflow.add_edge("research", "supervisor")
workflow.add_edge("coding", "supervisor")
workflow.add_edge("analysis", "supervisor")
workflow.add_edge("validation", "supervisor")

# Supervisor uses conditional routing (handled by Command objects)
# No explicit edges needed from supervisor to workers

# Supervisor can end workflow
# (Handled by Command(goto=END) in supervisor_node)

# Compile
app = workflow.compile(checkpointer=checkpointer)
```

**Pros:**
- Clear accountability - supervisor oversees all decisions
- Easy debugging - centralized control flow
- Quality control - supervisor validates outputs
- Scales effectively to 3-7 agents

**Cons:**
- Single point of failure - supervisor becomes bottleneck
- Communication overhead - O(n²) in naive implementations
- Limited parallelism - sequential execution through supervisor

**Optimization Tips:**
1. **Use structured outputs** for routing decisions (faster than parsing)
2. **Cache agent capabilities** in state (avoid repeated lookups)
3. **Implement early termination** (supervisor detects completion)
4. **Consider hierarchical** pattern when > 7 agents

### 3.2 Network Pattern (Decentralized)

**Architecture:** Many-to-many connections where each agent independently determines routing.

**Flow Diagram:**
```
        [Agent 1]
       /    |    \
      /     |     \
     v      v      v
[Agent 2] [Agent 3] [Agent 4]
     \      |      /
      \     |     /
       v    v    v
        [Agent 5]
```

**When to Use:**
- **Team Size:** 3-5 agents (scales poorly beyond 5)
- **Task Characteristics:** High modularity, specialized domains
- **Control Requirements:** Need explicit control over agent communication
- **Example Use Cases:** Multi-domain problem solving, autonomous agent collaboration

**State Management:**
```python
class NetworkState(MessagesState):
    """State for network pattern."""
    # All agents share identical state through central MessagesState
    messages: Annotated[list, add_messages]

    current_agent: str
    visited_agents: list[str]
    objective: str
```

**Implementation - Agent with Routing Logic:**
```python
from typing import Literal
from langgraph.types import Command

def agent_1(state: NetworkState) -> Command[Literal["agent_2", "agent_3", END]]:
    """Agent 1 processes state and decides next agent."""

    messages = state["messages"]
    objective = state["objective"]
    visited = state["visited_agents"]

    # Process task
    result = process_task(messages, objective)

    # Decide next agent using LLM
    routing_prompt = f"""Based on the objective and current progress, which agent should handle the next step?

Objective: {objective}
Current progress: {result}
Visited agents: {visited}

Available agents:
- agent_2: Data analysis specialist
- agent_3: Code generation expert
- END: Task is complete

Return JSON: {{"next": "agent_name"}}
"""

    decision = llm.invoke(routing_prompt, response_format={"type": "json_object"})
    next_agent = json.loads(decision.content)["next"]

    return Command(
        goto=next_agent,
        update={
            "messages": [AIMessage(content=result)],
            "current_agent": next_agent,
            "visited_agents": visited + ["agent_1"]
        }
    )
```

**Implementation - Tool-Based Routing:**
```python
@tool
def route_to_specialist(domain: str, task: str) -> Command:
    """Route task to appropriate domain specialist."""

    domain_mapping = {
        "data": "data_agent",
        "code": "coding_agent",
        "research": "research_agent"
    }

    target_agent = domain_mapping.get(domain, "generalist_agent")

    return Command(
        goto=target_agent,
        update={"current_task": task}
    )

# Agent uses routing tool
agent_with_routing = create_react_agent(
    model=llm,
    tools=[route_to_specialist, other_tools],
    state_schema=NetworkState
)
```

**Complete Workflow:**
```python
workflow = StateGraph(NetworkState)

# Add all agents
workflow.add_node("agent_1", agent_1)
workflow.add_node("agent_2", agent_2)
workflow.add_node("agent_3", agent_3)
workflow.add_node("agent_4", agent_4)

# No predefined edges - routing via Command objects
workflow.add_edge(START, "agent_1")  # Entry point only

# Compile
app = workflow.compile(checkpointer=checkpointer)
```

**Pros:**
- High modularity - agents are independent
- No central bottleneck - distributed decision making
- Flexible routing - dynamic based on context

**Cons:**
- Scaling challenges - full history sharing creates context bloat
- Debugging difficulty - non-linear execution paths
- Global optimality hard - local decisions may conflict

**Optimization Tips:**
1. **Limit agent count** to 3-5 (context management)
2. **Implement selective attention** - agents filter relevant messages
3. **Use structured handoffs** - explicit task passing
4. **Add circuit breakers** - prevent infinite loops

### 3.3 Hierarchical Teams

**Architecture:** Multiple levels of supervisors managing specialized teams.

**Flow Diagram:**
```
                [Top-Level Supervisor]
                    /            \
                   /              \
                  v                v
      [Research Team Super]   [Dev Team Super]
         /        \              /        \
        v          v            v          v
   [Web Search] [Analysis]  [Coding]  [Testing]
```

**When to Use:**
- **Team Size:** 8+ agents
- **Task Characteristics:** Clear domain boundaries (research, development, validation)
- **Control Requirements:** Distributed decision-making, prevent supervisor overload
- **Example Use Cases:** Large-scale projects, multi-department workflows, complex pipelines

**State Management:**
```python
class TopLevelState(MessagesState):
    """State for top-level supervisor."""
    messages: Annotated[list, add_messages]
    current_team: str
    team_results: dict[str, Any]

class TeamState(MessagesState):
    """State for team-level operations."""
    messages: Annotated[list, add_messages]
    team_name: str
    current_worker: str
    team_objective: str
```

**Implementation - Team as Subgraph:**
```python
def create_research_team():
    """Create research team as subgraph."""

    # Team supervisor
    def research_supervisor(state: TeamState) -> Command:
        # Route within team
        # ...
        return Command(goto=selected_worker)

    # Team workers
    web_search_agent = create_react_agent(llm, [web_search_tool])
    data_analysis_agent = create_react_agent(llm, [analysis_tools])

    # Build team graph
    team_workflow = StateGraph(TeamState)
    team_workflow.add_node("team_supervisor", research_supervisor)
    team_workflow.add_node("web_search", web_search_agent)
    team_workflow.add_node("data_analysis", data_analysis_agent)

    team_workflow.add_edge(START, "team_supervisor")
    team_workflow.add_edge("web_search", "team_supervisor")
    team_workflow.add_edge("data_analysis", "team_supervisor")

    return team_workflow.compile()

# Create other teams similarly
dev_team_graph = create_dev_team()
validation_team_graph = create_validation_team()
```

**Implementation - Top-Level Supervisor:**
```python
def top_supervisor(state: TopLevelState) -> Command[Literal["research_team", "dev_team", "validation_team", END]]:
    """Top-level supervisor routes between teams."""

    messages = state["messages"]

    # Decide which team should handle next phase
    routing_decision = llm.invoke(f"""
Route the task to the appropriate team:

- research_team: Information gathering, data collection
- dev_team: Code generation, implementation
- validation_team: Testing, verification, quality control

Current progress: {messages[-3:]}
Return JSON: {{"next_team": "team_name"}}
""", response_format={"type": "json_object"})

    decision = json.loads(routing_decision.content)
    next_team = decision["next_team"]

    return Command(
        goto=f"{next_team}_graph",
        update={"current_team": next_team}
    )
```

**Implementation - Compose Hierarchy:**
```python
# Top-level graph
top_workflow = StateGraph(TopLevelState)

# Add top supervisor
top_workflow.add_node("top_supervisor", top_supervisor)

# Add team graphs as nodes
top_workflow.add_node("research_team_graph", create_research_team())
top_workflow.add_node("dev_team_graph", create_dev_team())
top_workflow.add_node("validation_team_graph", create_validation_team())

# Define edges
top_workflow.add_edge(START, "top_supervisor")

# Teams return to top supervisor
top_workflow.add_edge("research_team_graph", "top_supervisor")
top_workflow.add_edge("dev_team_graph", "top_supervisor")
top_workflow.add_edge("validation_team_graph", "top_supervisor")

# Compile
app = top_workflow.compile(checkpointer=checkpointer)
```

**Multi-Level Navigation with Command.PARENT:**
```python
# Within team worker, signal completion to parent graph
def team_worker(state: TeamState) -> Command:
    result = perform_work(state)

    # If task complete, return to top-level supervisor
    if task_complete:
        return Command(
            goto="top_supervisor",
            update={"messages": [AIMessage(content=result)]},
            graph=Command.PARENT  # Navigate to parent graph
        )
    else:
        # Otherwise return to team supervisor
        return Command(
            goto="team_supervisor",
            update={"messages": [AIMessage(content=result)]}
        )
```

**Pros:**
- Scales beyond single supervisor limitations
- Organized hierarchy mirrors org structure
- Domain expertise clustering
- Prevents supervisor overload

**Cons:**
- Increased complexity
- More coordination overhead
- Deeper nesting can obscure flow

**Optimization Tips:**
1. **Limit hierarchy depth** to 2-3 levels max
2. **Clear team boundaries** - minimize cross-team dependencies
3. **State encapsulation** - teams manage internal state
4. **Use Command.PARENT** for efficient multi-level routing

### 3.4 Coordination Pattern Decision Tree

```
Start
  |
  v
How many agents?
  |
  +-- 1-2 agents --> Simple linear graph (no coordination needed)
  |
  +-- 3-7 agents --> SUPERVISOR PATTERN
  |                   - Centralized control
  |                   - Workers report to supervisor
  |                   - Use create_react_agent + handoff tools
  |
  +-- 8-15 agents --> HIERARCHICAL TEAMS
  |                    - Multiple supervisors
  |                    - Team-based organization
  |                    - Subgraph composition
  |
  +-- 15+ agents --> HIERARCHICAL + OPTIMIZATION
                      - 3-level hierarchy
                      - Adaptive communication filtering
                      - Consider if truly needed
```

**Selection Criteria:**

| Criteria | Supervisor | Hierarchical | Network |
|----------|-----------|--------------|---------|
| **Team Size** | 3-7 | 8-20+ | 3-5 |
| **Control** | Centralized | Distributed | Decentralized |
| **Scalability** | Medium | High | Low |
| **Debugging** | Easy | Medium | Hard |
| **Autonomy** | Low | Medium | High |
| **Coordination** | Simple | Complex | Very Complex |

**When in Doubt:** Start with Supervisor pattern, migrate to Hierarchical when supervisor becomes bottleneck (>7 agents).

---

## 4. Error Handling and Reliability

### 4.1 RetryPolicy Configuration

**Core Concept:** RetryPolicy provides granular retry control at the node level with exponential backoff and exception filtering.

**RetryPolicy Parameters:**
```python
from langgraph.types import RetryPolicy

RetryPolicy(
    initial_interval=0.5,      # Seconds before first retry
    backoff_factor=2.0,        # Multiplier for each retry interval
    max_interval=128.0,        # Maximum seconds between retries
    max_attempts=3,            # Total attempts including first
    jitter=True,               # Add randomization to intervals
    retry_on=Exception         # Exception classes or callable
)
```

**Basic Usage:**
```python
from langgraph.graph import StateGraph
from langgraph.types import RetryPolicy

builder = StateGraph(AgentState)

# Simple retry with max attempts
builder.add_node(
    "llm_call",
    call_llm_node,
    retry_policy=RetryPolicy(max_attempts=5)
)
```

**Retry Specific Exceptions:**
```python
import sqlite3
from requests.exceptions import Timeout, ConnectionError

# Retry only on transient errors
builder.add_node(
    "api_call",
    call_external_api,
    retry_policy=RetryPolicy(
        retry_on=(Timeout, ConnectionError),
        max_attempts=3,
        initial_interval=1.0
    )
)

# Retry on database lock errors
builder.add_node(
    "db_query",
    query_database,
    retry_policy=RetryPolicy(
        retry_on=sqlite3.OperationalError,
        max_attempts=5,
        backoff_factor=2.0
    )
)
```

**Multiple Retry Policies (First Matching Applies):**
```python
builder.add_node(
    "complex_operation",
    complex_node,
    retry_policy=[
        # Aggressive retry for timeouts
        RetryPolicy(
            retry_on=Timeout,
            max_attempts=5,
            initial_interval=0.5
        ),
        # Conservative retry for rate limits
        RetryPolicy(
            retry_on=RateLimitError,
            max_attempts=3,
            initial_interval=10.0,
            max_interval=300.0
        ),
        # Default for other exceptions
        RetryPolicy(
            retry_on=Exception,
            max_attempts=2
        )
    ]
)
```

**Custom Retry Logic:**
```python
def should_retry(exception: Exception) -> bool:
    """Custom retry decision logic."""
    # Retry on specific error messages
    if isinstance(exception, APIError):
        return "temporary" in str(exception).lower()
    # Retry on specific status codes
    if hasattr(exception, 'status_code'):
        return exception.status_code in [429, 502, 503, 504]
    return False

builder.add_node(
    "api_call",
    call_api_node,
    retry_policy=RetryPolicy(
        retry_on=should_retry,
        max_attempts=3
    )
)
```

**Exponential Backoff Calculation:**
```
Attempt 1: Execute immediately
Attempt 2: Wait initial_interval = 0.5s
Attempt 3: Wait 0.5s × 2.0 = 1.0s
Attempt 4: Wait 1.0s × 2.0 = 2.0s
Attempt 5: Wait 2.0s × 2.0 = 4.0s (if max_attempts >= 5)

With jitter: Random ±20% variation to prevent thundering herd
```

**Echo Agent Gap:**
```python
# From echo_agent.py:213 - No retry policy
workflow.add_node("generate_response", generate_response)

# Should be:
workflow.add_node(
    "generate_response",
    generate_response,
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_interval=1.0,
        retry_on=(APIError, Timeout)
    )
)
```

### 4.2 Checkpoint-Based Error Tracking

**Core Concept:** Checkpoints include error information if steps were previously attempted, providing visibility into failure history.

**Error Information in Checkpoints:**
- Exception type and message
- Stack trace
- Timestamp of failure
- Number of retry attempts
- Node that failed

**Accessing Checkpoint History:**
```python
from langgraph.checkpoint import CheckpointMetadata

# Get checkpoint after failure
config = {"configurable": {"thread_id": "user-123"}}
checkpoint = app.get_state(config)

print(f"State values: {checkpoint.values}")
print(f"Next nodes: {checkpoint.next}")
print(f"Metadata: {checkpoint.metadata}")

# Check if there was an error
if checkpoint.metadata.get("error"):
    error_info = checkpoint.metadata["error"]
    print(f"Error: {error_info['type']}: {error_info['message']}")
    print(f"Failed node: {error_info['node']}")
```

**Resume After Manual Fix:**
```python
# Workflow failed due to transient error
try:
    result = app.invoke(initial_state, config=config)
except Exception as e:
    print(f"Workflow failed: {e}")

# Manually fix issue (e.g., restore API connectivity)
fix_issue()

# Resume from last successful checkpoint
result = app.invoke(None, config=config)
```

**Inspect State at Breakpoint:**
```python
# Set breakpoint before risky operation
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["risky_operation"]
)

# Execution pauses before risky_operation
result = app.invoke(initial_state, config=config)

# Inspect state
state = app.get_state(config)
print(f"Current state: {state.values}")

# Decide whether to continue or abort
if state.values["confidence"] < 0.7:
    print("Low confidence, aborting")
else:
    # Continue execution
    result = app.invoke(None, config=config)
```

### 4.3 Human-in-the-Loop Patterns

**Breakpoints for State Inspection:**
```python
# Set breakpoints at critical decisions
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["critical_decision", "file_modification", "external_api_call"]
)

# Execution flow:
config = {"configurable": {"thread_id": "session-1"}}

# 1. Run until first breakpoint
result = app.invoke(initial_state, config=config)

# 2. Inspect state
state = app.get_state(config)
print(f"Paused before: {state.next}")
print(f"Current values: {state.values}")

# 3. Modify state if needed
app.update_state(
    config,
    {"user_approved": True, "modifications": ["fix typo"]}
)

# 4. Resume execution
result = app.invoke(None, config=config)
```

**Conditional Human Escalation:**
```python
def auto_escalate_node(state: AgentState) -> AgentState:
    """Automatically escalate on low confidence."""

    confidence = state.get("confidence", 0.0)
    threshold = 0.7

    if confidence < threshold:
        # Trigger human review
        raise NodeInterrupt(
            f"Low confidence ({confidence:.2f}), human review required. "
            f"Reason: {state.get('uncertainty_reason', 'Unknown')}"
        )

    return state

# Add escalation node before critical operations
workflow.add_node("check_confidence", auto_escalate_node)
workflow.add_edge("generate_output", "check_confidence")
workflow.add_edge("check_confidence", "final_decision")
```

**Human Approval Workflow:**
```python
def request_approval(state: AgentState) -> AgentState:
    """Request human approval for proposed action."""

    proposed_action = state["proposed_action"]

    # Send notification (email, Slack, etc.)
    notify_human(f"Approval needed for: {proposed_action}")

    # Pause execution
    raise NodeInterrupt(
        f"Awaiting approval for: {proposed_action}\n"
        f"To approve: app.update_state(config, {{'approved': True}})\n"
        f"To reject: app.update_state(config, {{'approved': False, 'reason': '...'}})"
    )

# Resume after human decision
config = {"configurable": {"thread_id": "workflow-1"}}

# Get current state
state = app.get_state(config)

# Human reviews and decides
if human_approves:
    app.update_state(config, {"approved": True})
else:
    app.update_state(config, {"approved": False, "reason": "Policy violation"})

# Continue execution
result = app.invoke(None, config=config)
```

### 4.4 Pending Writes Mechanism

**Core Concept:** When a node fails mid-execution at a given superstep, LangGraph stores pending checkpoint writes from nodes that completed successfully.

**How It Works:**
```python
# Scenario: 3 parallel operations
workflow.add_node("fetch_data", fetch_node)
workflow.add_node("process_data", process_node)
workflow.add_node("validate_data", validate_node)

# All 3 run in same superstep (parallel)
# Results:
# - fetch_data: SUCCESS ✓ (output stored as pending write)
# - process_data: SUCCESS ✓ (output stored as pending write)
# - validate_data: FAILED ✗

# LangGraph behavior:
# 1. Store pending writes from fetch_data and process_data
# 2. Save checkpoint with error information
# 3. On retry, ONLY re-execute validate_data
# 4. fetch_data and process_data outputs restored from pending writes
```

**Benefits:**
- **Efficiency:** No redundant re-execution
- **Cost Savings:** Avoid re-running expensive LLM calls
- **Consistency:** Partial progress preserved
- **Reliability:** Failed operations isolated

**Example:**
```python
def expensive_llm_call(state: AgentState) -> AgentState:
    """Expensive operation - don't want to re-run."""
    result = llm.invoke(complex_prompt)  # $$$
    return {"analysis": result}

def cheap_validation(state: AgentState) -> AgentState:
    """Cheap operation that might fail."""
    if not validate(state["analysis"]):
        raise ValueError("Validation failed")
    return {"validated": True}

# If validation fails, expensive_llm_call won't be re-run
# Its output is preserved in pending writes
```

**Requirements:**
- **Must use checkpointing** - Pending writes only work with checkpointer enabled
- **Must have persistent storage** - In-memory checkpointer loses pending writes on restart

### 4.5 Fallback Strategies

**Pattern 1: Fallback Agent**
```python
def primary_agent(state: AgentState) -> AgentState:
    """Primary agent with advanced capabilities."""
    try:
        result = advanced_llm.invoke(state["messages"])
        return {"response": result, "agent_used": "primary"}
    except Exception as e:
        # Signal fallback needed
        return {"response": None, "error": str(e)}

def fallback_agent(state: AgentState) -> AgentState:
    """Fallback agent with basic capabilities."""
    result = basic_llm.invoke(state["messages"])
    return {"response": result, "agent_used": "fallback"}

def router(state: AgentState) -> Literal["primary", "fallback", "output"]:
    """Route to fallback if primary failed."""
    if state.get("response"):
        return "output"
    else:
        return "fallback"

# Build graph with fallback
workflow.add_node("primary", primary_agent)
workflow.add_node("fallback", fallback_agent)
workflow.add_node("output", output_node)

workflow.add_edge(START, "primary")
workflow.add_conditional_edges("primary", router)
workflow.add_edge("fallback", "output")
```

**Pattern 2: Default Response**
```python
def agent_with_default(state: AgentState) -> AgentState:
    """Agent with default response on failure."""
    try:
        result = llm.invoke(state["messages"])
        return {"response": result, "success": True}
    except Exception as e:
        log_error(f"Agent failed: {e}")
        return {
            "response": "I encountered an error. Please try rephrasing your question.",
            "success": False,
            "error": str(e)
        }
```

**Pattern 3: Graceful Degradation**
```python
def degraded_service_node(state: AgentState) -> AgentState:
    """Provide partial results if full results unavailable."""
    try:
        # Attempt full processing
        full_result = full_processing(state)
        return {"result": full_result, "quality": "high"}
    except Exception as e:
        try:
            # Fall back to partial processing
            partial_result = partial_processing(state)
            return {"result": partial_result, "quality": "partial"}
        except Exception as e2:
            # Ultimate fallback: cached or default
            default_result = get_cached_or_default(state)
            return {"result": default_result, "quality": "low"}
```

### 4.6 Code Examples from Echo Agent

**Current Error Handling:**
```python
# From echo_agent.py:288-292
except Exception as e:
    error_msg = f"ERROR in echo agent: {str(e)}"
    log_decision(error_msg)
    log_decision(f"=== Echo agent run failed ===")
    raise
```

**Issues:**
1. **Too broad:** Catches all exceptions
2. **No retry:** Silent failures on transient errors
3. **No checkpointing:** Lost state on failure
4. **No stack trace:** Limited debugging information

**Improved Error Handling:**
```python
from langgraph.types import RetryPolicy
import traceback

# Add retry policy to nodes
workflow.add_node(
    "generate_response",
    generate_response,
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_interval=1.0,
        retry_on=(APIError, Timeout, ConnectionError)
    )
)

# Enable checkpointing
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))
app = workflow.compile(checkpointer=checkpointer)

# Improved exception handling
try:
    result = app.invoke(initial_state, config=config)
except APIError as e:
    log_decision(f"API ERROR: {e}")
    log_decision(f"Stack trace: {traceback.format_exc()}")
    # Attempt recovery or notify
    raise
except Exception as e:
    log_decision(f"UNEXPECTED ERROR: {e}")
    log_decision(f"Stack trace: {traceback.format_exc()}")
    # Log to monitoring system
    raise
```

---

## 5. Observability

### 5.1 LangSmith Integration

**Core Concept:** LangSmith provides execution tracing, debugging, and performance monitoring for LangGraph workflows.

**Setup with Validation:**
```python
# From echo_agent.py:50-127 (with improvements)
import os
from langsmith import Client, traceable

def setup_langsmith(strict_mode: bool = False):
    """Set up LangSmith with validation and error handling."""

    try:
        # Get API key from secret manager
        api_key = get_secret("LANGSMITH_API_KEY")

        # Validate API key format
        valid_prefixes = ("ls__", "lsv2_")
        if not api_key.startswith(valid_prefixes):
            error_msg = f"Invalid LangSmith API key format. Must start with {valid_prefixes}"
            if strict_mode:
                raise ValueError(error_msg)
            else:
                print(f"Warning: {error_msg}")
                return False

        # Test connectivity
        client = Client(api_key=api_key)
        _ = client.info  # Verify API connection

        # Configure environment
        os.environ["LANGSMITH_API_KEY"] = api_key
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_PROJECT"] = "myagents"

        print("LangSmith tracing enabled successfully")
        return True

    except Exception as e:
        if strict_mode:
            raise
        else:
            print(f"Warning: LangSmith setup failed: {e}")
            return False

# Call on module import
setup_langsmith(strict_mode=False)
```

**Using @traceable Decorator:**
```python
from langsmith import traceable

@traceable(name="supervisor_routing", run_type="chain")
def supervisor_node(state: SupervisorState) -> Command:
    """Supervisor with tracing."""
    # Decision logic
    return Command(goto=next_agent)

@traceable(name="research_task", run_type="tool")
def research_agent(state: ResearchState) -> ResearchState:
    """Research agent with tracing."""
    # Research logic
    return updated_state

@traceable(name="full_workflow", run_type="chain")
def run_workflow(user_input: str) -> str:
    """Top-level workflow with tracing."""
    result = app.invoke({"user_input": user_input})
    return result["response"]
```

**Explicit RunTree for Fine-Grained Control:**
```python
from langsmith.run_trees import RunTree

def run_with_detailed_tracing(user_input: str) -> str:
    """Run workflow with detailed trace metadata."""

    with RunTree(
        name="agent_workflow",
        run_type="chain",
        inputs={"user_input": user_input},
        tags=["production", "v2.0"],
        metadata={"user_id": "123", "session_id": "abc"}
    ) as run:
        try:
            result = app.invoke({"user_input": user_input})

            # Add outputs to trace
            run.outputs = {
                "response": result["response"],
                "agent_path": result.get("agent_path", [])
            }
            run.end(outputs=run.outputs)

            return result["response"]
        except Exception as e:
            # Record error in trace
            run.end(error=str(e))
            raise
```

**LangSmith Web UI Access:**
- URL: https://smith.langchain.com/
- View traces, debug execution, analyze performance
- Compare runs, detect regressions, optimize costs

### 5.2 Trace Analysis and Debugging

**Viewing Traces in LangSmith:**
1. Navigate to your project in LangSmith web UI
2. View list of runs with timestamps, status, latency
3. Click run to see detailed trace tree
4. Inspect inputs/outputs of each node
5. View LLM calls with prompts and completions
6. Analyze token usage and costs

**Trace Tree Structure:**
```
run_workflow (chain)
├── supervisor_routing (chain)
│   ├── llm_call (llm)
│   │   ├── Input: system prompt + messages
│   │   └── Output: {"next_agent": "research"}
│   └── Output: Command(goto="research")
├── research_agent (chain)
│   ├── web_search (tool)
│   │   └── Output: search results
│   ├── llm_call (llm)
│   │   └── Output: analysis
│   └── Output: updated state
└── Output: final response
```

**Debug Common Issues:**

**Issue: Agent Loop**
- **Symptom:** Same agent called repeatedly
- **Debug:** Check trace for repeated agent calls
- **Solution:** Add visited_agents tracking, loop detection

**Issue: Missing Context**
- **Symptom:** Agent makes decisions without relevant info
- **Debug:** Inspect LLM inputs in trace, verify state propagation
- **Solution:** Ensure state updates include necessary context

**Issue: High Latency**
- **Symptom:** Slow response times
- **Debug:** Analyze trace timeline, identify bottleneck nodes
- **Solution:** Parallelize independent operations, optimize prompts

**Issue: Unexpected Routing**
- **Symptom:** Wrong agent selected
- **Debug:** View supervisor LLM call, examine routing decision
- **Solution:** Improve routing prompt, add constraints

### 5.3 Performance Monitoring

**Metrics to Track:**

**1. Token Usage**
```python
from dataclasses import dataclass

@dataclass
class TokenMetrics:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    timestamp: datetime

def track_token_usage(response) -> TokenMetrics:
    """Extract token usage from LLM response."""
    usage = response.usage_metadata
    return TokenMetrics(
        prompt_tokens=usage["input_tokens"],
        completion_tokens=usage["output_tokens"],
        total_tokens=usage["total_tokens"],
        model=response.model,
        timestamp=datetime.now()
    )
```

**2. Execution Time**
```python
import time

def track_execution_time(node_fn):
    """Decorator to track node execution time."""
    def wrapper(state):
        start_time = time.time()
        result = node_fn(state)
        duration = time.time() - start_time

        # Log metrics
        log_metric(f"{node_fn.__name__}_duration", duration)

        return result
    return wrapper

@track_execution_time
def expensive_node(state: AgentState) -> AgentState:
    # Node logic
    return updated_state
```

**3. Success Rate**
```python
class MetricsCollector:
    def __init__(self):
        self.successes = 0
        self.failures = 0
        self.total_runs = 0

    def record_success(self):
        self.successes += 1
        self.total_runs += 1

    def record_failure(self, error: Exception):
        self.failures += 1
        self.total_runs += 1
        log_error(error)

    def get_success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.successes / self.total_runs

metrics = MetricsCollector()

try:
    result = app.invoke(state, config=config)
    metrics.record_success()
except Exception as e:
    metrics.record_failure(e)
    raise
```

**4. Agent Routing Distribution**
```python
from collections import Counter

class RoutingMetrics:
    def __init__(self):
        self.agent_calls = Counter()

    def record_agent_call(self, agent_name: str):
        self.agent_calls[agent_name] += 1

    def get_distribution(self) -> dict:
        total = sum(self.agent_calls.values())
        return {
            agent: count / total
            for agent, count in self.agent_calls.items()
        }

routing_metrics = RoutingMetrics()

def supervisor_with_metrics(state: SupervisorState) -> Command:
    next_agent = decide_next_agent(state)
    routing_metrics.record_agent_call(next_agent)
    return Command(goto=next_agent)
```

### 5.4 Cost Tracking

**Token-Based Cost Calculation:**
```python
# Gemini pricing (example rates)
GEMINI_PRICING = {
    "gemini-2.5-flash": {
        "input_per_1m": 0.10,   # $0.10 per 1M input tokens
        "output_per_1m": 0.40,  # $0.40 per 1M output tokens
    },
    "gemini-2.0-flash": {
        "input_per_1m": 0.075,
        "output_per_1m": 0.30,
    }
}

class CostTracker:
    def __init__(self):
        self.total_cost = 0.0
        self.cost_by_model = {}

    def calculate_cost(self, model: str, token_usage: dict) -> float:
        """Calculate cost for LLM call."""
        pricing = GEMINI_PRICING.get(model, {})

        input_cost = (token_usage["input_tokens"] / 1_000_000) * pricing["input_per_1m"]
        output_cost = (token_usage["output_tokens"] / 1_000_000) * pricing["output_per_1m"]

        total = input_cost + output_cost
        return total

    def track_call(self, model: str, token_usage: dict):
        """Track cost for single LLM call."""
        cost = self.calculate_cost(model, token_usage)
        self.total_cost += cost

        if model not in self.cost_by_model:
            self.cost_by_model[model] = 0.0
        self.cost_by_model[model] += cost

    def get_summary(self) -> dict:
        """Get cost summary."""
        return {
            "total_cost": self.total_cost,
            "cost_by_model": self.cost_by_model,
            "average_per_call": self.total_cost / len(self.cost_by_model) if self.cost_by_model else 0
        }

# Usage
cost_tracker = CostTracker()

def llm_node_with_cost_tracking(state: AgentState) -> AgentState:
    response = llm.invoke(state["messages"])

    # Track cost
    cost_tracker.track_call(
        model="gemini-2.5-flash",
        token_usage=response.usage_metadata
    )

    return {"response": response.content}
```

**Budget Alerts:**
```python
class BudgetMonitor:
    def __init__(self, daily_budget: float):
        self.daily_budget = daily_budget
        self.current_spend = 0.0

    def check_budget(self, cost: float) -> bool:
        """Check if cost would exceed budget."""
        return (self.current_spend + cost) <= self.daily_budget

    def record_spend(self, cost: float):
        """Record spending and alert if approaching limit."""
        self.current_spend += cost

        utilization = self.current_spend / self.daily_budget

        if utilization >= 0.9:
            alert(f"Budget 90% utilized: ${self.current_spend:.2f} / ${self.daily_budget:.2f}")
        elif utilization >= 0.75:
            warn(f"Budget 75% utilized: ${self.current_spend:.2f} / ${self.daily_budget:.2f}")

budget_monitor = BudgetMonitor(daily_budget=100.0)

def budget_aware_node(state: AgentState) -> AgentState:
    estimated_cost = estimate_llm_cost(state)

    if not budget_monitor.check_budget(estimated_cost):
        raise BudgetExceededError(f"Would exceed daily budget of ${budget_monitor.daily_budget}")

    response = llm.invoke(state["messages"])
    actual_cost = calculate_cost(response)

    budget_monitor.record_spend(actual_cost)

    return {"response": response.content}
```

### 5.5 Structured Logging

**Using structlog for Agent Decisions:**
```python
import structlog

logger = structlog.get_logger()

def log_agent_decision(
    agent_name: str,
    decision: str,
    context: dict,
    metadata: dict = None
):
    """Log agent decision with structured data."""
    logger.info(
        "agent_decision",
        agent_name=agent_name,
        decision=decision,
        context=context,
        metadata=metadata or {},
        timestamp=datetime.now().isoformat()
    )

# Usage in nodes
def supervisor_node(state: SupervisorState) -> Command:
    next_agent = decide_next_agent(state)

    log_agent_decision(
        agent_name="supervisor",
        decision=f"route_to_{next_agent}",
        context={
            "current_task": state["current_task"],
            "available_agents": list(state["agent_capabilities"].keys()),
            "reasoning": "Best fit for data analysis task"
        },
        metadata={"confidence": 0.85}
    )

    return Command(goto=next_agent)
```

**Logging Best Practices:**
1. **Structured over unstructured** - Use JSON-compatible formats
2. **Include context** - Agent name, decision, reasoning
3. **Add metadata** - Confidence, timestamp, user_id
4. **Log at decision points** - Routing, tool selection, escalation
5. **Avoid PII** - Sanitize sensitive data before logging

### 5.6 Best Practices

**1. Always Enable LangSmith in Production**
- Invaluable for debugging production issues
- Trace analysis reveals bottlenecks
- Cost tracking prevents budget overruns

**2. Use Structured Logging**
- JSON format for easy parsing
- Include agent name, decision, context
- Facilitate log aggregation (Datadog, CloudWatch)

**3. Track Key Metrics**
- Token usage per agent
- Execution time per node
- Success rate overall
- Agent routing distribution

**4. Set Up Alerts**
- Budget thresholds (75%, 90%)
- Error rate spikes
- Latency degradation
- Unusual routing patterns

**5. Regular Trace Review**
- Weekly review of failed traces
- Identify patterns in errors
- Optimize slow nodes
- Improve prompts based on LLM outputs

---

## 6. Advanced Patterns

### 6.1 Multi-Layer Memory

**Architecture Overview:**

```
┌─────────────────────────────────────┐
│      Short-Term Memory              │
│  (Recent conversation context)      │
│  - Last N messages                  │
│  - Current task context             │
│  - Immediate working memory         │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│      Long-Term Memory               │
│  (Persistent knowledge)             │
│  - Vector database (ChromaDB)       │
│  - Semantic search                  │
│  - Cross-session learning           │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│      Procedural Memory              │
│  (Execution patterns)               │
│  - Successful task approaches       │
│  - RAG with examples                │
│  - Best practices learned           │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│      Shared Memory                  │
│  (Agent coordination)               │
│  - Knowledge graph                  │
│  - Agent capabilities registry      │
│  - Task history                     │
└─────────────────────────────────────┘
```

**Layer 1: Short-Term Memory**
```python
from langgraph.graph import MessagesState
from typing import Annotated

class ShortTermMemory(MessagesState):
    """Short-term conversation memory."""
    messages: Annotated[list, add_messages]
    conversation_id: str
    conversation_summary: str  # Periodic summary
    recent_context: list[dict]  # Last 10 key points

# Summarization for context management
from langchain_core.messages import trim_messages

def summarize_conversation(state: ShortTermMemory) -> ShortTermMemory:
    """Summarize conversation when context gets too long."""

    messages = state["messages"]

    if len(messages) > 40:  # Threshold
        # Keep system message and recent messages
        trimmed = trim_messages(
            messages,
            max_tokens=4000,
            strategy="last",
            token_counter=llm.get_num_tokens
        )

        # Generate summary of removed messages
        removed_messages = messages[:-len(trimmed)]
        summary = llm.invoke(f"Summarize this conversation:\n{removed_messages}")

        return {
            "messages": trimmed,
            "conversation_summary": summary.content,
            "recent_context": extract_key_points(trimmed)
        }

    return state
```

**Layer 2: Long-Term Memory (Vector Database)**
```python
from chromadb import Client as ChromaClient
from langchain.embeddings import GoogleGenerativeAIEmbeddings

class LongTermMemory:
    def __init__(self):
        self.chroma_client = ChromaClient()
        self.collection = self.chroma_client.create_collection("agent_memory")
        self.embeddings = GoogleGenerativeAIEmbeddings(model="embedding-001")

    def store_interaction(
        self,
        conversation_id: str,
        messages: list,
        outcome: dict
    ):
        """Store successful interaction for future retrieval."""

        # Create embedding from conversation
        conversation_text = "\n".join([m.content for m in messages])
        embedding = self.embeddings.embed_query(conversation_text)

        # Store in vector DB
        self.collection.add(
            embeddings=[embedding],
            documents=[conversation_text],
            metadatas=[{
                "conversation_id": conversation_id,
                "outcome": str(outcome),
                "timestamp": datetime.now().isoformat()
            }],
            ids=[conversation_id]
        )

    def retrieve_similar(self, query: str, limit: int = 5):
        """Retrieve similar past interactions."""

        query_embedding = self.embeddings.embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit
        )

        return results

# Usage in agent
long_term_memory = LongTermMemory()

def agent_with_memory(state: AgentState) -> AgentState:
    """Agent that uses long-term memory."""

    # Retrieve similar past interactions
    similar_cases = long_term_memory.retrieve_similar(
        state["user_input"],
        limit=3
    )

    # Include in context
    context = f"Similar past interactions:\n{similar_cases}\n\nCurrent task: {state['user_input']}"

    response = llm.invoke(context)

    # Store successful interaction
    long_term_memory.store_interaction(
        conversation_id=state["conversation_id"],
        messages=state["messages"],
        outcome={"success": True, "response": response.content}
    )

    return {"response": response.content}
```

**Layer 3: Procedural Memory (RAG with Patterns)**
```python
class ProceduralMemory:
    """Store and retrieve successful execution patterns."""

    def __init__(self):
        self.patterns = []  # Could be vector DB

    def record_success(
        self,
        task_type: str,
        approach: dict,
        result: dict
    ):
        """Record successful task execution pattern."""
        pattern = {
            "task_type": task_type,
            "approach": approach,
            "result": result,
            "timestamp": datetime.now(),
            "success_count": 1
        }
        self.patterns.append(pattern)

    def get_examples(self, task_type: str, limit: int = 3) -> list:
        """Retrieve successful examples for task type."""
        matching = [p for p in self.patterns if p["task_type"] == task_type]
        # Sort by success count or recency
        matching.sort(key=lambda x: x["success_count"], reverse=True)
        return matching[:limit]

# Usage
procedural_memory = ProceduralMemory()

def agent_with_procedural_memory(state: AgentState) -> AgentState:
    """Agent uses past successful approaches."""

    task_type = classify_task(state["user_input"])

    # Get successful examples
    examples = procedural_memory.get_examples(task_type, limit=3)

    prompt = f"""Task: {state['user_input']}

Successful approaches from past similar tasks:
{format_examples(examples)}

Use these examples to guide your approach.
"""

    response = llm.invoke(prompt)

    # Record if successful
    if successful(response):
        procedural_memory.record_success(
            task_type=task_type,
            approach={"method": response.method},
            result={"output": response.content}
        )

    return {"response": response.content}
```

**Layer 4: Shared Memory (Knowledge Graph)**
```python
class SharedMemory:
    """Shared knowledge base for all agents."""

    def __init__(self):
        self.knowledge_graph = {}  # Simplified; use Neo4j in production
        self.agent_capabilities = {}
        self.task_history = []

    def register_agent(self, agent_name: str, capabilities: list[str]):
        """Register agent capabilities."""
        self.agent_capabilities[agent_name] = capabilities

    def add_knowledge(self, subject: str, predicate: str, object: str):
        """Add fact to knowledge graph."""
        if subject not in self.knowledge_graph:
            self.knowledge_graph[subject] = []
        self.knowledge_graph[subject].append((predicate, object))

    def query_knowledge(self, subject: str) -> list:
        """Query knowledge about subject."""
        return self.knowledge_graph.get(subject, [])

    def record_task(self, task: dict):
        """Record task execution for history."""
        self.task_history.append({
            **task,
            "timestamp": datetime.now()
        })

# Global shared memory
shared_memory = SharedMemory()

# Agents register capabilities
shared_memory.register_agent("research", ["web_search", "data_analysis"])
shared_memory.register_agent("coding", ["python", "javascript", "file_ops"])

# Agents add knowledge
def research_agent(state: AgentState) -> AgentState:
    results = perform_research(state)

    # Add findings to shared knowledge
    for finding in results:
        shared_memory.add_knowledge(
            subject=finding["topic"],
            predicate="research_finding",
            object=finding["content"]
        )

    return {"research_results": results}

# Other agents query knowledge
def coding_agent(state: AgentState) -> AgentState:
    task = state["current_task"]

    # Query relevant knowledge
    relevant_knowledge = shared_memory.query_knowledge(task["topic"])

    # Use in code generation
    code = generate_code(task, context=relevant_knowledge)

    return {"generated_code": code}
```

### 6.2 Task Decomposition Strategies

**BabyAGI-Inspired Pattern:**

```python
from queue import PriorityQueue

class TaskPlanningSystem:
    """Dynamic task decomposition system."""

    def __init__(self, llm):
        self.llm = llm
        self.task_queue = PriorityQueue()
        self.completed_tasks = []
        self.objective = ""

    def create_tasks(self, objective: str, context: dict) -> list:
        """Generate subtasks based on objective and progress."""

        prompt = f"""Objective: {objective}

Completed tasks:
{self.format_completed_tasks()}

Current context:
{json.dumps(context)}

Generate a list of NEW tasks needed to achieve the objective.
Avoid duplicating completed tasks.
Return JSON array: [{{"description": "...", "priority": 1-10, "dependencies": []}}]
"""

        response = self.llm.invoke(prompt, response_format={"type": "json_object"})
        tasks = json.loads(response.content)["tasks"]

        # Filter duplicates
        new_tasks = [t for t in tasks if not self.is_duplicate(t)]

        return new_tasks

    def prioritize_tasks(self, tasks: list) -> list:
        """Reorder tasks based on dependencies and importance."""

        prompt = f"""Objective: {self.objective}

Tasks to prioritize:
{json.dumps(tasks)}

Reorder tasks from highest to lowest priority.
Consider:
- Dependencies (tasks that unblock others)
- Alignment with objective
- Estimated impact

Return JSON: {{"task_order": [task_ids]}}
"""

        response = self.llm.invoke(prompt, response_format={"type": "json_object"})
        priority_order = json.loads(response.content)["task_order"]

        return reorder_tasks(tasks, priority_order)

    def execute_task(self, task: dict) -> dict:
        """Execute task using appropriate agent."""

        # Route to specialized agent based on task type
        agent = self.select_agent(task)
        result = agent.execute(task)

        # Store in vector memory
        self.store_task_result(task, result)

        return result

    def run(self, objective: str, max_iterations: int = 50):
        """Execute planning loop until objective achieved."""

        self.objective = objective

        # Initialize with first task
        initial_task = {"description": objective, "priority": 10}
        self.task_queue.put((10, initial_task))

        iteration = 0
        while not self.task_queue.empty() and iteration < max_iterations:
            # Get next task
            priority, task = self.task_queue.get()

            # Execute
            result = self.execute_task(task)
            self.completed_tasks.append({**task, "result": result})

            # Generate new tasks based on result
            new_tasks = self.create_tasks(objective, result)

            # Prioritize and enqueue
            prioritized = self.prioritize_tasks(new_tasks)
            for t in prioritized:
                self.task_queue.put((t["priority"], t))

            iteration += 1

            # Check completion
            if self.is_objective_achieved(objective):
                break

        return self.compile_final_result()
```

**Integration with LangGraph:**
```python
class PlanningState(TypedDict):
    """State for task planning workflow."""
    objective: str
    task_queue: list[dict]
    completed_tasks: list[dict]
    current_task: dict
    final_result: dict

def create_planning_workflow():
    """Create workflow with dynamic task planning."""

    def create_tasks_node(state: PlanningState) -> PlanningState:
        """Generate new tasks."""
        planner = TaskPlanningSystem(llm)
        new_tasks = planner.create_tasks(
            state["objective"],
            state.get("current_task", {})
        )
        return {"task_queue": state["task_queue"] + new_tasks}

    def prioritize_tasks_node(state: PlanningState) -> PlanningState:
        """Prioritize task queue."""
        planner = TaskPlanningSystem(llm)
        prioritized = planner.prioritize_tasks(state["task_queue"])
        return {"task_queue": prioritized}

    def execute_task_node(state: PlanningState) -> PlanningState:
        """Execute next task."""
        if not state["task_queue"]:
            return state

        task = state["task_queue"][0]
        planner = TaskPlanningSystem(llm)
        result = planner.execute_task(task)

        return {
            "task_queue": state["task_queue"][1:],
            "completed_tasks": state["completed_tasks"] + [task],
            "current_task": {"task": task, "result": result}
        }

    def should_continue(state: PlanningState) -> str:
        """Decide next step."""
        if not state["task_queue"]:
            return "finalize"
        else:
            return "execute_task"

    # Build workflow
    workflow = StateGraph(PlanningState)

    workflow.add_node("create_tasks", create_tasks_node)
    workflow.add_node("prioritize_tasks", prioritize_tasks_node)
    workflow.add_node("execute_task", execute_task_node)
    workflow.add_node("finalize", finalize_node)

    workflow.add_edge(START, "create_tasks")
    workflow.add_edge("create_tasks", "prioritize_tasks")
    workflow.add_conditional_edges(
        "prioritize_tasks",
        should_continue,
        {
            "execute_task": "execute_task",
            "finalize": "finalize"
        }
    )
    workflow.add_edge("execute_task", "create_tasks")  # Loop
    workflow.add_edge("finalize", END)

    return workflow.compile()
```

### 6.3 Dynamic Agent Routing

**Context-Based Routing:**
```python
def intelligent_router(state: AgentState) -> str:
    """Route based on task complexity and context."""

    task = state["current_task"]

    # Analyze task characteristics
    complexity = analyze_complexity(task)
    domain = classify_domain(task)
    urgency = assess_urgency(task)

    # Routing logic
    if complexity == "high" and domain == "research":
        return "expert_research_agent"
    elif complexity == "low" and domain == "research":
        return "basic_research_agent"
    elif domain == "coding":
        if urgency == "high":
            return "fast_coding_agent"
        else:
            return "thorough_coding_agent"
    else:
        return "generalist_agent"

workflow.add_conditional_edges(
    "router",
    intelligent_router,
    {
        "expert_research_agent": "expert_research_agent",
        "basic_research_agent": "basic_research_agent",
        "fast_coding_agent": "fast_coding_agent",
        "thorough_coding_agent": "thorough_coding_agent",
        "generalist_agent": "generalist_agent"
    }
)
```

**Load-Balanced Routing:**
```python
class LoadBalancer:
    """Balance load across multiple agent instances."""

    def __init__(self):
        self.agent_loads = {}

    def select_agent(self, agent_type: str, available_instances: list[str]) -> str:
        """Select least-loaded instance."""

        # Get current loads
        loads = {
            instance: self.agent_loads.get(instance, 0)
            for instance in available_instances
        }

        # Select minimum load
        selected = min(loads.items(), key=lambda x: x[1])[0]

        # Increment load
        self.agent_loads[selected] = self.agent_loads.get(selected, 0) + 1

        return selected

    def release_agent(self, instance: str):
        """Decrement load when task completes."""
        if instance in self.agent_loads:
            self.agent_loads[instance] = max(0, self.agent_loads[instance] - 1)

load_balancer = LoadBalancer()

def load_balanced_router(state: AgentState) -> str:
    """Route to least-loaded agent instance."""

    agent_type = state["required_agent_type"]
    instances = ["research_1", "research_2", "research_3"]

    selected = load_balancer.select_agent(agent_type, instances)

    return selected
```

### 6.4 Configuration Management

**YAML-Based Configuration:**
```yaml
# config/agents.yaml
models:
  default: "gemini-2.5-flash"
  alternatives:
    - "gemini-2.0-flash"
    - "gemini-1.5-pro"

llm_settings:
  temperature: 0.7
  max_tokens: 4096
  top_p: 0.9

agents:
  supervisor:
    model: "gemini-2.5-flash"
    system_prompt: "You are a supervisor coordinating specialized agents."
    temperature: 0.3
    tools:
      - delegate_to_research
      - delegate_to_coding

  research:
    model: "gemini-2.5-flash"
    system_prompt: "You are a research specialist."
    temperature: 0.7
    tools:
      - web_search
      - read_file

memory:
  short_term:
    max_messages: 50
    summarize_at: 40
  long_term:
    backend: "chromadb"
    collection: "myagents_memory"

workflow:
  max_iterations: 50
  timeout_seconds: 300
  checkpointing:
    enabled: true
    backend: "postgresql"
```

**Configuration Loader:**
```python
from dataclasses import dataclass
import yaml

@dataclass
class AgentConfig:
    model: str
    system_prompt: str
    temperature: float
    tools: list[str]

@dataclass
class SystemConfig:
    models: dict
    llm_settings: dict
    agents: dict[str, AgentConfig]
    memory: dict
    workflow: dict

class ConfigManager:
    def __init__(self, config_path: str = "config/agents.yaml"):
        self.config = self.load_config(config_path)

    def load_config(self, path: str) -> SystemConfig:
        """Load configuration from YAML."""
        with open(path) as f:
            data = yaml.safe_load(f)

        agents = {
            name: AgentConfig(**config)
            for name, config in data["agents"].items()
        }

        return SystemConfig(
            models=data["models"],
            llm_settings=data["llm_settings"],
            agents=agents,
            memory=data["memory"],
            workflow=data["workflow"]
        )

    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """Get configuration for specific agent."""
        return self.config.agents.get(agent_name)

# Usage
config = ConfigManager()
supervisor_config = config.get_agent_config("supervisor")

supervisor_llm = genai.GenerativeModel(
    supervisor_config.model,
    generation_config={
        "temperature": supervisor_config.temperature
    }
)
```

---

## 7. Implementation Guide

### 7.1 Echo Agent Evolution

**Current State (Alpha):**
- 1 agent (single LLM call)
- 2 nodes (process_input, generate_response)
- Linear graph (no conditionals)
- Basic MessagesState
- No checkpointing
- No retry logic
- Unverified LangSmith integration

**File: echo_agent.py:134-221**

**Phase 1 Target (Foundation):**

**Week 1: Add Supervisor Pattern**
```python
# New state with coordination fields
class SupervisorState(MessagesState):
    messages: Annotated[list, add_messages]
    user_input: str
    response: str
    current_agent: str
    task_results: dict[str, Any]
    agent_capabilities: dict[str, list[str]]

# Supervisor node
def supervisor_node(state: SupervisorState) -> Command:
    # Route to appropriate agent
    next_agent = decide_routing(state)
    return Command(goto=next_agent)

# Worker agents
research_agent = create_react_agent(llm, research_tools)
coding_agent = create_react_agent(llm, coding_tools)
analysis_agent = create_react_agent(llm, analysis_tools)

# Build graph
workflow = StateGraph(SupervisorState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("research", research_agent)
workflow.add_node("coding", coding_agent)
workflow.add_node("analysis", analysis_agent)

workflow.add_edge(START, "supervisor")
workflow.add_edge("research", "supervisor")
workflow.add_edge("coding", "supervisor")
workflow.add_edge("analysis", "supervisor")

app = workflow.compile()
```

**Week 2: Add Multi-Layer Memory**
```python
# Enhanced state with memory
class EnhancedState(SupervisorState):
    conversation_id: str
    conversation_summary: str
    recent_context: list[dict]

# Memory systems
long_term_memory = LongTermMemory()  # ChromaDB
procedural_memory = ProceduralMemory()  # RAG patterns
shared_memory = SharedMemory()  # Knowledge graph

# Memory-aware agent
def agent_with_memory(state: EnhancedState) -> EnhancedState:
    # Retrieve relevant past interactions
    similar = long_term_memory.retrieve_similar(state["user_input"])

    # Get successful patterns
    patterns = procedural_memory.get_examples(task_type)

    # Query shared knowledge
    knowledge = shared_memory.query_knowledge(topic)

    # Use in LLM call
    context = f"Past: {similar}\nPatterns: {patterns}\nKnowledge: {knowledge}"
    response = llm.invoke(context)

    return {"response": response.content}
```

**Week 3: Add Error Handling**
```python
# RetryPolicy on all LLM nodes
workflow.add_node(
    "research",
    research_agent,
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_interval=1.0,
        retry_on=(APIError, Timeout)
    )
)

# Enable checkpointing
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))
app = workflow.compile(checkpointer=checkpointer)

# Human-in-the-loop for low confidence
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["critical_decision"]
)
```

**Week 4: Add Observability**
```python
# Verify LangSmith setup
setup_langsmith(strict_mode=True)  # Fail fast on issues

# Structured logging
import structlog
logger = structlog.get_logger()

def supervisor_with_logging(state: SupervisorState) -> Command:
    next_agent = decide_routing(state)

    logger.info(
        "supervisor_routing",
        next_agent=next_agent,
        reasoning="Task requires data analysis",
        confidence=0.85
    )

    return Command(goto=next_agent)

# Cost tracking
cost_tracker = CostTracker()

def llm_node_with_tracking(state: AgentState) -> AgentState:
    response = llm.invoke(state["messages"])
    cost_tracker.track_call("gemini-2.5-flash", response.usage_metadata)
    return {"response": response.content}
```

**Phase 1 Result:**
- 5+ agents (supervisor + 4 workers)
- 6+ nodes (routing + execution)
- Conditional routing via Command objects
- Multi-layer memory (short + long-term)
- PostgreSQL checkpointing
- RetryPolicy on all LLM nodes
- Verified LangSmith + structured logging + cost tracking

### 7.2 From Single Agent to Multi-Agent Coordination

**Step-by-Step Migration:**

**Step 1: Identify Specializations**
```python
# Before: Single general agent
def general_agent(state: AgentState) -> AgentState:
    # Handles everything
    response = llm.invoke(state["user_input"])
    return {"response": response.content}

# After: Specialized agents
def research_specialist(state: AgentState) -> AgentState:
    # Focused on information gathering
    response = llm.invoke(state["query"], tools=research_tools)
    return {"research_results": response.content}

def coding_specialist(state: AgentState) -> AgentState:
    # Focused on code generation
    response = llm.invoke(state["requirements"], tools=coding_tools)
    return {"generated_code": response.content}
```

**Step 2: Add Supervisor**
```python
def supervisor(state: SupervisorState) -> Command:
    """Route to appropriate specialist."""

    task_type = classify_task(state["user_input"])

    routing_map = {
        "research": "research_specialist",
        "coding": "coding_specialist",
        "analysis": "analysis_specialist"
    }

    next_agent = routing_map.get(task_type, "general_agent")

    return Command(goto=next_agent)
```

**Step 3: Define State Flow**
```python
# State with coordination fields
class CoordinationState(MessagesState):
    messages: Annotated[list, add_messages]
    user_input: str
    task_type: str
    current_agent: str
    agent_results: dict[str, Any]
    final_response: str
```

**Step 4: Build Graph**
```python
workflow = StateGraph(CoordinationState)

# Add supervisor
workflow.add_node("supervisor", supervisor)

# Add specialists
workflow.add_node("research_specialist", research_specialist)
workflow.add_node("coding_specialist", coding_specialist)
workflow.add_node("analysis_specialist", analysis_specialist)

# Add finalize
workflow.add_node("finalize", finalize_response)

# Define edges
workflow.add_edge(START, "supervisor")
workflow.add_edge("research_specialist", "supervisor")
workflow.add_edge("coding_specialist", "supervisor")
workflow.add_edge("analysis_specialist", "supervisor")
# Supervisor routes to finalize via Command(goto=END) or Command(goto="finalize")

workflow.add_edge("finalize", END)

app = workflow.compile(checkpointer=checkpointer)
```

### 7.3 Progressive Complexity Approach

**Complexity Level 1: Single Agent (Current Echo Agent)**
- Linear workflow
- No coordination
- Basic state
- Use case: Simple tasks, prototyping

**Complexity Level 2: Supervisor with 3-5 Agents (Phase 1)**
- Centralized routing
- Specialized workers
- Extended state
- Use case: Multi-domain tasks, moderate complexity

**Complexity Level 3: Hierarchical Teams (Phase 2)**
- Multi-level supervisors
- Team-based organization
- Subgraph composition
- Use case: Large projects, 8+ agents

**Complexity Level 4: Advanced Patterns (Phase 3)**
- Dynamic task decomposition
- Consensus mechanisms
- Adaptive communication
- Use case: Complex autonomous systems

**When to Increase Complexity:**
- Single agent → Supervisor: Need specialization (3+ distinct domains)
- Supervisor → Hierarchical: Supervisor overloaded (7+ agents)
- Hierarchical → Advanced: Autonomous planning needed

**Anti-Pattern:** Jumping to complexity level 4 without mastering 1-3

### 7.4 Common Pitfalls and Solutions

**Pitfall 1: Monolithic State**
- **Problem:** Single massive state object
- **Solution:** Separate state layers, use private channels

**Pitfall 2: No Checkpointing**
- **Problem:** Lost state on failure
- **Solution:** Always use PostgreSQL checkpointer in production

**Pitfall 3: Missing Retry Logic**
- **Problem:** Silent failures on transient errors
- **Solution:** RetryPolicy on all LLM nodes

**Pitfall 4: Unstructured Messages**
- **Problem:** Hard to debug, no intent clarity
- **Solution:** Use performatives, conversation IDs

**Pitfall 5: Supervisor Overload**
- **Problem:** Single supervisor managing 10+ agents
- **Solution:** Migrate to hierarchical teams

**Pitfall 6: No Cost Tracking**
- **Problem:** Budget overruns
- **Solution:** Track token usage and costs per workflow

---

## 8. Decision Matrix

### 8.1 Pattern Selection Flowchart

```
┌─────────────────────────────────────┐
│   How many distinct agent roles?   │
└─────────────┬───────────────────────┘
              │
      ┌───────┴───────┐
      │               │
   1-2 agents    3+ agents
      │               │
      v               v
┌─────────┐   ┌───────────────────┐
│ Linear  │   │ Do you need       │
│ Graph   │   │ centralized       │
└─────────┘   │ control?          │
              └──┬────────────┬───┘
                 │            │
               Yes           No
                 │            │
                 v            v
        ┌────────────┐  ┌──────────┐
        │ Supervisor │  │ Network  │
        │ Pattern    │  │ Pattern  │
        └──────┬─────┘  └──────────┘
               │
               v
        ┌──────────────────┐
        │ More than 7      │
        │ agents?          │
        └──┬───────────┬───┘
           │           │
          No          Yes
           │           │
           v           v
    ┌──────────┐  ┌─────────────┐
    │ Keep     │  │ Hierarchical│
    │Supervisor│  │ Teams       │
    └──────────┘  └─────────────┘
```

### 8.2 Complexity vs Value Analysis

**Supervisor Pattern:**
- **Complexity:** Medium
- **Value:** High (foundational)
- **Time to Implement:** 1-2 weeks
- **When to Use:** 3-7 agents, centralized control needed
- **ROI:** Immediate value for multi-domain tasks

**Hierarchical Teams:**
- **Complexity:** High
- **Value:** High (at scale)
- **Time to Implement:** 2-3 weeks
- **When to Use:** 8+ agents, supervisor bottleneck
- **ROI:** Value increases with agent count

**Network Pattern:**
- **Complexity:** Very High
- **Value:** Medium (niche use cases)
- **Time to Implement:** 2-3 weeks
- **When to Use:** High modularity, specialized domains
- **ROI:** Diminishing returns, use only if needed

**Multi-Layer Memory:**
- **Complexity:** Medium-High
- **Value:** High (production essential)
- **Time to Implement:** 1-2 weeks
- **When to Use:** Context management, learning
- **ROI:** Essential for production quality

**Dynamic Task Decomposition:**
- **Complexity:** High
- **Value:** Very High (autonomous operation)
- **Time to Implement:** 2-3 weeks
- **When to Use:** Complex multi-step tasks
- **ROI:** High for autonomous systems

### 8.3 Scaling Considerations

**1 Agent (Echo Agent):**
- **Pros:** Simple, fast, easy to debug
- **Cons:** Limited capabilities, no specialization
- **Use Case:** Single-domain tasks, prototypes

**3-7 Agents (Supervisor):**
- **Pros:** Specialization, centralized control, moderate complexity
- **Cons:** Single point of failure, supervisor bottleneck potential
- **Use Case:** Multi-domain workflows, moderate scale
- **Communication Overhead:** O(n) through supervisor

**8-15 Agents (Hierarchical 2-Level):**
- **Pros:** Scales beyond supervisor, domain organization
- **Cons:** Increased complexity, coordination overhead
- **Use Case:** Large projects, clear domain boundaries
- **Communication Overhead:** O(n × k) where k = avg team size

**15+ Agents (Hierarchical 3-Level + Optimization):**
- **Pros:** Handles very large teams, distributed control
- **Cons:** High complexity, difficult debugging
- **Use Case:** Enterprise-scale, complex autonomous systems
- **Communication Overhead:** O(n × k × log k n) with adaptive filtering

**Recommendation:** Start with supervisor, migrate to hierarchical only when supervisor becomes bottleneck.

### 8.4 When to Use Which Pattern

**Use Supervisor Pattern When:**
- Team size: 3-7 agents
- Need centralized oversight
- Clear task boundaries
- Quality control important
- Debugging simplicity valued

**Use Hierarchical Teams When:**
- Team size: 8+ agents
- Clear domain boundaries (research team, dev team)
- Supervisor overload observed
- Distributed decision-making needed
- Scaling beyond supervisor limits

**Use Network Pattern When:**
- High modularity required
- Specialized agent domains
- Agent count: 3-5 (doesn't scale well)
- Explicit control over communication needed
- Experimentation/research context

**Use Linear Graph When:**
- 1-2 agents
- Simple sequential workflow
- No dynamic routing needed
- Prototyping phase

**Decision Table:**

| Scenario | Recommended Pattern | Alternative |
|----------|-------------------|-------------|
| 1-2 agents | Linear Graph | - |
| 3-7 agents, centralized | Supervisor | - |
| 8-15 agents | Hierarchical (2-level) | Supervisor |
| 15+ agents | Hierarchical (3-level) | - |
| High modularity, 3-5 agents | Network | Supervisor |
| Autonomous planning | Supervisor + Task Decomposition | - |
| Research/experimental | Network | Supervisor |

---

## 9. References

### 9.1 Official LangGraph Documentation

**Core Documentation:**
- LangGraph Homepage: https://langchain-ai.github.io/langgraph/
- Concepts: https://langchain-ai.github.io/langgraph/concepts/
- Tutorials: https://langchain-ai.github.io/langgraph/tutorials/
- How-to Guides: https://langchain-ai.github.io/langgraph/how-tos/
- API Reference: https://langchain-ai.github.io/langgraph/reference/

**State Management:**
- State Concept: https://langchain-ai.github.io/langgraph/concepts/low_level/#state
- Reducers: https://langchain-ai.github.io/langgraph/concepts/low_level/#reducers
- MessagesState: https://langchain-ai.github.io/langgraph/reference/graphs/#messagesstate
- Checkpointing: https://langchain-ai.github.io/langgraph/concepts/persistence/

**Multi-Agent Patterns:**
- Multi-Agent Concepts: https://langchain-ai.github.io/langgraph/concepts/multi_agent/
- Agent Supervisor: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/
- Multi-Agent Collaboration: https://langchain-ai.github.io/langgraph/tutorials/multi_agent/multi-agent-collaboration/
- Hierarchical Teams: https://langchain-ai.github.io/langgraph/concepts/multi_agent/#hierarchical

**Error Handling:**
- RetryPolicy: https://langchain-ai.github.io/langgraph/reference/types/#retrypolicy
- Error Handling: https://langchain-ai.github.io/langgraph/how-tos/error-handling/
- Breakpoints: https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/

**Advanced:**
- Subgraphs: https://langchain-ai.github.io/langgraph/how-tos/subgraph/
- Command: https://langchain-ai.github.io/langgraph/reference/types/#command
- Streaming: https://langchain-ai.github.io/langgraph/how-tos/streaming/

### 9.2 LangSmith Observability

**LangSmith Documentation:**
- LangSmith Homepage: https://docs.smith.langchain.com/
- Tracing: https://docs.smith.langchain.com/tracing
- Evaluation: https://docs.smith.langchain.com/evaluation
- Monitoring: https://docs.smith.langchain.com/monitoring

**LangSmith Platform:**
- Web UI: https://smith.langchain.com/
- API Reference: https://docs.smith.langchain.com/reference

### 9.3 Related Tools

**LangChain:**
- Documentation: https://python.langchain.com/docs/
- Message Types: https://python.langchain.com/docs/concepts/messages/
- Embeddings: https://python.langchain.com/docs/integrations/text_embedding/

**LangGraph Studio:**
- Visual debugging tool for LangGraph
- https://github.com/langchain-ai/langgraph-studio

**Checkpointer Backends:**
- PostgreSQL: https://langchain-ai.github.io/langgraph/reference/checkpoints/#postgressaver
- SQLite: https://langchain-ai.github.io/langgraph/reference/checkpoints/#sqlitesaver
- Memory: https://langchain-ai.github.io/langgraph/reference/checkpoints/#memorysaver

### 9.4 Source Documents

**Research Documents:**
1. LangGraph Architecture Analysis
2. Coordination Patterns Synthesis (27 patterns across 8 frameworks)
3. Multi-Agent Recommendations Report
4. Research Consolidation Map

**Reference Implementation:**
- Echo Agent: /home/code/myagents/MyAgents-langgraph/backend/services/agents/src/workflows/echo_agent.py

**Academic Research:**
- Multi-agent Reinforcement Learning (arXiv:2312.10256, 2024)
- Multi-Agent Collaboration Mechanisms (arXiv:2501.06322, 2025)
- AgentNet Dynamic Topology (arXiv:2504.00587, 2025)

### 9.5 Community Resources

**GitHub:**
- LangGraph Repository: https://github.com/langchain-ai/langgraph
- Examples: https://github.com/langchain-ai/langgraph/tree/main/examples

**Community:**
- LangChain Discord: https://discord.gg/langchain
- GitHub Discussions: https://github.com/langchain-ai/langgraph/discussions

**Learning Resources:**
- LangChain Academy: https://academy.langchain.com/
- LangChain Blog: https://blog.langchain.dev/

### 9.6 Further Reading

**Graph-Based Systems:**
- Google Pregel Paper: https://kowshik.github.io/JPregel/pregel_paper.pdf
- Message-Passing Architectures

**Multi-Agent Systems:**
- AutoGen Framework: https://microsoft.github.io/autogen/
- CrewAI: https://docs.crewai.com/
- MetaGPT: https://github.com/geekan/MetaGPT

**LLM Best Practices:**
- Prompt Engineering Guide: https://www.promptingguide.ai/
- LLM Patterns: https://eugeneyan.com/writing/llm-patterns/

---

## Conclusion

This comprehensive reference guide provides the definitive resource for implementing LangGraph-based multi-agent systems. Key takeaways:

**1. Start Simple, Iterate:**
- Begin with supervisor pattern (3-7 agents)
- Add hierarchical teams when supervisor overloaded (8+ agents)
- Implement advanced patterns only when needed

**2. Production Essentials:**
- Always use checkpointing (PostgreSQL)
- RetryPolicy on all LLM nodes
- LangSmith integration for observability
- Multi-layer memory for context management

**3. Pattern Selection:**
- Supervisor: Most common pattern, 3-7 agents, centralized control
- Hierarchical: 8+ agents, domain boundaries, distributed decision-making
- Network: Niche use case, 3-5 agents, high modularity

**4. Implementation Roadmap:**
- Phase 1 (Weeks 1-4): Foundation (supervisor, memory, error handling, observability)
- Phase 2 (Weeks 5-8): Intelligence (task decomposition, structured communication)
- Phase 3 (Weeks 9-12): Optimization (adaptive communication, consensus)

**5. Common Pitfalls to Avoid:**
- Monolithic state (use separate layers)
- No checkpointing (use PostgreSQL in production)
- Missing retry logic (use RetryPolicy)
- Supervisor overload (migrate to hierarchical at 8+ agents)

**6. Echo Agent Evolution:**
- Current: 1 agent, 2 nodes, linear graph
- Phase 1 Target: 5+ agents, 6+ nodes, conditional routing, multi-layer memory, checkpointing, retry, observability

**Official Documentation:** Always refer to https://langchain-ai.github.io/langgraph/ for latest updates and API changes.

**Version:** 1.0 (2025-10-24)
**Lines:** ~2,500
**Status:** Complete

---

**End of LangGraph Implementation Patterns Reference Guide**
