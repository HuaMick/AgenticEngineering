"""Tests for SDK env isolation (260308FX P2_003).

Validates that the SDK runner properly strips Claude Code env vars
before calling query(), restores them after, and logs appropriate warnings.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── Tests: _clean_claude_env context manager ─────────────────────────────


class TestCleanClaudeEnvContextManager:
    """Verify _clean_claude_env strips and restores env vars."""

    def test_strips_claudecode_var(self, monkeypatch):
        """CLAUDECODE should be absent inside the context manager."""
        from agenticcli.utils.sdk_runner import _clean_claude_env

        monkeypatch.setenv("CLAUDECODE", "1")

        with _clean_claude_env():
            assert "CLAUDECODE" not in os.environ

    def test_strips_entrypoint_var(self, monkeypatch):
        """CLAUDE_CODE_ENTRYPOINT should be absent inside the context manager."""
        from agenticcli.utils.sdk_runner import _clean_claude_env

        monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "test")

        with _clean_claude_env():
            assert "CLAUDE_CODE_ENTRYPOINT" not in os.environ

    def test_restores_vars_after_context(self, monkeypatch):
        """Both vars should be restored after the context manager exits."""
        from agenticcli.utils.sdk_runner import _clean_claude_env

        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "test-entry")

        with _clean_claude_env():
            pass

        assert os.environ.get("CLAUDECODE") == "1"
        assert os.environ.get("CLAUDE_CODE_ENTRYPOINT") == "test-entry"

    def test_restores_vars_on_exception(self, monkeypatch):
        """Vars should be restored even if an exception occurs inside the block."""
        from agenticcli.utils.sdk_runner import _clean_claude_env

        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "test-entry")

        with pytest.raises(ValueError):
            with _clean_claude_env():
                raise ValueError("simulated error")

        assert os.environ.get("CLAUDECODE") == "1"
        assert os.environ.get("CLAUDE_CODE_ENTRYPOINT") == "test-entry"

    def test_noop_when_vars_absent(self):
        """Should work without errors when vars are not set."""
        from agenticcli.utils.sdk_runner import _clean_claude_env

        # Ensure vars are not set
        os.environ.pop("CLAUDECODE", None)
        os.environ.pop("CLAUDE_CODE_ENTRYPOINT", None)

        with _clean_claude_env() as saved:
            assert saved == {}

    def test_logs_critical_when_vars_detected(self, monkeypatch, caplog):
        """Should log a critical warning when stripping vars."""
        from agenticcli.utils.sdk_runner import _clean_claude_env

        monkeypatch.setenv("CLAUDECODE", "1")

        with caplog.at_level(logging.CRITICAL):
            with _clean_claude_env():
                pass

        assert any("stripped Claude Code env vars" in r.message for r in caplog.records)

    def test_no_log_when_env_clean(self, caplog):
        """Should not log when no problematic vars are found."""
        from agenticcli.utils.sdk_runner import _clean_claude_env

        os.environ.pop("CLAUDECODE", None)
        os.environ.pop("CLAUDE_CODE_ENTRYPOINT", None)

        with caplog.at_level(logging.DEBUG):
            with _clean_claude_env():
                pass

        critical_records = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
        assert len(critical_records) == 0


# ── Tests: sdk_env_preflight ─────────────────────────────────────────────


class TestSdkEnvPreflight:
    """Verify sdk_env_preflight detects problematic env vars."""

    def test_detects_claudecode(self, monkeypatch):
        """Should detect CLAUDECODE when set."""
        from agenticcli.utils.sdk_runner import sdk_env_preflight

        monkeypatch.setenv("CLAUDECODE", "1")
        result = sdk_env_preflight()
        assert "CLAUDECODE" in result
        assert result["CLAUDECODE"] == "1"

    def test_detects_entrypoint(self, monkeypatch):
        """Should detect CLAUDE_CODE_ENTRYPOINT when set."""
        from agenticcli.utils.sdk_runner import sdk_env_preflight

        monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "vscode")
        result = sdk_env_preflight()
        assert "CLAUDE_CODE_ENTRYPOINT" in result

    def test_returns_empty_when_clean(self):
        """Should return empty dict when no problematic vars are set."""
        from agenticcli.utils.sdk_runner import sdk_env_preflight

        os.environ.pop("CLAUDECODE", None)
        os.environ.pop("CLAUDE_CODE_ENTRYPOINT", None)
        result = sdk_env_preflight()
        assert result == {}

    def test_logs_warning_when_vars_detected(self, monkeypatch, caplog):
        """Should log a warning when problematic vars are found."""
        from agenticcli.utils.sdk_runner import sdk_env_preflight

        monkeypatch.setenv("CLAUDECODE", "1")

        with caplog.at_level(logging.WARNING):
            sdk_env_preflight()

        assert any("SDK pre-flight check" in r.message for r in caplog.records)

    def test_does_not_modify_env(self, monkeypatch):
        """Pre-flight check should be read-only (not strip vars)."""
        from agenticcli.utils.sdk_runner import sdk_env_preflight

        monkeypatch.setenv("CLAUDECODE", "1")
        sdk_env_preflight()
        assert os.environ.get("CLAUDECODE") == "1"


# ── Tests: _ensure_clean_sdk_env ─────────────────────────────────────────


class TestEnsureCleanSdkEnv:
    """Verify _ensure_clean_sdk_env strips vars from options.env dict."""

    def test_strips_vars_from_options_env(self):
        """Should remove CLAUDECODE vars from options.env dict."""
        from agenticcli.utils.sdk_runner import _ensure_clean_sdk_env

        options = MagicMock()
        options.env = {
            "PATH": "/usr/bin",
            "CLAUDECODE": "1",
            "CLAUDE_CODE_ENTRYPOINT": "test",
            "HOME": "/home/user",
        }

        _ensure_clean_sdk_env(options)

        assert "CLAUDECODE" not in options.env
        assert "CLAUDE_CODE_ENTRYPOINT" not in options.env
        assert "PATH" in options.env
        assert "HOME" in options.env

    def test_handles_none_options(self):
        """Should not crash when options is None."""
        from agenticcli.utils.sdk_runner import _ensure_clean_sdk_env

        result = _ensure_clean_sdk_env(None)
        assert result is None

    def test_handles_no_env_attribute(self):
        """Should not crash when options has no env attribute."""
        from agenticcli.utils.sdk_runner import _ensure_clean_sdk_env

        options = MagicMock(spec=[])  # Empty spec, no attributes
        _ensure_clean_sdk_env(options)

    def test_handles_empty_env(self):
        """Should not crash when options.env is empty dict."""
        from agenticcli.utils.sdk_runner import _ensure_clean_sdk_env

        options = MagicMock()
        options.env = {}

        _ensure_clean_sdk_env(options)
        assert options.env == {}

    def test_handles_none_env(self):
        """Should not crash when options.env is None."""
        from agenticcli.utils.sdk_runner import _ensure_clean_sdk_env

        options = MagicMock()
        options.env = None

        _ensure_clean_sdk_env(options)
        assert options.env is None


# ── Tests: integration of env isolation in cmd_spawn SDK path ────────────


class TestCmdSpawnSdkEnvIsolation:
    """Verify that cmd_spawn's SDK path passes clean env to ClaudeAgentOptions."""

    def test_sdk_path_uses_get_clean_env(self):
        """Verify that cmd_spawn constructs SDK options with get_clean_env()."""
        # This is a structural test — we verify the pattern exists in the code.
        # The actual env cleaning is done by get_clean_env() which is already
        # tested in subprocess_utils tests.
        import inspect
        from agenticcli.commands.session import cmd_spawn

        source = inspect.getsource(cmd_spawn)
        assert "get_clean_env()" in source, \
            "cmd_spawn should pass get_clean_env() to ClaudeAgentOptions"
        assert "env=get_clean_env()" in source, \
            "SDK options should use env=get_clean_env()"
