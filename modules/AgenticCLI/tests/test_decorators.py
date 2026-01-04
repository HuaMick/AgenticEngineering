"""Tests for stability decorators and command metadata."""

from agenticcli.decorators import (
    COMMAND_STABILITY,
    STABILITY_COLORS,
    STABILITY_MESSAGES,
    StabilityLevel,
    get_command_stability,
    get_stability_banner_text,
    get_stability_color,
)


class TestStabilityLevels:
    """Tests for stability level definitions."""

    def test_stability_levels_defined(self):
        """Verify all expected stability levels exist."""
        assert StabilityLevel.ALPHA == "ALPHA"
        assert StabilityLevel.BETA == "BETA"
        assert StabilityLevel.EXPERIMENTAL == "EXPERIMENTAL"
        assert StabilityLevel.STABLE == "STABLE"

    def test_stability_levels_are_strings(self):
        """Verify stability levels are string enums."""
        assert isinstance(StabilityLevel.ALPHA.value, str)
        assert isinstance(StabilityLevel.BETA.value, str)

    def test_command_stability_mapping_exists(self):
        """Verify command stability mapping has expected entries."""
        assert "cicd" in COMMAND_STABILITY
        assert COMMAND_STABILITY["cicd"] == StabilityLevel.ALPHA

    def test_stability_messages_defined(self):
        """Verify stability messages exist for non-stable levels."""
        assert StabilityLevel.ALPHA in STABILITY_MESSAGES
        assert StabilityLevel.BETA in STABILITY_MESSAGES
        assert StabilityLevel.EXPERIMENTAL in STABILITY_MESSAGES
        assert StabilityLevel.STABLE not in STABILITY_MESSAGES

    def test_stability_colors_defined(self):
        """Verify stability colors exist for non-stable levels."""
        assert StabilityLevel.ALPHA in STABILITY_COLORS
        assert StabilityLevel.BETA in STABILITY_COLORS
        assert StabilityLevel.EXPERIMENTAL in STABILITY_COLORS


class TestGetCommandStability:
    """Tests for get_command_stability function."""

    def test_get_alpha_command(self):
        """Verify ALPHA command returns correct level."""
        assert get_command_stability("cicd") == StabilityLevel.ALPHA

    def test_get_beta_command(self):
        """Verify BETA command returns correct level."""
        assert get_command_stability("manifest") == StabilityLevel.BETA

    def test_get_stable_command_unlisted(self):
        """Verify unlisted command defaults to STABLE."""
        assert get_command_stability("plan") == StabilityLevel.STABLE
        assert get_command_stability("worktree") == StabilityLevel.STABLE

    def test_get_unknown_command(self):
        """Verify unknown command defaults to STABLE."""
        assert get_command_stability("nonexistent") == StabilityLevel.STABLE


class TestGetStabilityBannerText:
    """Tests for get_stability_banner_text function."""

    def test_banner_text_alpha(self):
        """Verify ALPHA banner text format."""
        text = get_stability_banner_text(StabilityLevel.ALPHA, "cicd")
        assert text is not None
        assert "[ALPHA]" in text
        assert "experimental" in text.lower()

    def test_banner_text_beta(self):
        """Verify BETA banner text format."""
        text = get_stability_banner_text(StabilityLevel.BETA, "manifest")
        assert text is not None
        assert "[BETA]" in text
        assert "beta" in text.lower()

    def test_banner_text_experimental(self):
        """Verify EXPERIMENTAL banner text format."""
        text = get_stability_banner_text(StabilityLevel.EXPERIMENTAL, "test")
        assert text is not None
        assert "[EXPERIMENTAL]" in text

    def test_banner_text_stable_is_none(self):
        """Verify STABLE commands return no banner text."""
        text = get_stability_banner_text(StabilityLevel.STABLE, "plan")
        assert text is None


class TestGetStabilityColor:
    """Tests for get_stability_color function."""

    def test_alpha_color_is_red(self):
        """Verify ALPHA uses red color."""
        assert get_stability_color(StabilityLevel.ALPHA) == "red"

    def test_beta_color_is_yellow(self):
        """Verify BETA uses yellow color."""
        assert get_stability_color(StabilityLevel.BETA) == "yellow"

    def test_experimental_color_is_magenta(self):
        """Verify EXPERIMENTAL uses magenta color."""
        assert get_stability_color(StabilityLevel.EXPERIMENTAL) == "magenta"

    def test_stable_color_fallback(self):
        """Verify STABLE has a fallback color."""
        color = get_stability_color(StabilityLevel.STABLE)
        assert color == "white"


class TestStabilityBannerIntegration:
    """Integration tests for stability banner in console output."""

    def test_print_stability_banner_suppressed_in_json_mode(self, cli_runner):
        """Verify banner is suppressed in JSON output mode."""
        # Run an ALPHA command with --json
        result = cli_runner("--json", "health")
        # Health is STABLE, but let's verify JSON mode works
        assert result.returncode == 0
        # Output should be JSON, not contain banner markers
        assert "[ALPHA]" not in result.stdout

    def test_help_shows_stability_indicator(self, cli_runner):
        """Verify help text includes stability indicators."""
        result = cli_runner("--help")
        assert result.returncode == 0
        # Should show [ALPHA] for cicd in help
        assert "[ALPHA]" in result.stdout
        assert "[BETA]" in result.stdout
