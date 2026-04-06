"""
Unit tests for planner-test story validation fence.

Tests verify that planner-test/process.yml includes proper story content
validation fences and UAT task generation guidance.
"""

import pytest
import yaml
from pathlib import Path

pytestmark = pytest.mark.story("US-PLN-031", "US-PLN-035", "US-PLN-091", "US-PLN-092", "US-GDN-030", "US-GDN-033", "US-GDN-041", "US-GDN-059", "US-GDN-067", "US-GDN-068")


@pytest.fixture
def planner_test_process():
    """Load planner-test/process.yml for testing."""
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-test" / "process.yml"
    with open(process_path, 'r') as f:
        return yaml.safe_load(f)


def test_planner_test_has_story_validation_fence():
    """
    Test that planner-test/process.yml includes STORY CONTENT MUST EXIST fence.

    Verifies:
    - FENCE section exists
    - Fence checks success_criteria, journey, testing fields
    - Clear error message when validation fails
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-test" / "process.yml"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that FENCE exists
    assert "FENCE: STORY CONTENT MUST EXIST" in content, \
        "planner-test/process.yml missing STORY CONTENT MUST EXIST fence"

    # Check that fence validates required fields
    assert "success_criteria field" in content, \
        "Fence missing success_criteria field validation"

    assert "journey field" in content, \
        "Fence missing journey field validation"

    assert "testing field" in content, \
        "Fence missing testing field validation"

    # Check that fence has error message
    assert "FENCE VIOLATION" in content, \
        "Fence missing FENCE VIOLATION error message"

    # Check that fence mentions story files location
    assert "docs/userstories/" in content, \
        "Fence missing docs/userstories/ location reference"


def test_story_validation_blocks_missing_files():
    """
    Test that story validation guidance blocks when story files missing.

    This is a documentation test - verifies the guidance text requires
    stopping when story files don't exist.
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-test" / "process.yml"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that guidance mentions reading affected_stories
    assert "affected_stories" in content, \
        "Missing affected_stories reference in validation fence"

    # Check that guidance mentions stopping when files missing
    assert "If story files missing, STOP" in content or "story files missing" in content.lower(), \
        "Missing guidance to STOP when story files missing"

    # Check for clear error message
    assert "Story content missing for UAT planning" in content, \
        "Missing error message for missing story content"


def test_story_validation_blocks_incomplete_content():
    """
    Test that story validation guidance blocks incomplete story content.

    Verifies:
    - Guidance checks for missing fields
    - Clear error message for incomplete stories
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-test" / "process.yml"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that guidance validates story content completeness
    assert "incomplete content" in content.lower() or "missing fields" in content.lower(), \
        "Missing guidance for incomplete story content"

    # Check that guidance lists required fields
    required_field_mentions = 0
    if "success_criteria" in content:
        required_field_mentions += 1
    if "journey" in content:
        required_field_mentions += 1
    if "testing" in content:
        required_field_mentions += 1

    assert required_field_mentions >= 3, \
        "Guidance should mention all required fields (success_criteria, journey, testing)"


def test_uat_tasks_generated_from_story_content():
    """
    Test that UAT task generation guidance exists and includes story mapping.

    Verifies:
    - uat_task_generation section exists
    - Task template includes story_id reference
    - Task template includes acceptance_criteria
    - Task template includes verification_method
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-test" / "process.yml"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that uat_task_generation section exists
    assert "uat_task_generation" in content, \
        "Missing uat_task_generation section in planner-test/process.yml"

    # Check for task template guidance
    assert "task_template" in content, \
        "Missing task_template in uat_task_generation section"

    # Check that template includes story_id
    assert "story_id:" in content, \
        "Task template missing story_id field"

    # Check that template includes acceptance_criteria
    assert "acceptance_criteria:" in content, \
        "Task template missing acceptance_criteria field"

    # Check that template includes verification_method
    assert "verification_method:" in content, \
        "Task template missing verification_method field"


def test_uat_task_mapping_rules_exist():
    """
    Test that UAT task generation includes mapping rules.

    Verifies:
    - mapping_rules section exists
    - Rules specify 1:1 mapping between tasks and stories
    - Rules require acceptance criteria to be copied verbatim
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-test" / "process.yml"

    with open(process_path, 'r') as f:
        content = f.read()

    # Check that mapping_rules section exists
    assert "mapping_rules" in content, \
        "Missing mapping_rules in uat_task_generation section"

    # Check for 1:1 mapping rule
    assert "One UAT task per user story" in content, \
        "Missing 1:1 mapping rule in mapping_rules"

    # Check that acceptance criteria should be copied verbatim
    assert "copied verbatim" in content or "verbatim" in content, \
        "Missing guidance to copy acceptance criteria verbatim"


@pytest.mark.story("US-PLN-092")
def test_uat_phase_planning_section_exists():
    """
    Test that uat_phase_planning section exists with proper references.

    Verifies:
    - uat_phase_planning section exists
    - Section marks UAT as mandatory
    """
    process_path = Path(__file__).parent.parent / "agents" / "planner" / "planner-test" / "process.yml"

    with open(process_path, 'r') as f:
        process_yml = yaml.safe_load(f)

    # uat_phase_planning is nested under the top-level 'process' key
    process = process_yml.get('process', {})
    assert 'uat_phase_planning' in process, \
        "Missing uat_phase_planning section in process.yml"

    # Check that it's marked as mandatory
    assert process['uat_phase_planning'].get('mandatory') is True, \
        "uat_phase_planning should be marked as mandatory: true"
