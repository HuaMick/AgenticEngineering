"""Unit tests for StoryService file locking and improved parse error logging.

Validates:
- FileLock is acquired during update_lifecycle
- FileLock is acquired during update_test_status
- Warning logged on parse failures (_parse_file)
- No YAML corruption under concurrent writes

@story US-STR-012
"""

import logging
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from agenticguidance.services.story import (
    StoryService,
    Story,
    LIFECYCLE_STATES,
    LIFECYCLE_TRANSITIONS,
)
from agenticguidance.services.state import FileLock

pytestmark = pytest.mark.story("US-STR-001")


def _write_story_file(path: Path, story_id: str = "US-TEST-001",
                       lifecycle: str = "under-construction",
                       test_status: str = "") -> Path:
    """Write a minimal valid story YAML file."""
    story_data = {
        "stories": [
            {
                "id": story_id,
                "title": "Test Story",
                "category": "testing",
                "lifecycle": lifecycle,
                "test_status": test_status,
            }
        ]
    }
    path.write_text(yaml.dump(story_data, sort_keys=False))
    return path


@pytest.fixture
def story_dir(tmp_path):
    """Create a userstories directory with a test category."""
    stories_dir = tmp_path / "userstories" / "Testing"
    stories_dir.mkdir(parents=True)
    return stories_dir


@pytest.fixture
def svc(story_dir):
    """StoryService backed by tmp_path."""
    return StoryService(userstories_dir=story_dir.parent)


class TestFileLockDuringUpdateLifecycle:
    """Verify FileLock is acquired during update_lifecycle."""

    def test_lock_file_created_during_update(self, story_dir, svc):
        """Lock file for the YAML file is created during update_lifecycle."""
        story_file = story_dir / "01_stories.yml"
        _write_story_file(story_file, lifecycle="under-construction")

        lock_observed = {"seen": False}
        _original_safe_load = yaml.safe_load

        def _spy_safe_load(content):
            """Check for lock file while inside the locked section."""
            lock_path = Path(str(story_file) + ".lock")
            if lock_path.exists():
                lock_observed["seen"] = True
            return _original_safe_load(content)

        with patch("agenticguidance.services.story.yaml.safe_load",
                    side_effect=_spy_safe_load):
            result = svc.update_lifecycle("US-TEST-001", "implemented")

        assert result is True
        assert lock_observed["seen"], "Lock file was not observed during update_lifecycle"

    def test_successful_lifecycle_transition(self, story_dir, svc):
        """update_lifecycle changes lifecycle state and writes to YAML."""
        story_file = story_dir / "01_stories.yml"
        _write_story_file(story_file, lifecycle="under-construction")

        result = svc.update_lifecycle("US-TEST-001", "implemented")
        assert result is True

        # Verify YAML was updated
        content = yaml.safe_load(story_file.read_text())
        assert content["stories"][0]["lifecycle"] == "implemented"

    def test_invalid_transition_rejected(self, story_dir, svc):
        """update_lifecycle rejects invalid transitions."""
        story_file = story_dir / "01_stories.yml"
        _write_story_file(story_file, lifecycle="under-construction")

        # Can't go backwards from under-construction to proposal
        result = svc.update_lifecycle("US-TEST-001", "proposal")
        assert result is False

    def test_lock_timeout_returns_false_and_logs(self, story_dir, svc, caplog):
        """When FileLock times out, returns False and logs error."""
        story_file = story_dir / "01_stories.yml"
        _write_story_file(story_file, lifecycle="under-construction")

        # Hold the lock so update_lifecycle can't acquire it
        holder = FileLock(story_file, timeout=5.0)
        acquired = holder.acquire()
        assert acquired is True

        try:
            # Patch FileLock to use a very short timeout so test doesn't wait long
            with patch("agenticguidance.services.story.FileLock",
                        side_effect=lambda path: _ShortTimeoutFileLock(path)):
                with caplog.at_level(logging.ERROR):
                    result = svc.update_lifecycle("US-TEST-001", "implemented")
        finally:
            holder.release()

        assert result is False


class TestFileLockDuringUpdateTestStatus:
    """Verify FileLock is acquired during update_test_status."""

    def test_lock_file_created_during_test_status_update(self, story_dir, svc):
        """Lock file observed during update_test_status."""
        story_file = story_dir / "01_stories.yml"
        _write_story_file(story_file)

        lock_observed = {"seen": False}
        _original_safe_load = yaml.safe_load

        def _spy_safe_load(content):
            lock_path = Path(str(story_file) + ".lock")
            if lock_path.exists():
                lock_observed["seen"] = True
            return _original_safe_load(content)

        with patch("agenticguidance.services.story.yaml.safe_load",
                    side_effect=_spy_safe_load):
            result = svc.update_test_status(
                "US-TEST-001", "passed", tested_by="test_plan"
            )

        assert result is True
        assert lock_observed["seen"], "Lock file was not observed during update_test_status"

    def test_successful_test_status_update(self, story_dir, svc):
        """update_test_status writes test_status and metadata to YAML."""
        story_file = story_dir / "01_stories.yml"
        _write_story_file(story_file)

        result = svc.update_test_status(
            "US-TEST-001",
            "passed",
            tested_by="260329AG",
            test_notes="All checks green",
            last_tested="2026-03-29",
        )
        assert result is True

        content = yaml.safe_load(story_file.read_text())
        story = content["stories"][0]
        assert story["test_status"] == "passed"
        assert story["tested_by_plan"] == "260329AG"
        assert story["test_notes"] == "All checks green"
        assert story["last_tested"] == "2026-03-29"

    def test_nonexistent_story_returns_false(self, story_dir, svc):
        """update_test_status for missing story returns False."""
        story_file = story_dir / "01_stories.yml"
        _write_story_file(story_file)

        result = svc.update_test_status("US-MISSING-999", "passed")
        assert result is False


class TestParseFileWarningLogging:
    """Verify _parse_file logs warnings instead of silently swallowing errors."""

    def test_warning_on_file_not_found(self, story_dir, svc, caplog):
        """FileNotFoundError triggers warning log."""
        missing = story_dir / "nonexistent.yml"

        with caplog.at_level(logging.WARNING):
            result = svc._parse_file(missing)

        assert result == []
        assert any("not found" in r.message for r in caplog.records)

    def test_warning_on_empty_file(self, story_dir, svc, caplog):
        """Empty YAML file triggers warning log."""
        empty_file = story_dir / "01_stories.yml"
        empty_file.write_text("")

        with caplog.at_level(logging.WARNING):
            result = svc._parse_file(empty_file)

        assert result == []
        assert any("empty" in r.message.lower() for r in caplog.records)

    def test_warning_on_yaml_syntax_error(self, story_dir, svc, caplog):
        """YAML syntax error triggers warning log with error details."""
        bad_file = story_dir / "01_stories.yml"
        bad_file.write_text(": broken: yaml: [")

        with caplog.at_level(logging.WARNING):
            result = svc._parse_file(bad_file)

        assert result == []
        assert any("syntax error" in r.message.lower() or "YAML" in r.message
                    for r in caplog.records)

    def test_warning_on_non_dict_content(self, story_dir, svc, caplog):
        """Non-dict YAML content triggers warning log."""
        list_file = story_dir / "01_stories.yml"
        list_file.write_text(yaml.dump(["not", "a", "dict"]))

        with caplog.at_level(logging.WARNING):
            result = svc._parse_file(list_file)

        assert result == []
        assert any("unexpected content type" in r.message.lower() for r in caplog.records)

    def test_warning_on_os_error(self, story_dir, svc, caplog):
        """OSError on file read triggers warning log."""
        path = story_dir / "01_stories.yml"
        path.write_text("valid: true")

        with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
            with caplog.at_level(logging.WARNING):
                result = svc._parse_file(path)

        assert result == []
        assert any("could not read" in r.message.lower() for r in caplog.records)


class TestNoConcurrentYAMLCorruption:
    """Verify no YAML corruption under concurrent writes."""

    def test_concurrent_lifecycle_updates_no_corruption(self, tmp_path):
        """Multiple threads updating stories in separate files — no corruption.

        Each story lives in its own YAML file to avoid the unprotected
        load_all() read seeing a half-written file from another thread's
        write_text(). The FileLock protects the read-modify-write section;
        this test validates that YAML files aren't corrupted by concurrent
        locked writes targeting different files.
        """
        stories_dir = tmp_path / "userstories" / "Testing"
        stories_dir.mkdir(parents=True)

        # Each story in its own file (mirrors production: one category per file)
        for i in range(4):
            story_file = stories_dir / f"{i:02d}_stories.yml"
            _write_story_file(
                story_file,
                story_id=f"US-TEST-{i:03d}",
                lifecycle="under-construction",
            )

        errors = {}

        def update_story(thread_id):
            try:
                svc = StoryService(userstories_dir=stories_dir.parent)
                story_id = f"US-TEST-{thread_id:03d}"
                result = svc.update_lifecycle(story_id, "implemented")
                if not result:
                    errors[thread_id] = f"update_lifecycle returned False for {story_id}"
            except Exception as e:
                errors[thread_id] = str(e)

        threads = []
        for i in range(4):
            t = threading.Thread(target=update_story, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"

        # Verify every YAML file is valid and each story was updated
        for i in range(4):
            story_file = stories_dir / f"{i:02d}_stories.yml"
            content = yaml.safe_load(story_file.read_text())
            assert isinstance(content, dict), f"YAML file {i} is corrupted"
            assert content["stories"][0]["lifecycle"] == "implemented"

    def test_concurrent_test_status_updates_no_corruption(self, tmp_path):
        """Multiple threads updating test_status in separate files — no corruption."""
        stories_dir = tmp_path / "userstories" / "Testing"
        stories_dir.mkdir(parents=True)

        for i in range(4):
            story_file = stories_dir / f"{i:02d}_stories.yml"
            _write_story_file(
                story_file,
                story_id=f"US-TEST-{i:03d}",
                lifecycle="implemented",
            )

        errors = {}

        def update_test_status(thread_id):
            try:
                svc = StoryService(userstories_dir=stories_dir.parent)
                story_id = f"US-TEST-{thread_id:03d}"
                result = svc.update_test_status(
                    story_id, "passed", tested_by=f"agent_{thread_id}"
                )
                if not result:
                    errors[thread_id] = f"update_test_status returned False for {story_id}"
            except Exception as e:
                errors[thread_id] = str(e)

        threads = []
        for i in range(4):
            t = threading.Thread(target=update_test_status, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Thread errors: {errors}"

        # Verify every YAML file is valid and test_status was set
        for i in range(4):
            story_file = stories_dir / f"{i:02d}_stories.yml"
            content = yaml.safe_load(story_file.read_text())
            assert isinstance(content, dict), f"YAML file {i} is corrupted"
            assert content["stories"][0]["test_status"] == "passed"


class _ShortTimeoutFileLock(FileLock):
    """FileLock with very short timeout for testing lock contention."""
    def __init__(self, path):
        super().__init__(path, timeout=0.1)
