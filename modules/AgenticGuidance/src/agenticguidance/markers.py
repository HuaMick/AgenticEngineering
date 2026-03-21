"""Production code story markers.

Tag functions or classes with user story IDs for traceability.
The decorator is a no-op at runtime — it stamps a ``_story_ids`` tuple
on the decorated object so that AST scanning can build a story-to-code index.

Usage::

    from agenticguidance.markers import story

    @story("US-CLI-110")
    def some_feature():
        ...

    @story("US-CLI-110", "US-CLI-111")
    def shared_feature():
        ...

Stacking merges IDs::

    @story("US-CLI-110")
    @story("US-CLI-111")
    def combined():
        ...
    # combined._story_ids == ("US-CLI-110", "US-CLI-111")
"""

from __future__ import annotations


def story(*story_ids: str):
    """Tag a function/class with user story IDs. No-op at runtime."""
    def decorator(obj):
        existing = getattr(obj, "_story_ids", ())
        obj._story_ids = tuple(sorted(set(existing + story_ids)))
        return obj
    return decorator
