import os

import pytest

from agenticcli.utils.subprocess_utils import get_clean_env


def test_strips_claudecode(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    env = get_clean_env()
    assert "CLAUDECODE" not in env


def test_strips_claude_code_entrypoint(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    env = get_clean_env()
    assert "CLAUDE_CODE_ENTRYPOINT" not in env


def test_does_not_mutate_os_environ(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    get_clean_env()
    assert "CLAUDECODE" in os.environ


def test_preserves_other_vars(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    env = get_clean_env()
    assert env.get("PATH") == "/usr/bin:/bin"


def test_custom_base_env():
    base = {"CLAUDECODE": "1", "HOME": "/home/test", "FOO": "bar"}
    env = get_clean_env(base_env=base)
    assert "CLAUDECODE" not in env
    assert env.get("HOME") == "/home/test"
    assert env.get("FOO") == "bar"


def test_no_claudecode_in_env(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)
    env = get_clean_env()
    assert "CLAUDECODE" not in env
    assert "CLAUDE_CODE_ENTRYPOINT" not in env
