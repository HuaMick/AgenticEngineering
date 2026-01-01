"""Core functionality tests for file operations.

Consolidates domain-level and tool-level tests using parametrization.
Tests path validation, tool registration, and core file operations.
"""

import pytest
from pathlib import Path
from myagents.backend.services.agents.domains.file_operations import FileOperations
from myagents.backend.services.agents.tools.file_tools import (
    read_file,
    list_files,
    edit_file,
    search_in_files,
    find_files,
    get_all_tools,
    get_tool_by_name,
    ALL_TOOLS,
    TOOLS_BY_NAME,
)


@pytest.fixture
def file_ops(temp_dir):
    """Create FileOperations instance with temp directory."""
    return FileOperations(allowed_dir=temp_dir)


@pytest.mark.integration
class TestPathValidation:
    """Test path validation for security."""

    @pytest.mark.parametrize("path,expected_filename", [
        ("test.txt", "test.txt"),
        ("subdir/file.txt", "file.txt"),
    ])
    def test_validate_path_accepts_relative_paths(self, file_ops, temp_dir, path, expected_filename):
        """Test that relative paths are accepted."""
        result = file_ops.validate_path(path)
        assert result.name == expected_filename
        assert str(result).startswith(str(temp_dir))

    @pytest.mark.parametrize("invalid_path,error_match", [
        ("/etc/passwd", "Absolute paths not allowed"),
        ("../../etc/passwd", "Path outside allowed directory"),
    ])
    def test_validate_path_rejects_invalid_paths(self, file_ops, invalid_path, error_match):
        """Test that absolute paths and directory traversal are rejected."""
        with pytest.raises(ValueError, match=error_match):
            file_ops.validate_path(invalid_path)

    def test_validate_path_handles_symlinks(self, file_ops, temp_dir):
        """Test that symlinks are resolved and validated."""
        target = temp_dir / "target.txt"
        target.write_text("content")
        link = temp_dir / "link.txt"
        link.symlink_to(target)

        result = file_ops.validate_path("link.txt")
        assert result == temp_dir / "target.txt"


@pytest.mark.integration
class TestFileOperations:
    """Test core file operations (read, list, edit)."""

    @pytest.mark.parametrize("filename,content", [
        ("test1.txt", "Hello, World!"),
        ("test2.txt", "Multiple lines\nLine 2\nLine 3"),
    ])
    def test_read_file_success(self, file_ops, temp_dir, filename, content):
        """Test successful file reading."""
        test_file = temp_dir / filename
        test_file.write_text(content)

        result = file_ops.read_file(filename)
        assert result == content

    @pytest.mark.parametrize("operation,error_type,error_match", [
        ("read_nonexistent", FileNotFoundError, None),
        ("read_large", ValueError, "File too large"),
    ])
    def test_file_operation_errors(self, file_ops, temp_dir, operation, error_type, error_match):
        """Test file operation error handling."""
        if operation == "read_nonexistent":
            with pytest.raises(error_type):
                file_ops.read_file("nonexistent.txt")
        elif operation == "read_large":
            test_file = temp_dir / "large.txt"
            test_file.write_text("x" * 200_000)  # 200KB
            with pytest.raises(error_type, match=error_match):
                file_ops.read_file("large.txt", max_size=100_000)

    def test_list_files_basic(self, file_ops, temp_dir):
        """Test basic directory listing."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / ".hidden").write_text("hidden")

        result = file_ops.list_files(".")
        assert "file1.txt" in result
        assert "file2.txt" in result
        assert ".hidden" not in result  # Hidden files excluded by default

    @pytest.mark.parametrize("include_hidden,expected_count", [
        (False, 1),
        (True, 2),
    ])
    def test_list_files_hidden_handling(self, file_ops, temp_dir, include_hidden, expected_count):
        """Test hidden file inclusion/exclusion."""
        (temp_dir / "visible.txt").write_text("content")
        (temp_dir / ".hidden").write_text("hidden")

        result = file_ops.list_files(".", include_hidden=include_hidden)
        assert len(result) == expected_count

    @pytest.mark.parametrize("old_text,new_text,expected", [
        ("World", "Python", "Hello Python"),
        ("Hello", "Hi", "Hi World"),
    ])
    def test_edit_file_success(self, file_ops, temp_dir, old_text, new_text, expected):
        """Test successful file editing."""
        test_file = temp_dir / "edit.txt"
        test_file.write_text("Hello World")

        result = file_ops.edit_file("edit.txt", old_text, new_text)
        assert "Updated" in result
        assert test_file.read_text() == expected

    def test_edit_file_replaces_only_first_occurrence(self, file_ops, temp_dir):
        """Test that only first occurrence is replaced."""
        test_file = temp_dir / "edit.txt"
        test_file.write_text("Hello Hello World")

        file_ops.edit_file("edit.txt", "Hello", "Hi")
        assert test_file.read_text() == "Hi Hello World"


@pytest.mark.integration
class TestSearchOperations:
    """Test search_in_files and find_files operations."""

    @pytest.mark.parametrize("pattern,expected_matches", [
        ("hello", 2),
        ("goodbye", 1),
        ("notfound", 0),
    ])
    def test_search_in_files(self, file_ops, temp_dir, pattern, expected_matches):
        """Test pattern matching in files."""
        test_file = temp_dir / "search_test.txt"
        test_file.write_text("Line 1: hello world\nLine 2: goodbye\nLine 3: hello again")

        results = file_ops.search_in_files(pattern, ".")
        assert len(results) == expected_matches

    @pytest.mark.parametrize("pattern,expected_count", [
        ("*.txt", 2),
        ("*.py", 1),
        ("*.md", 0),
    ])
    def test_find_files_glob_patterns(self, file_ops, temp_dir, pattern, expected_count):
        """Test glob pattern matching."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "script.py").write_text("content3")

        results = file_ops.find_files(pattern, ".")
        assert len(results) == expected_count

    @pytest.mark.parametrize("operation,invalid_path,error_match", [
        ("search", "/etc", "Absolute paths not allowed"),
        ("search", "../../etc", "Path outside allowed directory"),
        ("find", "/etc", "Absolute paths not allowed"),
        ("find", "../../etc", "Path outside allowed directory"),
    ])
    def test_search_operations_reject_invalid_paths(self, file_ops, operation, invalid_path, error_match):
        """Test that search operations reject invalid paths."""
        with pytest.raises(ValueError, match=error_match):
            if operation == "search":
                file_ops.search_in_files("pattern", invalid_path)
            elif operation == "find":
                file_ops.find_files("*.txt", invalid_path)


@pytest.mark.integration
class TestToolRegistry:
    """Test tool registry and lookup functions."""

    def test_all_tools_complete(self):
        """Test that ALL_TOOLS contains all expected tools."""
        tool_names = [tool.name for tool in ALL_TOOLS]
        expected_tools = ["read_file", "list_files", "edit_file", "create_file", "search_in_files", "find_files"]
        for expected in expected_tools:
            assert expected in tool_names
        assert len(tool_names) == 6

    def test_tools_by_name_mapping(self):
        """Test that TOOLS_BY_NAME provides correct mapping."""
        expected_tools = ["read_file", "list_files", "edit_file", "create_file", "search_in_files", "find_files"]
        for tool_name in expected_tools:
            assert tool_name in TOOLS_BY_NAME
            assert TOOLS_BY_NAME[tool_name].name == tool_name

    def test_get_tool_by_name_success(self):
        """Test retrieving tool by name."""
        tool = get_tool_by_name("read_file")
        assert tool.name == "read_file"

    def test_get_tool_by_name_unknown_tool(self):
        """Test that unknown tool raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            get_tool_by_name("nonexistent_tool")


@pytest.mark.integration
class TestToolDelegation:
    """Test that tools correctly delegate to domain."""

    @pytest.mark.parametrize("tool_name,setup_data,invoke_args", [
        ("read_file", {"file": "test.txt", "content": "Test content"}, {"path": "test.txt"}),
        ("list_files", {"files": ["file1.txt", "file2.txt"]}, {"path": "."}),
    ])
    def test_tool_delegates_to_domain(self, setup_test_env, tool_name, setup_data, invoke_args):
        """Test that tools delegate to domain correctly."""
        # Setup test data
        if "file" in setup_data:
            test_file = setup_test_env / setup_data["file"]
            test_file.write_text(setup_data["content"])
        elif "files" in setup_data:
            for filename in setup_data["files"]:
                (setup_test_env / filename).write_text("content")

        # Invoke tool
        if tool_name == "read_file":
            result = read_file.invoke(invoke_args)
            if "file" in setup_data:
                assert result == setup_data["content"]
        elif tool_name == "list_files":
            result = list_files.invoke(invoke_args)
            if "files" in setup_data:
                for filename in setup_data["files"]:
                    assert filename in result

    def test_edit_file_delegates_to_domain(self, setup_test_env):
        """Test that edit_file tool delegates to domain."""
        test_file = setup_test_env / "edit.txt"
        test_file.write_text("Original text")

        result = edit_file.invoke({
            "path": "edit.txt",
            "old_text": "Original",
            "new_text": "Modified"
        })
        assert "Updated" in result
        assert test_file.read_text() == "Modified text"

    @pytest.mark.parametrize("tool_func,invoke_args,error_type,error_match", [
        (read_file, {"path": "nonexistent.txt"}, FileNotFoundError, None),
        (edit_file, {"path": "test.txt", "old_text": "missing", "new_text": "new"}, ValueError, "Text not found"),
    ])
    def test_tool_propagates_errors(self, setup_test_env, tool_func, invoke_args, error_type, error_match):
        """Test that domain errors are propagated through tool layer."""
        if tool_func == edit_file and error_match == "Text not found":
            test_file = setup_test_env / "test.txt"
            test_file.write_text("content")

        with pytest.raises(error_type, match=error_match):
            tool_func.invoke(invoke_args)

    @pytest.mark.parametrize("operation,pattern,has_matches", [
        ("search", "hello", True),
        ("search", "notfound", False),
        ("find", "*.txt", True),
        ("find", "*.py", False),
    ])
    def test_search_tools_return_formatted_strings(self, setup_test_env, operation, pattern, has_matches):
        """Test that search tools return formatted string output."""
        if operation == "search":
            test_file = setup_test_env / "search.txt"
            test_file.write_text("Line 1: hello world\nLine 2: goodbye")
            result = search_in_files.invoke({"pattern": pattern, "directory": "."})
        else:  # find
            (setup_test_env / "file1.txt").write_text("content1")
            (setup_test_env / "file2.txt").write_text("content2")
            result = find_files.invoke({"name_pattern": pattern, "directory": "."})

        assert isinstance(result, str)
        if has_matches:
            assert len(result) > 0
            if operation == "search":
                assert pattern in result.lower()
        else:
            assert "No" in result


