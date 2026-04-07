"""Tests for console output utilities."""

import json

import pytest

pytestmark = pytest.mark.story("US-SET-001")


class TestJsonOutputMode:
    """Tests for JSON output mode."""

    def test_set_json_output(self):
        """Test enabling JSON output mode."""
        from agenticcli.console import is_json_output, set_json_output

        set_json_output(True)
        assert is_json_output() is True

        set_json_output(False)
        assert is_json_output() is False

    def test_print_json(self, capsys):
        """Test print_json outputs valid JSON."""
        from agenticcli.console import print_json

        data = {"key": "value", "number": 42}
        print_json(data)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == data

    def test_print_json_with_complex_types(self, capsys):
        """Test print_json handles complex types."""
        from pathlib import Path

        from agenticcli.console import print_json

        data = {"path": Path("/some/path")}
        print_json(data)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["path"] == "/some/path"


class TestPrintFunctions:
    """Tests for print helper functions."""

    def test_print_success_normal_mode(self, capsys):
        """Test print_success in normal mode."""
        from agenticcli.console import print_success, set_json_output

        set_json_output(False)
        print_success("Operation completed")

        captured = capsys.readouterr()
        assert "Operation completed" in captured.out

    def test_print_success_json_mode(self, capsys):
        """Test print_success is silent in JSON mode."""
        from agenticcli.console import print_success, set_json_output

        set_json_output(True)
        print_success("Operation completed")

        captured = capsys.readouterr()
        assert captured.out == ""
        set_json_output(False)

    def test_print_error_normal_mode(self, capsys):
        """Test print_error in normal mode."""
        from agenticcli.console import print_error, set_json_output

        set_json_output(False)
        print_error("Something went wrong")

        captured = capsys.readouterr()
        assert "Something went wrong" in captured.err

    def test_print_error_json_mode(self, capsys):
        """Test print_error outputs JSON in JSON mode."""
        from agenticcli.console import print_error, set_json_output

        set_json_output(True)
        print_error("Something went wrong")

        captured = capsys.readouterr()
        data = json.loads(captured.err)
        assert data["error"] == "Something went wrong"
        set_json_output(False)

    def test_print_warning_normal_mode(self, capsys):
        """Test print_warning in normal mode."""
        from agenticcli.console import print_warning, set_json_output

        set_json_output(False)
        print_warning("Be careful")

        captured = capsys.readouterr()
        assert "Be careful" in captured.out

    def test_print_warning_json_mode(self, capsys):
        """Test print_warning is silent in JSON mode."""
        from agenticcli.console import print_warning, set_json_output

        set_json_output(True)
        print_warning("Be careful")

        captured = capsys.readouterr()
        assert captured.out == ""
        set_json_output(False)

    def test_print_info_normal_mode(self, capsys):
        """Test print_info in normal mode."""
        from agenticcli.console import print_info, set_json_output

        set_json_output(False)
        print_info("Here is some info")

        captured = capsys.readouterr()
        assert "Here is some info" in captured.out

    def test_print_header_normal_mode(self, capsys):
        """Test print_header in normal mode."""
        from agenticcli.console import print_header, set_json_output

        set_json_output(False)
        print_header("My Header")

        captured = capsys.readouterr()
        assert "My Header" in captured.out


class TestFormatStatus:
    """Tests for format_status function."""

    def test_format_completed(self):
        """Test formatting completed status."""
        from agenticcli.console import format_status

        result = format_status("completed")
        assert "completed" in result
        assert "green" in result

    def test_format_in_progress(self):
        """Test formatting in_progress status."""
        from agenticcli.console import format_status

        result = format_status("in_progress")
        assert "in_progress" in result
        assert "yellow" in result

    def test_format_pending_normalizes_to_planning(self):
        """Test formatting pending status normalizes to planning."""
        from agenticcli.console import format_status

        result = format_status("pending")
        assert "planning" in result
        assert "blue" in result

    def test_format_proposed(self):
        """Test formatting proposed status maps to dim proposed."""
        from agenticcli.console import format_status

        result = format_status("proposed")
        assert "proposed" in result
        assert "dim" in result

    def test_format_failed(self):
        """Test formatting failed status."""
        from agenticcli.console import format_status

        result = format_status("failed")
        assert "failed" in result
        assert "red" in result

    def test_format_active_normalizes_to_planning(self):
        """Test formatting active status normalizes to planning."""
        from agenticcli.console import format_status

        result = format_status("active")
        assert "planning" in result
        assert "blue" in result

    def test_format_planning(self):
        """Test formatting planning status."""
        from agenticcli.console import format_status

        result = format_status("planning")
        assert "planning" in result
        assert "blue" in result

    def test_format_deferred(self):
        """Test formatting deferred status."""
        from agenticcli.console import format_status

        result = format_status("deferred")
        assert "deferred" in result
        assert "dim" in result

    def test_format_blocked(self):
        """Test formatting blocked status."""
        from agenticcli.console import format_status

        result = format_status("blocked")
        assert "blocked" in result
        assert "red" in result

    def test_format_approved_normalizes_to_in_progress(self):
        """Test formatting approved legacy status normalizes to in_progress."""
        from agenticcli.console import format_status

        result = format_status("approved")
        assert "in_progress" in result
        assert "yellow" in result

    def test_format_unknown(self):
        """Test formatting unknown status."""
        from agenticcli.console import format_status

        result = format_status("unknown_status")
        assert result == "unknown_status"


class TestPrintTable:
    """Tests for print_table function."""

    def test_print_table_normal_mode(self, capsys):
        """Test print_table in normal mode."""
        from agenticcli.console import print_table, set_json_output

        set_json_output(False)
        print_table("Test Table", ["Col1", "Col2"], [["a", "b"], ["c", "d"]])

        captured = capsys.readouterr()
        # Rich table output contains the data
        assert "Col1" in captured.out or "a" in captured.out

    def test_print_table_json_mode(self, capsys):
        """Test print_table outputs JSON in JSON mode."""
        from agenticcli.console import print_table, set_json_output

        set_json_output(True)
        print_table("Test Table", ["Col1", "Col2"], [["a", "b"], ["c", "d"]])

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 2
        assert data[0]["Col1"] == "a"
        set_json_output(False)


class TestPrintKeyValue:
    """Tests for print_key_value function."""

    def test_print_key_value_normal_mode(self, capsys):
        """Test print_key_value in normal mode."""
        from agenticcli.console import print_key_value, set_json_output

        set_json_output(False)
        print_key_value("Name", "Value")

        captured = capsys.readouterr()
        assert "Name" in captured.out
        assert "Value" in captured.out

    def test_print_key_value_with_indent(self, capsys):
        """Test print_key_value with indentation."""
        from agenticcli.console import print_key_value, set_json_output

        set_json_output(False)
        print_key_value("Key", "Val", indent=2)

        captured = capsys.readouterr()
        assert "Key" in captured.out
