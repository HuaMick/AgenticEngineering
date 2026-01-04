"""Tests for main CLI functionality."""


class TestCLIHelp:
    """Tests for CLI help output."""

    def test_main_help(self, cli_runner):
        """Test main --help output."""
        stdout, stderr, code = cli_runner(["--help"])
        assert "AgenticCLI" in stdout
        assert "worktree" in stdout
        assert "plan" in stdout
        assert "config" in stdout
        assert code == 0

    def test_no_args_shows_help(self, cli_runner):
        """Test that no args shows help."""
        stdout, stderr, code = cli_runner([])
        assert "usage:" in stdout.lower() or "AgenticCLI" in stdout
        assert code == 0


class TestSubcommandHelp:
    """Tests for subcommand help output."""

    def test_worktree_help(self, cli_runner):
        """Test worktree --help output."""
        stdout, stderr, code = cli_runner(["worktree", "--help"])
        assert "worktree" in stdout.lower()
        assert "create" in stdout
        assert "list" in stdout
        assert "remove" in stdout
        assert code == 0

    def test_plan_help(self, cli_runner):
        """Test plan --help output."""
        stdout, stderr, code = cli_runner(["plan", "--help"])
        assert "plan" in stdout.lower()
        assert "scaffold" in stdout
        assert "status" in stdout
        assert "validate" in stdout
        assert code == 0

    def test_config_help(self, cli_runner):
        """Test config --help output."""
        stdout, stderr, code = cli_runner(["config", "--help"])
        assert "config" in stdout.lower()
        assert "show" in stdout
        assert "get" in stdout
        assert "set" in stdout
        assert "delete" in stdout
        assert code == 0

    def test_template_help(self, cli_runner):
        """Test template --help output."""
        stdout, stderr, code = cli_runner(["template", "--help"])
        assert "template" in stdout.lower()
        assert "generate" in stdout
        assert "list" in stdout
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
        """Test 'wt' alias works for worktree."""
        result_full = cli_runner(["worktree", "--help"])
        result_alias = cli_runner(["wt", "--help"])
        assert result_full.returncode == 0
        assert result_alias.returncode == 0
        # Both should show worktree help
        assert "create" in result_alias.stdout
        assert "list" in result_alias.stdout

    def test_config_alias_cfg(self, cli_runner):
        """Test 'cfg' alias works for config."""
        result_full = cli_runner(["config", "--help"])
        result_alias = cli_runner(["cfg", "--help"])
        assert result_full.returncode == 0
        assert result_alias.returncode == 0
        # Both should show config help
        assert "show" in result_alias.stdout
        assert "get" in result_alias.stdout

    def test_template_alias_tpl(self, cli_runner):
        """Test 'tpl' alias works for template."""
        result_full = cli_runner(["template", "--help"])
        result_alias = cli_runner(["tpl", "--help"])
        assert result_full.returncode == 0
        assert result_alias.returncode == 0
        # Both should show template help
        assert "generate" in result_alias.stdout

    def test_stories_alias_st(self, cli_runner):
        """Test 'st' alias works for stories."""
        result_full = cli_runner(["stories", "--help"])
        result_alias = cli_runner(["st", "--help"])
        assert result_full.returncode == 0
        assert result_alias.returncode == 0
        # Both should show stories help
        assert "find" in result_alias.stdout

    def test_manifest_alias_mf(self, cli_runner):
        """Test 'mf' alias works for manifest."""
        result_full = cli_runner(["manifest", "--help"])
        result_alias = cli_runner(["mf", "--help"])
        assert result_full.returncode == 0
        assert result_alias.returncode == 0
        # Both should show manifest help
        assert "show" in result_alias.stdout


class TestFlagShortcuts:
    """Tests for flag shortcuts."""

    def test_json_flag_shortcut_j(self, cli_runner):
        """Test '-j' shortcut works for --json."""
        result = cli_runner(["-j", "health"])
        assert result.returncode == 0
        # Should be valid JSON output
        import json

        data = json.loads(result.stdout)
        assert "status" in data

    def test_help_shows_aliases(self, cli_runner):
        """Test main help shows aliases in epilog."""
        result = cli_runner(["--help"])
        assert result.returncode == 0
        # Check aliases are mentioned
        assert "(wt)" in result.stdout
        assert "(cfg)" in result.stdout
        assert "(tpl)" in result.stdout
        assert "(st)" in result.stdout
        assert "(mf)" in result.stdout
        # Check -j flag is documented
        assert "-j, --json" in result.stdout
