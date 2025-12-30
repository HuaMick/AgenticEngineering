"""Cleaner agent workflow for safe codebase cleanup.

This agent operates in two distinct modes:
1. IDENTIFY: Scan codebase for cleanup targets, report to live plan (NO deletions)
2. EXECUTE: Process approved targets from voting, perform deletions with safety checks

The separation ensures multi-agent consensus before any destructive operations.
"""
from typing import TypedDict, Annotated, Any, Dict, Optional, List
from pathlib import Path
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langsmith import traceable
from myagents.backend.services.agents.tools import get_all_tools, get_tool_by_name
from myagents.backend.services.agents.config import GEMINI_MODEL, ensure_log_dir
from myagents.backend.services.agents.workflows.secrets_workflow import get_secret
from myagents.backend.services.agents.domains.plan_management import PlanManager


def log_cleaner_decision(message: str, mode: str = "identify"):
    """Log cleaner agent decisions to file with timestamp."""
    log_dir = ensure_log_dir()
    log_filename = f"{datetime.now().strftime('%Y%m%d')}_cleaner_agent_{mode}.log"
    log_path = log_dir / log_filename
    timestamp = datetime.now().isoformat()
    try:
        with open(log_path, "a") as f:
            f.write(f"{timestamp} | {message}\n")
    except Exception as e:
        print(f"Warning: Failed to write to cleaner log: {e}")


class CleanerState(TypedDict):
    """State for cleaner agent workflow.

    - messages: Conversation history
    - user_input: Current user input
    - response: Agent's final response
    - iteration_count: Loop protection
    - mode: 'identify' or 'execute'
    - live_plan_path: Path to the live plan YAML file
    - agent_id: Agent number for identification (1, 2, 3)
    - targets: Identified or approved targets
    """
    messages: Annotated[list, add_messages]
    user_input: str
    response: str
    iteration_count: int
    mode: str
    live_plan_path: str
    agent_id: int
    targets: List[Dict[str, Any]]


# System prompts for different modes
IDENTIFY_SYSTEM_PROMPT = """You are a cleaner identification agent (agent #{agent_id}).

Your ONLY job is to identify potential cleanup targets. You do NOT remove anything.
Multiple identification agents run in parallel. Your targets will be compared with
other agents' targets using a voting system. Only unanimous targets get cleaned.

Focus areas:
1. Dead code: Unused imports, unreachable code, commented-out blocks
2. Redundancies: Duplicate files, duplicate functions
3. Overengineering: Unnecessary abstractions
4. Wrong location: Files in incorrect folders
5. Leftover folders: Directories remaining after refactors

CRITICAL RULES:
- NEVER flag lock files (uv.lock, poetry.lock, package-lock.json, yarn.lock)
- NEVER flag config files (pyproject.toml, Dockerfile*, cloudbuild.yaml)
- NEVER flag README.md files
- Be CONSERVATIVE - when in doubt, do NOT flag

After analysis, report your findings in a structured format.
"""

EXECUTE_SYSTEM_PROMPT = """You are a cleaner execution agent.

You execute cleanup of ONLY the targets that have been unanimously approved (3/3 votes).
You do NOT identify new targets. Process only the approved_targets list from the live plan.

Process:
1. Read approved_targets from live plan
2. Verify each target against preserved files list
3. Create a checkpoint commit before changes
4. Delete each approved target
5. Verify no import errors introduced
6. Update live plan with results
7. Commit successful changes

CRITICAL RULES:
- STOP if any preserved file is in the approved list
- Always commit before making changes
- Skip failed targets, continue with others
- Report all actions taken
"""


def create_cleaner_agent(mode: str = "identify"):
    """Create and configure the cleaner agent workflow.

    Args:
        mode: Either 'identify' or 'execute'

    Returns:
        Compiled LangGraph workflow
    """
    log_cleaner_decision(f"Creating cleaner agent in {mode} mode", mode)

    # Initialize LLM
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
    log_cleaner_decision(f"LLM initialized with {len(all_tools)} tools", mode)

    @traceable(name="cleaner_process_input")
    def process_input(state: CleanerState) -> Dict[str, Any]:
        """Process user input and set up context based on mode."""
        user_input = state["user_input"]
        agent_mode = state.get("mode", "identify")
        agent_id = state.get("agent_id", 1)

        # Build system message based on mode
        if agent_mode == "identify":
            system_content = IDENTIFY_SYSTEM_PROMPT.format(agent_id=agent_id)
        else:
            system_content = EXECUTE_SYSTEM_PROMPT

        log_cleaner_decision(f"Processing input in {agent_mode} mode: {user_input[:50]}...", agent_mode)

        return {
            "messages": [
                SystemMessage(content=system_content),
                HumanMessage(content=user_input)
            ]
        }

    @traceable(name="cleaner_generate_response")
    def generate_response(state: CleanerState) -> Dict[str, Any]:
        """Generate response using LLM with tools."""
        messages = state["messages"]
        agent_mode = state.get("mode", "identify")

        log_cleaner_decision(f"Generating response (message count: {len(messages)})", agent_mode)

        response = llm_with_tools.invoke(messages)
        has_tool_calls = hasattr(response, 'tool_calls') and len(response.tool_calls) > 0
        log_cleaner_decision(f"LLM response generated (has_tool_calls: {has_tool_calls})", agent_mode)

        updates = {"messages": [response]}
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            updates["response"] = response.content

        return updates

    def should_continue(state: CleanerState) -> str:
        """Check if we should continue to tool execution or end."""
        agent_mode = state.get("mode", "identify")

        if state.get("iteration_count", 0) >= 10:
            log_cleaner_decision("Iteration limit exceeded - routing to END", agent_mode)
            return "end"

        last_msg = state["messages"][-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "execute_tools"

        return "end"

    @traceable(name="cleaner_execute_tools")
    def execute_tools(state: CleanerState) -> CleanerState:
        """Execute requested tools with error handling."""
        agent_mode = state.get("mode", "identify")
        tool_calls = state["messages"][-1].tool_calls
        tool_messages = []

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            try:
                tool = get_tool_by_name(tool_name)
                result = tool.invoke(tool_args)
                tool_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                )
            except Exception as e:
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: {type(e).__name__}: {str(e)}",
                        tool_call_id=tool_call["id"],
                        is_error=True
                    )
                )

        new_iteration_count = state.get("iteration_count", 0) + 1
        log_cleaner_decision(f"Tool execution complete (iteration {new_iteration_count})", agent_mode)

        return {"messages": tool_messages, "iteration_count": new_iteration_count}  # type: ignore[typeddict-item]

    # Build graph
    workflow = StateGraph(CleanerState)
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

    app = workflow.compile()
    log_cleaner_decision(f"Cleaner agent workflow compiled successfully ({mode} mode)", mode)
    return app


# Singleton patterns for each mode
_identify_workflow = None
_execute_workflow = None


def get_identify_workflow():
    """Get or create the identification workflow singleton."""
    global _identify_workflow
    if _identify_workflow is None:
        _identify_workflow = create_cleaner_agent("identify")
    return _identify_workflow


def get_execute_workflow():
    """Get or create the execution workflow singleton."""
    global _execute_workflow
    if _execute_workflow is None:
        _execute_workflow = create_cleaner_agent("execute")
    return _execute_workflow


@traceable(name="cleaner_identify")
def run_cleaner_identify(
    live_plan_path: str,
    agent_id: int,
    scan_instruction: str = "Scan the codebase for cleanup targets"
) -> tuple[str, dict]:
    """Run the cleaner agent in identification mode.

    Args:
        live_plan_path: Path to the live plan YAML file
        agent_id: The agent number (1, 2, or 3) for voting
        scan_instruction: Optional custom scan instruction

    Returns:
        Tuple of (response, updated_state)
    """
    log_cleaner_decision(f"=== Starting cleaner identification (agent {agent_id}) ===", "identify")
    log_cleaner_decision(f"Live plan path: {live_plan_path}", "identify")

    workflow = get_identify_workflow()

    state = {
        "messages": [],
        "user_input": scan_instruction,
        "response": "",
        "iteration_count": 0,
        "mode": "identify",
        "live_plan_path": live_plan_path,
        "agent_id": agent_id,
        "targets": []
    }

    try:
        result = workflow.invoke(state)
        response = result["response"]

        # Record findings to live plan
        if live_plan_path:
            try:
                plan_manager = PlanManager(live_plan_path)
                plan_manager.record_agent_output(
                    agent_id=f"cleaner-{agent_id}",
                    output_type="identification",
                    data={
                        "response": response,
                        "targets": result.get("targets", [])
                    }
                )
            except Exception as e:
                log_cleaner_decision(f"Failed to update live plan: {e}", "identify")

        log_cleaner_decision(f"=== Cleaner identification completed (agent {agent_id}) ===", "identify")
        return response, result

    except Exception as e:
        error_msg = f"ERROR in cleaner identify: {str(e)}"
        log_cleaner_decision(error_msg, "identify")
        raise


@traceable(name="cleaner_execute")
def run_cleaner_execute(live_plan_path: str) -> tuple[str, dict]:
    """Run the cleaner agent in execution mode.

    Args:
        live_plan_path: Path to the live plan YAML file containing approved_targets

    Returns:
        Tuple of (response, updated_state)
    """
    log_cleaner_decision(f"=== Starting cleaner execution ===", "execute")
    log_cleaner_decision(f"Live plan path: {live_plan_path}", "execute")

    # Read approved targets from plan
    plan_manager = PlanManager(live_plan_path)
    plan = plan_manager.read_plan()

    approved_targets = plan.get("cleaner_voting", {}).get("approved_targets", [])
    log_cleaner_decision(f"Found {len(approved_targets)} approved targets", "execute")

    if not approved_targets:
        return "No approved targets to process. Cleanup complete with no actions.", {}

    workflow = get_execute_workflow()

    # Build execution instruction
    targets_desc = "\n".join([f"- {t.get('path', 'unknown')}: {t.get('rationale', 'no reason')}"
                              for t in approved_targets])
    instruction = f"""Process these approved cleanup targets:

{targets_desc}

For each target:
1. Verify it's not a preserved file
2. Delete the file or folder
3. Report success or failure
"""

    state = {
        "messages": [],
        "user_input": instruction,
        "response": "",
        "iteration_count": 0,
        "mode": "execute",
        "live_plan_path": live_plan_path,
        "agent_id": 0,  # Not used in execute mode
        "targets": approved_targets
    }

    try:
        result = workflow.invoke(state)
        response = result["response"]

        # Record execution results to live plan
        plan_manager.record_agent_output(
            agent_id="cleaner-execute",
            output_type="execution_results",
            data={
                "response": response,
                "processed_targets": len(approved_targets)
            }
        )

        log_cleaner_decision(f"=== Cleaner execution completed ===", "execute")
        return response, result

    except Exception as e:
        error_msg = f"ERROR in cleaner execute: {str(e)}"
        log_cleaner_decision(error_msg, "execute")
        raise
