"""Tests for EpicRepository.story_tests table (story-test hard link index).

Validates sync_story_tests(), get_tests_for_story(), get_stories_for_test(),
get_uncovered_stories(), and clear_story_tests() methods.
"""

from pathlib import Path

import pytest

from agenticguidance.services.epic_repository import EpicRepository

pytestmark = pytest.mark.story("US-STR-009")


@pytest.fixture
def repo(tmp_path):
    """Create an isolated EpicRepository."""
    db_path = tmp_path / "test.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


@pytest.mark.story("US-STR-009")
class TestSyncStoryTests:
    """Test sync_story_tests() bulk upsert."""

    def test_sync_empty_mappings(self, repo):
        count = repo.sync_story_tests({})
        assert count == 0

    def test_sync_single_story(self, repo):
        mappings = {
            "US-CLI-110": ["tests/test_foo.py::test_bar"],
        }
        count = repo.sync_story_tests(mappings)
        assert count == 1

    def test_sync_multiple_stories(self, repo):
        mappings = {
            "US-CLI-110": ["tests/test_a.py::test_1"],
            "US-CLI-111": ["tests/test_a.py::test_2", "tests/test_b.py::test_3"],
        }
        count = repo.sync_story_tests(mappings)
        assert count == 2

    def test_sync_upserts_existing(self, repo):
        repo.sync_story_tests({"US-CLI-110": ["tests/test_a.py::test_old"]})
        repo.sync_story_tests({"US-CLI-110": ["tests/test_a.py::test_new"]})
        tests = repo.get_tests_for_story("US-CLI-110")
        assert tests == ["tests/test_a.py::test_new"]

    def test_sync_stores_test_files(self, repo):
        mappings = {
            "US-CLI-110": [
                "tests/test_a.py::test_1",
                "tests/test_b.py::test_2",
                "tests/test_a.py::test_3",
            ],
        }
        repo.sync_story_tests(mappings)
        # Verify via raw table access that test_files are deduplicated and sorted
        from tinydb import Query
        ST = Query()
        docs = repo._story_tests.search(ST.story_id == "US-CLI-110")
        assert len(docs) == 1
        assert docs[0]["test_files"] == ["tests/test_a.py", "tests/test_b.py"]


@pytest.mark.story("US-STR-009")
class TestGetTestsForStory:
    """Test get_tests_for_story() lookup."""

    def test_existing_story(self, repo):
        repo.sync_story_tests({
            "US-CLI-110": ["tests/test_a.py::test_1", "tests/test_b.py::test_2"],
        })
        tests = repo.get_tests_for_story("US-CLI-110")
        assert "tests/test_a.py::test_1" in tests
        assert "tests/test_b.py::test_2" in tests

    def test_nonexistent_story(self, repo):
        assert repo.get_tests_for_story("US-NOPE-999") == []


@pytest.mark.story("US-STR-009")
class TestGetStoriesForTest:
    """Test get_stories_for_test() reverse lookup."""

    def test_test_linked_to_one_story(self, repo):
        repo.sync_story_tests({
            "US-CLI-110": ["tests/test_a.py::test_1"],
        })
        stories = repo.get_stories_for_test("tests/test_a.py::test_1")
        assert stories == ["US-CLI-110"]

    def test_test_linked_to_multiple_stories(self, repo):
        repo.sync_story_tests({
            "US-CLI-110": ["tests/test_a.py::test_shared"],
            "US-CLI-111": ["tests/test_a.py::test_shared"],
        })
        stories = repo.get_stories_for_test("tests/test_a.py::test_shared")
        assert sorted(stories) == ["US-CLI-110", "US-CLI-111"]

    def test_nonexistent_test(self, repo):
        assert repo.get_stories_for_test("tests/nonexistent.py::test_x") == []


@pytest.mark.story("US-STR-010", "US-STR-007", "US-GDN-066")
class TestGetUncoveredStories:
    """Test get_uncovered_stories() gap analysis."""

    def test_all_covered(self, repo):
        repo.sync_story_tests({
            "US-CLI-110": ["tests/test_a.py::test_1"],
            "US-CLI-111": ["tests/test_b.py::test_2"],
        })
        uncovered = repo.get_uncovered_stories({"US-CLI-110", "US-CLI-111"})
        assert uncovered == []

    def test_some_uncovered(self, repo):
        repo.sync_story_tests({
            "US-CLI-110": ["tests/test_a.py::test_1"],
        })
        uncovered = repo.get_uncovered_stories({"US-CLI-110", "US-CLI-111", "US-CLI-112"})
        assert uncovered == ["US-CLI-111", "US-CLI-112"]

    def test_all_uncovered(self, repo):
        uncovered = repo.get_uncovered_stories({"US-CLI-110", "US-CLI-111"})
        assert uncovered == ["US-CLI-110", "US-CLI-111"]

    def test_empty_input(self, repo):
        assert repo.get_uncovered_stories(set()) == []


@pytest.mark.story("US-STR-009")
class TestClearStoryTests:
    """Test clear_story_tests() wipe."""

    def test_clear_removes_all(self, repo):
        repo.sync_story_tests({
            "US-CLI-110": ["tests/test_a.py::test_1"],
            "US-CLI-111": ["tests/test_b.py::test_2"],
        })
        repo.clear_story_tests()
        assert repo.get_tests_for_story("US-CLI-110") == []
        assert repo.get_tests_for_story("US-CLI-111") == []

    def test_clear_on_empty_table(self, repo):
        repo.clear_story_tests()  # Should not raise
