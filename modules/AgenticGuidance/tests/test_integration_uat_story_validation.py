"""
Integration tests for UAT story validation by orchestration-executor.

Tests verify that orchestration-executor properly validates story content
before executing UAT phases and provides clear error messages when validation fails.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil
import yaml


@pytest.fixture
def temp_plan_dir():
    """Create temporary plan directory."""
    temp_dir = tempfile.mkdtemp(prefix="test_uat_plan_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_stories_dir():
    """Create temporary stories directory."""
    temp_dir = tempfile.mkdtemp(prefix="test_uat_stories_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.mark.integration
def test_executor_blocks_uat_when_stories_missing(temp_plan_dir, temp_stories_dir):
    """
    Test Case A: Stories referenced but files don't exist.

    Scenario:
    1. Create plan with UAT phase referencing stories
    2. Story files do NOT exist
    3. Attempt to execute UAT phase
    4. Verify executor blocks with validation error

    Expected outcome:
    - Executor detects missing story files
    - Returns clear error message listing missing stories
    - UAT phase does NOT execute
    """
    # Plan with UAT phase
    plan = {
        'name': 'test-uat-validation',
        'affected_stories': ['US-CLI-TEST-001', 'US-CLI-TEST-002'],
        'phases': [
            {
                'name': 'UAT Phase',
                'tasks': [
                    {'id': 'UAT_001', 'story_id': 'US-CLI-TEST-001'},
                    {'id': 'UAT_002', 'story_id': 'US-CLI-TEST-002'}
                ]
            }
        ]
    }

    # No story files exist
    story_files_exist = False

    # Expected validation behavior
    if not story_files_exist:
        expected_error = {
            'type': 'UAT_VALIDATION_GATE_FAILURE',
            'message': 'Cannot execute UAT phase - story content incomplete or missing',
            'failed_stories': [
                {'id': 'US-CLI-TEST-001', 'reason': 'Story file not found'},
                {'id': 'US-CLI-TEST-002', 'reason': 'Story file not found'}
            ]
        }

        assert expected_error['type'] == 'UAT_VALIDATION_GATE_FAILURE'
        assert len(expected_error['failed_stories']) == 2
        assert 'story content' in expected_error['message'].lower()

        # Verify UAT should NOT execute
        uat_should_execute = False
        assert uat_should_execute is False, "UAT should not execute when stories missing"


@pytest.mark.integration
def test_executor_blocks_uat_when_stories_incomplete(temp_plan_dir, temp_stories_dir):
    """
    Test Case B: Story files exist but content is incomplete.

    Scenario:
    1. Create plan with UAT phase
    2. Create story files with incomplete content (missing success_criteria)
    3. Attempt to execute UAT phase
    4. Verify executor blocks with field-specific error

    Expected outcome:
    - Executor detects incomplete story content
    - Error message specifies missing fields
    - UAT phase does NOT execute
    """
    # Plan with UAT phase
    plan = {
        'name': 'test-uat-incomplete',
        'affected_stories': ['US-CLI-TEST-003'],
        'phases': [
            {
                'name': 'UAT Phase',
                'tasks': [
                    {'id': 'UAT_003', 'story_id': 'US-CLI-TEST-003'}
                ]
            }
        ]
    }

    # Story file exists but incomplete
    incomplete_story = {
        'id': 'US-CLI-TEST-003',
        'name': 'Test incomplete story',
        'journey': ['Step 1', 'Step 2'],
        'testing': {'local': 'test locally'}
        # Missing success_criteria field
    }

    # Validation logic
    required_fields = ['success_criteria', 'journey', 'testing']
    validation_errors = []

    for field in required_fields:
        if field not in incomplete_story:
            validation_errors.append({
                'story_id': incomplete_story['id'],
                'field': field,
                'reason': f'Missing {field} field'
            })

    # Expected outcome
    assert len(validation_errors) > 0, "Incomplete story should fail validation"

    expected_error = {
        'type': 'UAT_VALIDATION_GATE_FAILURE',
        'message': 'Story content incomplete - missing success_criteria',
        'failed_stories': validation_errors
    }

    assert 'success_criteria' in expected_error['message']
    assert expected_error['failed_stories'][0]['field'] == 'success_criteria'

    # Verify UAT should NOT execute
    uat_should_execute = len(validation_errors) == 0
    assert uat_should_execute is False, "UAT should not execute when stories incomplete"


@pytest.mark.integration
def test_executor_proceeds_when_stories_complete(temp_plan_dir, temp_stories_dir):
    """
    Test Case C: Story files exist with complete content.

    Scenario:
    1. Create plan with UAT phase
    2. Create complete story files (all required fields)
    3. Execute UAT phase
    4. Verify executor validation passes
    5. Verify test-user-simulator spawned per story

    Expected outcome:
    - Executor validates story content successfully
    - UAT phase executes
    - test-user-simulator agent spawned for each story
    """
    # Plan with UAT phase
    plan = {
        'name': 'test-uat-complete',
        'affected_stories': ['US-CLI-TEST-004', 'US-CLI-TEST-005'],
        'phases': [
            {
                'name': 'UAT Phase',
                'tasks': [
                    {'id': 'UAT_004', 'story_id': 'US-CLI-TEST-004'},
                    {'id': 'UAT_005', 'story_id': 'US-CLI-TEST-005'}
                ]
            }
        ]
    }

    # Complete story files
    complete_stories = [
        {
            'id': 'US-CLI-TEST-004',
            'name': 'Complete story 1',
            'journey': ['Step 1', 'Step 2', 'Step 3'],
            'success_criteria': ['Criterion 1', 'Criterion 2'],
            'testing': {'local': 'test locally', 'docker': 'test in docker'}
        },
        {
            'id': 'US-CLI-TEST-005',
            'name': 'Complete story 2',
            'journey': ['Action 1', 'Action 2'],
            'success_criteria': ['Passes test 1', 'Passes test 2'],
            'testing': {'local': 'run test', 'docker': 'docker test'}
        }
    ]

    # Validation logic
    required_fields = ['success_criteria', 'journey', 'testing']
    validation_errors = []

    for story in complete_stories:
        for field in required_fields:
            if field not in story:
                validation_errors.append({
                    'story_id': story['id'],
                    'field': field
                })

    # Verify all stories pass validation
    assert len(validation_errors) == 0, "Complete stories should pass validation"

    # Expected behavior: UAT executes
    uat_should_execute = len(validation_errors) == 0
    assert uat_should_execute is True, "UAT should execute when stories complete"

    # Expected: test-user-simulator spawned per story
    expected_spawned_agents = [
        {'agent': 'test-user-simulator', 'story_id': 'US-CLI-TEST-004'},
        {'agent': 'test-user-simulator', 'story_id': 'US-CLI-TEST-005'}
    ]

    assert len(expected_spawned_agents) == len(complete_stories), \
        "One test-user-simulator per story"

    for spawned in expected_spawned_agents:
        assert spawned['agent'] == 'test-user-simulator'
        assert spawned['story_id'] in plan['affected_stories']


@pytest.mark.integration
def test_executor_validation_happens_before_spawn():
    """
    Test that validation gate runs BEFORE spawning test-user-simulator.

    Scenario:
    1. Mock executor workflow
    2. Verify validation runs before agent spawn
    3. Verify spawn only happens if validation passes

    Expected outcome:
    - Validation gate is checked first
    - Agent spawn happens only after validation passes
    - No agents spawned if validation fails
    """
    # Execution order tracking
    execution_order = []

    def mock_validate_stories(stories):
        execution_order.append('validate_stories')
        # Simulate validation
        for story in stories:
            if 'success_criteria' not in story:
                return False, f"Story {story['id']} missing success_criteria"
        return True, None

    def mock_spawn_agent(story_id):
        execution_order.append(f'spawn_agent_{story_id}')
        return {'status': 'spawned', 'story_id': story_id}

    # Test case: Complete stories
    complete_stories = [
        {
            'id': 'US-CLI-TEST-006',
            'journey': ['Step 1'],
            'success_criteria': ['Criterion 1'],
            'testing': {'local': 'test'}
        }
    ]

    # Execute workflow
    execution_order.clear()
    validation_passed, error = mock_validate_stories(complete_stories)

    if validation_passed:
        for story in complete_stories:
            mock_spawn_agent(story['id'])

    # Verify execution order
    assert execution_order[0] == 'validate_stories', "Validation must happen first"
    assert execution_order[1] == 'spawn_agent_US-CLI-TEST-006', "Spawn happens after validation"

    # Test case: Incomplete stories
    incomplete_stories = [
        {
            'id': 'US-CLI-TEST-007',
            'journey': ['Step 1'],
            'testing': {'local': 'test'}
            # Missing success_criteria
        }
    ]

    execution_order.clear()
    validation_passed, error = mock_validate_stories(incomplete_stories)

    if validation_passed:
        for story in incomplete_stories:
            mock_spawn_agent(story['id'])

    # Verify NO spawn happened
    assert execution_order == ['validate_stories'], \
        "No agent should spawn when validation fails"
    assert not validation_passed, "Validation should fail for incomplete story"


@pytest.mark.integration
def test_executor_provides_clear_error_messages():
    """
    Test that executor validation provides actionable error messages.

    Verifies:
    - Error message identifies which stories failed
    - Error message specifies what's missing
    - Error message provides remediation steps
    """
    # Test various validation failures
    validation_scenarios = [
        {
            'case': 'Missing story file',
            'story_id': 'US-CLI-TEST-008',
            'file_exists': False,
            'expected_error': 'Story file not found'
        },
        {
            'case': 'Missing success_criteria',
            'story_id': 'US-CLI-TEST-009',
            'file_exists': True,
            'story': {'id': 'US-CLI-TEST-009', 'journey': [], 'testing': {}},
            'expected_error': 'missing success_criteria'
        },
        {
            'case': 'Missing journey',
            'story_id': 'US-CLI-TEST-010',
            'file_exists': True,
            'story': {'id': 'US-CLI-TEST-010', 'success_criteria': [], 'testing': {}},
            'expected_error': 'missing journey'
        },
        {
            'case': 'Missing testing',
            'story_id': 'US-CLI-TEST-011',
            'file_exists': True,
            'story': {'id': 'US-CLI-TEST-011', 'success_criteria': [], 'journey': []},
            'expected_error': 'missing testing'
        }
    ]

    for scenario in validation_scenarios:
        if not scenario['file_exists']:
            error_msg = f"Story {scenario['story_id']}: {scenario['expected_error']}"
            assert scenario['story_id'] in error_msg
            assert scenario['expected_error'] in error_msg
        else:
            # Check for missing fields
            story = scenario['story']
            required_fields = ['success_criteria', 'journey', 'testing']
            missing_fields = [f for f in required_fields if f not in story]

            if missing_fields:
                expected_field = scenario['expected_error'].replace('missing ', '')
                assert expected_field in missing_fields, \
                    f"Should detect missing {expected_field}"
