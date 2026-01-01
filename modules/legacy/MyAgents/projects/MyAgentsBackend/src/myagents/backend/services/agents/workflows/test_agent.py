"""Test agent workflow for test execution and auditing.

This agent operates in three distinct modes:
1. RUNNER: Execute tests using pytest, report results to live plan
2. AUDIT: Review test quality, identify skip patterns and reward hacking
3. USER_SIMULATOR: Execute user stories from documentation perspective

The separation allows specialized agents to focus on their specific roles.
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


def log_test_decision(message: str, mode: str = "runner"):
    """Log test agent decisions to file with timestamp."""
    log_dir = ensure_log_dir()
    log_filename = f"{datetime.now().strftime('%Y%m%d')}_test_agent_{mode}.log"
    log_path = log_dir / log_filename
    timestamp = datetime.now().isoformat()
    try:
        with open(log_path, "a") as f:
            f.write(f"{timestamp} | {message}\n")
    except Exception as e:
        print(f"Warning: Failed to write to test log: {e}")


class TestAgentState(TypedDict):
    """State for test agent workflow."""
    messages: Annotated[list, add_messages]
    user_input: str
    response: str
    iteration_count: int
    mode: str  # 'runner', 'audit', 'user_simulator'
    live_plan_path: str
    test_targets: List[str]


# System prompts for different modes
RUNNER_SYSTEM_PROMPT = """You are a test execution agent.

Your job is to execute tests using pytest and report their results accurately.
You DO NOT fix tests or application code - you only OBSERVE and REPORT.

Process:
1. Discover tests based on the provided targets
2. Execute pytest with verbose output
3. Count PASS, FAIL, SKIP results
4. For failures: Extract error messages and stack traces
5. Report results to the live plan

A failed test is a SUCCESSFUL discovery of a bug. Report failures clearly and proudly.
"""

AUDIT_SYSTEM_PROMPT = """You are a test audit agent.

Your job is to review test code quality and identify issues:
- Silent failures (errors not properly reported)
- Reward hacking (tests that game metrics without real coverage)
- Unjustified skip patterns (skips that should be fixable)
- Structural issues (duplicate tests, wrong locations)

For each issue found, document:
- File and location
- Issue type
- Severity
- Recommendation

DO NOT fix anything. Your role is observation and reporting only.
"""

USER_SIMULATOR_SYSTEM_PROMPT = """You are a user simulator agent.

Your job is to test the system from a user's perspective by following ONLY
the documentation. You simulate a new user who has no insider knowledge.

Process:
1. Read the provided user story requirements
2. Follow ONLY the documented steps (README, SETUP.md, etc.)
3. Execute commands exactly as documented
4. Report any gaps between documentation and reality
5. Note any confusion points a new user would encounter

DO NOT use any knowledge beyond what's in the documentation.
Report both successes and failures clearly.
"""


def create_test_agent(mode: str = "runner"):
    """Create and configure the test agent workflow.

    Args:
        mode: 'runner', 'audit', or 'user_simulator'

    Returns:
        Compiled LangGraph workflow
    """
    log_test_decision(f"Creating test agent in {mode} mode", mode)

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
    log_test_decision(f"LLM initialized with {len(all_tools)} tools", mode)

    @traceable(name="test_process_input")
    def process_input(state: TestAgentState) -> Dict[str, Any]:
        """Process user input and set up context based on mode."""
        user_input = state["user_input"]
        agent_mode = state.get("mode", "runner")

        if agent_mode == "runner":
            system_content = RUNNER_SYSTEM_PROMPT
        elif agent_mode == "audit":
            system_content = AUDIT_SYSTEM_PROMPT
        else:
            system_content = USER_SIMULATOR_SYSTEM_PROMPT

        log_test_decision(f"Processing input in {agent_mode} mode", agent_mode)

        return {
            "messages": [
                SystemMessage(content=system_content),
                HumanMessage(content=user_input)
            ]
        }

    @traceable(name="test_generate_response")
    def generate_response(state: TestAgentState) -> Dict[str, Any]:
        """Generate response using LLM with tools."""
        messages = state["messages"]
        agent_mode = state.get("mode", "runner")

        response = llm_with_tools.invoke(messages)
        has_tool_calls = hasattr(response, 'tool_calls') and len(response.tool_calls) > 0
        log_test_decision(f"LLM response generated (has_tool_calls: {has_tool_calls})", agent_mode)

        updates = {"messages": [response]}
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            updates["response"] = response.content

        return updates

    def should_continue(state: TestAgentState) -> str:
        """Check if we should continue to tool execution or end."""
        if state.get("iteration_count", 0) >= 10:
            return "end"

        last_msg = state["messages"][-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "execute_tools"

        return "end"

    @traceable(name="test_execute_tools")
    def execute_tools(state: TestAgentState) -> TestAgentState:
        """Execute requested tools."""
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
        return {"messages": tool_messages, "iteration_count": new_iteration_count}  # type: ignore[typeddict-item]

    # Build graph
    workflow = StateGraph(TestAgentState)
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
    log_test_decision(f"Test agent workflow compiled ({mode} mode)", mode)
    return app


# Singleton patterns
_runner_workflow = None
_audit_workflow = None
_user_sim_workflow = None


def get_runner_workflow():
    global _runner_workflow
    if _runner_workflow is None:
        _runner_workflow = create_test_agent("runner")
    return _runner_workflow


def get_audit_workflow():
    global _audit_workflow
    if _audit_workflow is None:
        _audit_workflow = create_test_agent("audit")
    return _audit_workflow


def get_user_sim_workflow():
    global _user_sim_workflow
    if _user_sim_workflow is None:
        _user_sim_workflow = create_test_agent("user_simulator")
    return _user_sim_workflow


@traceable(name="test_runner")
def run_test_runner(
    live_plan_path: str,
    test_targets: Optional[List[str]] = None,
    instruction: str = "Run the test suite and report results"
) -> tuple[str, dict]:
    """Run the test agent in runner mode.

    Args:
        live_plan_path: Path to the live plan YAML file
        test_targets: Optional list of test paths/markers to run
        instruction: Custom test instruction

    Returns:
        Tuple of (response, updated_state)
    """
    log_test_decision(f"=== Starting test runner ===", "runner")

    workflow = get_runner_workflow()

    if test_targets:
        targets_str = ", ".join(test_targets)
        instruction = f"Run tests for: {targets_str}\n\n{instruction}"

    state = {
        "messages": [],
        "user_input": instruction,
        "response": "",
        "iteration_count": 0,
        "mode": "runner",
        "live_plan_path": live_plan_path,
        "test_targets": test_targets or []
    }

    try:
        result = workflow.invoke(state)
        response = result["response"]

        if live_plan_path:
            try:
                plan_manager = PlanManager(live_plan_path)
                plan_manager.record_agent_output(
                    agent_id="test-runner",
                    output_type="test_results",
                    data={"response": response}
                )
            except Exception as e:
                log_test_decision(f"Failed to update live plan: {e}", "runner")

        log_test_decision(f"=== Test runner completed ===", "runner")
        return response, result

    except Exception as e:
        log_test_decision(f"ERROR in test runner: {str(e)}", "runner")
        raise


@traceable(name="test_audit")
def run_test_audit(
    live_plan_path: str,
    test_package: Optional[str] = None,
    instruction: str = "Audit test quality and identify issues"
) -> tuple[str, dict]:
    """Run the test agent in audit mode.

    Args:
        live_plan_path: Path to the live plan YAML file
        test_package: Optional specific test package to audit
        instruction: Custom audit instruction

    Returns:
        Tuple of (response, updated_state)
    """
    log_test_decision(f"=== Starting test audit ===", "audit")

    workflow = get_audit_workflow()

    if test_package:
        instruction = f"Audit test package: {test_package}\n\n{instruction}"

    state = {
        "messages": [],
        "user_input": instruction,
        "response": "",
        "iteration_count": 0,
        "mode": "audit",
        "live_plan_path": live_plan_path,
        "test_targets": [test_package] if test_package else []
    }

    try:
        result = workflow.invoke(state)
        response = result["response"]

        if live_plan_path:
            try:
                plan_manager = PlanManager(live_plan_path)
                plan_manager.record_agent_output(
                    agent_id="test-audit",
                    output_type="audit_results",
                    data={"response": response, "package": test_package}
                )
            except Exception as e:
                log_test_decision(f"Failed to update live plan: {e}", "audit")

        log_test_decision(f"=== Test audit completed ===", "audit")
        return response, result

    except Exception as e:
        log_test_decision(f"ERROR in test audit: {str(e)}", "audit")
        raise


@traceable(name="test_user_simulator")
def run_test_user_simulator(
    live_plan_path: str,
    user_story_id: str,
    instruction: str = "Execute user story from documentation perspective"
) -> tuple[str, dict]:
    """Run the test agent in user simulator mode.

    Args:
        live_plan_path: Path to the live plan YAML file
        user_story_id: ID of the user story to simulate
        instruction: Custom simulation instruction

    Returns:
        Tuple of (response, updated_state)
    """
    log_test_decision(f"=== Starting user simulation for {user_story_id} ===", "user_simulator")

    workflow = get_user_sim_workflow()

    full_instruction = f"User Story: {user_story_id}\n\n{instruction}"

    state = {
        "messages": [],
        "user_input": full_instruction,
        "response": "",
        "iteration_count": 0,
        "mode": "user_simulator",
        "live_plan_path": live_plan_path,
        "test_targets": [user_story_id]
    }

    try:
        result = workflow.invoke(state)
        response = result["response"]

        if live_plan_path:
            try:
                plan_manager = PlanManager(live_plan_path)
                plan_manager.record_agent_output(
                    agent_id="test-user-sim",
                    output_type="simulation_results",
                    data={"response": response, "user_story": user_story_id}
                )
            except Exception as e:
                log_test_decision(f"Failed to update live plan: {e}", "user_simulator")

        log_test_decision(f"=== User simulation completed ===", "user_simulator")
        return response, result

    except Exception as e:
        log_test_decision(f"ERROR in user simulator: {str(e)}", "user_simulator")
        raise
