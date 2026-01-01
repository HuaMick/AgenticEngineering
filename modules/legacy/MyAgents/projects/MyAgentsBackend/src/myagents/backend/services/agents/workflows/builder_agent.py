from typing import TypedDict, Annotated, Any, Dict, Optional
from pathlib import Path
from datetime import datetime
import os
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langsmith import traceable
from myagents.backend.services.agents.tools import get_all_tools, get_tool_by_name
from myagents.backend.services.agents.config import GEMINI_MODEL, ensure_log_dir
from myagents.backend.services.agents.workflows.secrets_workflow import get_secret

# Decision logging helper (inline - simple utility)
def log_decision(message: str):
    """Log agent decisions to file with timestamp."""
    log_dir = ensure_log_dir()
    log_filename = f"{datetime.now().strftime('%Y%m%d')}_builder_agent.log"
    log_path = log_dir / log_filename
    timestamp = datetime.now().isoformat()
    try:
        with open(log_path, "a") as f:
            f.write(f"{timestamp} | {message}\n")
    except Exception as e:
        print(f"Warning: Failed to write to log: {e}")


class AgentState(TypedDict):
    """State for builder agent workflow.

    - messages: Conversation history (persists across turns)
    - user_input: Current user input (per-turn)
    - response: Agent's final response (per-turn)
    - iteration_count: Loop protection counter (per-turn, resets each turn)
    """
    messages: Annotated[list, add_messages]
    user_input: str
    response: str
    iteration_count: int  # Prevent infinite loops within a turn


def create_builder_agent():
    """
    Create and configure the builder agent workflow.

    Returns:
        Compiled LangGraph workflow
    """
    # Initialize LLM with tools INSIDE factory (not at module level)
    # Explicitly pass API key to avoid ADC timeout issues
    # Try GEMINI_API_KEY first, fall back to GOOGLE_API_KEY (backward compatibility)
    try:
        api_key = get_secret("GEMINI_API_KEY")
    except ValueError:
        api_key = get_secret("GOOGLE_API_KEY")

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0,
        google_api_key=api_key
    )
    all_tools = get_all_tools()
    llm_with_tools = llm.bind_tools(all_tools)
    log_decision(f"LLM initialized with {len(all_tools)} tools")

    # Define workflow nodes as nested functions (can access llm_with_tools via closure)
    @traceable(name="process_input_node")
    def process_input(state: AgentState) -> Dict[str, Any]:
        """Process user input and add to message history."""
        user_input = state["user_input"]
        log_decision(f"Processing input: {user_input[:50]}...")
        return {"messages": [HumanMessage(content=user_input)]}

    @traceable(name="generate_response_node")
    def generate_response(state: AgentState) -> Dict[str, Any]:
        """Generate response using LLM with tool-calling support."""
        messages = state["messages"]
        log_decision(f"Generating response (tools enabled, message count: {len(messages)})")

        response = llm_with_tools.invoke(messages)
        has_tool_calls = hasattr(response, 'tool_calls') and len(response.tool_calls) > 0
        log_decision(f"LLM response generated (has tool_calls: {has_tool_calls})")

        # CRITICAL: Extract final response text when no tool calls
        # This sets state["response"] for the CLI to display
        updates = {"messages": [response]}
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            # No more tool calls - this is the final response
            updates["response"] = response.content

        return updates

    def should_continue(state: AgentState) -> str:
        """Check if we should continue to tool execution or end.

        CRITICAL: Also checks iteration limit to prevent infinite loops.
        When limit exceeded, route to END (not execute_tools).
        """
        # FIRST: Check iteration limit BEFORE checking for tool calls
        # This prevents the loop from continuing when limit is exceeded
        # Use >= to enforce exactly 10 iterations (0-9)
        if state.get("iteration_count", 0) >= 10:
            log_decision("Iteration limit exceeded - routing to END")
            return "end"

        # SECOND: Check if there are tool calls to execute
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "execute_tools"

        return "end"

    @traceable(name="execute_tools_node")
    def execute_tools(state: AgentState) -> AgentState:
        """Execute requested tools with error handling.

        CRITICAL: Increments iteration_count AFTER execution.
        The should_continue() function checks the limit and routes to END if exceeded.
        Returns NEW dict with tool messages (no state mutation).
        """
        # Execute each tool call with individual error handling
        tool_calls = state["messages"][-1].tool_calls
        tool_messages = []

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            try:
                # Look up and execute tool
                tool = get_tool_by_name(tool_name)
                result = tool.invoke(tool_args)

                # Add success result
                tool_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                )

            except FileNotFoundError as e:
                # File doesn't exist
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: File not found - {str(e)}",
                        tool_call_id=tool_call["id"],
                        is_error=True
                    )
                )

            except ValueError as e:
                # Validation failures (path outside directory, file too large, text not found)
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: {str(e)}",
                        tool_call_id=tool_call["id"],
                        is_error=True
                    )
                )

            except Exception as e:
                # Catch-all for unexpected errors
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: Tool execution failed - {type(e).__name__}: {str(e)}",
                        tool_call_id=tool_call["id"],
                        is_error=True
                    )
                )

        # CRITICAL: Increment iteration count AFTER all tools execute
        # This count is checked by should_continue() to prevent infinite loops
        new_iteration_count = state.get("iteration_count", 0) + 1
        log_decision(f"Tool execution complete (iteration {new_iteration_count})")

        # Return NEW dict with tool messages and updated iteration count
        return {"messages": tool_messages, "iteration_count": new_iteration_count}  # type: ignore[typeddict-item]

    # Build graph
    workflow = StateGraph(AgentState)
    workflow.add_node("process_input", process_input)
    workflow.add_node("generate_response", generate_response)
    workflow.add_node("execute_tools", execute_tools)

    workflow.set_entry_point("process_input")
    workflow.add_edge("process_input", "generate_response")
    workflow.add_conditional_edges(
        "generate_response",
        should_continue,
        {"execute_tools": "execute_tools", "end": END}
    )
    workflow.add_edge("execute_tools", "generate_response")

    # Compile and return
    app = workflow.compile()
    log_decision("Builder agent workflow compiled successfully")
    return app

# Singleton pattern
_agent_workflow = None

def get_agent_workflow():
    """Get or create the agent workflow singleton."""
    global _agent_workflow
    if _agent_workflow is None:
        _agent_workflow = create_builder_agent()
    return _agent_workflow

@traceable(name="builder_agent")
def run_builder_agent(user_input: str, state: Optional[dict] = None) -> tuple[str, dict]:
    """
    Run the builder agent with user input.

    Args:
        user_input: User's message to the agent
        state: Optional state from previous turn (for multi-turn conversations)

    Returns:
        Tuple of (response, updated_state)
    """
    log_decision("=== Starting builder agent run ===")
    log_decision(f"User input received: {user_input}")

    try:
        # Get workflow using singleton pattern (initializes on first call)
        workflow = get_agent_workflow()

        # Initialize or use existing state
        if state is None:
            state = {
                "messages": [],
                "user_input": "",
                "response": "",
                "iteration_count": 0
            }

        # Update input for this turn
        state["user_input"] = user_input

        # CRITICAL: Reset iteration count at START of each turn
        state["iteration_count"] = 0

        # Run workflow
        log_decision("Invoking workflow...")
        result = workflow.invoke(state)

        # Extract response
        response = result["response"]
        log_decision("Workflow completed successfully")
        log_decision(f"Final response: {response[:50]}...")
        log_decision("=== Builder agent run completed ===")

        return response, result

    except Exception as e:
        error_msg = f"ERROR in builder agent: {str(e)}"
        log_decision(error_msg)
        log_decision("=== Builder agent run failed ===")
        raise


# Backward compatibility aliases
create_coding_agent = create_builder_agent
run_coding_agent = run_builder_agent
