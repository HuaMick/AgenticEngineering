"""Unit tests for PreferencesWorkflow.

Tests the preferences management workflow functionality.
Following the Domain → Workflow → Entrypoint pattern.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from myagents.backend.services.agents.workflows.setup_workflow import (
    PreferencesWorkflow,
    get_preference,
    set_preference,
    delete_preference,
    list_preferences,
    clear_preferences
)


@pytest.fixture
def temp_prefs_file(tmp_path):
    """Create a temporary preferences file for testing."""
    prefs_file = tmp_path / "test_preferences.json"
    return prefs_file


@pytest.fixture
def workflow(temp_prefs_file):
    """Create a PreferencesWorkflow instance with temporary file."""
    return PreferencesWorkflow(preferences_file=temp_prefs_file)


@pytest.mark.workflow_preferences
class TestGetPreference:
    """Test get_preference() method."""

    @pytest.mark.parametrize("return_value,expected_success,key,expected_value", [
        ("test_value", True, "test.key", "test_value"),
        (None, False, "nonexistent.key", None),
    ])
    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_get_preference(self, mock_manager_class, workflow, return_value, expected_success, key, expected_value):
        """Test getting existing and non-existent preferences."""
        mock_manager = MagicMock()
        mock_manager.get.return_value = return_value
        mock_manager_class.return_value = mock_manager

        success, message, value = workflow.get_preference(key)

        assert success is expected_success
        assert value == expected_value
        if expected_success:
            assert key in message
        else:
            assert "not found" in message.lower()
        mock_manager.get.assert_called_once_with(key)

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_get_preference_permission_error(self, mock_manager_class, workflow):
        """Test get_preference handles permission errors."""
        # Setup mock to raise PermissionError
        mock_manager = MagicMock()
        mock_manager.get.side_effect = PermissionError("Access denied")
        mock_manager_class.return_value = mock_manager

        success, message, value = workflow.get_preference("test.key")

        assert success is False
        assert "permission denied" in message.lower()
        assert value is None

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_get_preference_general_error(self, mock_manager_class, workflow):
        """Test get_preference handles general errors."""
        # Setup mock to raise generic exception
        mock_manager = MagicMock()
        mock_manager.get.side_effect = Exception("Read failed")
        mock_manager_class.return_value = mock_manager

        success, message, value = workflow.get_preference("test.key")

        assert success is False
        assert "failed to read" in message.lower()
        assert value is None

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_get_preference_with_nested_key(self, mock_manager_class, workflow):
        """Test getting preference with dot notation."""
        mock_manager = MagicMock()
        mock_manager.get.return_value = "nested_value"
        mock_manager_class.return_value = mock_manager

        success, message, value = workflow.get_preference("agent.default.model")

        assert success is True
        assert value == "nested_value"
        mock_manager.get.assert_called_once_with("agent.default.model")


@pytest.mark.workflow_preferences
class TestSetPreference:
    """Test set_preference() method."""

    @pytest.mark.parametrize("should_raise,expected_success", [
        (False, True),
        (True, False),
    ])
    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_set_preference(self, mock_manager_class, workflow, should_raise, expected_success):
        """Test setting a preference with success and failure scenarios."""
        mock_manager = MagicMock()
        if should_raise:
            mock_manager.set.side_effect = Exception("Write failed")
        mock_manager_class.return_value = mock_manager

        success, message = workflow.set_preference("test.key", "test_value")

        assert success is expected_success
        if expected_success:
            assert "test.key" in message
            assert "test_value" in message
            mock_manager.set.assert_called_once_with("test.key", "test_value")
        else:
            assert "failed to set" in message.lower()

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_set_preference_with_number(self, mock_manager_class, workflow):
        """Test setting preference with numeric value."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        success, message = workflow.set_preference("studio.port", 3000)

        assert success is True
        mock_manager.set.assert_called_once_with("studio.port", 3000)

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_set_preference_with_boolean(self, mock_manager_class, workflow):
        """Test setting preference with boolean value."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        success, message = workflow.set_preference("debug.enabled", True)

        assert success is True
        mock_manager.set.assert_called_once_with("debug.enabled", True)

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_set_preference_with_nested_key(self, mock_manager_class, workflow):
        """Test setting preference with dot notation."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        success, message = workflow.set_preference("agent.default.model", "gpt-4")

        assert success is True
        mock_manager.set.assert_called_once_with("agent.default.model", "gpt-4")


@pytest.mark.workflow_preferences
class TestDeletePreference:
    """Test delete_preference() method."""

    @pytest.mark.parametrize("delete_result,expected_success,expected_text", [
        (True, True, "deleted"),
        (False, False, "not found"),
    ])
    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_delete_preference(self, mock_manager_class, workflow, delete_result, expected_success, expected_text):
        """Test deleting existing and non-existent preferences."""
        mock_manager = MagicMock()
        mock_manager.delete.return_value = delete_result
        mock_manager_class.return_value = mock_manager

        key = "test.key" if expected_success else "nonexistent.key"
        success, message = workflow.delete_preference(key)

        assert success is expected_success
        assert expected_text in message.lower()
        if expected_success:
            assert key in message
        mock_manager.delete.assert_called_once_with(key)

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_delete_preference_permission_error(self, mock_manager_class, workflow):
        """Test delete_preference handles permission errors."""
        mock_manager = MagicMock()
        mock_manager.delete.side_effect = PermissionError("Access denied")
        mock_manager_class.return_value = mock_manager

        success, message = workflow.delete_preference("test.key")

        assert success is False
        assert "permission denied" in message.lower()

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_delete_preference_general_error(self, mock_manager_class, workflow):
        """Test delete_preference handles general errors."""
        mock_manager = MagicMock()
        mock_manager.delete.side_effect = Exception("Delete failed")
        mock_manager_class.return_value = mock_manager

        success, message = workflow.delete_preference("test.key")

        assert success is False
        assert "failed to delete" in message.lower()


@pytest.mark.workflow_preferences
class TestListPreferences:
    """Test list_preferences() method."""

    @pytest.mark.parametrize("prefs_data,expected_count", [
        ({"agent.default": "coding", "studio.port": 3000}, 2),
        ({}, 0),
    ])
    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_list_preferences(self, mock_manager_class, workflow, prefs_data, expected_count):
        """Test listing preferences with data and empty scenarios."""
        mock_manager = MagicMock()
        mock_manager.list_all.return_value = prefs_data
        mock_manager_class.return_value = mock_manager

        success, message, prefs = workflow.list_preferences()

        assert success is True
        assert prefs == prefs_data
        if expected_count > 0:
            assert f"{expected_count} preference(s)" in message
        else:
            assert "no preferences" in message.lower()
        mock_manager.list_all.assert_called_once()

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_list_preferences_permission_error(self, mock_manager_class, workflow):
        """Test list_preferences handles permission errors."""
        mock_manager = MagicMock()
        mock_manager.list_all.side_effect = PermissionError("Access denied")
        mock_manager_class.return_value = mock_manager

        success, message, prefs = workflow.list_preferences()

        assert success is False
        assert "permission denied" in message.lower()
        assert prefs == {}

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_list_preferences_general_error(self, mock_manager_class, workflow):
        """Test list_preferences handles general errors."""
        mock_manager = MagicMock()
        mock_manager.list_all.side_effect = Exception("Read failed")
        mock_manager_class.return_value = mock_manager

        success, message, prefs = workflow.list_preferences()

        assert success is False
        assert "failed to list" in message.lower()
        assert prefs == {}


@pytest.mark.workflow_preferences
class TestClearPreferences:
    """Test clear_preferences() method."""

    @pytest.mark.parametrize("should_raise,expected_success,expected_text", [
        (False, True, "cleared"),
        (True, False, "failed to clear"),
    ])
    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_clear_preferences(self, mock_manager_class, workflow, should_raise, expected_success, expected_text):
        """Test clearing preferences with success and failure scenarios."""
        mock_manager = MagicMock()
        if should_raise:
            mock_manager.clear_all.side_effect = Exception("Clear failed")
        mock_manager_class.return_value = mock_manager

        success, message = workflow.clear_preferences()

        assert success is expected_success
        assert expected_text in message.lower()
        mock_manager.clear_all.assert_called_once()


@pytest.mark.workflow_preferences
class TestBackwardCompatibleFunctions:
    """Test backward-compatible function-based API."""

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_function_get_preference(self, mock_manager_class, temp_prefs_file):
        """Test backward-compatible get_preference function."""
        mock_manager = MagicMock()
        mock_manager.get.return_value = "test_value"
        mock_manager_class.return_value = mock_manager

        success, message, value = get_preference("test.key", preferences_file=temp_prefs_file)

        assert success is True
        assert value == "test_value"

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_function_set_preference(self, mock_manager_class, temp_prefs_file):
        """Test backward-compatible set_preference function."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        success, message = set_preference("test.key", "test_value", preferences_file=temp_prefs_file)

        assert success is True

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_function_delete_preference(self, mock_manager_class, temp_prefs_file):
        """Test backward-compatible delete_preference function."""
        mock_manager = MagicMock()
        mock_manager.delete.return_value = True
        mock_manager_class.return_value = mock_manager

        success, message = delete_preference("test.key", preferences_file=temp_prefs_file)

        assert success is True

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_function_list_preferences(self, mock_manager_class, temp_prefs_file):
        """Test backward-compatible list_preferences function."""
        mock_manager = MagicMock()
        mock_manager.list_all.return_value = {"test": "value"}
        mock_manager_class.return_value = mock_manager

        success, message, prefs = list_preferences(preferences_file=temp_prefs_file)

        assert success is True
        assert prefs == {"test": "value"}

    @patch('myagents.backend.services.preferences.domains.preferences_manager.manager.PreferencesManager')
    def test_function_clear_preferences(self, mock_manager_class, temp_prefs_file):
        """Test backward-compatible clear_preferences function."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        success, message = clear_preferences(preferences_file=temp_prefs_file)

        assert success is True


@pytest.mark.workflow_preferences
class TestPreferencesWorkflowInitialization:
    """Test PreferencesWorkflow initialization."""

    def test_workflow_init_with_file(self, temp_prefs_file):
        """Test workflow initialization with preferences file."""
        workflow = PreferencesWorkflow(preferences_file=temp_prefs_file)

        assert workflow.preferences_file == temp_prefs_file

    def test_workflow_init_without_file(self):
        """Test workflow initialization without preferences file."""
        workflow = PreferencesWorkflow()

        assert workflow.preferences_file is None


@pytest.mark.workflow_preferences
class TestPreferencesWorkflowSetup:
    """Test PreferencesWorkflow setup functionality."""

    def test_initialize_config_creates_file(self, tmp_path, monkeypatch):
        """Test that initialize_config creates config.yml in home directory."""
        # Setup: Use tmp_path as fake home directory
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        # Import after monkeypatch
        from myagents.backend.services.agents.workflows.setup_workflow import SetupWorkflow

        # Execute
        workflow = SetupWorkflow()
        success, message = workflow.initialize_config()

        # Verify
        assert success is True
        config_file = fake_home / ".config" / "myagents" / "config.yml"
        assert config_file.exists()
        assert "Config created" in message or "created" in message.lower()

    def test_initialize_config_has_proper_schema(self, tmp_path, monkeypatch):
        """Test that created config has server/runtime/langgraph sections."""
        import yaml  # type: ignore[import-untyped]

        # Setup
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        from myagents.backend.services.agents.workflows.setup_workflow import SetupWorkflow

        # Execute
        workflow = SetupWorkflow()
        success, message = workflow.initialize_config()

        # Verify schema
        config_file = fake_home / ".config" / "myagents" / "config.yml"
        with open(config_file) as f:
            config_data = yaml.safe_load(f)

        assert "server" in config_data
        assert "runtime" in config_data
        assert "langgraph" in config_data
        assert config_data["server"]["host"] == "127.0.0.1"
        assert config_data["server"]["port"] == 2024

    def test_initialize_config_no_overwrite_existing(self, tmp_path, monkeypatch):
        """Test that existing config is not overwritten."""
        import yaml  # type: ignore[import-untyped]

        # Setup: Create existing config
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        config_dir = fake_home / ".config" / "myagents"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.yml"

        existing_config = {"custom": "value"}
        with open(config_file, 'w') as f:
            yaml.dump(existing_config, f)

        monkeypatch.setenv("HOME", str(fake_home))

        from myagents.backend.services.agents.workflows.setup_workflow import SetupWorkflow

        # Execute
        workflow = SetupWorkflow()
        success, message = workflow.initialize_config(overwrite=False)

        # Verify existing config preserved
        with open(config_file) as f:
            config_data = yaml.safe_load(f)

        assert config_data == existing_config
        assert "already exists" in message

    def test_run_setup_success(self, tmp_path, monkeypatch):
        """Test run_setup completes successfully."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        from myagents.backend.services.agents.workflows.setup_workflow import SetupWorkflow

        workflow = SetupWorkflow()
        success, message = workflow.run_setup()

        assert success is True
        assert "Setup complete" in message or "complete" in message.lower()


@pytest.mark.workflow_preferences
class TestLangGraphConfigSetup:
    """TEST-001 & TEST-002: Test langgraph.json setup functionality."""

    def test_initialize_langgraph_config_creates_valid_file(self, tmp_path, monkeypatch):
        """TEST-001: Verify langgraph.json is created with valid content."""
        import json

        # Setup fake home directory
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        from myagents.backend.services.agents.workflows.setup_workflow import SetupWorkflow

        # Execute
        workflow = SetupWorkflow()
        success, message = workflow.initialize_langgraph_config()

        # Verify file was created
        langgraph_file = fake_home / ".config" / "myagents" / "langgraph.json"
        assert langgraph_file.exists(), "langgraph.json should be created"
        assert success is True, f"Should succeed but got: {message}"
        assert "created" in message.lower()

        # Verify JSON is valid
        with open(langgraph_file) as f:
            data = json.load(f)

        # Verify required fields exist
        assert "dependencies" in data, "langgraph.json should have dependencies"
        assert "graphs" in data, "langgraph.json should have graphs"
        assert "env" in data, "langgraph.json should have env path"

        # Verify dependencies are a list
        assert isinstance(data["dependencies"], list), "dependencies should be a list"
        assert len(data["dependencies"]) > 0, "dependencies should not be empty"

        # Verify graphs is a dict with at least one entry
        assert isinstance(data["graphs"], dict), "graphs should be a dict"
        assert len(data["graphs"]) > 0, "graphs should not be empty"

        # Verify each graph path format (path:function)
        for graph_name, graph_path in data["graphs"].items():
            assert ":" in graph_path, f"Graph {graph_name} should have format path:function"
            parts = graph_path.split(":")
            assert len(parts) == 2, f"Graph {graph_name} should have exactly one colon separator"

    def test_setup_with_installed_package_verifies_files(self, tmp_path, monkeypatch):
        """TEST-002: Test setup uses actual installed package files and verifies they exist."""
        import json

        # Setup fake home directory
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        from myagents.backend.services.agents.workflows.setup_workflow import SetupWorkflow

        # Execute
        workflow = SetupWorkflow()
        success, message = workflow.initialize_langgraph_config()

        # Verify success (if files don't exist, this should fail with clear message)
        if not success:
            # Expected failure should have clear error about missing files
            assert "doesn't exist" in message.lower() or "not found" in message.lower(), \
                f"Failure should explain missing files: {message}"
            pytest.skip(f"Installed package files not available: {message}")

        # If successful, verify referenced files actually exist
        langgraph_file = fake_home / ".config" / "myagents" / "langgraph.json"
        with open(langgraph_file) as f:
            data = json.load(f)

        for graph_name, graph_path in data["graphs"].items():
            file_path, entry_point = graph_path.split(":")
            assert Path(file_path).exists(), \
                f"Graph {graph_name} references {file_path} which doesn't exist"

    def test_langgraph_config_no_overwrite_existing(self, tmp_path, monkeypatch):
        """Test that existing langgraph.json is not overwritten."""
        import json

        # Setup: Create existing langgraph.json
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        config_dir = fake_home / ".config" / "myagents"
        config_dir.mkdir(parents=True)
        langgraph_file = config_dir / "langgraph.json"

        existing_data = {"custom": "value", "graphs": {}}
        with open(langgraph_file, 'w') as f:
            json.dump(existing_data, f)

        monkeypatch.setenv("HOME", str(fake_home))

        from myagents.backend.services.agents.workflows.setup_workflow import SetupWorkflow

        # Execute without overwrite
        workflow = SetupWorkflow()
        success, message = workflow.initialize_langgraph_config(overwrite=False)

        # Verify existing config preserved
        with open(langgraph_file) as f:
            data = json.load(f)

        assert data == existing_data, "Existing config should be preserved"
        assert "already exists" in message

    def test_langgraph_config_overwrite_when_requested(self, tmp_path, monkeypatch):
        """Test that langgraph.json can be overwritten when requested."""
        import json

        # Setup: Create existing langgraph.json
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        config_dir = fake_home / ".config" / "myagents"
        config_dir.mkdir(parents=True)
        langgraph_file = config_dir / "langgraph.json"

        existing_data = {"custom": "value", "graphs": {}}
        with open(langgraph_file, 'w') as f:
            json.dump(existing_data, f)

        monkeypatch.setenv("HOME", str(fake_home))

        from myagents.backend.services.agents.workflows.setup_workflow import SetupWorkflow

        # Execute with overwrite
        workflow = SetupWorkflow()
        success, message = workflow.initialize_langgraph_config(overwrite=True)

        # Check if we actually overwrote (depends on package being installed)
        if success:
            with open(langgraph_file) as f:
                data = json.load(f)
            assert data != existing_data, "Config should be overwritten"
            assert "created" in message.lower()
        else:
            # If failed, it should be due to missing package files, not overwrite logic
            assert "doesn't exist" in message.lower() or "not found" in message.lower()
