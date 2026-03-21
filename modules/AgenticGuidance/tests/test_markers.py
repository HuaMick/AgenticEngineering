"""Tests for the @story() production code decorator."""

from agenticguidance.markers import story


def test_single_story_id():
    @story("US-CLI-001")
    def my_func():
        pass

    assert my_func._story_ids == ("US-CLI-001",)


def test_multiple_story_ids():
    @story("US-CLI-001", "US-CLI-002")
    def my_func():
        pass

    assert my_func._story_ids == ("US-CLI-001", "US-CLI-002")


def test_stacking_merges_ids():
    @story("US-CLI-001")
    @story("US-CLI-002")
    def my_func():
        pass

    assert set(my_func._story_ids) == {"US-CLI-001", "US-CLI-002"}


def test_stacking_deduplicates():
    @story("US-CLI-001")
    @story("US-CLI-001", "US-CLI-002")
    def my_func():
        pass

    assert set(my_func._story_ids) == {"US-CLI-001", "US-CLI-002"}


def test_class_decoration():
    @story("US-CLI-003")
    class MyClass:
        pass

    assert MyClass._story_ids == ("US-CLI-003",)


def test_noop_behavior():
    """Decorator should not alter function behavior."""
    @story("US-CLI-001")
    def add(a, b):
        return a + b

    assert add(1, 2) == 3


def test_sorted_ids():
    @story("US-CLI-003", "US-CLI-001", "US-CLI-002")
    def my_func():
        pass

    assert my_func._story_ids == ("US-CLI-001", "US-CLI-002", "US-CLI-003")


def test_no_ids():
    @story()
    def my_func():
        pass

    assert my_func._story_ids == ()
