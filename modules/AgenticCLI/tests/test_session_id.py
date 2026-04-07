"""Tests for session ID generation and tmux session naming (Bug 2 — naming fix)."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.story("US-SES-001")

from agenticcli.utils.session_id import generate_session_id, tmux_session_name


@pytest.mark.story("US-SES-001")
class TestGenerateSessionId:
    """Basic tests for generate_session_id."""

    def test_returns_non_empty_string(self):
        """generate_session_id returns a non-empty string."""
        sid = generate_session_id()
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_returns_unique_values(self):
        """Each call returns a different session ID."""
        assert generate_session_id() != generate_session_id()


@pytest.mark.story("US-SES-001")
class TestTmuxSessionName:
    """Tests for tmux_session_name function (Bug 2 — collision fix)."""

    def test_epic_role_name_includes_session_id(self):
        """Session ID prefix appears in name when epic+role provided."""
        name = tmux_session_name("abc12345-6789", epic_folder=Path("260311PB_test"), role="build-python")
        assert "abc123" in name  # session_id[:6]

    def test_different_session_ids_produce_different_names(self):
        """Same epic/role but different session_ids produce different names."""
        name1 = tmux_session_name("aaaa1111-2222", epic_folder=Path("260311PB_test"), role="build-python")
        name2 = tmux_session_name("bbbb3333-4444", epic_folder=Path("260311PB_test"), role="build-python")
        assert name1 != name2

    def test_backward_compat_no_epic(self):
        """Without epic, format is agentic-spawn-{session_id[:8]}."""
        name = tmux_session_name("abc12345-6789")
        assert name == "agentic-spawn-abc12345"

    def test_epic_only_no_role(self):
        """With epic but no role, session_id[:8] appears in the name."""
        name = tmux_session_name("abc12345-6789", epic_folder=Path("260311PB_test"))
        assert "abc12345" in name

    def test_sanitizes_special_characters(self):
        """Special characters in epic folder name get sanitized away."""
        name = tmux_session_name("abc12345", epic_folder=Path("260311PB_test@special"), role="build-python")
        assert "@" not in name

    def test_name_has_no_leading_or_trailing_hyphens(self):
        """Result never starts or ends with a hyphen."""
        name = tmux_session_name("abc12345-6789", epic_folder=Path("260311PB_test"), role="build-python")
        assert not name.startswith("-")
        assert not name.endswith("-")

    def test_consecutive_hyphens_collapsed(self):
        """Consecutive hyphens are collapsed into a single hyphen."""
        name = tmux_session_name("abc12345", epic_folder=Path("260311PB_test!!name"), role="build-python")
        assert "--" not in name
