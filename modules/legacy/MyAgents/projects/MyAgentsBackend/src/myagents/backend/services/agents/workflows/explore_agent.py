"""Explore agent workflow for codebase exploration and analysis.

This agent operates in five distinct modes:
1. ARCHITECTURE: Analyze project structure and design patterns
2. FEATURE: Explore specific feature implementations
3. DEPENDENCY: Map dependencies and relationships
4. TEST: Analyze test coverage and patterns
5. SYNTHESIS: Combine findings from all explorers into summary

Each explorer writes findings to the live plan for the synthesizer to aggregate.
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


def log_explore_decision(message: str, mode: str = "architecture"):
    """Log explore agent decisions to file with timestamp."""
    log_dir = ensure_log_dir()
    log_filename = f"{datetime.now().strftime('%Y%m%d')}_explore_agent_{mode}.log"
    log_path = log_dir / log_filename
    timestamp = datetime.now().isoformat()
    try:
        with open(log_path, "a") as f:
            f.write(f"{timestamp} | {message}\n")
    except Exception as e:
        print(f"Warning: Failed to write to explore log: {e}")


class ExploreAgentState(TypedDict):
    """State for explore agent workflow."""
    messages: Annotated[list, add_messages]
    user_input: str
    response: str
    iteration_count: int
    mode: str  # 'architecture', 'feature', 'dependency', 'test', 'synthesis'
    live_plan_path: str
    exploration_scope: str


# System prompts for different exploration modes
ARCHITECTURE_SYSTEM_PROMPT = """You are an architecture exploration agent.

Your job is to analyze the project's architectural structure:
- Directory layout and organization
- Key modules and their responsibilities
- Design patterns used
- Layer separation (frontend/backend/domain)
- Configuration management approach

Report your findings in a structured format suitable for other agents
and for inclusion in the live plan.
"""

FEATURE_SYSTEM_PROMPT = """You are a feature exploration agent.

Your job is to analyze specific feature implementations:
- How features are organized and implemented
- Entry points and API boundaries
- State management approaches
- Integration points between features
- Feature dependencies

Focus on understanding HOW things work, not evaluating quality.
"""

DEPENDENCY_SYSTEM_PROMPT = """You are a dependency exploration agent.

Your job is to map the project's dependencies:
- External package dependencies (from pyproject.toml, requirements.txt)
- Internal module dependencies
- Circular dependency detection
- Version constraints and compatibility
- Optional vs required dependencies

Provide a clear map of what depends on what.
"""

TEST_SYSTEM_PROMPT = """You are a test exploration agent.

Your job is to analyze the testing setup:
- Test directory structure
- Test frameworks and tools used
- Test coverage patterns
- Test categories (unit, integration, e2e)
- Fixtures and test utilities

Focus on understanding the testing approach, not running tests.
"""

SYNTHESIS_SYSTEM_PROMPT = """You are an exploration synthesis agent.

Your job is to combine findings from all other exploration agents:
- Read architecture, feature, dependency, and test findings
- Identify patterns and connections across domains
- Highlight key insights and potential issues
- Create a cohesive summary for the orchestrator

You synthesize - you don't do new exploration.
"""


def create_explore_agent(mode: str = "architecture"):
    """Create and configure the explore agent workflow.

    Args:
        mode: 'architecture', 'feature', 'dependency', 'test', or 'synthesis'

    Returns:
        Compiled LangGraph workflow
    """
    log_explore_decision(f"Creating explore agent in {mode} mode", mode)

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
    log_explore_decision(f"LLM initialized with {len(all_tools)} tools", mode)

    SYSTEM_PROMPTS = {
        "architecture": ARCHITECTURE_SYSTEM_PROMPT,
        "feature": FEATURE_SYSTEM_PROMPT,
        "dependency": DEPENDENCY_SYSTEM_PROMPT,
        "test": TEST_SYSTEM_PROMPT,
        "synthesis": SYNTHESIS_SYSTEM_PROMPT,
    }

    @traceable(name="explore_process_input")
    def process_input(state: ExploreAgentState) -> Dict[str, Any]:
        """Process user input and set up context based on mode."""
        user_input = state["user_input"]
        agent_mode = state.get("mode", "architecture")
        system_content = SYSTEM_PROMPTS.get(agent_mode, ARCHITECTURE_SYSTEM_PROMPT)

        log_explore_decision(f"Processing input in {agent_mode} mode", agent_mode)

        return {
            "messages": [
                SystemMessage(content=system_content),
                HumanMessage(content=user_input)
            ]
        }

    @traceable(name="explore_generate_response")
    def generate_response(state: ExploreAgentState) -> Dict[str, Any]:
        """Generate response using LLM with tools."""
        messages = state["messages"]
        agent_mode = state.get("mode", "architecture")

        response = llm_with_tools.invoke(messages)
        has_tool_calls = hasattr(response, 'tool_calls') and len(response.tool_calls) > 0
        log_explore_decision(f"LLM response generated (has_tool_calls: {has_tool_calls})", agent_mode)

        updates = {"messages": [response]}
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            updates["response"] = response.content

        return updates

    def should_continue(state: ExploreAgentState) -> str:
        """Check if we should continue to tool execution or end."""
        if state.get("iteration_count", 0) >= 15:  # Allow more iterations for exploration
            return "end"

        last_msg = state["messages"][-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "execute_tools"

        return "end"

    @traceable(name="explore_execute_tools")
    def execute_tools(state: ExploreAgentState) -> ExploreAgentState:
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
    workflow = StateGraph(ExploreAgentState)
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
    log_explore_decision(f"Explore agent workflow compiled ({mode} mode)", mode)
    return app


# Singleton patterns for each mode
_arch_workflow = None
_feature_workflow = None
_dep_workflow = None
_test_workflow = None
_synth_workflow = None


def get_arch_workflow():
    global _arch_workflow
    if _arch_workflow is None:
        _arch_workflow = create_explore_agent("architecture")
    return _arch_workflow


def get_feature_workflow():
    global _feature_workflow
    if _feature_workflow is None:
        _feature_workflow = create_explore_agent("feature")
    return _feature_workflow


def get_dep_workflow():
    global _dep_workflow
    if _dep_workflow is None:
        _dep_workflow = create_explore_agent("dependency")
    return _dep_workflow


def get_test_workflow():
    global _test_workflow
    if _test_workflow is None:
        _test_workflow = create_explore_agent("test")
    return _test_workflow


def get_synth_workflow():
    global _synth_workflow
    if _synth_workflow is None:
        _synth_workflow = create_explore_agent("synthesis")
    return _synth_workflow


def _run_explorer(
    mode: str,
    workflow_getter,
    live_plan_path: str,
    instruction: str
) -> tuple[str, dict]:
    """Generic runner for exploration agents."""
    log_explore_decision(f"=== Starting {mode} exploration ===", mode)

    workflow = workflow_getter()

    state = {
        "messages": [],
        "user_input": instruction,
        "response": "",
        "iteration_count": 0,
        "mode": mode,
        "live_plan_path": live_plan_path,
        "exploration_scope": ""
    }

    try:
        result = workflow.invoke(state)
        response = result["response"]

        if live_plan_path:
            try:
                plan_manager = PlanManager(live_plan_path)
                plan_manager.record_agent_output(
                    agent_id=f"explore-{mode}",
                    output_type=f"{mode}_findings",
                    data={"response": response}
                )
            except Exception as e:
                log_explore_decision(f"Failed to update live plan: {e}", mode)

        log_explore_decision(f"=== {mode} exploration completed ===", mode)
        return response, result

    except Exception as e:
        log_explore_decision(f"ERROR in {mode} exploration: {str(e)}", mode)
        raise


@traceable(name="explore_architecture")
def run_explore_architecture(
    live_plan_path: str,
    instruction: str = "Analyze the project architecture and structure"
) -> tuple[str, dict]:
    """Run architecture exploration."""
    return _run_explorer("architecture", get_arch_workflow, live_plan_path, instruction)


@traceable(name="explore_feature")
def run_explore_feature(
    live_plan_path: str,
    feature_name: Optional[str] = None,
    instruction: str = "Explore feature implementations"
) -> tuple[str, dict]:
    """Run feature exploration."""
    if feature_name:
        instruction = f"Focus on feature: {feature_name}\n\n{instruction}"
    return _run_explorer("feature", get_feature_workflow, live_plan_path, instruction)


@traceable(name="explore_dependency")
def run_explore_dependency(
    live_plan_path: str,
    instruction: str = "Map project dependencies"
) -> tuple[str, dict]:
    """Run dependency exploration."""
    return _run_explorer("dependency", get_dep_workflow, live_plan_path, instruction)


@traceable(name="explore_test")
def run_explore_test(
    live_plan_path: str,
    instruction: str = "Analyze testing setup and patterns"
) -> tuple[str, dict]:
    """Run test exploration."""
    return _run_explorer("test", get_test_workflow, live_plan_path, instruction)


@traceable(name="explore_synthesis")
def run_explore_synthesis(
    live_plan_path: str,
    instruction: str = "Synthesize findings from all explorations"
) -> tuple[str, dict]:
    """Run synthesis exploration.

    This should be run after the other explorers have completed
    to aggregate their findings into a cohesive summary.
    """
    # Read existing findings from live plan
    plan_manager = PlanManager(live_plan_path)
    findings_summary = "Previous exploration findings:\n"

    for explorer_type in ["architecture", "feature", "dependency", "test"]:
        finding = plan_manager.get_agent_output(f"explore-{explorer_type}", f"{explorer_type}_findings")
        if finding:
            findings_summary += f"\n## {explorer_type.title()} Findings:\n{finding.get('response', 'N/A')}\n"

    full_instruction = f"{findings_summary}\n\n{instruction}"
    return _run_explorer("synthesis", get_synth_workflow, live_plan_path, full_instruction)
