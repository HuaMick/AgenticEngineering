"""Smoke coverage: every `agentic stories <cmd> <args>` invocation must dispatch
without AttributeError.

Regression context: `agentic stories status US-PLN-046` crashed with
``AttributeError: 'types.SimpleNamespace' object has no attribute 'id'`` because
the typer binding passed ``story_id=...`` into the namespace but
``cmd_status`` read ``args.id``. Blind-agent UAT had no way to catch this
silently — the agent just exits. These tests invoke each subcommand in-process
with a mock-friendly story service and assert that the attribute wiring does
not raise. A missing story is an acceptable outcome (sys.exit(1)) as long as it
does not raise ``AttributeError``.
"""
from __future__ import annotations

import sys
import subprocess

import pytest

pytestmark = pytest.mark.story("US-SES-001")


def _run_cli(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    """Invoke `agentic <args>` as a subprocess and capture output."""
    return subprocess.run(
        ["agentic", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestStoriesStatusAttrWiring:
    """Direct regression for P5-F1: stories status args.id/story_id mismatch."""

    def test_status_known_story_does_not_raise_attributeerror(self):
        """`agentic stories status US-PLN-046` exits without AttributeError."""
        result = _run_cli(["stories", "status", "US-PLN-046"])
        # Either it prints status (returncode 0) or reports story-not-found
        # (returncode 1). Either is fine; what matters is we didn't crash.
        assert "AttributeError" not in result.stderr, (
            f"stories status raised AttributeError:\n{result.stderr}"
        )
        assert "AttributeError" not in result.stdout, (
            f"stories status printed AttributeError:\n{result.stdout}"
        )

    def test_status_unknown_story_does_not_raise_attributeerror(self):
        """Unknown story returns a clean 'not found' error, not AttributeError."""
        result = _run_cli(["stories", "status", "US-XXX-99999"])
        assert "AttributeError" not in result.stderr
        assert "AttributeError" not in result.stdout


class TestStoriesHandlerAttrContract:
    """Unit guard: every cmd_* handler reads attributes that the typer binding
    actually provides via _ns(...). We check by invoking the handler with a
    SimpleNamespace mirroring the real dispatch contract.
    """

    def test_cmd_status_reads_story_id_attribute(self, monkeypatch):
        """cmd_status must accept a namespace with `story_id` (not just `id`)."""
        import types
        from agenticcli.commands import stories

        # Stub StoryService so we don't need real story files.
        class FakeStory:
            id = "US-PLN-046"
            title = "Fake"
            status = "pass"
            lifecycle = "implemented"
            last_tested = "2026-04-15"
            notes = ""
            tested_by_plan = ""
            last_pass_commit = "abc"
            last_uat_commit = "def"

            def __getattr__(self, name):
                return None

        class FakeService:
            def __init__(self, *a, **kw):
                pass
            def get_by_id(self, sid):
                return FakeStory() if sid == "US-PLN-046" else None

        monkeypatch.setattr(stories, "StoryService", FakeService)
        monkeypatch.setattr(
            stories, "_find_userstories_dir", lambda: "/tmp/noop", raising=False
        )
        # Patch the repo so code-coverage lookup doesn't touch TinyDB.
        import agenticguidance.services.epic_repository as er_mod
        class FakeRepo:
            def __init__(self, *a, **kw): pass
            def get_code_for_story(self, sid): return []
        monkeypatch.setattr(er_mod, "EpicRepository", FakeRepo)
        monkeypatch.setattr(
            stories, "_get_repo_db_path", lambda: "/tmp/none.db", raising=False
        )

        # This is exactly the namespace the typer binding constructs.
        args = types.SimpleNamespace(
            stories_command="status",
            story_id="US-PLN-046",
            json=False,
            debug=False,
        )
        # Must not raise AttributeError for missing `.id`.
        try:
            stories.cmd_status(args)
        except SystemExit:
            pass  # `sys.exit(1)` on story-not-found is fine
        except AttributeError as e:
            pytest.fail(f"cmd_status raised AttributeError on valid namespace: {e}")


class TestStoriesCliCoverageMatrix:
    """Smoke each stories subcommand that takes a positional story id."""

    @pytest.mark.parametrize(
        "subcmd",
        ["status", "code", "promote", "deprecate", "archive", "pattern-check"],
    )
    def test_subcommand_accepts_story_id_without_attributeerror(self, subcmd):
        """Each subcommand must dispatch without AttributeError for a real story id."""
        story_id = "US-PLN-046"
        result = _run_cli(["stories", subcmd, story_id])
        assert "AttributeError" not in result.stderr, (
            f"`stories {subcmd} {story_id}` raised AttributeError:\n{result.stderr}"
        )
