"""Planner agent prompt template builder.

Generates structured prompts for planner agents that instruct them to:
1. Discover affected user stories
2. Write README.md with objective and phases
3. Write plan_build.yml following planning-standard format
4. Include UAT phase (mandatory per planning-standard.yml)
5. Define success_criteria at plan level
"""

from pathlib import Path


def build_planner_prompt(objective: str, plan_folder: Path, context: str | None = None) -> str:
    """Build a structured prompt for the planner agent.

    Args:
        objective: The planning objective description.
        plan_folder: Path to the plan folder where planner will write files.
        context: Optional additional context to include in the prompt.

    Returns:
        Formatted prompt string instructing the planner agent.
    """
    plan_folder_str = str(plan_folder)

    prompt_parts = [
        "You are a planner agent. Your task is to create a comprehensive implementation plan.",
        "",
        f"OBJECTIVE: {objective}",
        "",
        f"PLAN FOLDER: {plan_folder_str}",
        "",
        "INSTRUCTIONS:",
        "",
        "1. STORY DISCOVERY (MANDATORY - STORY-FIRST PLANNING FENCE):",
        "   Run `agentic stories find` to discover affected user stories BEFORE creating phases.",
        "   Story discovery must occur FIRST - it's a mandatory fence per planning-standard.yml.",
        "   Record affected story IDs in plan metadata (affected_stories field).",
        "   If no stories are found, you MUST provide no_stories_rationale explaining why.",
        "   Stories location: docs/userstories/",
        "",
        "2. WRITE README.md:",
        "   Create README.md in the plan folder with:",
        "   - Objective statement",
        "   - Phases overview",
        "   - Dependencies and prerequisites",
        "   - Success criteria",
        "",
        "3. WRITE plan_build.yml:",
        "   Create plan_build.yml following planning-standard.yml format with:",
        "   - Plan-level metadata (name, worktree_path, status, affected_stories)",
        "   - Phases with tasks (each task must have: id, name, guidance, target_files, inputs)",
        "   - Success criteria defined at plan level",
        "   - Each task MUST declare target_files for parallelization decisions",
        "   - Each task MUST declare inputs (project-specific context files to pre-read)",
        "   Reference: modules/AgenticGuidance/assets/guidelines/planning-standard.yml",
        "",
        "4. UAT PHASE (MANDATORY FENCE):",
        "   Every plan MUST include a User Acceptance Testing (UAT) phase.",
        "   UAT is mandatory per planning-standard.yml - plans without UAT are incomplete.",
        "   UAT must be anchored to user stories with acceptance criteria.",
        "   Select appropriate UAT strategy:",
        "   - test-user-simulator: For CLI tools and user journey validation",
        "   - guidance-blind-test: For documentation completeness validation",
        "   - documentation-loop: For end-user facing features needing docs validation",
        "   - manual: For complex scenarios requiring human judgment",
        "",
        "5. PLANNING STANDARD FENCES:",
        "   Your plan MUST comply with these mandatory fences:",
        "   - FENCE: STORY-FIRST PLANNING - Story discovery MUST occur before phase determination",
        "   - FENCE: UAT IS MANDATORY - Every plan must include a UAT phase",
        "   - FENCE: UAT USER STORY ANCHORING - UAT phases must trace back to user story IDs",
        "",
        "REQUIRED OUTPUTS:",
        f"- {plan_folder_str}/README.md",
        f"- {plan_folder_str}/plan_build.yml",
        "",
        "PLANNING GUIDELINES:",
        "- Reference planning-standard.yml for structure and format",
        "- Use Domain -> Workflow -> Entrypoint architecture pattern",
        "- Include loop structures where iterative work is needed (test-fix-loop, audit-test-fix-loop)",
        "- Add open_questions section for blocking questions requiring human input",
        "- Analyze impacted_artifacts for semantic impacts (APIs, CLI commands, services)",
        "",
    ]

    if context:
        prompt_parts.extend([
            "ADDITIONAL CONTEXT:",
            context,
            "",
        ])

    prompt_parts.extend([
        "Start by running `agentic stories find` to discover affected user stories.",
        "Then create the plan files in the specified folder.",
        "",
        "When complete, report the files you created and their paths.",
    ])

    return "\n".join(prompt_parts)
