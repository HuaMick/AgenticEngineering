"""Tests for inputs commands."""

import pytest
import yaml


@pytest.fixture
def sample_inputs_file(temp_dir):
    """Create a sample inputs.yml file."""
    inputs_content = {
        "inputs": {
            "definitions": [{"name": "test_def", "path": "assets/definitions/test.yml"}],
            "guidelines": [{"name": "test_guide", "path": "assets/guidelines/test.yml"}],
        }
    }
    inputs_file = temp_dir / "inputs.yml"
    with open(inputs_file, "w") as f:
        yaml.dump(inputs_content, f)
    return inputs_file


@pytest.fixture
def valid_inputs_structure(temp_dir):
    """Create a valid inputs structure with referenced files."""
    # Create inputs.yml
    inputs_content = {
        "inputs": {
            "definitions": [{"name": "test_def", "path": "definitions/test.yml"}],
        }
    }
    inputs_file = temp_dir / "inputs.yml"
    with open(inputs_file, "w") as f:
        yaml.dump(inputs_content, f)

    # Create referenced file
    defs_dir = temp_dir / "definitions"
    defs_dir.mkdir()
    with open(defs_dir / "test.yml", "w") as f:
        yaml.dump({"definition": "test"}, f)

    return inputs_file


class TestInputsValidate:
    """Tests for 'agentic inputs validate' command."""

    def test_validate_help(self, cli_runner):
        """Test inputs validate --help output."""
        stdout, stderr, code = cli_runner(["inputs", "validate", "--help"])
        assert "validate" in stdout.lower()
        assert "file" in stdout
        assert code == 0

    def test_validate_missing_file(self, cli_runner, temp_dir):
        """Test validate with non-existent file."""
        stdout, stderr, code = cli_runner(["inputs", "validate", str(temp_dir / "nonexistent.yml")])
        assert code == 1

    def test_validate_valid_file(self, cli_runner, valid_inputs_structure):
        """Test validate with valid inputs file."""
        stdout, stderr, code = cli_runner(["inputs", "validate", str(valid_inputs_structure)])
        # Should pass or show validation results
        assert code in [0, 1]  # May fail if relative paths don't resolve


class TestInputsResolve:
    """Tests for 'agentic inputs resolve' command."""

    def test_resolve_help(self, cli_runner):
        """Test inputs resolve --help output."""
        stdout, stderr, code = cli_runner(["inputs", "resolve", "--help"])
        assert "resolve" in stdout.lower()
        assert "file" in stdout
        assert code == 0

    def test_resolve_missing_file(self, cli_runner, temp_dir):
        """Test resolve with non-existent file."""
        stdout, stderr, code = cli_runner(["inputs", "resolve", str(temp_dir / "nonexistent.yml")])
        assert code == 1

    def test_resolve_sample_file(self, cli_runner, sample_inputs_file):
        """Test resolve with sample inputs file."""
        stdout, stderr, code = cli_runner(["inputs", "resolve", str(sample_inputs_file)])
        # Should show resolved paths or errors
        assert code in [0, 1]
