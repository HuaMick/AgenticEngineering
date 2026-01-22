"""Context workflow for JIT context retrieval.

Implements Main-First plan resolution and role context loading
for the JIT Pull-based context architecture.
"""

import subprocess
from pathlib import Path
from typing import Optional

import yaml


class MainFirstPlanResolver:
    """Resolves active plans from Main-First worktree.

    Main-First Planning: Plans are created and maintained in the main
    worktree for visibility, but execution happens in feature worktrees.
    This class resolves plans from main when running in any worktree.
    """

    def __init__(self, cwd: Optional[Path] = None):
        """Initialize resolver.

        Args:
            cwd: Current working directory, defaults to Path.cwd().
        """
        self.cwd = cwd or Path.cwd()
        self._main_worktree: Optional[Path] = None
        self._current_branch: Optional[str] = None

    def find_main_worktree(self) -> Optional[Path]:
        """Find the main worktree path (branch main or master).

        Returns:
            Path to main worktree, or None if not found.
        """
        if self._main_worktree:
            return self._main_worktree

        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.cwd,
            )
            lines = result.stdout.strip().split("\n")
            i = 0
            while i < len(lines):
                if lines[i].startswith("worktree "):
                    wt_path = lines[i].split(" ", 1)[1]
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if lines[j].startswith("branch "):
                            wt_branch = lines[j].split(" ", 1)[1].replace("refs/heads/", "")
                            if wt_branch in ("main", "master"):
                                self._main_worktree = Path(wt_path)
                                return self._main_worktree
                            break
                        elif lines[j].startswith("worktree "):
                            break
                i += 1
        except subprocess.CalledProcessError:
            pass

        return None

    def get_current_branch(self) -> Optional[str]:
        """Get the current git branch name.

        Returns:
            Branch name, or None if not in a git repo.
        """
        if self._current_branch:
            return self._current_branch

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.cwd,
            )
            self._current_branch = result.stdout.strip()
            return self._current_branch
        except subprocess.CalledProcessError:
            return None

    def resolve_active_plan(self, branch: Optional[str] = None) -> Optional[dict]:
        """Find the active plan for a branch.

        Scans main_worktree/docs/plans/live/ for folders matching the branch.

        Args:
            branch: Branch name to find plan for, defaults to current branch.

        Returns:
            Dict with plan info or None if not found:
            {
                "plan_folder": Path,
                "plan_folder_name": str,
                "objective": str,
                "status": str,
                "main_worktree": Path,
            }
        """
        main_wt = self.find_main_worktree()
        if not main_wt:
            return None

        branch = branch or self.get_current_branch()
        if not branch:
            return None

        plans_live = main_wt / "docs" / "plans" / "live"
        if not plans_live.exists():
            return None

        # Search strategies:
        # 1. Exact branch match in folder name (e.g., 261115CL_agenticcli matches agenticcli)
        # 2. Folder with matching branch field in plan.yml
        # 3. Most recent folder if on main/master (return first with live/ content)

        matching_plan = None

        for folder in sorted(plans_live.iterdir(), key=lambda x: x.name, reverse=True):
            if not folder.is_dir():
                continue

            # Strategy 1: Check folder name contains branch
            folder_name = folder.name.lower()
            branch_lower = branch.lower().replace("-", "").replace("_", "")

            # Extract the description part of YYMMDDXX_description
            if "_" in folder.name and len(folder.name) > 9:
                folder_desc = folder.name[9:].lower().replace("-", "").replace("_", "")
                if branch_lower in folder_desc or folder_desc in branch_lower:
                    matching_plan = folder
                    break

            # Strategy 2: Check plan.yml for branch field
            plan_yml = folder / "live" / "plan.yml"
            if not plan_yml.exists():
                # Try root level plan_*.yml files
                for pf in folder.glob("live/plan_*.yml"):
                    plan_yml = pf
                    break

            if plan_yml.exists():
                try:
                    with open(plan_yml) as f:
                        plan_data = yaml.safe_load(f)
                    if plan_data:
                        plan_branch = plan_data.get("branch", "")
                        if plan_branch and branch_lower in plan_branch.lower():
                            matching_plan = folder
                            break
                except (yaml.YAMLError, IOError):
                    pass

        # Strategy 3: If on main/master, return most recent active plan
        if not matching_plan and branch in ("main", "master"):
            for folder in sorted(plans_live.iterdir(), key=lambda x: x.name, reverse=True):
                if folder.is_dir() and (folder / "live").exists():
                    # Check if there are actual files in live/
                    live_files = list((folder / "live").glob("*.yml"))
                    if live_files:
                        matching_plan = folder
                        break

        if not matching_plan:
            return None

        # Extract plan info
        plan_info = {
            "plan_folder": matching_plan,
            "plan_folder_name": matching_plan.name,
            "main_worktree": main_wt,
            "objective": None,
            "status": None,
        }

        # Try to extract objective from plan files
        for plan_file in (matching_plan / "live").glob("plan_*.yml"):
            try:
                with open(plan_file) as f:
                    plan_data = yaml.safe_load(f)
                if plan_data:
                    if "objective" in plan_data:
                        plan_info["objective"] = plan_data["objective"]
                    elif "plan" in plan_data and "objective" in plan_data["plan"]:
                        plan_info["objective"] = plan_data["plan"]["objective"]
                    if "status" in plan_data:
                        plan_info["status"] = plan_data["status"]
                    break
            except (yaml.YAMLError, IOError):
                pass

        return plan_info

    def extract_current_task(self, plan_folder: Path) -> Optional[dict]:
        """Extract the current task (in_progress or next pending).

        Args:
            plan_folder: Path to the plan folder.

        Returns:
            Task dict or None.
        """
        tasks = self.extract_all_tasks(plan_folder)

        # First: find in_progress
        for task in tasks:
            if task.get("status") == "in_progress":
                return task

        # Then: find first pending
        for task in tasks:
            if task.get("status") == "pending":
                return task

        return None

    def extract_all_tasks(self, plan_folder: Path) -> list:
        """Extract all tasks from plan files in a folder.

        Args:
            plan_folder: Path to the plan folder.

        Returns:
            List of task dicts.
        """
        tasks = []
        live_folder = plan_folder / "live"

        if not live_folder.exists():
            return tasks

        for plan_file in live_folder.glob("plan_*.yml"):
            try:
                with open(plan_file) as f:
                    plan_data = yaml.safe_load(f)

                if not plan_data:
                    continue

                # Extract phases
                phases = plan_data.get("phases", [])
                if not phases and "plan" in plan_data:
                    phases = plan_data["plan"].get("phases", [])

                for phase in phases:
                    phase_name = phase.get("name", "Unknown Phase")
                    phase_id = phase.get("id", "")

                    for task in phase.get("tasks", []):
                        task_info = {
                            "id": task.get("id", ""),
                            "name": task.get("name", ""),
                            "description": task.get("description", ""),
                            "status": task.get("status", "pending"),
                            "phase": phase_name,
                            "phase_id": phase_id,
                            "agent_type": task.get("agent_type", ""),
                            "inputs": task.get("inputs", []),
                            "target_files": task.get("target_files", []),
                            "guidance": task.get("guidance", ""),
                            "success_criteria": task.get("success_criteria", []),
                            "source_file": str(plan_file),
                        }
                        tasks.append(task_info)

            except (yaml.YAMLError, IOError):
                pass

        return tasks


def get_role_process(role_id: str) -> Optional[dict]:
    """Load role-specific process from AgenticGuidance.

    Args:
        role_id: Role identifier (e.g., planner-build, build-python).

    Returns:
        Process dict with steps and guidelines, or None if not found.
    """
    # Find AgenticGuidance module
    agent_base = _find_agents_directory()
    if not agent_base:
        return None

    # Try different category directories
    categories = ["planner", "build", "test", "orchestration", "teacher", "deploy"]

    for category in categories:
        agent_dir = agent_base / category / role_id
        if agent_dir.exists():
            return _load_agent_process(agent_dir)

    # Also try direct match without category
    for category_dir in agent_base.iterdir():
        if category_dir.is_dir():
            agent_dir = category_dir / role_id
            if agent_dir.exists():
                return _load_agent_process(agent_dir)

    return None


def _find_agents_directory() -> Optional[Path]:
    """Find the AgenticGuidance agents directory.

    Returns:
        Path to agents directory or None.
    """
    # Try from cwd upward
    cwd = Path.cwd()

    # Check common locations
    candidates = [
        cwd / "modules" / "AgenticGuidance" / "agents",
        cwd.parent / "modules" / "AgenticGuidance" / "agents",
        Path("/home/code/AgenticEngineering/modules/AgenticGuidance/agents"),
    ]

    # Also check git root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        git_root = Path(result.stdout.strip())
        candidates.insert(0, git_root / "modules" / "AgenticGuidance" / "agents")
    except subprocess.CalledProcessError:
        pass

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _load_agent_process(agent_dir: Path) -> Optional[dict]:
    """Load process.yml or process.mmd from an agent directory.

    Args:
        agent_dir: Path to agent directory.

    Returns:
        Process dict or None.
    """
    result = {
        "role_id": agent_dir.name,
        "category": agent_dir.parent.name,
        "process": None,
        "manifest": None,
        "invocation_context": None,
    }

    # Load process.yml
    process_yml = agent_dir / "process.yml"
    if process_yml.exists():
        try:
            with open(process_yml) as f:
                result["process"] = yaml.safe_load(f)
        except (yaml.YAMLError, IOError):
            pass

    # Load manifest.yml
    manifest_yml = agent_dir / "manifest.yml"
    if manifest_yml.exists():
        try:
            with open(manifest_yml) as f:
                manifest = yaml.safe_load(f)
                result["manifest"] = manifest
                if manifest and "agent" in manifest:
                    result["invocation_context"] = manifest["agent"].get("invocation_context")
        except (yaml.YAMLError, IOError):
            pass

    return result if result["process"] or result["manifest"] else None


def get_role_inputs_manifest(role_id: str, resolve_layers: bool = False) -> Optional[dict]:
    """Load inputs manifest for a role.

    Args:
        role_id: Role identifier.
        resolve_layers: Whether to expand layer references.

    Returns:
        Manifest dict with inputs, their paths, and existence status.
    """
    agent_base = _find_agents_directory()
    if not agent_base:
        return None

    # Find agent directory
    categories = ["planner", "build", "test", "orchestration", "teacher", "deploy"]
    agent_dir = None

    for category in categories:
        candidate = agent_base / category / role_id
        if candidate.exists():
            agent_dir = candidate
            break

    if not agent_dir:
        return None

    inputs_yml = agent_dir / "inputs.yml"
    if not inputs_yml.exists():
        return {"role": role_id, "inputs": [], "missing": []}

    try:
        with open(inputs_yml) as f:
            inputs_data = yaml.safe_load(f)
    except (yaml.YAMLError, IOError):
        return None

    if not inputs_data:
        return {"role": role_id, "inputs": [], "missing": []}

    # Extract inputs
    inputs_list = inputs_data.get("inputs", [])
    if not isinstance(inputs_list, list):
        inputs_list = []

    # Resolve paths and check existence
    manifest = {
        "role": role_id,
        "inputs": [],
        "missing": [],
        "layers": inputs_data.get("layers", []),
    }

    # Find project root for path resolution
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        project_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        project_root = Path.cwd()

    for input_item in inputs_list:
        if isinstance(input_item, dict):
            location = input_item.get("location", "")
            description = input_item.get("description", "")
        elif isinstance(input_item, str):
            location = input_item
            description = ""
        else:
            continue

        # Resolve path
        if location.startswith("/"):
            abs_path = Path(location)
        else:
            abs_path = project_root / location

        exists = abs_path.exists()

        manifest["inputs"].append({
            "path": str(abs_path),
            "relative_path": location,
            "description": description,
            "exists": exists,
        })

        if not exists:
            manifest["missing"].append(location)

    return manifest


def generate_agent_bootstrap(role_id: str) -> Optional[str]:
    """Generate thin-client bootstrap file for an agent.

    Loads the bootstrap template from assets and substitutes variables.

    Args:
        role_id: Role identifier.

    Returns:
        Markdown content for agent bootstrap file.
    """
    role_process = get_role_process(role_id)
    if not role_process:
        return None

    # Get role name from manifest
    role_name = role_id.replace("-", " ").title()
    role_specific_notes = ""
    if role_process.get("manifest"):
        agent_info = role_process["manifest"].get("agent", {})
        role_name = agent_info.get("name", role_name)
        # Get role-specific notes if available
        role_specific_notes = agent_info.get("bootstrap_notes", "")

    # Try to load template from file
    template_content = _load_bootstrap_template()

    if template_content:
        # Substitute variables
        content = template_content.replace("{{ROLE_ID}}", role_id)
        content = content.replace("{{ROLE_NAME}}", role_name)
        content = content.replace("{{ROLE_SPECIFIC_NOTES}}", role_specific_notes)
        return content

    # Fallback to inline template if file not found
    return f"""# {role_name} Agent

You are the **{role_id}** agent.

## Bootstrap Protocol

Before taking action, run these commands to get your context:

```bash
# 1. Get your role context and current task
agentic context bootstrap --role {role_id} -j

# 2. Get your current/next task details
agentic plan task current -j
```

## Execution Loop

1. **Read** your current task from `agentic plan task current`
2. **Execute** the task following the guidance provided
3. **Update** status when done: `agentic plan task update <task-id> --status completed`
4. **Repeat** from step 1 until all tasks are complete

## CLI Commands Reference

| Command | Purpose |
|---------|---------|
| `agentic context bootstrap --role {role_id}` | Get Seed Context |
| `agentic plan task current` | Get current/next task |
| `agentic plan task update <id> --status <s>` | Update task status |

## Role Boundary

Plan management is owned by **planner agents**. You READ and UPDATE via CLI only.
"""


def _load_bootstrap_template() -> Optional[str]:
    """Load the bootstrap template from assets.

    Returns:
        Template content or None if not found.
    """
    # Find template file
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_root = Path(result.stdout.strip())
        template_path = git_root / "modules" / "AgenticGuidance" / "assets" / "templates" / "bootstrap-agent-template.md"

        if template_path.exists():
            return template_path.read_text()
    except (subprocess.CalledProcessError, IOError):
        pass

    # Try common paths
    candidates = [
        Path("/home/code/AgenticEngineering/modules/AgenticGuidance/assets/templates/bootstrap-agent-template.md"),
        Path.cwd() / "modules" / "AgenticGuidance" / "assets" / "templates" / "bootstrap-agent-template.md",
    ]

    for candidate in candidates:
        if candidate.exists():
            try:
                return candidate.read_text()
            except IOError:
                pass

    return None
