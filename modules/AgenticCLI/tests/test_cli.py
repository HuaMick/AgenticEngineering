"""Tests for main CLI functionality."""


class TestCLIHelp:
    """Tests for CLI help output."""

    def test_main_help(self, cli_runner):
        """Test main --help output."""
        stdout, stderr, code = cli_runner(["--help"])
        assert "AgenticCLI" in stdout
        assert "devops" in stdout
        assert "plan" in stdout
        assert "configure" in stdout
        assert "setup" in stdout
        assert "session" in stdout
        assert code == 0

    def test_no_args_shows_help(self, cli_runner):
        """Test that no args shows help."""
        stdout, stderr, code = cli_runner([])
        assert "usage:" in stdout.lower() or "AgenticCLI" in stdout
        assert code == 0


class TestSubcommandHelp:
    """Tests for subcommand help output."""

    def test_worktree_help(self, cli_runner):
        """Test devops worktree --help output."""
        stdout, stderr, code = cli_runner(["devops", "worktree", "--help"])
        assert "worktree" in stdout.lower()
        assert "create" in stdout
        assert "list" in stdout
        assert "remove" in stdout
        assert code == 0

    def test_plan_help(self, cli_runner):
        """Test plan --help output shows user-facing commands only."""
        stdout, stderr, code = cli_runner(["plan", "--help"])
        assert "plan" in stdout.lower()
        # User-facing commands should be visible
        assert "status" in stdout
        assert "list" in stdout
        assert "cancel" in stdout
        # Agent-facing commands should be hidden from command list.
        # Use line-based checks to avoid matching inside description text.
        lines = stdout.splitlines()
        # Find command-list lines (lines that start with a command name after the pipe char)
        cmd_lines = [line.strip().strip("|").strip() for line in lines
                     if line.strip().startswith("|") or line.strip().startswith("│")]
        cmd_names = [line.split()[0] for line in cmd_lines if line and line.split()[0].isalpha()]
        assert "scaffold" not in cmd_names
        assert "validate" not in cmd_names
        assert "task" not in cmd_names
        assert "phase" not in cmd_names
        assert "archive" not in cmd_names
        assert code == 0

    def test_config_help(self, cli_runner):
        """Test configure config --help output."""
        stdout, stderr, code = cli_runner(["configure", "config", "--help"])
        assert "config" in stdout.lower()
        assert "show" in stdout
        assert "get" in stdout
        assert "set" in stdout
        assert "delete" in stdout
        assert code == 0



class TestCLIVersion:
    """Tests for CLI version output."""

    def test_version(self, cli_runner):
        """Test --version output."""
        stdout, stderr, code = cli_runner(["--version"])
        assert "0.1.0" in stdout
        assert code == 0


class TestCommandAliases:
    """Tests for command aliases."""

    def test_worktree_alias_wt(self, cli_runner):
        """Test 'wt' alias works for worktree under devops."""
        result_full = cli_runner(["devops", "worktree", "--help"])
        result_alias = cli_runner(["devops", "wt", "--help"])
        assert result_full.returncode == 0
        assert result_alias.returncode == 0
        # Both should show worktree help
        assert "create" in result_alias.stdout
        assert "list" in result_alias.stdout

    def test_configure_alias_cfg(self, cli_runner):
        """Test 'cfg' alias works for configure."""
        result_full = cli_runner(["configure", "--help"])
        result_alias = cli_runner(["cfg", "--help"])
        assert result_full.returncode == 0
        assert result_alias.returncode == 0
        # Both should show configure subcommands
        assert "config" in result_alias.stdout
        assert "preferences" in result_alias.stdout

    def test_stories_alias_st(self, cli_runner):
        """Test 'stories' and 'st' commands now show deprecation messages."""
        for cmd in ["stories", "st"]:
            result = cli_runner([cmd])
            output = (result.stdout or "") + (result.stderr or "")
            normalized = " ".join(output.split())
            assert result.returncode == 1
            assert "agentic agent stories" in normalized

    def test_manifest_alias_mf(self, cli_runner):
        """Test 'manifest' and 'mf' commands now show deprecation messages."""
        for cmd in ["manifest", "mf"]:
            result = cli_runner([cmd])
            output = (result.stdout or "") + (result.stderr or "")
            normalized = " ".join(output.split())
            assert result.returncode == 1
            assert "agentic agent manifest" in normalized


class TestFlagShortcuts:
    """Tests for flag shortcuts."""

    def test_json_flag_shortcut_j(self, cli_runner):
        """Test '-j' shortcut works for --json."""
        result = cli_runner(["-j", "setup", "health"])
        assert result.returncode == 0
        # Should be valid JSON output
        import json

        data = json.loads(result.stdout)
        assert "status" in data

    def test_help_shows_aliases(self, cli_runner):
        """Test main help shows user-facing command names, not hidden ones."""
        result = cli_runner(["--help"])
        assert result.returncode == 0
        # Check user-facing top-level groups are visible
        assert "setup" in result.stdout
        assert "configure" in result.stdout
        assert "session" in result.stdout
        assert "devops" in result.stdout
        assert "question" in result.stdout
        assert "plan" in result.stdout
        assert "langsmith" in result.stdout
        # Hidden groups should NOT appear as command names in main help.
        # Use line-based checks to avoid matching inside description text.
        lines = result.stdout.splitlines()
        cmd_lines = [line.strip().strip("|").strip() for line in lines
                     if line.strip().startswith("|") or line.strip().startswith("\u2502")]
        cmd_names = [line.split()[0] for line in cmd_lines if line and line.split()[0].isalpha()]
        assert "stories" not in cmd_names
        assert "manifest" not in cmd_names
        assert "context" not in cmd_names
        assert "entrypoint" not in cmd_names
        assert "agent" not in cmd_names
        # Check -j flag is documented
        assert "-j" in result.stdout or "--json" in result.stdout
