"""Planner agent prompt template builder.

Generates structured prompts for planner agents that instruct them to:
1. Discover affected user stories
2. Write README.md with objective and phases
3. Create tickets in TinyDB via CLI following planning-standard format
4. Include UAT phase (mandatory per planning-standard.yml)
5. Define success_criteria at epic level
"""

from pathlib import Path


def build_planner_prompt(objective: str, epic_folder: Path, context: str | None = None) -> str:
    """Build a structured prompt for the planner agent.

    Args:
        objective: The planning objective description.
        epic_folder: Epic folder name or Path; only the name (ID) is used, not
            the filesystem path.
        context: Optional additional context to include in the prompt.

    Returns:
        Formatted prompt string instructing the planner agent.
    """
    epic_folder_name = Path(epic_folder).name

    prompt_parts = [
        "You are a planner agent. Your task is to create a comprehensive implementation plan.",
        "",
        f"OBJECTIVE: {objective}",
        "",
        f"EPIC NAME: {epic_folder_name}",
        "",
        "INSTRUCTIONS:",
        "",
        "1. STORY DISCOVERY (MANDATORY - STORY-FIRST PLANNING FENCE):",
        "   Run `agentic stories find` to discover affected user stories BEFORE creating phases.",
        "   Story discovery must occur FIRST - it's a mandatory fence per planning-standard.yml.",
        "   Record affected story IDs in epic metadata (affected_stories field).",
        "   If no stories are found, you MUST provide no_stories_rationale explaining why.",
        "   Stories location: docs/userstories/",
        "",
        "2. WRITE README.md:",
        "   Create README.md in the epic folder with:",
        "   - Objective statement",
        "   - Phases overview",
        "   - Dependencies and prerequisites",
        "   - Success criteria",
        "",
        "3. CREATE TICKETS IN TinyDB via CLI:",
        "   Use the `agentic` CLI to create phases and tickets in TinyDB:",
        f"   - Add phases: `agentic epic phase add --epic {epic_folder_name} --name '<phase_name>'`",
        f"   - Add tickets: `agentic epic ticket add --epic {epic_folder_name} --phase '<phase_name>' --id '<ticket_id>' --name '<ticket_name>'`",
        "   Each ticket must have: id, name, guidance, target_files, inputs",
        "   Success criteria should be defined at epic level in README.md",
        "   Each ticket MUST declare target_files for parallelization decisions",
        "   Each ticket MUST declare inputs (project-specific context files to pre-read)",
        "   Reference: modules/AgenticGuidance/assets/guidelines/planning-standard.yml",
        "   NOTE: Do NOT create plan_build.yml or ticket_build.yml files on disk.",
        "         TinyDB is the sole data store for epic/ticket data.",
        "",
        "4. UAT PHASE (MANDATORY FENCE):",
        "   Every epic MUST include a User Acceptance Testing (UAT) phase.",
        "   UAT is mandatory per planning-standard.yml - epics without UAT are incomplete.",
        "   UAT must be anchored to user stories with acceptance criteria.",
        "   Select appropriate UAT strategy:",
        "   - test-user-simulator: For CLI tools and user journey validation",
        "   - guidance-blind-test: For documentation completeness validation",
        "   - documentation-loop: For end-user facing features needing docs validation",
        "   - manual: For complex scenarios requiring human judgment",
        "",
        "5. PLANNING STANDARD FENCES:",
        "   Your epic MUST comply with these mandatory fences:",
        "   - FENCE: STORY-FIRST PLANNING - Story discovery MUST occur before phase determination",
        "   - FENCE: UAT IS MANDATORY - Every epic must include a UAT phase",
        "   - FENCE: UAT USER STORY ANCHORING - UAT phases must trace back to user story IDs",
        "",
        "REQUIRED OUTPUTS:",
        f"- README.md in the epic folder",
        f"- Tickets created in TinyDB for epic '{epic_folder_name}'",
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
        "Then create tickets via the CLI in the specified epic.",
        "",
        "When complete, report the tickets you created and their IDs.",
    ])

    return "\n".join(prompt_parts)
