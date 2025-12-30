# Learning Guide: Data Engineer to AI Engineer with LangGraph

**Version:** 1.0
**Created:** 2025-10-24
**Target Audience:** Data engineers transitioning to AI engineer roles
**Total Duration:** 40-60 hours (5 modules)
**Framework Focus:** LangGraph for multi-agent systems

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Learning Path Overview](#2-learning-path-overview)
3. [Module 1: LLM Fundamentals](#3-module-1-llm-fundamentals-8-10-hours)
4. [Module 2: AI Agents Fundamentals](#4-module-2-ai-agents-fundamentals-8-10-hours)
5. [Module 3: LangGraph State Management](#5-module-3-langgraph-state-management-10-12-hours)
6. [Module 4: Multi-Agent Coordination](#6-module-4-multi-agent-coordination-12-15-hours)
7. [Module 5: Production Patterns](#7-module-5-production-patterns-10-12-hours)
8. [Advanced Topics](#8-advanced-topics-self-study)
9. [Capstone Project](#9-capstone-project-research-assistant)
10. [Resources](#10-resources)

---

## 1. Prerequisites

### 1.1 Required Background

**Data Engineering Skills:**
- Python programming (intermediate)
- Working with APIs and JSON
- Database fundamentals (SQL, basic NoSQL)
- Understanding of state and data pipelines
- Git version control

**Environment Setup:**
- Python 3.10+
- Poetry or pip for package management
- GCP account (for Secret Manager, Gemini API)
- LangSmith account (free tier)
- IDE with Python support (VS Code recommended)

### 1.2 Installation

```bash
# Clone MyAgents repository
git clone <repository-url>
cd myagents

# Install dependencies
poetry install

# Set up secrets (GCP Secret Manager)
# - GEMINI_API_KEY
# - LANGSMITH_API_KEY

# Verify installation
python -m backend.services.agents.src.workflows.echo_agent
```

### 1.3 Time Commitment

- **Total Hours:** 40-60 hours over 5-8 weeks
- **Weekly Commitment:** 8-12 hours/week
- **Module Duration:** Each module 2-3 hours of concepts + 6-9 hours hands-on
- **Capstone Project:** 10-15 hours

---

## 2. Learning Path Overview

### 2.1 Five Module Progression

```
Module 1: LLM Fundamentals (8-10 hrs)
  └─> Understand LLMs, prompting, LangChain basics, echo agent

Module 2: AI Agents Fundamentals (8-10 hrs)
  └─> What is an agent, state management, tools, modify echo agent

Module 3: LangGraph State Management (10-12 hrs)
  └─> StateGraph, reducers, checkpointing, hands-on checkpointing

Module 4: Multi-Agent Coordination (12-15 hrs)
  └─> Supervisor, Network, Hierarchical, build 3-agent system

Module 5: Production Patterns (10-12 hrs)
  └─> Error handling, observability, memory, production features

Capstone: Research Assistant (10-15 hrs)
  └─> Build complete multi-agent system with validation
```

### 2.2 Learning Objectives by Module

**Module 1:** Understand LLM capabilities, limitations, and basic LangChain integration

**Module 2:** Define agent concept, recognize state management patterns, implement basic tools

**Module 3:** Master LangGraph state schemas, reducers, and persistence mechanisms

**Module 4:** Design multi-agent architectures, implement coordination patterns, route between agents

**Module 5:** Harden agents for production with retry logic, observability, and memory

**Capstone:** Synthesize all modules into production-ready research assistant

### 2.3 Hands-On Philosophy

- **Learn by Doing:** Each module includes practical exercises
- **Echo Agent as Foundation:** Start with working code, extend incrementally
- **Progressive Complexity:** Build on previous modules
- **Reference Patterns:** Use langgraph_implementation_patterns.md for details

---

## 3. Module 1: LLM Fundamentals (8-10 hours)

### 3.1 Learning Objectives

- Understand how LLMs work at high level (no deep learning math required)
- Write effective prompts for different tasks
- Recognize LLM limitations (hallucinations, context windows)
- Use LangChain for LLM integration
- Understand echo agent architecture

### 3.2 Core Concepts

**Large Language Models:**
- Trained on massive text datasets to predict next tokens
- Stateless: no memory between API calls unless provided
- Context window: limited input size (typically 8k-128k tokens)
- Temperature: controls randomness (0.0 = deterministic, 1.0 = creative)

**Prompting Fundamentals:**
- System prompts: define agent behavior/role
- Few-shot prompting: provide examples for better results
- Chain of thought: ask LLM to "think step by step"
- Structured outputs: request JSON/specific formats

**LangChain Basics:**
- Abstraction layer over LLM providers (OpenAI, Google, Anthropic)
- Message types: SystemMessage, HumanMessage, AIMessage
- Chains: composable sequences of LLM calls
- Tools: functions LLMs can call for external capabilities

**Key Limitation for Data Engineers:**
- LLMs don't have direct database access (need tools)
- No real-time data unless provided in context
- Cannot execute code unless given code execution tool

### 3.3 Hands-On Exercise: Echo Agent Analysis

**Task:** Understand echo_agent.py line by line

**Analysis Steps:**

1. **State Definition (lines 134-138):**
```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_input: str
    response: str
```
- TypedDict defines state schema
- `add_messages` is reducer for message accumulation
- Compare to data pipeline state management

2. **Node Functions (lines 162-206):**
- `process_input`: converts user input to HumanMessage
- `generate_response`: calls LLM, returns AIMessage
- Nodes are pure functions: state in, state update out

3. **Graph Construction (lines 209-221):**
- StateGraph initialized with AgentState
- Nodes added with `workflow.add_node()`
- Linear edges: START → process_input → generate_response → END
- Compile creates executable workflow

4. **LangSmith Integration (lines 50-127):**
- Observability for agent execution
- Traces show node execution, timing, LLM calls
- Validation and connectivity testing

**Questions to Answer:**
- What happens if LLM API call fails?
- Where is state persisted between runs?
- How would you add a third node?

### 3.4 Exercise: Modify Echo Agent

**Task:** Extend echo agent to include sentiment in response

**Steps:**

1. Add sentiment field to AgentState
2. Create sentiment analysis node (use LLM prompt)
3. Insert node between process_input and generate_response
4. Update generate_response to include sentiment in response

**Expected Output:**
```
User: "I love this product!"
Agent: "[Positive Sentiment] I'm glad to hear you love the product! ..."
```

**Time:** 2-3 hours

### 3.5 Assessment Criteria

- [ ] Explain LLM statelessness and implications
- [ ] Write effective system prompts for 3 different agent roles
- [ ] Identify hallucination vs factual error
- [ ] Trace echo_agent.py execution flow in LangSmith
- [ ] Successfully add new node to echo agent graph
- [ ] Understand add_messages reducer purpose

---

## 4. Module 2: AI Agents Fundamentals (8-10 hours)

### 4.1 Learning Objectives

- Define what makes an LLM application an "agent"
- Understand agent components: LLM + tools + memory + control flow
- Implement simple tools for agents
- Recognize when to use agents vs simple LLM calls
- Build ReAct (Reasoning + Acting) loop

### 4.2 Core Concepts

**What is an AI Agent?**

An agent is an LLM application that can:
1. **Reason** about tasks (plan, decide)
2. **Act** using tools (search, compute, retrieve data)
3. **Remember** context across interactions (memory)
4. **Iterate** until task complete (control flow)

**Agent vs LLM Call:**
- LLM call: single request/response
- Agent: iterative loop with tool use and decision-making

**ReAct Pattern:**
```
1. Thought: "I need to search for current stock price"
2. Action: call search_tool("AAPL stock price")
3. Observation: "AAPL is $150.23"
4. Thought: "Now I have the price, I can respond"
5. Action: respond to user with price
```

**Tools:**
- Python functions agents can call
- Decorated with `@tool` or schema defined
- Parameters extracted from LLM structured output
- Return values fed back to LLM as observations

**State Management:**
- Conversation history (short-term memory)
- Task results accumulation
- Control flags (is_complete, needs_human_input)

### 4.3 Hands-On Exercise: Add Calculator Tool

**Task:** Give echo agent ability to do math

**Implementation:**

1. **Define tool:**
```python
from langchain_core.tools import tool

@tool
def calculator(expression: str) -> str:
    """Evaluate mathematical expression safely.

    Args:
        expression: Math expression like "2 + 2" or "15 * 3"

    Returns:
        Result as string
    """
    try:
        # Use safe eval (restricted to math operations)
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"
```

2. **Integrate with agent:**
- Import `create_react_agent` from langgraph
- Pass tools list to agent creation
- Update system prompt to mention calculator capability

3. **Test:**
```
User: "What is 123 * 456?"
Agent: [Uses calculator tool] "The result is 56,088"
```

**Time:** 3-4 hours

### 4.4 Hands-On Exercise: Build Simple Research Agent

**Task:** Create agent that can search web and summarize

**Requirements:**
- Use Tavily search API or similar (free tier available)
- Search tool that takes query and returns results
- Summarize tool that condenses text
- Agent decides when to search vs summarize vs respond

**State Schema:**
```python
class ResearchState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    search_results: list[str]
    summary: str
```

**Tools Needed:**
- `web_search(query: str) -> list[str]`
- `summarize(text: str) -> str`

**Expected Behavior:**
```
User: "What are the latest trends in AI agents?"
Agent Thought: "I need to search for recent information"
Agent Action: web_search("AI agents trends 2025")
Agent Observation: [5 article summaries]
Agent Thought: "Now I'll summarize key points"
Agent Action: summarize(combined_articles)
Agent Response: "The latest trends include..."
```

**Time:** 4-5 hours

### 4.5 Assessment Criteria

- [ ] Define agent components (LLM + tools + memory + control)
- [ ] Implement at least 2 custom tools with proper schemas
- [ ] Explain ReAct loop with concrete example
- [ ] Identify when agent is overkill vs necessary
- [ ] Debug tool calling failures using LangSmith traces
- [ ] Build working research agent with search + summarize

---

## 5. Module 3: LangGraph State Management (10-12 hours)

### 5.1 Learning Objectives

- Master StateGraph architecture
- Implement custom reducers for complex state
- Use checkpointing for persistence and fault tolerance
- Understand pending writes mechanism
- Design state schemas for multi-agent coordination

### 5.2 Core Concepts

**StateGraph Architecture:**
- Nodes: functions that receive state, return updates
- Edges: control flow (direct, conditional)
- State: TypedDict or Pydantic schema
- Super-steps: atomic execution units with checkpointing

**Reducers:**
- Functions that merge node outputs into state
- Default: overwrite (last write wins)
- Built-in: `add_messages` (append with deduplication)
- Custom: `operator.add` (list concatenation), `merge_dicts`, etc.

**Why Reducers Matter:**
Without reducer:
```python
state["items"] = ["a"]
state["items"] = ["b"]  # Overwrites! Result: ["b"]
```

With reducer:
```python
items: Annotated[list, operator.add]
state["items"] = ["a"]
state["items"] = ["b"]  # Appends! Result: ["a", "b"]
```

**Checkpointing:**
- Automatic state persistence at every super-step
- Enables pause/resume of workflows
- Fault tolerance: resume from last successful checkpoint
- Backends: MemorySaver (dev), SQLite (local), PostgreSQL (prod)

**Pending Writes:**
- When node fails, successful parallel nodes' outputs preserved
- Resume doesn't re-execute successful nodes
- Requires checkpointing enabled

### 5.3 Hands-On Exercise: Implement Checkpointing

**Task:** Add PostgreSQL checkpointing to echo agent

**Steps:**

1. **Install PostgreSQL locally:**
```bash
docker run -d -p 5432:5432 \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=langgraph \
  postgres:15
```

2. **Add checkpointer to agent:**
```python
from langgraph.checkpoint.postgres import PostgresSaver

# In create_echo_agent():
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://postgres:password@localhost:5432/langgraph"
)

app = workflow.compile(checkpointer=checkpointer)
```

3. **Test persistence:**
```python
# Run 1: Start conversation
config = {"configurable": {"thread_id": "test-123"}}
response1 = workflow.invoke(
    {"user_input": "My name is Alice", ...},
    config=config
)

# Run 2: Continue conversation (same thread_id)
response2 = workflow.invoke(
    {"user_input": "What's my name?", ...},
    config=config
)
# Should remember "Alice" from checkpoint
```

**Expected:** Agent remembers previous conversation via checkpoints

**Time:** 3-4 hours

### 5.4 Hands-On Exercise: Custom Reducers

**Task:** Build agent with complex state accumulation

**Scenario:** Multi-step data processing agent

**State Schema:**
```python
from typing import Annotated
from operator import add

class ProcessingState(TypedDict):
    messages: Annotated[list, add_messages]
    raw_data: list[dict]  # Overwrite (latest data)
    processing_steps: Annotated[list[str], add]  # Accumulate steps
    errors: Annotated[list[str], add]  # Accumulate errors
    final_result: dict  # Overwrite (final output)
```

**Nodes:**
1. `fetch_data`: Gets raw data, adds to processing_steps
2. `validate_data`: Checks data, adds errors if invalid
3. `transform_data`: Processes data, adds to processing_steps
4. `finalize`: Creates final_result

**Test Custom Reducer:**
- Run workflow multiple times
- Verify processing_steps accumulates all steps
- Verify errors list grows with each validation issue
- Verify raw_data and final_result overwrite (not accumulate)

**Time:** 3-4 hours

### 5.5 Advanced Exercise: Breakpoints and Human-in-the-Loop

**Task:** Add breakpoint before critical operation

**Implementation:**
```python
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["finalize"]  # Pause before finalize
)

# Run workflow
config = {"configurable": {"thread_id": "review-123"}}
result = app.invoke(initial_state, config)

# Workflow pauses at "finalize" node
# Inspect state: result["processing_steps"], result["errors"]

# Human reviews and approves
# Resume workflow
final_result = app.invoke(None, config)  # Continue from checkpoint
```

**Use Case:** Data engineer reviews transformed data before loading

**Time:** 2-3 hours

### 5.6 Assessment Criteria

- [ ] Implement StateGraph with 4+ nodes
- [ ] Use at least 2 custom reducers correctly
- [ ] Configure PostgreSQL checkpointing
- [ ] Demonstrate conversation memory across runs (same thread_id)
- [ ] Explain pending writes mechanism with example
- [ ] Implement breakpoint with human approval step
- [ ] Debug state issues using checkpoint history

---

## 6. Module 4: Multi-Agent Coordination (12-15 hours)

### 6.1 Learning Objectives

- Design multi-agent architectures
- Implement Supervisor pattern (3-7 agents)
- Implement Network pattern (peer-to-peer)
- Implement Hierarchical Teams (8+ agents)
- Choose coordination pattern based on requirements
- Use Command objects for dynamic routing

### 6.2 Core Concepts

**Coordination Patterns:**

1. **Supervisor Pattern:**
   - Central coordinator routes tasks to specialized workers
   - Workers always return to supervisor
   - Use case: 3-7 agents, clear task boundaries
   - Scale limit: supervisor becomes bottleneck at 7+ agents

2. **Network Pattern:**
   - Agents route to each other directly (peer-to-peer)
   - Each agent decides next agent via LLM or logic
   - Use case: 3-5 specialized agents, high modularity
   - Challenge: debugging complex routing paths

3. **Hierarchical Teams:**
   - Multiple supervisor levels
   - Teams compiled as subgraphs
   - Top supervisor routes between teams
   - Use case: 8+ agents, domain-separated teams

**Command Objects:**
```python
from langgraph.types import Command

# Navigate to specific node
return Command(goto="research_agent")

# Navigate with state update
return Command(
    goto="coding_agent",
    update={"current_task": "implement feature X"}
)

# Navigate to parent graph (for subgraphs)
return Command(goto="supervisor", graph=Command.PARENT)
```

**Handoff Tools:**
- Tools that transfer control between agents
- Use InjectedState to access current state
- Return Command object to route to target agent

### 6.3 Hands-On Exercise: Supervisor Pattern (3 Agents)

**Task:** Build supervisor + 2 workers system

**Architecture:**
```
Supervisor (coordinator)
  ├─> Research Agent (web search)
  ├─> Coding Agent (code generation)
  └─> User (final response)
```

**Implementation Steps:**

1. **Define State:**
```python
class MultiAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    task: str
    task_results: dict
    current_agent: str
```

2. **Create Workers:**
```python
from langgraph.prebuilt import create_react_agent

research_agent = create_react_agent(
    llm,
    tools=[web_search_tool],
    state_modifier="You are a research specialist. Search for information."
)

coding_agent = create_react_agent(
    llm,
    tools=[generate_code_tool],
    state_modifier="You are a coding specialist. Write Python code."
)
```

3. **Create Handoff Tools:**
```python
@tool
def delegate_to_research(
    state: Annotated[dict, InjectedState],
    query: str
) -> Command:
    """Delegate research task to research agent."""
    return Command(
        goto="research_agent",
        update={"task": query, "current_agent": "research"}
    )

@tool
def delegate_to_coding(
    state: Annotated[dict, InjectedState],
    requirements: str
) -> Command:
    """Delegate coding task to coding agent."""
    return Command(
        goto="coding_agent",
        update={"task": requirements, "current_agent": "coding"}
    )
```

4. **Create Supervisor:**
```python
supervisor = create_react_agent(
    llm,
    tools=[delegate_to_research, delegate_to_coding],
    state_modifier="""You are a supervisor coordinating specialized agents.
    Analyze the user's request and delegate to the appropriate agent:
    - Research Agent: for information gathering, web search
    - Coding Agent: for code generation, programming tasks
    """
)
```

5. **Build Graph:**
```python
workflow = StateGraph(MultiAgentState)

workflow.add_node("supervisor", supervisor)
workflow.add_node("research_agent", research_agent)
workflow.add_node("coding_agent", coding_agent)

workflow.add_edge(START, "supervisor")
# Workers return to supervisor
workflow.add_edge("research_agent", "supervisor")
workflow.add_edge("coding_agent", "supervisor")
workflow.add_edge("supervisor", END)

app = workflow.compile()
```

**Test Cases:**
- "Search for latest Python best practices" → delegates to research
- "Write a function to merge two sorted lists" → delegates to coding
- "Research sorting algorithms then implement quicksort" → both agents

**Time:** 5-6 hours

### 6.4 Hands-On Exercise: Add 3rd Agent and Validation

**Task:** Extend supervisor system with validation agent

**New Agent:**
- Validation Agent: reviews outputs from other agents
- Tools: syntax checker, fact checker, quality scorer

**Updated Architecture:**
```
Supervisor
  ├─> Research Agent
  ├─> Coding Agent
  ├─> Validation Agent (reviews others' work)
  └─> User (after validation)
```

**Workflow:**
1. User asks for code
2. Supervisor delegates to Coding Agent
3. Coding Agent returns code to Supervisor
4. Supervisor delegates to Validation Agent for review
5. Validation Agent checks syntax, quality
6. If validation passes, respond to user
7. If validation fails, delegate back to Coding Agent for fix

**Implementation:**
- Add validation_agent with quality checking tools
- Update supervisor to always validate before final response
- Add conditional routing based on validation result

**Time:** 4-5 hours

### 6.5 Hands-On Exercise: Hierarchical Teams

**Task:** Evolve 3-agent system to hierarchical (5+ agents)

**Target Architecture:**
```
Top Supervisor
  ├─> Research Team (sub-graph)
  │     ├─> Team Supervisor
  │     ├─> Web Search Agent
  │     └─> Data Analysis Agent
  └─> Development Team (sub-graph)
        ├─> Team Supervisor
        ├─> Coding Agent
        └─> Testing Agent
```

**Implementation:**

1. **Create Team Subgraphs:**
```python
def create_research_team():
    team_state = StateGraph(MultiAgentState)

    team_state.add_node("team_supervisor", research_supervisor)
    team_state.add_node("web_search", web_search_agent)
    team_state.add_node("data_analysis", data_analysis_agent)

    # Team routing logic
    # ...

    return team_state.compile()

def create_dev_team():
    # Similar structure
    pass
```

2. **Compile Teams as Nodes:**
```python
research_team_graph = create_research_team()
dev_team_graph = create_dev_team()

# Add compiled graphs as nodes
main_workflow.add_node("research_team", research_team_graph)
main_workflow.add_node("dev_team", dev_team_graph)
```

3. **Top-Level Routing:**
```python
@tool
def route_to_research_team(...) -> Command:
    return Command(goto="research_team")

@tool
def route_to_dev_team(...) -> Command:
    return Command(goto="dev_team")
```

**Test:** Complex task requiring both teams (research + implementation)

**Time:** 5-6 hours

### 6.6 Assessment Criteria

- [ ] Implement supervisor pattern with 3+ workers
- [ ] Create handoff tools with Command objects
- [ ] Demonstrate routing decisions in LangSmith traces
- [ ] Build hierarchical system with 2 teams (5+ agents total)
- [ ] Choose appropriate pattern for 3 different scenarios
- [ ] Debug routing issues using state inspection
- [ ] Implement validation loop (agent → validator → agent)

---

## 7. Module 5: Production Patterns (10-12 hours)

### 7.1 Learning Objectives

- Implement RetryPolicy for transient failures
- Add comprehensive observability (logging, metrics, traces)
- Build multi-layer memory (short-term + vector DB)
- Configure production-ready checkpointing
- Handle edge cases and error scenarios
- Deploy agent to production environment

### 7.2 Core Concepts

**Error Handling Strategies:**
- Retry: transient errors (API timeouts, rate limits)
- Fallback: permanent errors (use alternative approach)
- Escalate: low confidence or critical decisions (human-in-the-loop)
- Graceful degradation: partial results better than total failure

**Observability Pillars:**
1. **Traces:** Execution flow through agents (LangSmith)
2. **Logs:** Structured decision logs (JSON format)
3. **Metrics:** Performance, cost, success rate
4. **Alerts:** Anomaly detection, error rate thresholds

**Memory Layers:**
1. **Short-term:** Conversation history (MessagesState)
2. **Long-term:** Vector database (semantic search)
3. **Procedural:** Successful execution patterns (RAG)
4. **Shared:** Knowledge base for all agents

### 7.3 Hands-On Exercise: RetryPolicy

**Task:** Add retry logic to handle LLM API failures

**Implementation:**
```python
from langgraph.types import RetryPolicy

workflow.add_node(
    "generate_response",
    generate_response_node,
    retry_policy=RetryPolicy(
        max_attempts=3,
        initial_interval=1.0,
        backoff_factor=2.0,  # 1s, 2s, 4s
        max_interval=10.0,
        jitter=True,  # Add randomness to prevent thundering herd
        retry_on=Exception  # Retry on any exception
    )
)
```

**Testing:**
1. Mock API failure (simulate timeout)
2. Verify retry attempts in logs
3. Confirm exponential backoff timing
4. Test max_attempts limit reached

**Advanced:** Retry only on specific exceptions
```python
from google.api_core.exceptions import ResourceExhausted, DeadlineExceeded

retry_policy = RetryPolicy(
    max_attempts=5,
    retry_on=(ResourceExhausted, DeadlineExceeded)  # Only retry these
)
```

**Time:** 2-3 hours

### 7.4 Hands-On Exercise: Structured Logging

**Task:** Replace print statements with structured logging

**Implementation:**
```python
import structlog

logger = structlog.get_logger()

def supervisor_node(state: MultiAgentState) -> Command:
    task = state["task"]

    # Analyze task
    selected_agent = decide_agent(task)

    # Structured log
    logger.info(
        "supervisor_routing_decision",
        agent_name="supervisor",
        selected_agent=selected_agent,
        task_summary=task[:100],
        task_length=len(task),
        timestamp=datetime.now().isoformat()
    )

    return Command(goto=selected_agent)
```

**Benefits:**
- Machine-readable logs (JSON)
- Easy filtering (all supervisor decisions)
- Metrics aggregation (routing distribution)
- Production debugging

**Configure Output:**
```python
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
```

**Time:** 2-3 hours

### 7.5 Hands-On Exercise: Vector Memory

**Task:** Add long-term memory with semantic search

**Implementation:**

1. **Install ChromaDB:**
```bash
pip install chromadb
```

2. **Create Memory Manager:**
```python
import chromadb

class VectorMemory:
    def __init__(self, collection_name="agent_memory"):
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )

    def store_interaction(
        self,
        interaction_id: str,
        query: str,
        response: str,
        metadata: dict
    ):
        """Store successful interaction for future retrieval."""
        self.collection.add(
            ids=[interaction_id],
            documents=[f"Query: {query}\nResponse: {response}"],
            metadatas=[metadata]
        )

    def retrieve_similar(self, query: str, n_results: int = 3):
        """Retrieve similar past interactions."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results
```

3. **Integrate with Agent:**
```python
memory = VectorMemory()

def generate_response_with_memory(state: AgentState) -> AgentState:
    query = state["user_input"]

    # Search memory for similar past interactions
    similar = memory.retrieve_similar(query, n_results=3)

    # Build context with memory
    context = "Similar past interactions:\n"
    for doc in similar["documents"][0]:
        context += f"- {doc}\n"

    # Add to prompt
    prompt = f"{context}\n\nCurrent query: {query}"

    # Generate response
    response = llm.generate_content(prompt)

    # Store this interaction
    memory.store_interaction(
        interaction_id=str(uuid.uuid4()),
        query=query,
        response=response.text,
        metadata={"timestamp": datetime.now().isoformat()}
    )

    return {"response": response.text}
```

**Test:** Ask similar questions, verify agent references past interactions

**Time:** 3-4 hours

### 7.6 Hands-On Exercise: Cost Tracking

**Task:** Track LLM API costs per workflow run

**Implementation:**
```python
GEMINI_PRICING = {
    "gemini-2.5-flash": {
        "input_per_1m": 0.15,   # $0.15 per 1M input tokens
        "output_per_1m": 0.60   # $0.60 per 1M output tokens
    }
}

class CostTracker:
    def __init__(self):
        self.total_cost = 0.0
        self.runs = []

    def track_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate and track cost of LLM call."""
        pricing = GEMINI_PRICING[model]

        input_cost = (input_tokens / 1_000_000) * pricing["input_per_1m"]
        output_cost = (output_tokens / 1_000_000) * pricing["output_per_1m"]
        total = input_cost + output_cost

        self.total_cost += total

        logger.info(
            "llm_cost",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=total
        )

        return total

    def get_summary(self) -> dict:
        return {
            "total_cost_usd": self.total_cost,
            "total_runs": len(self.runs),
            "avg_cost_per_run": self.total_cost / len(self.runs) if self.runs else 0
        }

# Usage
cost_tracker = CostTracker()

def generate_response(state: AgentState) -> AgentState:
    response = llm.generate_content(prompt)

    # Extract token counts (model-specific)
    input_tokens = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count

    cost_tracker.track_llm_call(
        model="gemini-2.5-flash",
        input_tokens=input_tokens,
        output_tokens=output_tokens
    )

    return {"response": response.text}
```

**Dashboard:** Aggregate costs by day/week/month

**Time:** 2-3 hours

### 7.7 Assessment Criteria

- [ ] Implement RetryPolicy on all LLM-calling nodes
- [ ] Configure exponential backoff with jitter
- [ ] Replace all print() with structured logging
- [ ] Integrate ChromaDB for long-term memory
- [ ] Demonstrate semantic search retrieval
- [ ] Track LLM costs per workflow run
- [ ] Set up alerts for error rate > 5%
- [ ] Document error handling strategy

---

## 8. Advanced Topics (Self-Study)

### 8.1 Dynamic Task Decomposition

**Pattern:** BabyAGI-inspired autonomous task breakdown

**Key Concepts:**
- Task creation agent: generates subtasks from objectives
- Task prioritization agent: orders tasks by dependencies
- Task execution agent: routes to appropriate specialist

**Reference:** langgraph_implementation_patterns.md Section 6.5

**Time:** 8-10 hours

### 8.2 Consensus Through Debate

**Pattern:** Multi-agent verification via iterative refinement

**Key Concepts:**
- Multiple agents solve problem independently
- Agents review each other's solutions
- Iterative debate rounds
- Voting mechanism for consensus

**Use Cases:**
- Code review (syntax, security, logic agents)
- Fact checking (multiple research agents)
- Critical decisions (healthcare, finance)

**Reference:** recommendations_report.md lines 962-1087

**Time:** 6-8 hours

### 8.3 Contract Net Task Allocation

**Pattern:** Competitive bidding for task assignment

**Key Concepts:**
- Call for proposals (CFP) broadcast
- Agents bid with cost/time/confidence estimates
- Coordinator selects best proposal
- Load balancing across agents

**Use Cases:**
- Large agent pools (10+)
- Heterogeneous agent capabilities
- Cost optimization

**Reference:** recommendations_report.md lines 817-959

**Time:** 6-8 hours

### 8.4 Adaptive Communication Filtering

**Pattern:** Relevance-based message filtering for efficiency

**Key Concepts:**
- Semantic similarity scoring
- Temporal recency weighting
- Token budget management
- 30-40% communication overhead reduction

**Use Cases:**
- Large teams (10+ agents)
- Token optimization
- Latency improvement

**Reference:** recommendations_report.md lines 1091-1217

**Time:** 6-8 hours

---

## 9. Capstone Project: Research Assistant

### 9.1 Project Overview

**Goal:** Build production-ready research assistant with 4 specialized agents

**Duration:** 10-15 hours

**Requirements:**
- Supervisor pattern coordination
- Multi-layer memory (short-term + vector DB)
- RetryPolicy on all LLM nodes
- PostgreSQL checkpointing
- Structured logging
- Cost tracking
- LangSmith traces

### 9.2 Architecture

```
Supervisor Agent
  ├─> Research Agent (web search, paper retrieval)
  ├─> Analysis Agent (summarization, synthesis)
  ├─> Validation Agent (fact checking, quality)
  └─> Writer Agent (report generation)
```

### 9.3 Core Features

**1. Research Agent:**
- Tools: Tavily search, arXiv API, Wikipedia
- Capability: gather information from multiple sources
- Return: structured list of sources with summaries

**2. Analysis Agent:**
- Tools: summarize, extract key points, identify themes
- Capability: synthesize information from research
- Return: organized analysis with themes

**3. Validation Agent:**
- Tools: fact checker, citation validator, quality scorer
- Capability: verify accuracy and quality
- Return: validation report with confidence score

**4. Writer Agent:**
- Tools: format report, create citations, generate markdown
- Capability: produce final deliverable
- Return: formatted research report

**5. Supervisor Agent:**
- Handoff tools: delegate to each specialist
- Workflow logic:
  1. Receive user query
  2. Delegate to Research Agent
  3. Delegate to Analysis Agent with research results
  4. Delegate to Validation Agent with analysis
  5. If validation passes (confidence > 0.7), delegate to Writer Agent
  6. If validation fails, return to Research or Analysis with feedback
  7. Return final report to user

### 9.4 State Schema

```python
class ResearchState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    research_results: list[dict]
    analysis: dict
    validation_report: dict
    final_report: str
    current_agent: str
    iteration_count: int
    max_iterations: int  # Prevent infinite loops
```

### 9.5 Implementation Steps

**Phase 1: Basic Workflow (4-5 hours)**
1. Create 4 agent nodes with basic tools
2. Implement supervisor with handoff tools
3. Build linear workflow: research → analysis → writer
4. Test with simple query

**Phase 2: Validation Loop (2-3 hours)**
1. Add validation agent
2. Implement conditional routing based on confidence
3. Add feedback loop: validator → research/analysis
4. Test with query requiring fact checking

**Phase 3: Production Features (3-4 hours)**
1. Add RetryPolicy to all LLM nodes
2. Configure PostgreSQL checkpointing
3. Integrate ChromaDB for memory
4. Add structured logging
5. Implement cost tracking

**Phase 4: Testing & Polish (2-3 hours)**
1. Test with 5 diverse queries
2. Verify LangSmith traces
3. Check cost per query
4. Document usage and examples

### 9.6 Example Usage

```python
assistant = create_research_assistant()

query = """Research the latest advancements in multi-agent AI systems
from 2024-2025. Focus on coordination patterns, real-world applications,
and production challenges. Provide a 500-word summary with citations."""

config = {"configurable": {"thread_id": "research-001"}}

result = assistant.invoke(
    {"query": query, "max_iterations": 10},
    config=config
)

print(result["final_report"])
```

**Expected Output:**
```markdown
# Multi-Agent AI Systems: Recent Advancements (2024-2025)

## Overview
[Summary paragraph]

## Coordination Patterns
[Analysis of supervisor, hierarchical, network patterns]

## Real-World Applications
[Production use cases with citations]

## Challenges
[Technical and operational challenges]

## References
1. Smith et al. (2024) - Multi-Agent Collaboration Mechanisms
2. Johnson (2025) - Production Multi-Agent Systems at Scale
...
```

### 9.7 Testing Scenarios

**Scenario 1: Simple Query**
- Query: "What is LangGraph?"
- Expected: Research → Analysis → Writer (no validation issues)
- Validation: Single-pass completion, cost < $0.10

**Scenario 2: Fact-Checking Required**
- Query: "What was the GDP of China in 2023?"
- Expected: Research → Analysis → Validation → (if wrong) Research → Writer
- Validation: Correct facts, citations present

**Scenario 3: Multi-Source Synthesis**
- Query: "Compare AutoGen, CrewAI, and LangGraph frameworks"
- Expected: Research (3 sources) → Analysis (comparison) → Validation → Writer
- Validation: All 3 frameworks covered, balanced comparison

**Scenario 4: Complex Research**
- Query: "Analyze the impact of transformer architecture on NLP (2017-2025)"
- Expected: Multiple research iterations, deep analysis, comprehensive report
- Validation: 8+ sources, timeline coverage, technical depth

**Scenario 5: Interruption and Resume**
- Query: Long research task
- Action: Pause mid-workflow, resume later
- Validation: Checkpointing works, no duplicate work

### 9.8 Evaluation Rubric

**Functionality (40 points):**
- [ ] 4 specialized agents operational (10 pts)
- [ ] Supervisor routes correctly (10 pts)
- [ ] Validation loop functions (10 pts)
- [ ] Final report quality high (10 pts)

**Production Features (30 points):**
- [ ] RetryPolicy configured (5 pts)
- [ ] Checkpointing enabled (5 pts)
- [ ] Vector memory integrated (5 pts)
- [ ] Structured logging (5 pts)
- [ ] Cost tracking (5 pts)
- [ ] LangSmith traces visible (5 pts)

**Code Quality (20 points):**
- [ ] Clean state schema (5 pts)
- [ ] Proper error handling (5 pts)
- [ ] Tool schemas documented (5 pts)
- [ ] Modular design (5 pts)

**Documentation (10 points):**
- [ ] Usage examples (3 pts)
- [ ] Architecture diagram (3 pts)
- [ ] Configuration guide (4 pts)

**Total:** 100 points

**Passing Score:** 70+ points

---

## 10. Resources

### 10.1 Official Documentation

**LangGraph:**
- Docs: https://langchain-ai.github.io/langgraph/
- Tutorials: https://langchain-ai.github.io/langgraph/tutorials/
- API Reference: https://langchain-ai.github.io/langgraph/reference/

**LangChain:**
- Docs: https://python.langchain.com/docs/
- Tools: https://python.langchain.com/docs/integrations/tools/

**LangSmith:**
- Platform: https://smith.langchain.com/
- Tracing Guide: https://docs.smith.langchain.com/

### 10.2 MyAgents Reference Materials

**Implementation Patterns:**
- File: `/docs/research/consolidated/langgraph_implementation_patterns.md`
- Purpose: Code-focused patterns with examples
- Use: Reference for specific pattern implementations

**Recommendations Report:**
- File: `/docs/research/recommendations_report.md`
- Purpose: Prioritized recommendations with roadmap
- Use: Understand production requirements

**Consolidation Map:**
- File: `/docs/research/consolidation_map.md`
- Purpose: Pattern catalog and cross-references
- Use: Navigate between documents

### 10.3 Example Code

**Echo Agent (Starting Point):**
- File: `/backend/services/agents/src/workflows/echo_agent.py`
- Lines: 302 lines total
- Features: Basic graph, LangSmith integration, logging

**Key Sections:**
- State definition: lines 134-138
- Node functions: lines 162-206
- Graph construction: lines 209-221
- LangSmith setup: lines 50-127

### 10.4 Tools and APIs

**LLM Providers:**
- Google Gemini: https://ai.google.dev/ (recommended for MyAgents)
- OpenAI: https://platform.openai.com/
- Anthropic Claude: https://www.anthropic.com/

**Search APIs:**
- Tavily: https://tavily.com/ (AI-optimized search)
- SerpAPI: https://serpapi.com/ (Google search wrapper)

**Vector Databases:**
- ChromaDB: https://www.trychroma.com/ (local, easy setup)
- Pinecone: https://www.pinecone.io/ (cloud, production)
- Weaviate: https://weaviate.io/ (open source, scalable)

**Observability:**
- LangSmith: https://smith.langchain.com/ (built-in)
- Weights & Biases: https://wandb.ai/ (experiment tracking)

### 10.5 Community and Support

**LangChain Discord:**
- Invite: https://discord.gg/langchain
- Channels: #langgraph, #help, #show-and-tell

**GitHub Discussions:**
- LangGraph: https://github.com/langchain-ai/langgraph/discussions
- LangChain: https://github.com/langchain-ai/langchain/discussions

**Stack Overflow:**
- Tags: [langgraph], [langchain], [multi-agent-systems]

### 10.6 Learning Resources

**Academic Papers:**
- Multi-Agent Collaboration Mechanisms (arXiv:2501.06322)
- Multi-Agent Cooperative Decision-Making (arXiv:2503.13415)
- LLM Multi-Agent Systems Challenges (arXiv:2402.03578)

**Blogs and Tutorials:**
- LangChain Blog: https://blog.langchain.dev/
- LangGraph Tutorials: Official tutorial series
- Real Python: Multi-agent systems articles

### 10.7 Next Steps After Completion

**Immediate:**
1. Deploy capstone project to production (Cloud Run, AWS Lambda)
2. Monitor performance and costs for 1 week
3. Iterate based on real usage patterns

**Short-Term (1-3 months):**
1. Implement advanced topics (task decomposition, consensus)
2. Scale to 8+ agents with hierarchical teams
3. Add domain-specific tools for your use case

**Long-Term (3-6 months):**
1. Contribute patterns back to LangGraph community
2. Build agent evaluation framework
3. Research adaptive communication for large teams

---

## Completion

**Congratulations!** Upon finishing this guide, you will have:

- Built 5+ progressively complex agent systems
- Mastered LangGraph state management and coordination patterns
- Implemented production features (retry, observability, memory)
- Created a working research assistant with 4 agents
- Developed expertise transitioning from data engineering to AI engineering

**Key Takeaway:** Multi-agent systems are data pipelines for decision-making. Your data engineering background (state management, error handling, observability) transfers directly to AI agent development.

**Next Role:** AI Engineer, ML Engineer (Agents), LLM Engineer

**Document Status:** Complete
**Total Lines:** ~1850
**Modules:** 5
**Hands-On Exercises:** 12
**Capstone Project:** 1 (Research Assistant)
**Estimated Hours:** 40-60 hours
