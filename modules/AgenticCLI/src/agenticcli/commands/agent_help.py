"""Agent-specific help command handler.

Provides quick help output for agent names as positional arguments:
  agentic planner-guidance
  agentic build-python

This is the PRIMARY entrypoint for agents - no file exploration needed.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import yaml


# All known agents - ordered by category
KNOWN_AGENTS = [
    # Planners (7)
    "planner-audit",
    "planner-build",
    "planner-cleaning",
    "planner-guidance",
    "planner-guidance-testing",
    "planner-reviewer",
    "planner-test",
    # Test agents (7)
    "test-audit",
    "test-builder",
    "test-final-output",
    "test-guidance-simulator",
    "test-runner",
    "test-service",
    "test-user-simulator",
    # Orchestration agents (3)
    "orchestration-executor",
    "orchestration-friction",
    "orchestration-planning",
    # Teacher agents (3)
    "teacher-trace-diagnostics",
    "teacher-update-assets",
    "teacher-update-guidance",
    # Build agents (2)
    "build-flutter",
    "build-python",
    # Deploy agents (2)
    "deploy-cicd",
    "deploy-worktree",
]

# Agent category mapping
AGENT_CATEGORIES = {
    "planner-audit": "planner",
    "planner-build": "planner",
    "planner-cleaning": "planner",
    "planner-guidance": "planner",
    "planner-guidance-testing": "planner",
    "planner-reviewer": "planner",
    "planner-test": "planner",
    "test-audit": "test",
    "test-builder": "test",
    "test-final-output": "test",
    "test-guidance-simulator": "test",
    "test-runner": "test",
    "test-service": "test",
    "test-user-simulator": "test",
    "orchestration-executor": "orchestration",
    "orchestration-friction": "orchestration",
    "orchestration-planning": "orchestration",
    "teacher-trace-diagnostics": "teacher",
    "teacher-update-assets": "teacher",
    "teacher-update-guidance": "teacher",
    "build-flutter": "build",
    "build-python": "build",
    "deploy-cicd": "deploy",
    "deploy-worktree": "deploy",
}


def is_agent_name(arg: str) -> bool:
    """Check if an argument is a known agent name.

    Args:
        arg: Command line argument to check (positional, no -- prefix).

    Returns:
        True if the argument is a known agent name.
    """
    return arg in KNOWN_AGENTS


def get_agent_name(arg: str) -> Optional[str]:
    """Get agent name if argument matches a known agent.

    Args:
        arg: Command line argument (positional, e.g., planner-guidance).

    Returns:
        Agent name or None if not a valid agent name.
    """
    if arg in KNOWN_AGENTS:
        return arg
    return None


def show_agent_help(agent_name: str, json_output: bool = False, bootstrap: bool = False) -> None:
    """Display help for a specific agent.

    This is the PRIMARY entrypoint for agents. It provides everything
    an agent needs to start working without file exploration.

    Args:
        agent_name: The agent name (e.g., planner-guidance).
        json_output: Whether to output as JSON.
        bootstrap: Whether to include full bootstrap context (expanded details).
    """
    if agent_name not in KNOWN_AGENTS:
        _print_unknown_agent_error(agent_name)
        sys.exit(1)

    # Load agent context
    if bootstrap:
        context = _load_agent_bootstrap_context(agent_name)
    else:
        context = _load_agent_context(agent_name)

    if json_output:
        print(json.dumps(context, indent=2, default=str))
    else:
        if bootstrap:
            _print_agent_bootstrap_human(context)
        else:
            _print_agent_help_human(context)


def _load_agent_context(agent_name: str) -> dict:
    """Load full context for an agent.

    Args:
        agent_name: The agent name.

    Returns:
        Dict with role, process steps, inputs, current task, and next commands.
    """
    import subprocess

    context = {
        "agent": agent_name,
        "category": AGENT_CATEGORIES.get(agent_name, "unknown"),
        "role": None,
        "agent_path": None,
        "current_task": None,
        "process_steps": [],
        "inputs": [],
        "next_commands": [],
        "deprecation_notice": None,
    }

    # Find git root for path resolution
    git_root = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        git_root = Path("/home/code/AgenticEngineering")

    # Find agent directory
    agent_dir = _find_agent_directory(agent_name)
    if not agent_dir:
        context["error"] = f"Agent guidance not found at expected path for: {agent_name}"
        return context

    # Set agent path (absolute)
    context["agent_path"] = str(agent_dir.resolve())

    # Load manifest.yml for role description
    manifest_path = agent_dir / "manifest.yml"
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                manifest = yaml.safe_load(f)
            if manifest and "agent" in manifest:
                agent_info = manifest["agent"]
                context["role"] = agent_info.get("description", agent_info.get("name", agent_name))
                # Check for deprecation
                if agent_info.get("deprecated"):
                    context["deprecation_notice"] = agent_info.get(
                        "deprecation_message",
                        "This agent is deprecated."
                    )
        except (yaml.YAMLError, IOError):
            pass

    # Load process.yml for steps
    process_path = agent_dir / "process.yml"
    if process_path.exists():
        try:
            with open(process_path) as f:
                process = yaml.safe_load(f)
            if process and "process" in process:
                proc = process["process"]
                context["role"] = context["role"] or proc.get("goal", "")
                # Extract step names/summaries
                steps = proc.get("steps", [])
                for step in steps[:10]:  # Limit to first 10 steps
                    if isinstance(step, dict):
                        step_name = step.get("name", step.get("id", ""))
                        context["process_steps"].append(step_name)
                    elif isinstance(step, str):
                        # First line only
                        context["process_steps"].append(step.split("\n")[0][:100])
        except (yaml.YAMLError, IOError):
            pass

    # Load process.mmd for orchestration agents
    process_mmd = agent_dir / "process.mmd"
    if process_mmd.exists() and not context["process_steps"]:
        try:
            content = process_mmd.read_text()
            # Extract GOAL from MMD comments
            for line in content.split("\n"):
                if line.strip().startswith("%% GOAL:"):
                    context["role"] = context["role"] or line.replace("%% GOAL:", "").strip()
                    break
            # Extract node names as step summary
            for line in content.split("\n"):
                line = line.strip()
                if "-->" in line and "[" in line:
                    # Extract node label like [Load Context Inputs]
                    start = line.find("[")
                    end = line.find("]", start)
                    if start > 0 and end > start:
                        label = line[start+1:end]
                        if len(label) < 60 and label not in context["process_steps"]:
                            context["process_steps"].append(label)
                if len(context["process_steps"]) >= 8:
                    break
        except IOError:
            pass

    # Load inputs.yml
    inputs_path = agent_dir / "inputs.yml"
    if inputs_path.exists():
        try:
            with open(inputs_path) as f:
                inputs_data = yaml.safe_load(f)
            if inputs_data:
                # Handle nested inputs structure (inputs.core_inputs or inputs.layers)
                inputs_section = inputs_data.get("inputs", {})
                if isinstance(inputs_section, dict):
                    # Try core_inputs first
                    core_inputs = inputs_section.get("core_inputs", [])
                    if isinstance(core_inputs, list):
                        for inp in core_inputs[:8]:
                            if isinstance(inp, dict):
                                inp_path = inp.get("path", inp.get("location", ""))
                                abs_path = _resolve_path(inp_path, git_root)
                                context["inputs"].append({
                                    "path": str(abs_path) if abs_path else inp_path,
                                    "description": inp.get("description", ""),
                                })
                    # Also add layers
                    layers = inputs_section.get("layers", [])
                    if isinstance(layers, list):
                        for layer in layers[:4]:
                            if isinstance(layer, dict):
                                layer_path = layer.get("path", "")
                                abs_path = _resolve_path(layer_path, git_root)
                                context["inputs"].append({
                                    "path": str(abs_path) if abs_path else layer_path,
                                    "description": layer.get("description", ""),
                                })
                elif isinstance(inputs_section, list):
                    # Direct list format
                    for inp in inputs_section[:8]:
                        if isinstance(inp, dict):
                            inp_path = inp.get("path", inp.get("location", ""))
                            abs_path = _resolve_path(inp_path, git_root)
                            context["inputs"].append({
                                "path": str(abs_path) if abs_path else inp_path,
                                "description": inp.get("description", ""),
                            })
                        elif isinstance(inp, str):
                            abs_path = _resolve_path(inp, git_root)
                            context["inputs"].append({
                                "path": str(abs_path) if abs_path else inp,
                                "description": "",
                            })
        except (yaml.YAMLError, IOError):
            pass

    # Get current task from Main-First plan (lazy import to avoid circular deps)
    try:
        from agenticguidance.services import MainFirstPlanResolver
        resolver = MainFirstPlanResolver()
        plan_info = resolver.resolve_active_plan()
        if plan_info:
            current_task = resolver.extract_current_task(plan_info["plan_folder"])
            if current_task:
                context["current_task"] = {
                    "id": current_task.get("id"),
                    "name": current_task.get("name"),
                    "status": current_task.get("status"),
                    "phase": current_task.get("phase"),
                }
    except Exception:
        # Don't fail if plan resolution fails - still show agent help
        pass

    # Build next commands
    context["next_commands"] = [
        f"agentic context bootstrap --role {agent_name} -j  # Get full seed context",
        "agentic plan task current -j                       # Get current task details",
        "agentic plan task update <id> --status completed   # Mark task done",
        "agentic plan task list                             # Show all tasks",
    ]

    return context


def _load_agent_bootstrap_context(agent_name: str) -> dict:
    """Load full bootstrap context for an agent (expanded details).

    This provides MORE context than the basic help, including:
    - Full process steps with details
    - All input file paths with existence checks
    - Current task with full details
    - Related guidelines and definitions paths
    - Next CLI commands

    Args:
        agent_name: The agent name.

    Returns:
        Dict with full bootstrap context.
    """
    import subprocess

    context = {
        "agent": agent_name,
        "category": AGENT_CATEGORIES.get(agent_name, "unknown"),
        "role": None,
        "objective": None,
        "agent_path": None,
        "process_path": None,
        "inputs_path": None,
        "plan_folder": None,
        "plan_path": None,
        "current_task": None,
        "process_steps": [],
        "process_goal": None,
        "inputs": [],
        "layers": [],
        "guidelines": [],
        "definitions": [],
        "guidance_files": [],
        "related_files": [],
        "next_commands": [],
        "deprecation_notice": None,
    }

    # Find git root for path resolution
    git_root = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        git_root = Path("/home/code/AgenticEngineering")

    # Find agent directory
    agent_dir = _find_agent_directory(agent_name)
    if not agent_dir:
        context["error"] = f"Agent guidance not found at expected path for: {agent_name}"
        return context

    # Set agent path (absolute)
    context["agent_path"] = str(agent_dir.resolve())

    # Build guidance_files list with all agent files
    for gf_name in ["manifest.yml", "process.yml", "process.mmd", "inputs.yml", "outputs.yml"]:
        gf_path = agent_dir / gf_name
        if gf_path.exists():
            context["guidance_files"].append({
                "name": gf_name,
                "path": str(gf_path.resolve()),
                "exists": True,
            })

    # Load manifest.yml for role description
    manifest_path = agent_dir / "manifest.yml"
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                manifest = yaml.safe_load(f)
            if manifest and "agent" in manifest:
                agent_info = manifest["agent"]
                context["role"] = agent_info.get("description", agent_info.get("name", agent_name))
                if agent_info.get("deprecated"):
                    context["deprecation_notice"] = agent_info.get(
                        "deprecation_message",
                        "This agent is deprecated."
                    )
        except (yaml.YAMLError, IOError):
            pass

    # Load process.yml with FULL details
    process_path = agent_dir / "process.yml"
    if process_path.exists():
        context["process_path"] = str(process_path.resolve())
        try:
            with open(process_path) as f:
                process = yaml.safe_load(f)
            if process and "process" in process:
                proc = process["process"]
                context["process_goal"] = proc.get("goal", "")
                context["role"] = context["role"] or proc.get("goal", "")

                # Extract ALL steps with details (not just names)
                steps = proc.get("steps", [])
                for i, step in enumerate(steps):
                    if isinstance(step, dict):
                        step_info = {
                            "number": i + 1,
                            "name": step.get("name", step.get("id", f"Step {i+1}")),
                            "description": step.get("description", ""),
                        }
                        context["process_steps"].append(step_info)
                    elif isinstance(step, str):
                        # Include more of the step text for bootstrap
                        step_text = step.strip()
                        # First line as name, rest as description
                        lines = step_text.split("\n")
                        step_info = {
                            "number": i + 1,
                            "name": lines[0][:100],
                            "description": "\n".join(lines[1:])[:500] if len(lines) > 1 else "",
                        }
                        context["process_steps"].append(step_info)

                # Extract guidelines from process
                proc_guidelines = proc.get("guidelines") or []
                for guideline in proc_guidelines[:5]:
                    if isinstance(guideline, str):
                        context["guidelines"].append(guideline[:300])
        except (yaml.YAMLError, IOError):
            pass

    # Load process.mmd for orchestration agents
    process_mmd = agent_dir / "process.mmd"
    if process_mmd.exists() and not context["process_steps"]:
        # Set process_path to .mmd if no .yml was found
        if not context["process_path"]:
            context["process_path"] = str(process_mmd.resolve())
        try:
            content = process_mmd.read_text()
            # Extract GOAL from MMD comments
            for line in content.split("\n"):
                if line.strip().startswith("%% GOAL:"):
                    context["process_goal"] = line.replace("%% GOAL:", "").strip()
                    context["role"] = context["role"] or context["process_goal"]
                    break

            # Extract node names as step summary with more context
            step_num = 1
            for line in content.split("\n"):
                line = line.strip()
                if "-->" in line and "[" in line:
                    start = line.find("[")
                    end = line.find("]", start)
                    if start > 0 and end > start:
                        label = line[start+1:end]
                        if len(label) < 80:
                            context["process_steps"].append({
                                "number": step_num,
                                "name": label,
                                "description": "",
                            })
                            step_num += 1
                if len(context["process_steps"]) >= 15:
                    break
        except IOError:
            pass

    # Load inputs.yml with FULL details and existence checks
    inputs_path = agent_dir / "inputs.yml"
    if inputs_path.exists():
        context["inputs_path"] = str(inputs_path.resolve())
        try:
            with open(inputs_path) as f:
                inputs_data = yaml.safe_load(f)
            if inputs_data:
                inputs_section = inputs_data.get("inputs", {})

                # Handle layers
                if isinstance(inputs_section, dict):
                    layers = inputs_section.get("layers", [])
                    if isinstance(layers, list):
                        for layer in layers:
                            if isinstance(layer, dict):
                                layer_path = layer.get("path", "")
                                abs_path = _resolve_path(layer_path, git_root)
                                context["layers"].append({
                                    "path": str(abs_path),
                                    "relative_path": layer_path,
                                    "description": layer.get("description", ""),
                                    "required": layer.get("required", False),
                                    "exists": abs_path.exists() if abs_path else False,
                                })

                    # Handle core_inputs
                    core_inputs = inputs_section.get("core_inputs", [])
                    if isinstance(core_inputs, list):
                        for inp in core_inputs:
                            if isinstance(inp, dict):
                                inp_path = inp.get("path", inp.get("location", ""))
                                abs_path = _resolve_path(inp_path, git_root)
                                context["inputs"].append({
                                    "path": str(abs_path),
                                    "relative_path": inp_path,
                                    "description": inp.get("description", ""),
                                    "required": inp.get("required", False),
                                    "exists": abs_path.exists() if abs_path else False,
                                })

                elif isinstance(inputs_section, list):
                    for inp in inputs_section:
                        if isinstance(inp, dict):
                            inp_path = inp.get("path", inp.get("location", ""))
                            abs_path = _resolve_path(inp_path, git_root)
                            context["inputs"].append({
                                "path": str(abs_path),
                                "relative_path": inp_path,
                                "description": inp.get("description", ""),
                                "required": inp.get("required", False),
                                "exists": abs_path.exists() if abs_path else False,
                            })
                        elif isinstance(inp, str):
                            abs_path = _resolve_path(inp, git_root)
                            context["inputs"].append({
                                "path": str(abs_path),
                                "relative_path": inp,
                                "description": "",
                                "required": False,
                                "exists": abs_path.exists() if abs_path else False,
                            })
        except (yaml.YAMLError, IOError):
            pass

    # Get current task from Main-First plan with FULL details
    try:
        from agenticguidance.services import MainFirstPlanResolver
        resolver = MainFirstPlanResolver()
        plan_info = resolver.resolve_active_plan()
        if plan_info:
            context["plan_folder"] = plan_info.get("plan_folder_name")
            context["plan_path"] = str(plan_info.get("plan_folder"))
            context["objective"] = plan_info.get("objective")

            current_task = resolver.extract_current_task(plan_info["plan_folder"])
            if current_task:
                # Include full task details for bootstrap
                context["current_task"] = {
                    "id": current_task.get("id"),
                    "name": current_task.get("name"),
                    "description": current_task.get("description"),
                    "status": current_task.get("status"),
                    "phase": current_task.get("phase"),
                    "phase_id": current_task.get("phase_id"),
                    "agent_type": current_task.get("agent_type"),
                    "guidance": current_task.get("guidance"),
                    "success_criteria": current_task.get("success_criteria", []),
                    "inputs": current_task.get("inputs", []),
                    "target_files": current_task.get("target_files", []),
                    "source_file": current_task.get("source_file"),
                }
    except Exception:
        pass

    # Add related guideline and definition paths
    guidance_base = git_root / "modules" / "AgenticGuidance" if git_root else None
    if guidance_base and guidance_base.exists():
        # Common guidelines
        guidelines_dir = guidance_base / "assets" / "guidelines"
        if guidelines_dir.exists():
            for gf in sorted(guidelines_dir.glob("*.yml"))[:8]:
                context["related_files"].append({
                    "type": "guideline",
                    "path": str(gf),
                    "name": gf.stem,
                })

        # Common definitions
        definitions_dir = guidance_base / "assets" / "definitions"
        if definitions_dir.exists():
            for df in sorted(definitions_dir.glob("*.yml"))[:8]:
                context["related_files"].append({
                    "type": "definition",
                    "path": str(df),
                    "name": df.stem,
                })

    # Build next commands
    context["next_commands"] = [
        f"agentic context bootstrap --role {agent_name} -j  # Get full seed context (workflow integration)",
        "agentic plan task current -j                       # Get current task details",
        "agentic plan task update <id> --status in_progress # Start working on task",
        "agentic plan task update <id> --status completed   # Mark task done",
        "agentic plan task list                             # Show all tasks",
        "agentic context inputs --role {agent_name}         # Get input files with existence checks",
    ]

    return context


def _resolve_path(path_str: str, git_root: Optional[Path]) -> Optional[Path]:
    """Resolve a path to absolute, checking against git root.

    Args:
        path_str: Path string (may be relative or absolute).
        git_root: Git repository root path.

    Returns:
        Resolved Path or None.
    """
    if not path_str:
        return None

    if path_str.startswith("/"):
        return Path(path_str)

    if git_root:
        return git_root / path_str

    return Path(path_str)


def _find_agent_directory(agent_name: str) -> Optional[Path]:
    """Find the agent's guidance directory.

    Args:
        agent_name: The agent name.

    Returns:
        Path to agent directory or None.
    """
    import subprocess

    # Get category
    category = AGENT_CATEGORIES.get(agent_name)
    if not category:
        return None

    # Try git root first
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_root = Path(result.stdout.strip())
        agent_dir = git_root / "modules" / "AgenticGuidance" / "agents" / category / agent_name
        if agent_dir.exists():
            return agent_dir
    except subprocess.CalledProcessError:
        pass

    # Try common paths
    candidates = [
        Path("/home/code/AgenticEngineering/modules/AgenticGuidance/agents") / category / agent_name,
        Path.cwd() / "modules" / "AgenticGuidance" / "agents" / category / agent_name,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _print_agent_help_human(context: dict) -> None:
    """Print agent help in human-readable format.

    Args:
        context: Agent context dict.
    """
    agent = context["agent"]

    print("=" * 60)
    print(f"AGENT: {agent}")
    print("=" * 60)
    print()

    if context.get("deprecation_notice"):
        print(f"[DEPRECATED] {context['deprecation_notice']}")
        print()

    if context.get("role"):
        print(f"ROLE: {context['role'][:200]}")
        print()

    # Show agent path for source exploration
    if context.get("agent_path"):
        print(f"AGENT PATH: {context['agent_path']}")
        print()

    if context.get("current_task"):
        task = context["current_task"]
        print("CURRENT TASK:")
        print(f"  ID: {task.get('id', 'N/A')}")
        print(f"  Name: {task.get('name', 'N/A')}")
        print(f"  Status: {task.get('status', 'N/A')}")
        print(f"  Phase: {task.get('phase', 'N/A')}")
        print()
    else:
        print("CURRENT TASK: No active task - check plan folder")
        print()

    if context.get("process_steps"):
        print("PROCESS STEPS:")
        for i, step in enumerate(context["process_steps"], 1):
            print(f"  {i}. {step}")
        print()

    if context.get("inputs"):
        print("INPUTS TO READ:")
        for inp in context["inputs"]:
            path = inp.get("path", "")
            desc = inp.get("description", "")
            if desc:
                print(f"  - {path}: {desc[:50]}")
            else:
                print(f"  - {path}")
        print()

    print("NEXT COMMANDS:")
    for cmd in context.get("next_commands", []):
        print(f"  {cmd}")
    print()
    print("=" * 60)


def _print_agent_bootstrap_human(context: dict) -> None:
    """Print full bootstrap context in human-readable format.

    Provides expanded details compared to basic help.

    Args:
        context: Bootstrap context dict.
    """
    agent = context["agent"]

    print("=" * 70)
    print(f"BOOTSTRAP CONTEXT: {agent}")
    print("=" * 70)
    print()

    if context.get("deprecation_notice"):
        print(f"[DEPRECATED] {context['deprecation_notice']}")
        print()

    # Role and objective
    if context.get("role"):
        print(f"ROLE: {context['role'][:300]}")
        print()

    if context.get("objective"):
        print(f"OBJECTIVE: {context['objective'][:300]}")
        print()

    # Agent files (absolute paths)
    if context.get("agent_path"):
        print("AGENT FILES:")
        print(f"  Agent Directory: {context.get('agent_path', 'N/A')}")
        if context.get("process_path"):
            print(f"  Process File:    {context.get('process_path', 'N/A')}")
        if context.get("inputs_path"):
            print(f"  Inputs File:     {context.get('inputs_path', 'N/A')}")
        print()

    # Plan info
    if context.get("plan_folder"):
        print("PLAN INFO:")
        print(f"  Folder: {context.get('plan_folder', 'N/A')}")
        print(f"  Path: {context.get('plan_path', 'N/A')}")
        print()

    # Current task with full details
    if context.get("current_task"):
        task = context["current_task"]
        print("CURRENT TASK:")
        print(f"  ID: {task.get('id', 'N/A')}")
        print(f"  Name: {task.get('name', 'N/A')}")
        print(f"  Status: {task.get('status', 'N/A')}")
        print(f"  Phase: {task.get('phase', 'N/A')}")
        print(f"  Agent Type: {task.get('agent_type', 'N/A')}")
        if task.get("description"):
            print(f"  Description: {task.get('description', '')[:200]}")
        if task.get("guidance"):
            print(f"  Guidance: {task.get('guidance', '')[:300]}")
        if task.get("success_criteria"):
            print("  Success Criteria:")
            for sc in task.get("success_criteria", [])[:5]:
                print(f"    - {sc[:100]}")
        if task.get("inputs"):
            print("  Task Inputs:")
            for inp in task.get("inputs", [])[:5]:
                print(f"    - {inp}")
        if task.get("target_files"):
            print("  Target Files:")
            for tf in task.get("target_files", [])[:5]:
                print(f"    - {tf}")
        if task.get("source_file"):
            print(f"  Source File: {task.get('source_file')}")
        print()
    else:
        print("CURRENT TASK: No active task - check plan folder")
        print()

    # Process steps with details
    if context.get("process_steps"):
        print("PROCESS STEPS:")
        for step in context["process_steps"]:
            if isinstance(step, dict):
                print(f"  {step.get('number', '?')}. {step.get('name', 'Unnamed')}")
                if step.get("description"):
                    # Print first 150 chars of description, indented
                    desc = step["description"][:150].replace("\n", " ")
                    print(f"      {desc}...")
            else:
                print(f"  - {step}")
        print()

    # Input layers
    if context.get("layers"):
        print("INPUT LAYERS:")
        for layer in context["layers"]:
            exists = "[OK]" if layer.get("exists") else "[MISSING]"
            required = "(required)" if layer.get("required") else "(optional)"
            print(f"  {exists} {layer.get('relative_path', 'N/A')} {required}")
            if layer.get("description"):
                print(f"       {layer['description'][:80]}")
        print()

    # Core inputs with existence checks
    if context.get("inputs"):
        print("CORE INPUTS:")
        for inp in context["inputs"]:
            exists = "[OK]" if inp.get("exists") else "[MISSING]"
            required = "(required)" if inp.get("required") else "(optional)"
            print(f"  {exists} {inp.get('path', 'N/A')} {required}")
            if inp.get("description"):
                print(f"       {inp['description'][:80]}")
        print()

    # Guidelines
    if context.get("guidelines"):
        print("GUIDELINES:")
        for g in context["guidelines"][:3]:
            print(f"  - {g[:150]}...")
        print()

    # Related files
    if context.get("related_files"):
        print("RELATED FILES:")
        guidelines = [f for f in context["related_files"] if f.get("type") == "guideline"]
        definitions = [f for f in context["related_files"] if f.get("type") == "definition"]

        if guidelines:
            print("  Guidelines:")
            for gf in guidelines[:5]:
                print(f"    - {gf.get('path', 'N/A')}")
        if definitions:
            print("  Definitions:")
            for df in definitions[:5]:
                print(f"    - {df.get('path', 'N/A')}")
        print()

    # Next commands
    print("NEXT COMMANDS:")
    for cmd in context.get("next_commands", []):
        print(f"  {cmd}")
    print()
    print("=" * 70)


def _print_unknown_agent_error(agent_name: str) -> None:
    """Print error for unknown agent with suggestions.

    Args:
        agent_name: The unknown agent name.
    """
    print(f"Unknown agent: {agent_name}", file=sys.stderr)
    print(file=sys.stderr)
    print("Available agents:", file=sys.stderr)

    # Group by category
    by_category = {}
    for agent in KNOWN_AGENTS:
        cat = AGENT_CATEGORIES.get(agent, "other")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(agent)

    for category in sorted(by_category.keys()):
        agents = by_category[category]
        print(f"  {category}:", file=sys.stderr)
        for agent in agents:
            print(f"    {agent}", file=sys.stderr)

    print(file=sys.stderr)
    print("Run `agentic --help` for full command reference.", file=sys.stderr)


def get_agent_flags_for_help() -> str:
    """Generate agent names section for main --help output.

    Returns:
        Formatted string for argparse epilog.
    """
    lines = ["\nAgent-Specific Help:"]

    # Group by category
    by_category = {}
    for agent in KNOWN_AGENTS:
        cat = AGENT_CATEGORIES.get(agent, "other")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(agent)

    for category in ["planner", "build", "test", "orchestration", "teacher", "deploy"]:
        if category in by_category:
            agents = by_category[category]
            lines.append(f"  {category.title()} agents: {', '.join(agents[:3])}{'...' if len(agents) > 3 else ''}")

    lines.append("")
    lines.append("Example: agentic planner-guidance  # Show help for planner-guidance agent")

    return "\n".join(lines)
