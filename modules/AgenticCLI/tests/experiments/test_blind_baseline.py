"""Blind Testing - Baseline Scenario (No Prefill).

This test documents the baseline behavior of planner-build
WITHOUT task prefilling. Run this to establish forgotten-task rates.

Experiment Protocol
===================

1. Start fresh planner-build session
2. Provide specification for a multi-phase feature
3. DO NOT use task prefill
4. Observe which ancillary tasks are forgotten

Observation Checklist
=====================

After planner-build completes, check for presence of:
- [ ] README.md update
- [ ] success_criteria on ALL tasks
- [ ] target_files on ALL tasks
- [ ] guidance on complex tasks
- [ ] inputs.yml file references validated

Expected Baseline Results
=========================

Based on prior observations:
- README update forgotten: ~40% of sessions
- success_criteria incomplete: ~30% of tasks
- target_files missing: ~25% of tasks

Measurement Criteria
====================

This experiment measures completion rates for commonly forgotten items:
1. README.md update - often forgotten after plan creation
2. success_criteria per task - often incomplete or generic
3. target_files specification - often missing from tasks
"""

import pytest
import yaml

pytestmark = pytest.mark.story("US-PLN-053", "US-GDN-083")


class TestBlindBaseline:
    """Baseline scenario for blind testing experiment.

    This is a DOCUMENTATION test, not automated.
    Manual execution is required for valid experiment results.
    """

    @pytest.mark.skip(reason="Manual experiment - see module docstring for protocol")
    def test_baseline_protocol(self):
        """Document baseline test protocol.

        BASELINE EXPERIMENT PROTOCOL:

        1. Create new plan folder:
           agentic plan scaffold 260120CL_blind_baseline

        2. Create specification.md with multi-phase feature:
           - At least 3 phases
           - At least 10 tasks total

        3. Run planner-build WITHOUT prefill:
           > You are planner-build. Create a build plan for...

        4. Record observations in baseline_results.yml:
           - readme_updated: true/false
           - tasks_with_success_criteria: N/M
           - tasks_with_target_files: N/M
           - session_duration: minutes

        5. CRITICAL: Do NOT inform the agent this is an experiment.
           The agent should operate under normal conditions.

        6. Copy templates/baseline_result_template.yml to record results.
        """
        pass

    @pytest.mark.skip(reason="Manual experiment - execute for each baseline session")
    def test_baseline_session_checklist(self):
        """Checklist to complete during each baseline session.

        PRE-SESSION:
        [ ] Fresh plan folder created
        [ ] Specification.md prepared (matches treatment specification)
        [ ] Recording template copied
        [ ] No task prefill commands run

        DURING SESSION:
        [ ] Note start time
        [ ] Do not mention experiment to agent
        [ ] Let agent complete naturally
        [ ] Note any prompting required

        POST-SESSION:
        [ ] Count tasks with success_criteria
        [ ] Count tasks with target_files
        [ ] Check for README.md update
        [ ] Note session duration
        [ ] Record all observations in result template
        """
        pass

    def test_observation_checklist_structure(self):
        """Test that observation checklist YAML is valid.

        This test validates the YAML structure used for recording
        experiment observations.
        """
        checklist = {
            "experiment": "baseline",
            "session_id": "YYYYMMDD_HHmm",
            "agent_info": {
                "model": "",
                "agent_type": "planner-build",
                "session_duration_minutes": None,
            },
            "specification": {
                "num_phases": None,
                "num_tasks": None,
                "complexity": "",
            },
            "observations": {
                "readme_updated": None,
                "total_tasks": None,
                "tasks_with_success_criteria": None,
                "tasks_with_target_files": None,
                "tasks_with_guidance": None,
                "tasks_with_inputs": None,
            },
            "notes": "",
        }

        # Validate structure is valid YAML
        yaml_str = yaml.dump(checklist)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["experiment"] == "baseline"
        assert "observations" in parsed
        assert "tasks_with_success_criteria" in parsed["observations"]
        assert "tasks_with_target_files" in parsed["observations"]

    def test_baseline_calculation_formulas(self):
        """Test the calculation formulas for baseline metrics.

        Documents how to calculate completion rates from observations.
        """
        # Example observation data
        observations = {
            "total_tasks": 10,
            "tasks_with_success_criteria": 6,
            "tasks_with_target_files": 7,
            "tasks_with_guidance": 5,
            "readme_updated": False,
        }

        # Calculate completion rates
        success_criteria_rate = (
            observations["tasks_with_success_criteria"] / observations["total_tasks"]
        )
        target_files_rate = (
            observations["tasks_with_target_files"] / observations["total_tasks"]
        )
        guidance_rate = (
            observations["tasks_with_guidance"] / observations["total_tasks"]
        )

        # Document expected rate calculations
        assert success_criteria_rate == 0.6  # 60%
        assert target_files_rate == 0.7  # 70%
        assert guidance_rate == 0.5  # 50%

        # Binary metrics
        assert observations["readme_updated"] is False

    @pytest.mark.skip(reason="Manual experiment - comparison guide")
    def test_baseline_comparison_requirements(self):
        """Document requirements for valid baseline comparison.

        For valid experiment results, baseline sessions must:

        1. Use IDENTICAL specification to treatment sessions
           - Same number of phases
           - Same complexity level
           - Same feature domain

        2. Use same agent/model for both conditions
           - Record model version
           - Use consistent system prompts

        3. Avoid priming or hinting
           - Do not mention the experiment
           - Do not ask about task completeness
           - Let agent complete naturally

        4. Record timing consistently
           - Note session start/end times
           - Record any interruptions

        5. Minimum sample size: 5 sessions per condition
           - More sessions improve statistical validity
           - Target: 10+ sessions per condition
        """
        pass
