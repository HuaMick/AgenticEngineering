"""Tests for STORY_COVERAGE_INCOMPLETE feedback trigger and story-coverage-loop (P4-T5).

Validates the guidance changes for the story coverage feedback loop added in
the 260308PD_planner_design_agent_story_alignment epic:
- P2-T7: STORY_COVERAGE_INCOMPLETE trigger in orchestration-executor process.yml
- P2-T8: story-coverage-loop in planner-test process.yml
- P2-T9: pytest marker check in orchestration-executor validation_gate
"""

from pathlib import Path

import pytest
import yaml


AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"
EXECUTOR_PROCESS = AGENTS_DIR / "orchestration" / "orchestration-executor" / "process.yml"
PLANNER_TEST_PROCESS = AGENTS_DIR / "planner" / "planner-test" / "process.yml"


# ---------------------------------------------------------------------------
# Tests for STORY_COVERAGE_INCOMPLETE trigger in executor
# ---------------------------------------------------------------------------

class TestStoryCoverageIncompleteTrigger:
    """Test the STORY_COVERAGE_INCOMPLETE feedback trigger definition."""

    @pytest.fixture
    def executor_process(self):
        """Load orchestration-executor process.yml content."""
        return yaml.safe_load(EXECUTOR_PROCESS.read_text())

    @pytest.fixture
    def executor_text(self):
        """Load orchestration-executor process.yml as raw text."""
        return EXECUTOR_PROCESS.read_text()

    def test_trigger_exists_in_executor(self, executor_text):
        """Verify STORY_COVERAGE_INCOMPLETE trigger is defined."""
        assert "STORY_COVERAGE_INCOMPLETE" in executor_text

    def test_trigger_in_evaluate_triggers_step(self, executor_text):
        """Verify trigger is in the loop_evaluate_triggers step."""
        # The trigger should be in the evaluate triggers section
        assert "STORY_COVERAGE_INCOMPLETE" in executor_text
        # Should be alongside other triggers like TEST_FAILURE
        assert "TEST_FAILURE" in executor_text
        assert "BUILD_FAILURE" in executor_text

    def test_trigger_has_condition(self, executor_text):
        """Verify trigger has a condition defined."""
        # Find the STORY_COVERAGE_INCOMPLETE section and check it has a condition
        idx = executor_text.find("STORY_COVERAGE_INCOMPLETE")
        assert idx > 0
        section = executor_text[idx:idx + 1500]
        assert "Condition" in section or "condition" in section.lower()

    def test_trigger_checks_pytest_markers(self, executor_text):
        """Verify trigger checks for @pytest.mark.story markers."""
        idx = executor_text.find("STORY_COVERAGE_INCOMPLETE")
        assert idx > 0
        section = executor_text[idx:idx + 1500]
        assert "pytest.mark.story" in section

    def test_trigger_has_max_iterations(self, executor_text):
        """Verify trigger has MAX_ITERATIONS limit (default: 3)."""
        idx = executor_text.find("STORY_COVERAGE_INCOMPLETE")
        assert idx > 0
        section = executor_text[idx:idx + 1500]
        assert "MAX_ITERATIONS" in section or "max_iterations" in section.lower()

    def test_trigger_re_spawns_test_builder(self, executor_text):
        """Verify trigger action re-spawns test-builder with uncovered story context."""
        idx = executor_text.find("STORY_COVERAGE_INCOMPLETE")
        assert idx > 0
        section = executor_text[idx:idx + 1500]
        assert "test-builder" in section

    def test_trigger_has_exit_condition(self, executor_text):
        """Verify trigger has an exit condition."""
        idx = executor_text.find("STORY_COVERAGE_INCOMPLETE")
        assert idx > 0
        section = executor_text[idx:idx + 2500]
        assert "Exit condition" in section or "exit" in section.lower()

    def test_trigger_references_uncovered_story_ids(self, executor_text):
        """Verify trigger references uncovered_story_ids in context."""
        idx = executor_text.find("STORY_COVERAGE_INCOMPLETE")
        assert idx > 0
        section = executor_text[idx:idx + 1500]
        assert "uncovered_story_ids" in section or "uncovered" in section


# ---------------------------------------------------------------------------
# Tests for validation_gate pytest marker check
# ---------------------------------------------------------------------------

class TestValidationGateMarkerCheck:
    """Test the validation_gate checks pytest story markers."""

    @pytest.fixture
    def executor_text(self):
        """Load orchestration-executor process.yml as raw text."""
        return EXECUTOR_PROCESS.read_text()

    def test_validation_gate_checks_pytest_markers(self, executor_text):
        """Verify validation_gate references pytest.mark.story for coverage check."""
        # Find the validation_gate section
        idx = executor_text.find("validation_gate")
        assert idx > 0
        # Get the section (up to the next major section)
        gate_section = executor_text[idx:idx + 3000]
        assert "pytest.mark.story" in gate_section

    def test_validation_gate_markers_are_primary(self, executor_text):
        """Verify markers are described as PRIMARY source of truth."""
        idx = executor_text.find("STORY COVERAGE CHECK")
        assert idx > 0
        section = executor_text[idx:idx + 1500]
        assert "PRIMARY" in section or "primary" in section

    def test_validation_gate_still_checks_yaml(self, executor_text):
        """Verify YAML test_status is still checked as secondary signal."""
        idx = executor_text.find("STORY COVERAGE CHECK")
        assert idx > 0
        section = executor_text[idx:idx + 1500]
        assert "test_status" in section
        assert "secondary" in section.lower() or "ALSO" in section

    def test_validation_gate_has_coverage_classifications(self, executor_text):
        """Verify validation gate classifies stories as COVERED/UNTESTED/FAILED."""
        idx = executor_text.find("STORY COVERAGE CHECK")
        assert idx > 0
        section = executor_text[idx:idx + 2000]
        assert "COVERED" in section
        assert "UNTESTED" in section
        assert "FAILED" in section


# ---------------------------------------------------------------------------
# Tests for story-coverage-loop in planner-test
# ---------------------------------------------------------------------------

class TestStoryCoverageLoop:
    """Test story-coverage-loop option in planner-test process.yml."""

    @pytest.fixture
    def planner_test_text(self):
        """Load planner-test process.yml as raw text."""
        return PLANNER_TEST_PROCESS.read_text()

    def test_story_coverage_loop_defined(self, planner_test_text):
        """Verify story-coverage-loop is listed as a loop option."""
        assert "story-coverage-loop" in planner_test_text

    def test_story_coverage_loop_alongside_existing_loops(self, planner_test_text):
        """Verify story-coverage-loop is alongside existing loop types."""
        assert "test-fix-loop" in planner_test_text
        assert "audit-test-fix-loop" in planner_test_text
        assert "user-story-validation-loop" in planner_test_text
        assert "story-coverage-loop" in planner_test_text

    def test_story_coverage_loop_has_max_iterations(self, planner_test_text):
        """Verify story-coverage-loop example includes max iterations."""
        idx = planner_test_text.find("story-coverage-loop")
        assert idx > 0
        section = planner_test_text[idx:idx + 1000]
        assert "maximum_iterations" in section or "max_iterations" in section.lower()

    def test_story_coverage_loop_references_trigger(self, planner_test_text):
        """Verify story-coverage-loop references STORY_COVERAGE_INCOMPLETE trigger."""
        idx = planner_test_text.find("story-coverage-loop")
        assert idx > 0
        section = planner_test_text[idx:idx + 1000]
        assert "STORY_COVERAGE_INCOMPLETE" in section

    def test_story_coverage_loop_mentions_pytest_markers(self, planner_test_text):
        """Verify story-coverage-loop references @pytest.mark.story markers."""
        idx = planner_test_text.find("story-coverage-loop")
        assert idx > 0
        section = planner_test_text[idx:idx + 1000]
        assert "pytest.mark.story" in section

    def test_story_coverage_loop_has_exit_conditions(self, planner_test_text):
        """Verify story-coverage-loop example has exit conditions."""
        # Look for exit_conditions in the story-coverage-loop example
        idx = planner_test_text.find("story-coverage-loop")
        assert idx > 0
        section = planner_test_text[idx:idx + 1000]
        assert "exit_conditions" in section or "COVERAGE_COMPLETE" in section
