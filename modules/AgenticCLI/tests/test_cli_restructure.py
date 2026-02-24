"""Tests for the CLI restructure (P05).

Validates:
- Agent group infrastructure and subcommands
- Hidden commands not visible in user-facing help
- User-facing commands visible in help
- Deprecation stubs (old paths print an error and exit 1)
"""


def _extract_cmd_names(help_output: str) -> list[str]:
    """Extract command names from Typer help output.

    Parses lines within the Commands section that start with the box-drawing
    pipe character or ASCII pipe, returning the first word on each such line.
    """
    lines = help_output.splitlines()
    cmd_names = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("\u2502") or stripped.startswith("|"):
            inner = stripped.lstrip("\u2502|").strip()
            if inner and inner.split()[0].isalpha():
                cmd_names.append(inner.split()[0])
    return cmd_names


# =========================================================================
# 1. Agent group infrastructure
# =========================================================================

class TestAgentGroupInfrastructure:
    """Verify the hidden 'agent' group and its sub-groups function correctly."""

    def test_agent_help_returns_zero(self, cli_runner):
        """agentic agent --help returns exit code 0."""
        result = cli_runner(["agent", "--help"])
        assert result.returncode == 0

    def test_agent_help_shows_subgroups(self, cli_runner):
        """agentic agent --help shows: plan, context, entrypoint, manifest, stories, question."""
        result = cli_runner(["agent", "--help"])
        assert result.returncode == 0
        output = result.stdout
        assert "plan" in output
        assert "context" in output
        assert "entrypoint" in output
        assert "manifest" in output
        assert "stories" in output
        assert "question" in output

    def test_agent_plan_help_returns_zero(self, cli_runner):
        """agentic agent plan --help returns exit code 0."""
        result = cli_runner(["agent", "plan", "--help"])
        assert result.returncode == 0

    def test_agent_plan_help_shows_subcommands(self, cli_runner):
        """agentic agent plan --help shows task, phase, archive, etc."""
        result = cli_runner(["agent", "plan", "--help"])
        assert result.returncode == 0
        output = result.stdout
        assert "task" in output
        assert "phase" in output
        assert "archive" in output
        assert "validate" in output
        assert "scaffold" in output
        assert "init" in output
        assert "bootstrap" in output

    def test_agent_plan_task_help_returns_zero(self, cli_runner):
        """agentic agent plan task --help returns exit code 0."""
        result = cli_runner(["agent", "plan", "task", "--help"])
        assert result.returncode == 0

    def test_agent_plan_task_help_shows_actions(self, cli_runner):
        """agentic agent plan task --help shows start, complete, list, etc."""
        result = cli_runner(["agent", "plan", "task", "--help"])
        assert result.returncode == 0
        output = result.stdout
        assert "start" in output
        assert "complete" in output
        assert "list" in output
        assert "status" in output

    def test_agent_context_help_returns_zero(self, cli_runner):
        """agentic agent context --help returns exit code 0."""
        result = cli_runner(["agent", "context", "--help"])
        assert result.returncode == 0

    def test_agent_context_help_shows_commands(self, cli_runner):
        """agentic agent context --help shows bootstrap, role, task, inputs."""
        result = cli_runner(["agent", "context", "--help"])
        assert result.returncode == 0
        output = result.stdout
        assert "bootstrap" in output
        assert "role" in output
        assert "task" in output
        assert "inputs" in output

    def test_agent_entrypoint_help_returns_zero(self, cli_runner):
        """agentic agent entrypoint --help returns exit code 0."""
        result = cli_runner(["agent", "entrypoint", "--help"])
        assert result.returncode == 0

    def test_agent_entrypoint_help_shows_commands(self, cli_runner):
        """agentic agent entrypoint --help shows list, show, execute."""
        result = cli_runner(["agent", "entrypoint", "--help"])
        assert result.returncode == 0
        output = result.stdout
        assert "list" in output
        assert "show" in output
        assert "execute" in output

    def test_agent_manifest_help_returns_zero(self, cli_runner):
        """agentic agent manifest --help returns exit code 0."""
        result = cli_runner(["agent", "manifest", "--help"])
        assert result.returncode == 0

    def test_agent_manifest_help_shows_commands(self, cli_runner):
        """agentic agent manifest --help shows show, list, validate."""
        result = cli_runner(["agent", "manifest", "--help"])
        assert result.returncode == 0
        output = result.stdout
        assert "show" in output
        assert "list" in output
        assert "validate" in output

    def test_agent_stories_help_returns_zero(self, cli_runner):
        """agentic agent stories --help returns exit code 0."""
        result = cli_runner(["agent", "stories", "--help"])
        assert result.returncode == 0

    def test_agent_stories_help_shows_commands(self, cli_runner):
        """agentic agent stories --help shows find, init, cat, etc."""
        result = cli_runner(["agent", "stories", "--help"])
        assert result.returncode == 0
        output = result.stdout
        assert "find" in output
        assert "init" in output

    def test_agent_question_help_returns_zero(self, cli_runner):
        """agentic agent question --help returns exit code 0."""
        result = cli_runner(["agent", "question", "--help"])
        assert result.returncode == 0

    def test_agent_question_help_shows_commands(self, cli_runner):
        """agentic agent question --help shows ask, defer, watch."""
        result = cli_runner(["agent", "question", "--help"])
        assert result.returncode == 0
        output = result.stdout
        assert "ask" in output
        assert "defer" in output
        assert "watch" in output


# =========================================================================
# 2. Hidden verification
# =========================================================================

class TestHiddenVerification:
    """Verify hidden groups do NOT appear in user-facing help output."""

    def test_main_help_shows_agent(self, cli_runner):
        """agentic --help contains 'agent' as a visible top-level group."""
        result = cli_runner(["--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "agent" in cmd_names

    def test_main_help_does_not_show_context(self, cli_runner):
        """agentic --help does NOT contain 'context' as a top-level group."""
        result = cli_runner(["--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "context" not in cmd_names

    def test_main_help_does_not_show_entrypoint(self, cli_runner):
        """agentic --help does NOT contain 'entrypoint' as a top-level group."""
        result = cli_runner(["--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "entrypoint" not in cmd_names

    def test_main_help_does_not_show_manifest(self, cli_runner):
        """agentic --help does NOT contain 'manifest' as a top-level group."""
        result = cli_runner(["--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "manifest" not in cmd_names

    def test_main_help_does_not_show_stories(self, cli_runner):
        """agentic --help does NOT contain 'stories' as a top-level group."""
        result = cli_runner(["--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "stories" not in cmd_names

    def test_plan_help_does_not_show_task(self, cli_runner):
        """agentic plan --help does NOT show 'task' as a subcommand."""
        result = cli_runner(["plan", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "task" not in cmd_names

    def test_plan_help_does_not_show_phase(self, cli_runner):
        """agentic plan --help does NOT show 'phase' as a subcommand."""
        result = cli_runner(["plan", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "phase" not in cmd_names

    def test_plan_help_does_not_show_archive(self, cli_runner):
        """agentic plan --help does NOT show 'archive' as a subcommand."""
        result = cli_runner(["plan", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "archive" not in cmd_names

    def test_question_help_does_not_show_ask(self, cli_runner):
        """agentic question --help does NOT show 'ask' as a subcommand."""
        result = cli_runner(["question", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "ask" not in cmd_names

    def test_plan_help_does_not_show_new(self, cli_runner):
        """agentic plan --help does NOT show 'new' since it is deprecated."""
        result = cli_runner(["plan", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "new" not in cmd_names


# =========================================================================
# 3. User-facing commands visible
# =========================================================================

class TestUserFacingCommandsVisible:
    """Verify that user-facing commands are properly visible in help."""

    def test_main_help_shows_expected_groups(self, cli_runner):
        """agentic --help shows: setup, configure, session, plan, question, langsmith, devops."""
        result = cli_runner(["--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "setup" in cmd_names
        assert "configure" in cmd_names
        assert "session" in cmd_names
        assert "plan" in cmd_names
        assert "question" in cmd_names
        assert "langsmith" in cmd_names
        assert "devops" in cmd_names

    def test_plan_help_shows_list(self, cli_runner):
        """agentic plan --help contains 'list'."""
        result = cli_runner(["plan", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "list" in cmd_names

    def test_plan_help_shows_status(self, cli_runner):
        """agentic plan --help contains 'status'."""
        result = cli_runner(["plan", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "status" in cmd_names

    def test_plan_help_shows_cancel(self, cli_runner):
        """agentic plan --help contains 'cancel'."""
        result = cli_runner(["plan", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "cancel" in cmd_names

    def test_plan_question_help_shows_list(self, cli_runner):
        """agentic plan question --help contains 'list'."""
        result = cli_runner(["plan", "question", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "list" in cmd_names

    def test_plan_question_help_shows_show(self, cli_runner):
        """agentic plan question --help contains 'show'."""
        result = cli_runner(["plan", "question", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "show" in cmd_names

    def test_plan_question_help_shows_answer(self, cli_runner):
        """agentic plan question --help contains 'answer'."""
        result = cli_runner(["plan", "question", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "answer" in cmd_names

    def test_plan_question_help_shows_dashboard(self, cli_runner):
        """agentic plan question --help contains 'dashboard'."""
        result = cli_runner(["plan", "question", "--help"])
        assert result.returncode == 0
        cmd_names = _extract_cmd_names(result.stdout)
        assert "dashboard" in cmd_names


# =========================================================================
# 4. Deprecation stubs
# =========================================================================

class TestDeprecationStubs:
    """Verify old command paths print an error message and exit 1."""

    def test_plan_task_list_help(self, cli_runner):
        """agentic plan task list exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "task", "list"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent plan task" in normalized

    def test_plan_task_start_help(self, cli_runner):
        """agentic plan task start exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "task", "start"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent plan task" in normalized

    def test_plan_task_complete_help(self, cli_runner):
        """agentic plan task complete exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "task", "complete"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent plan task" in normalized

    def test_plan_archive_help(self, cli_runner):
        """agentic plan archive exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "archive"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent plan archive" in normalized

    def test_plan_validate_help(self, cli_runner):
        """agentic plan validate exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "validate"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent plan validate" in normalized

    def test_plan_scaffold_help(self, cli_runner):
        """agentic plan scaffold exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "scaffold"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent plan scaffold" in normalized

    def test_plan_phase_help(self, cli_runner):
        """agentic plan phase exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "phase"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent plan phase" in normalized

    def test_context_bootstrap_help(self, cli_runner):
        """agentic context bootstrap exits 1 with a 'has moved' message."""
        result = cli_runner(["context", "bootstrap"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent context" in normalized

    def test_entrypoint_list_help(self, cli_runner):
        """agentic entrypoint list exits 1 with a 'has moved' message."""
        result = cli_runner(["entrypoint", "list"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent entrypoint" in normalized

    def test_manifest_list_help(self, cli_runner):
        """agentic manifest list exits 1 with a 'has moved' message."""
        result = cli_runner(["manifest", "list"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent manifest" in normalized

    def test_stories_find_help(self, cli_runner):
        """agentic stories find exits 1 with a 'has moved' message."""
        result = cli_runner(["stories", "find"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent stories" in normalized

    def test_question_ask_help(self, cli_runner):
        """agentic question ask exits 1 with a 'has moved' message."""
        result = cli_runner(["question", "ask"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized
        assert "agentic agent question ask" in normalized

    def test_question_defer_help(self, cli_runner):
        """agentic question defer exits 1 with a 'has moved' message."""
        result = cli_runner(["question", "defer"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized

    def test_plan_orchestration_help(self, cli_runner):
        """agentic plan orchestration exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "orchestration"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized

    def test_plan_stories_help(self, cli_runner):
        """agentic plan stories exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "stories"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized

    def test_plan_unarchive_help(self, cli_runner):
        """agentic plan unarchive exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "unarchive"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized

    def test_plan_init_help(self, cli_runner):
        """agentic plan init exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "init"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized

    def test_plan_bootstrap_help(self, cli_runner):
        """agentic plan bootstrap exits 1 with a 'has moved' message."""
        result = cli_runner(["plan", "bootstrap"])
        output = (result.stdout or "") + (result.stderr or "")
        normalized = " ".join(output.split())
        assert result.returncode == 1
        assert "has moved" in normalized


# =========================================================================
# 5. Agent path equivalence
# =========================================================================

class TestAgentPathEquivalence:
    """Verify that agent paths are accessible and functional."""

    def test_agent_plan_task_start_help(self, cli_runner):
        """agentic agent plan task start --help returns 0."""
        result = cli_runner(["agent", "plan", "task", "start", "--help"])
        assert result.returncode == 0

    def test_agent_plan_task_complete_help(self, cli_runner):
        """agentic agent plan task complete --help returns 0."""
        result = cli_runner(["agent", "plan", "task", "complete", "--help"])
        assert result.returncode == 0

    def test_agent_plan_archive_help(self, cli_runner):
        """agentic agent plan archive --help returns 0."""
        result = cli_runner(["agent", "plan", "archive", "--help"])
        assert result.returncode == 0

    def test_agent_plan_validate_help(self, cli_runner):
        """agentic agent plan validate --help returns 0."""
        result = cli_runner(["agent", "plan", "validate", "--help"])
        assert result.returncode == 0

    def test_agent_context_bootstrap_help(self, cli_runner):
        """agentic agent context bootstrap --help returns 0."""
        result = cli_runner(["agent", "context", "bootstrap", "--help"])
        assert result.returncode == 0

    def test_agent_entrypoint_list_help(self, cli_runner):
        """agentic agent entrypoint list --help returns 0."""
        result = cli_runner(["agent", "entrypoint", "list", "--help"])
        assert result.returncode == 0

    def test_agent_manifest_list_help(self, cli_runner):
        """agentic agent manifest list --help returns 0."""
        result = cli_runner(["agent", "manifest", "list", "--help"])
        assert result.returncode == 0

    def test_agent_stories_find_help(self, cli_runner):
        """agentic agent stories find --help returns 0."""
        result = cli_runner(["agent", "stories", "find", "--help"])
        assert result.returncode == 0

    def test_agent_question_ask_help(self, cli_runner):
        """agentic agent question ask --help returns 0."""
        result = cli_runner(["agent", "question", "ask", "--help"])
        assert result.returncode == 0

    def test_agent_plan_phase_help(self, cli_runner):
        """agentic agent plan phase --help returns 0."""
        result = cli_runner(["agent", "plan", "phase", "--help"])
        assert result.returncode == 0

    def test_agent_plan_move_help(self, cli_runner):
        """agentic agent plan move --help returns 0."""
        result = cli_runner(["agent", "plan", "move", "--help"])
        assert result.returncode == 0

    def test_agent_plan_orchestration_help(self, cli_runner):
        """agentic agent plan orchestration --help returns 0."""
        result = cli_runner(["agent", "plan", "orchestration", "--help"])
        assert result.returncode == 0

    def test_agent_plan_stories_help(self, cli_runner):
        """agentic agent plan stories --help returns 0."""
        result = cli_runner(["agent", "plan", "stories", "--help"])
        assert result.returncode == 0
