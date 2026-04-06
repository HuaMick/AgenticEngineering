"""
Unit tests for planner-build story generation guidance.

Tests verify that planner-build/process.yml includes proper story generation
steps and that the guidance enforces story generation when no stories are found.
"""

import pytest
import yaml
from pathlib import Path

pytestmark = pytest.mark.story("US-PLN-027", "US-PLN-030", "US-PLN-091", "US-STR-012", "US-GDN-048", "US-GDN-052")


@pytest.fixture
def planner_build_process():
    """Load planner-build/process.yml for testing."""
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-build" / "process.yml"
    with open(process_path, 'r') as f:
        return yaml.safe_load(f)


def test_planner_build_has_story_generation_step():
    """
    Test that planner-build/process.yml includes the USER STORY GENERATION step.

    Verifies:
    - "USER STORY GENERATION" section exists
    - Section includes "3-8 user stories" guidance
    - Section includes escape hatch rules
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-build" / "process.yml"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that USER STORY GENERATION section exists
    assert "USER STORY GENERATION (MANDATORY - when stories missing)" in content, \
        "planner-build/process.yml missing USER STORY GENERATION section"

    # Check for story quantity guidance
    assert "3-8 user stories" in content, \
        "Missing story quantity guidance (3-8 user stories)"

    # Check for escape hatch rules
    assert "ESCAPE HATCH" in content, \
        "Missing escape hatch guidance"

    # Check for story format specification
    assert "id: US-<PROJECT>-<NNN>" in content, \
        "Missing story ID format specification"

    # Check for required story fields
    assert "success_criteria" in content and "journey" in content and "testing" in content, \
        "Missing required story field specifications"


def test_story_generation_fence_blocks_without_stories():
    """
    Test that story generation guidance blocks plans without stories.

    This is a documentation test - verifies the guidance text requires
    story generation when `agentic stories find` returns empty.
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-build" / "process.yml"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that guidance mentions the fence behavior
    assert "If `agentic stories find` returns no stories" in content, \
        "Missing guidance for when story discovery returns empty"

    # Check that guidance requires story generation
    assert "MUST generate user stories" in content, \
        "Missing MUST requirement for story generation"

    # Check that guidance mentions affected_stories field
    assert "affected_stories" in content, \
        "Missing affected_stories field guidance"

    # Check that guidance mentions story_creation_tasks
    assert "story_creation_tasks" in content, \
        "Missing story_creation_tasks field guidance"


def test_story_format_includes_required_fields():
    """
    Test that story format guidance includes all required fields.

    Verifies the guidance specifies:
    - id, name, journey, success_criteria, testing fields
    - Measurable acceptance criteria (not vague)
    - Story categories and personas
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-build" / "process.yml"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check for required field specifications in story format
    required_fields = [
        "id:",
        "name:",
        "category:",
        "persona:",
        "priority:",
        "starting_state:",
        "journey:",
        "success_criteria:",
        "testing:"
    ]

    for field in required_fields:
        assert field in content, \
            f"Story format guidance missing required field: {field}"

    # Check for measurable criteria guidance
    assert "specific, measurable acceptance criteria" in content, \
        "Missing guidance on measurable acceptance criteria"

    # Check for anti-pattern guidance (no vague criteria)
    assert 'not vague "it works"' in content or "not vague" in content, \
        "Missing guidance against vague acceptance criteria"


def test_user_story_integration_section_updated():
    """
    Test that USER STORY INTEGRATION section title updated to mention generation.

    Verifies:
    - Section title includes "Discovery + Generation"
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-build" / "process.yml"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that section title was updated
    assert "USER STORY INTEGRATION (MANDATORY - Discovery + Generation)" in content, \
        "Section title should include 'Discovery + Generation'"


def test_success_criteria_includes_story_generation():
    """
    Test that success criteria section mentions user story generation.

    Verifies:
    - "User stories generated" appears in success criteria list
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-build" / "process.yml"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that success criteria includes story generation
    assert "User stories generated" in content, \
        "Success criteria missing 'User stories generated' requirement"

    # Verify it's in the success criteria section
    success_criteria_start = content.find("Success criteria MUST include user-focused validation:")
    story_generated_pos = content.find("User stories generated")

    assert success_criteria_start > 0, "Success criteria section not found"
    assert story_generated_pos > success_criteria_start, \
        "'User stories generated' should be in success criteria section"
