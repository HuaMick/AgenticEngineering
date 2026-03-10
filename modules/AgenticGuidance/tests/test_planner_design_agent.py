"""Tests for planner-design agent definition validity (P4-T4).

Validates the planner-design agent files (manifest.yml, process.yml, inputs.yml)
added in P2 of the 260308PD_planner_design_agent_story_alignment epic.
"""

from pathlib import Path

import pytest
import yaml


AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"
PLANNER_DESIGN_DIR = AGENTS_DIR / "planner" / "planner-design"


# ---------------------------------------------------------------------------
# Tests for agent file existence
# ---------------------------------------------------------------------------

class TestPlannerDesignAgentFiles:
    """Test planner-design agent files exist and are valid YAML."""

    def test_manifest_exists(self):
        """Verify manifest.yml exists."""
        assert (PLANNER_DESIGN_DIR / "manifest.yml").exists()

    def test_process_exists(self):
        """Verify process.yml exists."""
        assert (PLANNER_DESIGN_DIR / "process.yml").exists()

    def test_inputs_exists(self):
        """Verify inputs.yml exists."""
        assert (PLANNER_DESIGN_DIR / "inputs.yml").exists()

    def test_manifest_valid_yaml(self):
        """Verify manifest.yml is valid YAML."""
        content = yaml.safe_load((PLANNER_DESIGN_DIR / "manifest.yml").read_text())
        assert isinstance(content, dict)

    def test_process_valid_yaml(self):
        """Verify process.yml is valid YAML."""
        content = yaml.safe_load((PLANNER_DESIGN_DIR / "process.yml").read_text())
        assert isinstance(content, dict)

    def test_inputs_valid_yaml(self):
        """Verify inputs.yml is valid YAML."""
        content = yaml.safe_load((PLANNER_DESIGN_DIR / "inputs.yml").read_text())
        assert isinstance(content, dict)


# ---------------------------------------------------------------------------
# Tests for manifest.yml content
# ---------------------------------------------------------------------------

class TestPlannerDesignManifest:
    """Test planner-design manifest content."""

    @pytest.fixture
    def manifest(self):
        """Load manifest.yml content."""
        return yaml.safe_load((PLANNER_DESIGN_DIR / "manifest.yml").read_text())

    def test_manifest_has_name(self, manifest):
        """Verify manifest has name field set to 'planner-design'."""
        assert "name" in manifest, "manifest.yml must have a 'name' field"
        assert manifest["name"] == "planner-design"

    def test_manifest_has_version(self, manifest):
        """Verify manifest has a version field."""
        assert "version" in manifest, "manifest.yml must have a 'version' field"

    def test_manifest_has_description(self, manifest):
        """Verify manifest has a description field."""
        assert "description" in manifest, "manifest.yml must have a 'description' field"
        assert len(manifest["description"]) > 20, "Description should be substantive"

    def test_manifest_has_design_principles(self, manifest):
        """Verify manifest defines design_principles field with story-first architecture."""
        assert "design_principles" in manifest, "manifest.yml must have 'design_principles'"
        principles = manifest["design_principles"]
        assert "Story-First" in principles, "design_principles should include Story-First"
        assert "Traceability" in principles, "design_principles should include Traceability"

    def test_manifest_has_outputs(self, manifest):
        """Verify manifest defines outputs."""
        assert "outputs" in manifest, "manifest.yml must define outputs"
        assert isinstance(manifest["outputs"], list)
        assert len(manifest["outputs"]) >= 2, "At least 2 output types expected"


# ---------------------------------------------------------------------------
# Tests for process.yml content
# ---------------------------------------------------------------------------

class TestPlannerDesignProcess:
    """Test planner-design process content."""

    @pytest.fixture
    def process(self):
        """Load process.yml content."""
        return yaml.safe_load((PLANNER_DESIGN_DIR / "process.yml").read_text())

    def test_process_has_goal(self, process):
        """Verify process has a goal field."""
        # process.yml may have top-level "goal" or nested under "process"
        if "process" in process:
            assert "goal" in process["process"]
        else:
            assert "goal" in process

    def test_process_has_steps(self, process):
        """Verify process has steps defined."""
        if "process" in process:
            assert "steps" in process["process"]
            steps = process["process"]["steps"]
        else:
            assert "steps" in process
            steps = process["steps"]
        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_process_requires_affected_stories(self, process):
        """Verify process references affected_stories as required input."""
        process_str = str(process)
        assert "affected_stories" in process_str

    def test_process_outputs_design_context(self, process):
        """Verify process outputs design_context.yml."""
        process_str = str(process)
        assert "design_context" in process_str

    def test_process_has_story_to_phase_mapping(self, process):
        """Verify process includes story-to-phase mapping step."""
        process_str = str(process)
        assert "traceability" in process_str.lower() or "story_to_phase" in process_str

    def test_process_references_pytest_markers(self, process):
        """Verify process references @pytest.mark.story markers."""
        process_str = str(process)
        assert "pytest.mark.story" in process_str


# ---------------------------------------------------------------------------
# Tests for inputs.yml content
# ---------------------------------------------------------------------------

class TestPlannerDesignInputs:
    """Test planner-design inputs content."""

    @pytest.fixture
    def inputs(self):
        """Load inputs.yml content."""
        return yaml.safe_load((PLANNER_DESIGN_DIR / "inputs.yml").read_text())

    def test_inputs_has_required_inputs(self, inputs):
        """Verify inputs defines required_inputs with objective and affected_stories."""
        assert "required_inputs" in inputs, "inputs.yml must define 'required_inputs'"
        required = inputs["required_inputs"]
        assert isinstance(required, list), "required_inputs should be a list"
        names = [ri.get("name") for ri in required if isinstance(ri, dict)]
        assert "objective" in names, "objective should be a required input"

    def test_inputs_requires_affected_stories(self, inputs):
        """Verify affected_stories is listed as a required input with required=true."""
        required = inputs.get("required_inputs", [])
        stories_input = [
            ri for ri in required
            if isinstance(ri, dict) and ri.get("name") == "affected_stories"
        ]
        assert len(stories_input) == 1, "affected_stories must be in required_inputs"
        assert stories_input[0].get("required") is True, \
            "affected_stories must be marked required: true"

    def test_inputs_has_reference_layers(self, inputs):
        """Verify inputs defines reference layers for transitive loading."""
        assert "inputs" in inputs, "inputs.yml must have top-level 'inputs' key"
        agent_inputs = inputs["inputs"]
        assert "layers" in agent_inputs, "inputs should define reference layers"
        layers = agent_inputs["layers"]
        assert isinstance(layers, list), "layers should be a list"
        assert len(layers) >= 1, "At least one reference layer expected"


# ---------------------------------------------------------------------------
# Tests for agent registration
# ---------------------------------------------------------------------------

class TestPlannerDesignRegistration:
    """Test planner-design is registered in planner manifest."""

    def test_planner_design_in_planner_roster(self):
        """Verify planner-design is registered in planner manifest.yml."""
        planner_manifest = AGENTS_DIR / "planner" / "manifest.yml"
        assert planner_manifest.exists(), \
            f"Planner manifest should exist at {planner_manifest}"
        content_str = planner_manifest.read_text()
        assert "planner-design" in content_str, \
            "planner-design must be registered in agents/planner/manifest.yml"

    def test_planner_design_dir_in_agent_tree(self):
        """Verify planner-design directory is in the planner agent tree."""
        assert PLANNER_DESIGN_DIR.is_dir()
        # Should be under agents/planner/
        assert PLANNER_DESIGN_DIR.parent.name == "planner"
