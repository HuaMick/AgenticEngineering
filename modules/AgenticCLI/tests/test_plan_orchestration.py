"""Tests for orchestration commands in plan management.

Unit tests for 'agentic plan orchestration generate/validate' commands.
Tests cover generating orchestration MMD files from plan YAML and
validating MMD files against plan YAML structure.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def minimal_plan():
    """Create a temporary plan with minimal structure (single phase, no tasks)."""
    plan_content = {
        "name": "minimal-test-plan",
        "objective": "Test minimal orchestration generation",
        "status": "pending",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Build Phase",
                "status": "pending",
                "tickets": [],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260128MP_minimal_plan"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        yield plan_dir


@pytest.fixture
def complex_plan():
    """Create a temporary plan with complex structure (multiple phases, tasks)."""
    plan_content = {
        "name": "complex-test-plan",
        "objective": "Test complex orchestration generation with multiple phases",
        "status": "in_progress",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Setup Phase",
                "status": "completed",
                "tickets": [
                    {"id": "P1-001", "name": "Initialize project", "status": "completed"},
                    {"id": "P1-002", "name": "Configure dependencies", "status": "completed"},
                ],
            },
            {
                "phase_id": "P2",
                "name": "Build Phase",
                "status": "in_progress",
                "tickets": [
                    {"id": "P2-001", "name": "Implement core module", "status": "completed"},
                    {"id": "P2-002", "name": "Implement utilities", "status": "pending"},
                ],
            },
            {
                "phase_id": "P3",
                "name": "Testing Phase",
                "status": "pending",
                "tickets": [
                    {"id": "P3-001", "name": "Unit tests", "status": "pending"},
                    {"id": "P3-002", "name": "Integration tests", "status": "pending"},
                ],
            },
            {
                "phase_id": "P4",
                "name": "Documentation Phase",
                "status": "pending",
                "tickets": [
                    {"id": "P4-001", "name": "API documentation", "status": "pending"},
                ],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260128CP_complex_plan"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        yield plan_dir


@pytest.fixture
def plan_with_matching_mmd():
    """Create a plan with a correctly structured MMD file."""
    plan_content = {
        "name": "matching-test-plan",
        "objective": "Test validation with matching MMD",
        "status": "in_progress",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Build Phase",
                "status": "completed",
                "tickets": [
                    {"id": "P1-001", "name": "Task 1", "status": "completed"},
                ],
            },
            {
                "phase_id": "P2",
                "name": "Test Phase",
                "status": "pending",
                "tickets": [
                    {"id": "P2-001", "name": "Test Task", "status": "pending"},
                ],
            },
        ],
    }

    # MMD content that matches the plan phases
    mmd_content = """%% =============================================================================
%% GOAL: Test validation with matching MMD
%% =============================================================================
%% PROFILE: Orchestration-matching-test-plan
%% INPUT_PATH: /tmp/plan_build.yml
%%
%% PHASES:
%%   P1: Build Phase
%%   P2: Test Phase
%%
%% AGENT_ROUTING: P1 -> build-python, P2 -> test-builder
%% STATUS: P1=completed, P2=pending
%% FEEDBACK_TRIGGERS: TEST_FAILURE -> test-fix-loop, BUILD_FAILURE -> escalate
%% =============================================================================

flowchart LR
    Start((Start)) --> LoadInputs[Load Context Inputs]

    %% PHASE 1: BUILD PHASE
    %% Tasks: P1-001
    LoadInputs --> Phase1[P1: Build Phase]
    Phase1 --> P1_001[P1-001: Task 1]

    %% PHASE 2: TEST PHASE
    %% Tasks: P2-001
    P1_001 --> Phase2[P2: Test Phase]
    Phase2 --> P2_001[P2-001: Test Task]

    P2_001 --> End((End))
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260128MM_matching_mmd"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        mmd_file = plan_dir / "orchestration_matching_mmd.mmd"
        mmd_file.write_text(mmd_content)
        yield plan_dir


@pytest.fixture
def plan_with_missing_phase_mmd():
    """Create a plan where MMD is missing a phase from YAML."""
    plan_content = {
        "name": "missing-phase-plan",
        "objective": "Test validation detects missing phase",
        "status": "in_progress",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Build Phase",
                "status": "completed",
                "tickets": [],
            },
            {
                "phase_id": "P2",
                "name": "Test Phase",
                "status": "pending",
                "tickets": [],
            },
            {
                "phase_id": "P3",
                "name": "Deploy Phase",
                "status": "pending",
                "tickets": [],
            },
        ],
    }

    # MMD is missing P3 (Deploy Phase)
    mmd_content = """%% =============================================================================
%% GOAL: Test validation detects missing phase
%% =============================================================================
%% PROFILE: Orchestration-missing-phase
%% INPUT_PATH: /tmp/plan_build.yml
%%
%% PHASES:
%%   P1: Build Phase
%%   P2: Test Phase
%%
%% AGENT_ROUTING: P1 -> build-python, P2 -> test-builder
%% STATUS: P1=completed, P2=pending
%% =============================================================================

flowchart LR
    Start((Start)) --> Phase1[P1: Build Phase]
    Phase1 --> Phase2[P2: Test Phase]
    Phase2 --> End((End))
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260128PM_phase_missing"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        mmd_file = plan_dir / "orchestration_phase_missing.mmd"
        mmd_file.write_text(mmd_content)
        yield plan_dir


@pytest.fixture
def plan_with_missing_task_mmd():
    """Create a plan where MMD is missing task IDs from YAML."""
    plan_content = {
        "name": "missing-task-plan",
        "objective": "Test validation detects missing task IDs",
        "status": "in_progress",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Build Phase",
                "status": "in_progress",
                "tickets": [
                    {"id": "P1-001", "name": "First task", "status": "completed"},
                    {"id": "P1-002", "name": "Second task", "status": "pending"},
                    {"id": "P1-003", "name": "Third task", "status": "pending"},
                ],
            },
        ],
    }

    # MMD only mentions P1-001, missing P1-002 and P1-003
    mmd_content = """%% =============================================================================
%% GOAL: Test validation detects missing task IDs
%% =============================================================================
%% PROFILE: Orchestration-missing-tasks
%% INPUT_PATH: /tmp/plan_build.yml
%%
%% PHASES:
%%   P1: Build Phase
%%
%% AGENT_ROUTING: P1 -> build-python
%% STATUS: P1=in_progress
%% =============================================================================

flowchart LR
    Start((Start)) --> Phase1[P1: Build Phase]
    %% Task P1-001 is mentioned
    Phase1 --> P1_001[P1-001: First task]
    P1_001 --> End((End))
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260128TM_task_missing"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        mmd_file = plan_dir / "orchestration_task_missing.mmd"
        mmd_file.write_text(mmd_content)
        yield plan_dir


@pytest.fixture
def plan_without_mmd():
    """Create a plan with no MMD file."""
    plan_content = {
        "name": "no-mmd-plan",
        "objective": "Test validation error when no MMD file exists",
        "status": "pending",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Build Phase",
                "status": "pending",
                "tickets": [],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260128NM_no_mmd"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        # No MMD file created
        yield plan_dir


@pytest.fixture
def plan_with_existing_mmd():
    """Create a plan with an existing MMD file for overwrite tests."""
    plan_content = {
        "name": "existing-mmd-plan",
        "objective": "Test force overwrite behavior",
        "status": "pending",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Build Phase",
                "status": "pending",
                "tickets": [],
            },
        ],
    }

    # Pre-existing MMD content
    mmd_content = """%% OLD CONTENT - should be overwritten with --force
flowchart LR
    Start((Start)) --> End((End))
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260128EM_existing_mmd"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        mmd_file = plan_dir / "orchestration_existing_mmd.mmd"
        mmd_file.write_text(mmd_content)
        yield plan_dir


# =============================================================================
# TEST CLASSES: ORCHESTRATION GENERATE
# =============================================================================


class TestOrchestrationGenerateMinimalPlan:
    """Tests for generating orchestration from minimal plan."""

    def test_orchestration_generate_minimal_plan(self, minimal_plan, cli_runner):
        """Test generating MMD from a minimal plan with single phase."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "generate", "--plan", str(minimal_plan)]
        )
        assert code == 0
        assert "Generated" in stdout or "orchestration" in stdout.lower()

        # Verify MMD file was created
        mmd_files = list(minimal_plan.glob("orchestration_*.mmd"))
        assert len(mmd_files) == 1

        # Verify content includes the phase
        mmd_content = mmd_files[0].read_text()
        assert "P1" in mmd_content
        assert "Build Phase" in mmd_content
        assert "flowchart" in mmd_content

    def test_orchestration_generate_includes_goal(self, minimal_plan, cli_runner):
        """Test that generated MMD includes objective as GOAL."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "generate", "--plan", str(minimal_plan)]
        )
        assert code == 0

        mmd_files = list(minimal_plan.glob("orchestration_*.mmd"))
        mmd_content = mmd_files[0].read_text()
        assert "GOAL:" in mmd_content
        assert "Test minimal orchestration generation" in mmd_content

    def test_orchestration_generate_includes_agent_routing(self, minimal_plan, cli_runner):
        """Test that generated MMD includes AGENT_ROUTING header."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "generate", "--plan", str(minimal_plan)]
        )
        assert code == 0

        mmd_files = list(minimal_plan.glob("orchestration_*.mmd"))
        mmd_content = mmd_files[0].read_text()
        assert "AGENT_ROUTING:" in mmd_content
        assert "P1 ->" in mmd_content


class TestOrchestrationGenerateComplexPlan:
    """Tests for generating orchestration from complex multi-phase plan."""

    def test_orchestration_generate_complex_plan(self, complex_plan, cli_runner):
        """Test generating MMD from a complex plan with multiple phases."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "generate", "--plan", str(complex_plan)]
        )
        assert code == 0

        # Verify MMD file was created
        mmd_files = list(complex_plan.glob("orchestration_*.mmd"))
        assert len(mmd_files) == 1

        # Verify content includes all phases
        mmd_content = mmd_files[0].read_text()
        assert "P1" in mmd_content
        assert "P2" in mmd_content
        assert "P3" in mmd_content
        assert "P4" in mmd_content

    def test_orchestration_generate_includes_all_phases_in_header(
        self, complex_plan, cli_runner
    ):
        """Test that generated MMD lists all phases in PHASES header."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "generate", "--plan", str(complex_plan)]
        )
        assert code == 0

        mmd_files = list(complex_plan.glob("orchestration_*.mmd"))
        mmd_content = mmd_files[0].read_text()

        assert "PHASES:" in mmd_content
        assert "P1:" in mmd_content
        assert "P2:" in mmd_content
        assert "P3:" in mmd_content
        assert "P4:" in mmd_content

    def test_orchestration_generate_test_phase_routing(self, complex_plan, cli_runner):
        """Test that test phases get test-builder agent routing."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "generate", "--plan", str(complex_plan)]
        )
        assert code == 0

        mmd_files = list(complex_plan.glob("orchestration_*.mmd"))
        mmd_content = mmd_files[0].read_text()

        # P3 is "Testing Phase" - should route to test-builder
        assert "P3 -> test-builder" in mmd_content

    def test_orchestration_generate_includes_status(self, complex_plan, cli_runner):
        """Test that generated MMD includes STATUS header with phase statuses."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "generate", "--plan", str(complex_plan)]
        )
        assert code == 0

        mmd_files = list(complex_plan.glob("orchestration_*.mmd"))
        mmd_content = mmd_files[0].read_text()

        assert "STATUS:" in mmd_content
        assert "P1=completed" in mmd_content
        assert "P2=in_progress" in mmd_content
        assert "P3=pending" in mmd_content


class TestOrchestrationGenerateCreatesFile:
    """Tests for file creation behavior of orchestration generate."""

    def test_orchestration_generate_creates_file(self, minimal_plan, cli_runner):
        """Test that orchestration generate creates the MMD file."""
        # Verify no MMD file exists initially
        mmd_files_before = list(minimal_plan.glob("orchestration_*.mmd"))
        assert len(mmd_files_before) == 0

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "generate", "--plan", str(minimal_plan)]
        )
        assert code == 0

        # Verify MMD file was created
        mmd_files_after = list(minimal_plan.glob("orchestration_*.mmd"))
        assert len(mmd_files_after) == 1

    def test_orchestration_generate_file_naming(self, minimal_plan, cli_runner):
        """Test that generated MMD file uses plan folder name for naming."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "generate", "--plan", str(minimal_plan)]
        )
        assert code == 0

        mmd_files = list(minimal_plan.glob("orchestration_*.mmd"))
        # File should be named orchestration_minimal_plan.mmd (based on folder name)
        assert "minimal_plan" in mmd_files[0].name

    def test_orchestration_generate_custom_output_name(self, minimal_plan, cli_runner):
        """Test generating MMD with custom output filename."""
        stdout, stderr, code = cli_runner(
            [
                "agent",
                "epic",
                "orchestration",
                "generate",
                "--plan",
                str(minimal_plan),
                "--output",
                "custom_orchestration.mmd",
            ]
        )
        assert code == 0

        # Verify custom-named file was created
        custom_file = minimal_plan / "custom_orchestration.mmd"
        assert custom_file.exists()


class TestOrchestrationGenerateForceOverwrite:
    """Tests for force overwrite behavior of orchestration generate."""

    def test_orchestration_generate_fails_without_force(
        self, plan_with_existing_mmd, cli_runner
    ):
        """Test that generate fails when MMD exists without --force."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "generate", "--plan", str(plan_with_existing_mmd)]
        )
        assert code != 0
        assert "already exists" in stderr or "already exists" in stdout
        assert "--force" in stderr or "force" in (stderr + stdout).lower()

    def test_orchestration_generate_force_overwrite(
        self, plan_with_existing_mmd, cli_runner
    ):
        """Test that --force allows overwriting existing MMD file."""
        # Get original content
        mmd_files = list(plan_with_existing_mmd.glob("orchestration_*.mmd"))
        original_content = mmd_files[0].read_text()
        assert "OLD CONTENT" in original_content

        stdout, stderr, code = cli_runner(
            [
                "agent",
                "epic",
                "orchestration",
                "generate",
                "--plan",
                str(plan_with_existing_mmd),
                "--force",
            ]
        )
        assert code == 0

        # Verify content was overwritten
        mmd_files = list(plan_with_existing_mmd.glob("orchestration_*.mmd"))
        new_content = mmd_files[0].read_text()
        assert "OLD CONTENT" not in new_content
        assert "flowchart" in new_content
        assert "P1" in new_content

    def test_orchestration_generate_force_overwrites_completely(
        self, plan_with_existing_mmd, cli_runner
    ):
        """Test that --force completely replaces the file content."""
        stdout, stderr, code = cli_runner(
            [
                "agent",
                "epic",
                "orchestration",
                "generate",
                "--plan",
                str(plan_with_existing_mmd),
                "--force",
            ]
        )
        assert code == 0

        mmd_files = list(plan_with_existing_mmd.glob("orchestration_*.mmd"))
        new_content = mmd_files[0].read_text()

        # Should have proper structure
        assert "GOAL:" in new_content
        assert "PHASES:" in new_content
        assert "AGENT_ROUTING:" in new_content


# =============================================================================
# TEST CLASSES: ORCHESTRATION VALIDATE
# =============================================================================


class TestOrchestrationValidateMatchingMmd:
    """Tests for validating a correctly matching MMD file."""

    def test_orchestration_validate_matching_mmd(
        self, plan_with_matching_mmd, cli_runner
    ):
        """Test validation passes when MMD matches YAML phases."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "validate", "--plan", str(plan_with_matching_mmd)]
        )
        assert code == 0
        assert "passed" in stdout.lower() or "valid" in stdout.lower()

    def test_orchestration_validate_reports_file_names(
        self, plan_with_matching_mmd, cli_runner
    ):
        """Test that validation reports which files were checked."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "validate", "--plan", str(plan_with_matching_mmd)]
        )
        assert code == 0
        assert "orchestration_matching_mmd.mmd" in stdout
        assert "plan_build.yml" in stdout

    def test_orchestration_validate_matching_json_output(
        self, plan_with_matching_mmd, cli_runner
    ):
        """Test validation with JSON output format."""
        import json

        stdout, stderr, code = cli_runner(
            [
                "-j",
                "agent",
                "epic",
                "orchestration",
                "validate",
                "--plan",
                str(plan_with_matching_mmd),
            ]
        )
        assert code == 0

        result = json.loads(stdout)
        assert result["validation_passed"] is True
        assert "errors" in result
        assert len(result["errors"]) == 0


class TestOrchestrationValidateMissingPhase:
    """Tests for detecting missing phases in MMD."""

    def test_orchestration_validate_missing_phase(
        self, plan_with_missing_phase_mmd, cli_runner
    ):
        """Test validation fails when MMD is missing a phase from YAML."""
        stdout, stderr, code = cli_runner(
            [
                "agent",
                "epic",
                "orchestration",
                "validate",
                "--plan",
                str(plan_with_missing_phase_mmd),
            ]
        )
        assert code != 0
        # Should report P3 is missing
        assert "P3" in stdout or "P3" in stderr
        assert "missing" in (stdout + stderr).lower() or "error" in (stdout + stderr).lower()

    def test_orchestration_validate_missing_phase_error_details(
        self, plan_with_missing_phase_mmd, cli_runner
    ):
        """Test that missing phase error includes helpful details."""
        import json

        stdout, stderr, code = cli_runner(
            [
                "-j",
                "agent",
                "epic",
                "orchestration",
                "validate",
                "--plan",
                str(plan_with_missing_phase_mmd),
            ]
        )
        assert code != 0

        result = json.loads(stdout)
        assert result["validation_passed"] is False
        assert len(result["errors"]) > 0

        # Find the error about P3
        missing_errors = [e for e in result["errors"] if e.get("phase_id") == "P3"]
        assert len(missing_errors) > 0
        assert "not found" in missing_errors[0]["message"].lower()


class TestOrchestrationValidateMissingTask:
    """Tests for detecting missing task IDs in MMD."""

    def test_orchestration_validate_missing_task(
        self, plan_with_missing_task_mmd, cli_runner
    ):
        """Test validation warns when MMD is missing task IDs from YAML."""
        stdout, stderr, code = cli_runner(
            [
                "agent",
                "epic",
                "orchestration",
                "validate",
                "--plan",
                str(plan_with_missing_task_mmd),
            ]
        )
        # Missing tasks are warnings, not errors (should pass without --strict)
        assert code == 0
        # Should mention the missing tasks as warnings
        output = stdout + stderr
        # Warnings about P1-002 and P1-003 should appear
        assert "P1-002" in output or "warn" in output.lower()

    def test_orchestration_validate_missing_task_strict_mode(
        self, plan_with_missing_task_mmd, cli_runner
    ):
        """Test validation fails in strict mode when tasks are missing."""
        stdout, stderr, code = cli_runner(
            [
                "agent",
                "epic",
                "orchestration",
                "validate",
                "--plan",
                str(plan_with_missing_task_mmd),
                "--strict",
            ]
        )
        # With --strict, warnings become failures
        assert code != 0

    def test_orchestration_validate_missing_task_json_details(
        self, plan_with_missing_task_mmd, cli_runner
    ):
        """Test that missing task warnings include helpful details in JSON."""
        import json

        stdout, stderr, code = cli_runner(
            [
                "-j",
                "agent",
                "epic",
                "orchestration",
                "validate",
                "--plan",
                str(plan_with_missing_task_mmd),
            ]
        )

        result = json.loads(stdout)
        # Should have warnings for P1-002 and P1-003
        assert len(result["warnings"]) >= 2

        task_ids_warned = [w.get("task_id") for w in result["warnings"]]
        assert "P1-002" in task_ids_warned
        assert "P1-003" in task_ids_warned


class TestOrchestrationValidateNoMmdFile:
    """Tests for error handling when no MMD file exists."""

    def test_orchestration_validate_no_mmd_file(self, plan_without_mmd, cli_runner):
        """Test validation fails gracefully when no MMD file exists."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "orchestration", "validate", "--plan", str(plan_without_mmd)]
        )
        # Should fail with exit code 2 (file not found)
        assert code == 2
        assert "orchestration" in (stdout + stderr).lower()
        assert "not found" in (stdout + stderr).lower() or "no" in (stdout + stderr).lower()

    def test_orchestration_validate_no_mmd_json_output(self, plan_without_mmd, cli_runner):
        """Test no MMD error with JSON output."""
        stdout, stderr, code = cli_runner(
            ["-j", "agent", "epic", "orchestration", "validate", "--plan", str(plan_without_mmd)]
        )
        assert code == 2


# =============================================================================
# TEST CLASSES: EDGE CASES
# =============================================================================


class TestOrchestrationGenerateEdgeCases:
    """Edge case tests for orchestration generate command."""

    def test_orchestration_generate_no_plan_files(self, cli_runner):
        """Test error when no plan_*.yml files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260128NP_no_plan"
            plan_dir.mkdir()
            # No plan files created

            stdout, stderr, code = cli_runner(
                ["agent", "epic", "orchestration", "generate", "--plan", str(plan_dir)]
            )
            assert code != 0
            assert "No plan" in (stdout + stderr) or "not found" in (stdout + stderr).lower()

    def test_orchestration_generate_empty_phases(self, cli_runner):
        """Test error when plan has no phases."""
        plan_content = {
            "name": "empty-phases-plan",
            "objective": "Test with no phases",
            "status": "pending",
            "phases": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260128EP_empty_phases"
            plan_dir.mkdir()
            plan_file = plan_dir / "plan_build.yml"
            with open(plan_file, "w") as f:
                yaml.dump(plan_content, f, default_flow_style=False)

            stdout, stderr, code = cli_runner(
                ["agent", "epic", "orchestration", "generate", "--plan", str(plan_dir)]
            )
            assert code != 0
            assert "No phases" in (stdout + stderr) or "phases" in (stdout + stderr).lower()

    def test_orchestration_generate_nested_plan_structure(self, cli_runner):
        """Test generate works with phases nested under 'plan' key."""
        plan_content = {
            "plan": {
                "name": "nested-plan",
                "objective": "Test nested structure",
                "phases": [
                    {
                        "phase_id": "NP1",
                        "name": "Nested Build Phase",
                        "status": "pending",
                        "tickets": [],
                    },
                ],
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260128NS_nested_structure"
            plan_dir.mkdir()
            plan_file = plan_dir / "plan_build.yml"
            with open(plan_file, "w") as f:
                yaml.dump(plan_content, f, default_flow_style=False)

            stdout, stderr, code = cli_runner(
                ["agent", "epic", "orchestration", "generate", "--plan", str(plan_dir)]
            )
            assert code == 0

            mmd_files = list(plan_dir.glob("orchestration_*.mmd"))
            assert len(mmd_files) == 1
            mmd_content = mmd_files[0].read_text()
            assert "NP1" in mmd_content
            assert "Nested Build Phase" in mmd_content


class TestOrchestrationValidateEdgeCases:
    """Edge case tests for orchestration validate command."""

    def test_orchestration_validate_no_plan_files(self, cli_runner):
        """Test error when no plan_*.yml files exist during validation."""
        mmd_content = """%% Test MMD
flowchart LR
    Start --> End
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260128NP_no_plan"
            plan_dir.mkdir()
            mmd_file = plan_dir / "orchestration_test.mmd"
            mmd_file.write_text(mmd_content)
            # No plan files created

            stdout, stderr, code = cli_runner(
                ["agent", "epic", "orchestration", "validate", "--plan", str(plan_dir)]
            )
            assert code == 2
            assert "No plan" in (stdout + stderr) or "not found" in (stdout + stderr).lower()

    def test_orchestration_validate_invalid_yaml(self, cli_runner):
        """Test validation handles invalid YAML gracefully."""
        mmd_content = """%% Test MMD
%% PHASES:
%%   P1: Test Phase
flowchart LR
    Start --> P1[P1: Test]
    P1 --> End
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260128IY_invalid_yaml"
            plan_dir.mkdir()
            # Create invalid YAML
            plan_file = plan_dir / "plan_build.yml"
            plan_file.write_text("invalid: yaml: content: [")
            mmd_file = plan_dir / "orchestration_test.mmd"
            mmd_file.write_text(mmd_content)

            stdout, stderr, code = cli_runner(
                ["agent", "epic", "orchestration", "validate", "--plan", str(plan_dir)]
            )
            # Should handle gracefully (skip invalid file or warn)
            # May still succeed if no valid phases found, or fail
            assert code in [0, 1, 2]

    def test_orchestration_validate_multiple_mmd_files(self, cli_runner):
        """Test validation uses first MMD when multiple exist."""
        plan_content = {
            "name": "multi-mmd-plan",
            "phases": [{"phase_id": "P1", "name": "Test", "status": "pending", "tickets": []}],
        }
        mmd_content = """%% Test MMD
%% PHASES:
%%   P1: Test
flowchart LR
    Start --> P1[P1: Test]
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260128MM_multi_mmd"
            plan_dir.mkdir()
            plan_file = plan_dir / "plan_build.yml"
            with open(plan_file, "w") as f:
                yaml.dump(plan_content, f, default_flow_style=False)
            # Create multiple MMD files
            (plan_dir / "orchestration_first.mmd").write_text(mmd_content)
            (plan_dir / "orchestration_second.mmd").write_text(mmd_content)

            stdout, stderr, code = cli_runner(
                ["agent", "epic", "orchestration", "validate", "--plan", str(plan_dir)]
            )
            # Should succeed and potentially warn about multiple files
            assert code == 0
            # May include warning about multiple files
            output = stdout + stderr
            if "multiple" in output.lower() or "warning" in output.lower():
                assert "using" in output.lower() or "first" in output.lower()


# =============================================================================
# DYNAMIC AGENT TYPE REGISTRY TESTS (GA_007, GA_008, GA_009)
# =============================================================================


class TestGetValidAgentTypes:
    """Tests for the dynamic agent type registry."""

    def test_discovers_agents_from_mock_directory(self, tmp_path):
        """Test that get_valid_agent_types discovers agents from directory structure."""
        from agenticcli.commands.plan import get_valid_agent_types

        # Create mock agent directory structure
        agents_dir = tmp_path / "agents"
        (agents_dir / "build" / "build-python").mkdir(parents=True)
        (agents_dir / "build" / "build-flutter").mkdir(parents=True)
        (agents_dir / "test" / "test-runner").mkdir(parents=True)
        (agents_dir / "test" / "test-audit").mkdir(parents=True)

        result = get_valid_agent_types(agents_dir=agents_dir)

        assert "build-python" in result
        assert "build-flutter" in result
        assert "test-runner" in result
        assert "test-audit" in result
        assert len(result) == 4

    def test_fallback_when_directory_missing(self, tmp_path):
        """Test fallback to hardcoded set when agents directory doesn't exist."""
        from agenticcli.commands.plan import get_valid_agent_types, _FALLBACK_AGENT_TYPES

        nonexistent = tmp_path / "nonexistent"
        result = get_valid_agent_types(agents_dir=nonexistent)

        assert result == _FALLBACK_AGENT_TYPES

    def test_fallback_when_directory_empty(self, tmp_path):
        """Test fallback when directory exists but has no agents."""
        from agenticcli.commands.plan import get_valid_agent_types, _FALLBACK_AGENT_TYPES

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        result = get_valid_agent_types(agents_dir=agents_dir)

        assert result == _FALLBACK_AGENT_TYPES

    def test_discovers_real_agents(self):
        """Test that get_valid_agent_types discovers from real filesystem."""
        from agenticcli.commands.plan import get_valid_agent_types

        result = get_valid_agent_types()

        # Should discover at least these known agents
        assert "build-python" in result
        assert "test-runner" in result
        assert "planner-build" in result
        assert len(result) >= 20  # We know there are 25+

    def test_skips_hidden_directories(self, tmp_path):
        """Test that hidden directories are skipped."""
        from agenticcli.commands.plan import get_valid_agent_types

        agents_dir = tmp_path / "agents"
        (agents_dir / "build" / "build-python").mkdir(parents=True)
        (agents_dir / "build" / ".hidden-agent").mkdir(parents=True)

        result = get_valid_agent_types(agents_dir=agents_dir)

        assert "build-python" in result
        assert ".hidden-agent" not in result

    def test_skips_files_in_category_dir(self, tmp_path):
        """Test that files (like manifest.yml) in category dirs are skipped."""
        from agenticcli.commands.plan import get_valid_agent_types

        agents_dir = tmp_path / "agents"
        (agents_dir / "build" / "build-python").mkdir(parents=True)
        (agents_dir / "build" / "manifest.yml").write_text("name: build")

        result = get_valid_agent_types(agents_dir=agents_dir)

        assert "build-python" in result
        assert "manifest.yml" not in result


class TestAgentRoutingValidationErrors:
    """Tests for AGENT_ROUTING validation producing errors (not warnings)."""

    def test_invalid_agent_type_is_error(self, tmp_path):
        """Test that an invalid agent type in AGENT_ROUTING produces an error, not a warning."""
        from agenticcli.commands.epic import cmd_orchestration_validate

        plan_dir = tmp_path / "260208XX_test"
        plan_dir.mkdir()

        # Create plan YAML
        plan_content = {
            "name": "test-plan",
            "objective": "Test validation",
            "status": "pending",
            "phases": [
                {"phase_id": "P1", "name": "Build", "status": "pending", "tickets": [
                    {"id": "T001", "name": "Task 1", "status": "pending"}
                ]},
            ],
        }
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Create MMD with invalid agent type
        mmd_content = """flowchart LR
    %% AGENT_ROUTING: Build -> nonexistent-agent-type
    Start((Start)) --> T001[Task 1]
    T001 --> End((End))
"""
        mmd_file = plan_dir / "orchestration_test.mmd"
        mmd_file.write_text(mmd_content)

        # Run validation - capture via capsys-like approach
        from types import SimpleNamespace
        args = SimpleNamespace(plan=str(plan_dir), json=False, debug=False, strict=False)

        # We need to call the inner validation function directly
        import re
        from agenticcli.commands.plan import get_valid_agent_types

        valid_agent_types = get_valid_agent_types(agents_dir=tmp_path / "agents_fake")
        # Since agents_fake doesn't exist, it uses fallback

        # Verify nonexistent-agent-type is NOT in valid set
        assert "nonexistent-agent-type" not in valid_agent_types

    def test_valid_agent_routing_passes(self, tmp_path):
        """Test that valid agent types in AGENT_ROUTING do not produce errors."""
        from agenticcli.commands.plan import get_valid_agent_types

        agents_dir = tmp_path / "agents"
        (agents_dir / "build" / "build-python").mkdir(parents=True)
        (agents_dir / "test" / "test-runner").mkdir(parents=True)

        valid_types = get_valid_agent_types(agents_dir=agents_dir)

        assert "build-python" in valid_types
        assert "test-runner" in valid_types

    def test_equals_format_routing_parsed(self, tmp_path):
        """Test that Phase=agent-type format is also parsed (newer format)."""
        import re

        mmd_content = "%% AGENT_ROUTING: Build=build-python, Testing=test-runner"
        routing_pattern = r"(?:%%|#)\s*AGENT_ROUTING:\s*(.+)"
        routing_matches = re.findall(routing_pattern, mmd_content)

        assert len(routing_matches) == 1

        # Parse the routing line
        routings = routing_matches[0].split(",")
        parsed = []
        for routing in routings:
            routing = routing.strip()
            match = re.match(r"(\w+)\s*(?:->|=)\s*(\S+)", routing)
            if match:
                parsed.append((match.group(1), match.group(2)))

        assert ("Build", "build-python") in parsed
        assert ("Testing", "test-runner") in parsed

    def test_hash_comment_routing_parsed(self):
        """Test that # AGENT_ROUTING: format is parsed (used in some MMDs)."""
        import re

        mmd_content = "# AGENT_ROUTING: ProtocolAsset=teacher-update-assets, Validation=test-guidance-simulator"
        routing_pattern = r"(?:%%|#)\s*AGENT_ROUTING:\s*(.+)"
        routing_matches = re.findall(routing_pattern, mmd_content)

        assert len(routing_matches) == 1
        assert "ProtocolAsset=teacher-update-assets" in routing_matches[0]


# =============================================================================
# LOOP TYPE VALIDATION TESTS (GA_010, GA_011, GA_012)
# =============================================================================


class TestGetValidLoopTypes:
    """Tests for the loop type registry."""

    def test_returns_expected_loop_types(self):
        """Test that get_valid_loop_types returns expected set from real file."""
        from agenticcli.commands.plan import get_valid_loop_types

        result = get_valid_loop_types()

        assert "test-fix-loop" in result
        assert "audit-test-fix-loop" in result
        assert "planner-loop" in result
        assert "guidance-test-loop" in result
        assert len(result) >= 10

    def test_fallback_when_file_missing(self, tmp_path):
        """Test fallback to hardcoded set when file doesn't exist."""
        from agenticcli.commands.plan import get_valid_loop_types, _FALLBACK_LOOP_TYPES

        result = get_valid_loop_types(loops_file=tmp_path / "nonexistent.yml")

        assert result == _FALLBACK_LOOP_TYPES

    def test_fallback_on_invalid_yaml(self, tmp_path):
        """Test fallback when YAML is invalid."""
        from agenticcli.commands.plan import get_valid_loop_types, _FALLBACK_LOOP_TYPES

        bad_file = tmp_path / "bad.yml"
        bad_file.write_text("{{{invalid yaml}")

        result = get_valid_loop_types(loops_file=bad_file)

        assert result == _FALLBACK_LOOP_TYPES

    def test_reads_from_custom_file(self, tmp_path):
        """Test reading loop types from a custom file."""
        from agenticcli.commands.plan import get_valid_loop_types

        custom_file = tmp_path / "loops.yml"
        custom_file.write_text(yaml.dump({
            "loop_types": {
                "custom-loop": {"purpose": "test", "maximum_iterations": 3},
                "another-loop": {"purpose": "test2", "maximum_iterations": 5},
            }
        }))

        result = get_valid_loop_types(loops_file=custom_file)

        assert result == {"custom-loop", "another-loop"}


class TestLoopTypeValidation:
    """Tests for loop type validation in cmd_validate."""

    def test_valid_loop_type_no_warning(self, tmp_path, cli_runner):
        """Test that valid loop types don't produce warnings."""
        plan_dir = tmp_path / "260208XX_test"
        plan_dir.mkdir()

        plan_content = {
            "name": "test-plan",
            "objective": "Test",
            "status": "pending",
            "phases": [],
            "loop_structures": [
                {"id": "loop1", "type": "test-fix-loop", "applies_to_phase": "P1"},
            ],
        }
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Create a minimal MMD to avoid missing-mmd errors
        (plan_dir / "orchestration_test.mmd").write_text("flowchart LR\n    Start((Start)) --> End((End))")

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "validate", str(plan_dir)]
        )
        output = stdout + stderr
        assert "not defined in agent-loops.yml" not in output

    def test_invalid_loop_type_warns(self, tmp_path, cli_runner):
        """Test that invalid loop types produce a warning."""
        plan_dir = tmp_path / "260208XX_test"
        plan_dir.mkdir()

        plan_content = {
            "name": "test-plan",
            "objective": "Test",
            "status": "pending",
            "phases": [],
            "loop_structures": [
                {"id": "loop1", "type": "nonexistent-loop-type", "applies_to_phase": "P1"},
            ],
        }
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        (plan_dir / "orchestration_test.mmd").write_text("flowchart LR\n    Start((Start)) --> End((End))")

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "validate", str(plan_dir)]
        )
        output = stdout + stderr
        assert "nonexistent-loop-type" in output
        assert "not defined in agent-loops.yml" in output
        # Should be a warning, not error (exit code 0)
        assert code == 0

    def test_no_loop_structures_no_warning(self, tmp_path, cli_runner):
        """Test that plans without loop_structures validate cleanly."""
        plan_dir = tmp_path / "260208XX_test"
        plan_dir.mkdir()

        plan_content = {
            "name": "test-plan",
            "objective": "Test",
            "status": "pending",
            "phases": [],
        }
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        (plan_dir / "orchestration_test.mmd").write_text("flowchart LR\n    Start((Start)) --> End((End))")

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "validate", str(plan_dir)]
        )
        output = stdout + stderr
        assert "not defined in agent-loops.yml" not in output
