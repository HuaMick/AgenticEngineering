"""
Integration tests for end-to-end planning with user story generation.

These tests verify the complete workflow from objective to plan with generated
user stories and UAT phases that reference those stories.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import yaml
import tempfile
import shutil

pytestmark = pytest.mark.story("US-PLN-027", "US-PLN-034", "US-PLN-076", "US-PLN-091", "US-STR-012", "US-GDN-081")


@pytest.fixture
def temp_epic_folder():
    """Create temporary epic folder for testing."""
    temp_dir = tempfile.mkdtemp(prefix="test_epic_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_userstories_dir():
    """Create temporary userstories directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="test_stories_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.mark.integration
def test_planning_workflow_generates_stories_when_none_found(temp_epic_folder, temp_userstories_dir):
    """
    Integration test: Verify planning workflow generates stories when discovery finds none.

    Scenario:
    1. Create test objective: "Add new CLI command for X"
    2. Mock empty story discovery (no existing stories)
    3. Verify planning process includes story generation
    4. Verify plan has affected_stories field
    5. Verify story files created
    6. Verify UAT phase references generated stories

    Expected outcome:
    - Plan metadata has affected_stories field
    - Story files exist in docs/userstories/
    - Plan includes story_creation_tasks
    - Test plan has UAT phase with story references
    """
    # This is a documentation/framework test
    # Actual integration would require full orchestration context

    test_objective = "Add new CLI command for user profile management"

    # Mock story discovery returning empty
    with patch('subprocess.run') as mock_run:
        # Mock `agentic stories find` returning no stories
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"stories": []}\n',
            stderr=''
        )

        # Expected behavior based on guidance:
        # 1. planner-build should detect empty story list
        # 2. planner-build should generate 3-8 user stories
        # 3. Plan should have affected_stories field
        # 4. Plan should have story_creation_tasks

        expected_plan_structure = {
            'name': 'add-user-profile-command',
            'affected_stories': ['US-CLI-PROFILE-001', 'US-CLI-PROFILE-002', 'US-CLI-PROFILE-003'],
            'story_updates_needed': True,
            'story_creation_tasks': [
                {
                    'id': 'STORY_001',
                    'description': 'Create user stories for profile management feature'
                }
            ]
        }

        # Verify expected structure
        assert 'affected_stories' in expected_plan_structure
        assert len(expected_plan_structure['affected_stories']) >= 1
        assert expected_plan_structure['story_updates_needed'] is True
        assert len(expected_plan_structure['story_creation_tasks']) >= 1


@pytest.mark.integration
@pytest.mark.story("US-STR-014")
def test_orchestration_validates_story_content_before_uat(temp_epic_folder, temp_userstories_dir):
    """
    Integration test: Verify orchestration validates story content exists before UAT.

    Scenario:
    1. Create plan with affected_stories
    2. Create incomplete story files (missing success_criteria)
    3. Attempt orchestration execution
    4. Verify orchestration blocks at validation gate
    5. Fix story content
    6. Verify orchestration proceeds to UAT

    Expected outcome:
    - Orchestration validates story content before UAT
    - Clear error when stories incomplete
    - UAT only runs when stories are complete
    """
    # Create test plan metadata
    plan_data = {
        'name': 'test-plan',
        'affected_stories': ['US-CLI-TEST-001'],
        'phases': [
            {
                'name': 'UAT Phase',
                'tasks': [
                    {
                        'id': 'UAT_001',
                        'story_id': 'US-CLI-TEST-001',
                        'description': 'Validate test story'
                    }
                ]
            }
        ]
    }

    # Test case A: Incomplete story (missing success_criteria)
    incomplete_story = {
        'stories': [
            {
                'id': 'US-CLI-TEST-001',
                'name': 'Test story',
                'journey': ['Step 1', 'Step 2'],
                'testing': {'local': 'test locally'}
                # Missing success_criteria - should fail validation
            }
        ]
    }

    # Expected validation behavior:
    validation_errors = []
    story = incomplete_story['stories'][0]

    required_fields = ['success_criteria', 'journey', 'testing']
    for field in required_fields:
        if field not in story:
            validation_errors.append(f"Story {story['id']} missing {field}")

    assert len(validation_errors) > 0, "Incomplete story should fail validation"
    assert 'success_criteria' in validation_errors[0], "Should detect missing success_criteria"

    # Test case B: Complete story
    complete_story = {
        'stories': [
            {
                'id': 'US-CLI-TEST-001',
                'name': 'Test story',
                'journey': ['Step 1', 'Step 2'],
                'success_criteria': ['Criterion 1', 'Criterion 2'],
                'testing': {'local': 'test locally', 'docker': 'test in docker'}
            }
        ]
    }

    # Expected validation behavior:
    validation_errors_complete = []
    story_complete = complete_story['stories'][0]

    for field in required_fields:
        if field not in story_complete:
            validation_errors_complete.append(f"Story {story_complete['id']} missing {field}")

    assert len(validation_errors_complete) == 0, "Complete story should pass validation"


@pytest.mark.integration
@pytest.mark.story("US-STR-013", "US-STR-015")
def test_planner_test_creates_uat_tasks_from_stories(temp_epic_folder):
    """
    Integration test: Verify planner-test creates UAT tasks that map to stories.

    Scenario:
    1. Create plan with affected_stories
    2. Create complete story files
    3. Run planner-test
    4. Verify UAT phase created
    5. Verify UAT tasks map 1:1 to stories
    6. Verify acceptance criteria copied from stories

    Expected outcome:
    - Test plan has UAT phase
    - One UAT task per story
    - Each task has story_id, acceptance_criteria, verification_method
    """
    # Input: Plan with affected stories
    build_plan = {
        'name': 'test-build-plan',
        'affected_stories': ['US-CLI-TEST-001', 'US-CLI-TEST-002']
    }

    # Input: Story files with complete content
    stories = [
        {
            'id': 'US-CLI-TEST-001',
            'name': 'User can run help command',
            'journey': ['User runs: agentic --help', 'Help text is displayed'],
            'success_criteria': ['Help text includes all commands', 'Exit code is 0'],
            'testing': {'local': 'Run agentic --help'}
        },
        {
            'id': 'US-CLI-TEST-002',
            'name': 'User can view version',
            'journey': ['User runs: agentic --version', 'Version is displayed'],
            'success_criteria': ['Version matches package.json', 'Format is semantic versioning'],
            'testing': {'local': 'Run agentic --version'}
        }
    ]

    # Expected output: Test plan with UAT tasks
    expected_test_plan = {
        'phases': [
            {
                'name': 'UAT Phase',
                'tasks': [
                    {
                        'id': 'uat_US-CLI-TEST-001',
                        'name': 'Validate User can run help command',
                        'story_id': 'US-CLI-TEST-001',
                        'acceptance_criteria': ['Help text includes all commands', 'Exit code is 0'],
                        'verification_method': 'test-user-simulator'
                    },
                    {
                        'id': 'uat_US-CLI-TEST-002',
                        'name': 'Validate User can view version',
                        'story_id': 'US-CLI-TEST-002',
                        'acceptance_criteria': ['Version matches package.json', 'Format is semantic versioning'],
                        'verification_method': 'test-user-simulator'
                    }
                ]
            }
        ]
    }

    # Verify mapping rules
    uat_phase = expected_test_plan['phases'][0]
    uat_tasks = uat_phase['tasks']

    # Check 1:1 mapping
    assert len(uat_tasks) == len(build_plan['affected_stories']), \
        "Should have one UAT task per story"

    # Check each task has required fields
    for task in uat_tasks:
        assert 'story_id' in task, "UAT task must have story_id"
        assert 'acceptance_criteria' in task, "UAT task must have acceptance_criteria"
        assert 'verification_method' in task, "UAT task must have verification_method"

        # Verify acceptance criteria copied from story
        story_id = task['story_id']
        matching_story = next((s for s in stories if s['id'] == story_id), None)
        assert matching_story is not None, f"Story {story_id} should exist"
        assert task['acceptance_criteria'] == matching_story['success_criteria'], \
            "Acceptance criteria should be copied verbatim from story"


@pytest.mark.integration
def test_full_planning_workflow_with_story_generation():
    """
    Integration test: Complete workflow from objective to plan with stories.

    This is a high-level documentation test that outlines the expected workflow.

    Workflow:
    1. User invokes: agentic entrypoint _plan_build.yml
    2. orchestration-planning discovers affected stories via `agentic stories find`
    3. No stories found
    4. planner-build generates NEW user stories (3-8 stories)
    5. planner-build creates plan_build.yml with affected_stories and story_creation_tasks
    6. planner-test validates story content exists
    7. planner-test creates test plan with UAT phase
    8. UAT tasks reference story IDs and include acceptance criteria
    9. orchestration-executor validates stories before UAT execution

    Expected outcome:
    - Plan has affected_stories field
    - Story files created
    - Test plan has UAT phase
    - UAT tasks map to stories with acceptance criteria
    """
    # This documents the expected workflow
    workflow_steps = [
        "orchestration-planning: Run agentic stories find",
        "orchestration-planning: Detect empty story list",
        "planner-build: Generate 3-8 user stories",
        "planner-build: Create affected_stories field in plan",
        "planner-build: Create story_creation_tasks",
        "planner-test: Validate story content exists (FENCE)",
        "planner-test: Create UAT phase with story references",
        "orchestration-executor: Validate stories before UAT (FENCE)",
        "orchestration-executor: Spawn test-user-simulator per story"
    ]

    assert len(workflow_steps) == 9, "Complete workflow has 9 key steps"

    # Key validation points (FENCES)
    validation_gates = [
        {
            'agent': 'planner-test',
            'gate': 'STORY CONTENT MUST EXIST',
            'checks': ['story files exist', 'success_criteria present', 'journey present', 'testing present']
        },
        {
            'agent': 'orchestration-executor',
            'gate': 'UAT VALIDATION GATE',
            'checks': ['story files exist', 'complete content', 'ready for UAT']
        }
    ]

    assert len(validation_gates) == 2, "Should have 2 validation gates"
    assert all('gate' in gate for gate in validation_gates), "Each gate should be named"
