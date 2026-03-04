"""
Unit tests for orchestration-planning story validation gate.

Tests verify that orchestration-planning/process.mmd includes proper story
content validation gates and that planning-standard.yml clarifies the story lifecycle.
"""

import pytest
from pathlib import Path


def test_orchestration_has_content_validation_gate():
    """
    Test that orchestration-planning/process.mmd includes story content validation.

    Verifies:
    - ValidateStoryContent node exists after RecordStories
    - Gate checks for missing files and incomplete fields
    - Flow includes BlockIncompleteStories and BlockMissingStories nodes
    """
    process_path = Path(__file__).parent.parent / "agents" / "orchestration" / "orchestration-planning" / "process.mmd"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that ValidateStoryContent node exists
    assert "ValidateStoryContent" in content, \
        "Missing ValidateStoryContent node in orchestration-planning/process.mmd"

    # Check that it comes after RecordStories
    record_pos = content.find("RecordStories")
    validate_pos = content.find("ValidateStoryContent")

    assert record_pos > 0, "RecordStories node not found"
    assert validate_pos > record_pos, \
        "ValidateStoryContent should come after RecordStories in the flow"

    # Check for StoryFilesExist decision node
    assert "StoryFilesExist" in content, \
        "Missing StoryFilesExist decision node"

    # Check for block nodes
    assert "BlockIncompleteStories" in content, \
        "Missing BlockIncompleteStories block node"

    assert "BlockMissingStories" in content, \
        "Missing BlockMissingStories block node"


def test_orchestration_blocks_incomplete_stories():
    """
    Test that orchestration flow blocks when stories have incomplete content.

    Verifies:
    - Flow path for incomplete stories exists
    - Error message mentions missing fields
    """
    process_path = Path(__file__).parent.parent / "agents" / "orchestration" / "orchestration-planning" / "process.mmd"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check for incomplete content path
    assert "Incomplete: Missing Fields" in content or "incomplete" in content.lower(), \
        "Missing flow path for incomplete story content"

    # Check for error message with missing fields
    assert "success_criteria" in content and "journey" in content, \
        "Error message should mention required fields (success_criteria, journey)"


def test_orchestration_allows_story_creation_tasks():
    """
    Test that orchestration allows planning when story_creation_tasks exist.

    Verifies:
    - CheckStoryCreationTasks decision node exists
    - Flow has path for "Yes: Will Generate"
    - NoteStoryGeneration node exists
    - Flow reaches StoryContextReady when story generation planned
    """
    process_path = Path(__file__).parent.parent / "agents" / "orchestration" / "orchestration-planning" / "process.mmd"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check for CheckStoryCreationTasks node
    assert "CheckStoryCreationTasks" in content, \
        "Missing CheckStoryCreationTasks decision node"

    # Check for story generation path
    assert "Yes: Will Generate" in content or "Will Generate" in content, \
        "Missing flow path for planned story generation"

    # Check for NoteStoryGeneration node
    assert "NoteStoryGeneration" in content, \
        "Missing NoteStoryGeneration node"

    # Check that it leads to StoryContextReady
    note_pos = content.find("NoteStoryGeneration")
    ready_pos = content.find("StoryContextReady", note_pos)

    assert ready_pos > note_pos, \
        "NoteStoryGeneration should lead to StoryContextReady"


def test_orchestration_has_story_lifecycle_comment():
    """
    Test that orchestration includes explanatory comment about story lifecycle.

    Verifies:
    - Comment distinguishes discovery, generation, and validation
    - Comment appears in StoryDiscovery_SG subgraph
    """
    process_path = Path(__file__).parent.parent / "agents" / "orchestration" / "orchestration-planning" / "process.mmd"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that comment about story lifecycle exists
    assert "STORY DISCOVERY vs STORY GENERATION" in content, \
        "Missing explanatory comment about story discovery vs generation"

    # Check that comment mentions all three phases
    assert "Discovery:" in content and "Generation:" in content and "Validation:" in content, \
        "Comment should distinguish Discovery, Generation, and Validation"

    # Check for key concepts in comment
    assert "`agentic agent stories find`" in content, \
        "Comment should mention agentic agent stories find command"

    assert "success_criteria" in content and "journey" in content, \
        "Comment should mention required fields for validation"


def test_planning_standard_has_story_lifecycle():
    """
    Test that planning-standard.yml includes story_lifecycle section.

    Verifies:
    - story_lifecycle section exists
    - Contains discovery, generation, validation subsections
    - Each subsection has description, responsibility, when fields
    """
    standard_path = Path(__file__).parent.parent / "assets" / "guidelines" / "planning-standard.yml"

    with open(standard_path, 'r') as f:
        content = f.read()

    # Check that story_lifecycle section exists
    assert "story_lifecycle:" in content, \
        "Missing story_lifecycle section in planning-standard.yml"

    # Check for discovery subsection
    assert "discovery:" in content, \
        "Missing discovery subsection in story_lifecycle"

    # Check for generation subsection
    assert "generation:" in content, \
        "Missing generation subsection in story_lifecycle"

    # Check for validation subsection
    assert "validation:" in content, \
        "Missing validation subsection in story_lifecycle"

    # Verify key fields are mentioned
    lifecycle_start = content.find("story_lifecycle:")
    lifecycle_section = content[lifecycle_start:lifecycle_start + 2000]  # Read next 2000 chars

    assert "description:" in lifecycle_section, \
        "story_lifecycle subsections should have description field"

    assert "responsibility:" in lifecycle_section, \
        "story_lifecycle should specify responsibility"

    assert "when:" in lifecycle_section, \
        "story_lifecycle should specify when each phase occurs"


def test_planning_standard_story_lifecycle_content():
    """
    Test that story_lifecycle has correct content for each phase.

    Verifies:
    - Discovery mentions agentic stories find command
    - Generation mentions planner-build and planner-guidance
    - Validation mentions orchestration-planning and planner-test
    - Required fields listed: journey, success_criteria, testing
    """
    standard_path = Path(__file__).parent.parent / "assets" / "guidelines" / "planning-standard.yml"

    with open(standard_path, 'r') as f:
        content = f.read()

    # Extract story_lifecycle section
    lifecycle_start = content.find("story_lifecycle:")
    # Find next top-level key (escape_hatch_rules)
    lifecycle_end = content.find("escape_hatch_rules:", lifecycle_start)
    lifecycle_section = content[lifecycle_start:lifecycle_end]

    # Check discovery content
    assert "agentic agent stories find" in lifecycle_section, \
        "Discovery should mention agentic agent stories find command"

    # Check generation content
    assert "planner-build" in lifecycle_section, \
        "Generation should mention planner-build responsibility"

    # Check validation content
    assert "orchestration-planning" in lifecycle_section, \
        "Validation should mention orchestration-planning responsibility"

    assert "planner-test" in lifecycle_section, \
        "Validation should mention planner-test responsibility"

    # Check required fields
    assert "journey" in lifecycle_section and "success_criteria" in lifecycle_section and "testing" in lifecycle_section, \
        "Validation should list required fields: journey, success_criteria, testing"


def test_story_lifecycle_distinguishes_when_phases_run():
    """
    Test that story_lifecycle clearly states when each phase runs.

    Verifies:
    - Discovery: ALWAYS
    - Generation: When discovery returns empty AND build/test
    - Validation: After discovery and before UAT planning
    """
    standard_path = Path(__file__).parent.parent / "assets" / "guidelines" / "planning-standard.yml"

    with open(standard_path, 'r') as f:
        content = f.read()

    lifecycle_start = content.find("story_lifecycle:")
    lifecycle_end = content.find("escape_hatch_rules:", lifecycle_start)
    lifecycle_section = content[lifecycle_start:lifecycle_end]

    # Check discovery timing
    assert "ALWAYS" in lifecycle_section or "always" in lifecycle_section.lower(), \
        "Discovery should run ALWAYS"

    # Check generation timing
    assert "discovery returns empty" in lifecycle_section.lower() or "no stories" in lifecycle_section.lower(), \
        "Generation should run when discovery finds no stories"

    # Check validation timing
    assert "After discovery" in lifecycle_section or "before UAT" in lifecycle_section, \
        "Validation should run after discovery and before UAT planning"
