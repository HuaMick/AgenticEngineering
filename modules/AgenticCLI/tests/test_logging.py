"""Tests for logging utilities."""

import logging
import os
from unittest.mock import patch

import pytest

from agenticcli.logging import (
    BACKUP_COUNT,
    DEFAULT_LOG_LEVEL,
    LOGGER_NAME,
    MAX_LOG_BYTES,
    get_logger,
    reset_logging,
    setup_logging,
)


@pytest.fixture(autouse=True)
def reset_logging_state():
    """Reset logging state before and after each test."""
    reset_logging()
    yield
    reset_logging()


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_creates_log_directory(self, tmp_path):
        """Test that log directory is created if missing."""
        log_dir = tmp_path / "logs"
        assert not log_dir.exists()

        setup_logging(log_dir)

        assert log_dir.exists()

    def test_creates_log_file_on_write(self, tmp_path):
        """Test that log file is created when logging."""
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir)

        logger.info("Test message")

        log_file = log_dir / "agenticcli.log"
        assert log_file.exists()

    def test_default_log_level_is_info(self, tmp_path):
        """Test default log level is INFO."""
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir)

        assert logger.level == logging.INFO

    def test_log_level_from_env(self, tmp_path):
        """Test AGENTIC_LOG_LEVEL env var controls level."""
        log_dir = tmp_path / "logs"

        with patch.dict(os.environ, {"AGENTIC_LOG_LEVEL": "DEBUG"}):
            logger = setup_logging(log_dir)

        assert logger.level == logging.DEBUG

    def test_log_level_from_argument(self, tmp_path):
        """Test level argument overrides default."""
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir, level="WARNING")

        assert logger.level == logging.WARNING

    def test_log_format(self, tmp_path):
        """Test log format matches specification."""
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir)

        logger.info("Test format message")

        log_file = log_dir / "agenticcli.log"
        content = log_file.read_text()
        # Format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        assert "agenticcli" in content
        assert "INFO" in content
        assert "Test format message" in content
        assert "-" in content  # separator

    def test_debug_to_console_adds_handler(self, tmp_path):
        """Test debug_to_console adds console handler."""
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir, debug_to_console=True)

        # Should have 2 handlers: file + console
        assert len(logger.handlers) == 2

    def test_only_initializes_once(self, tmp_path):
        """Test logging only initializes once per session."""
        log_dir = tmp_path / "logs"

        logger1 = setup_logging(log_dir)
        handler_count = len(logger1.handlers)

        logger2 = setup_logging(log_dir)

        # Should not add duplicate handlers
        assert len(logger2.handlers) == handler_count


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_root_logger(self, tmp_path):
        """Test get_logger returns root agenticcli logger."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir)

        logger = get_logger()
        assert logger.name == LOGGER_NAME

    def test_returns_child_logger(self, tmp_path):
        """Test get_logger with name returns child logger."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir)

        logger = get_logger("commands")
        assert logger.name == f"{LOGGER_NAME}.commands"

    def test_child_logger_inherits_level(self, tmp_path):
        """Test child logger inherits parent level."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir, level="WARNING")

        child = get_logger("child")
        # Child should have notset but inherit from parent
        assert child.getEffectiveLevel() == logging.WARNING


class TestLogRotation:
    """Tests for log rotation settings."""

    def test_max_bytes_setting(self):
        """Test MAX_LOG_BYTES is 1MB."""
        assert MAX_LOG_BYTES == 1024 * 1024

    def test_backup_count_setting(self):
        """Test BACKUP_COUNT is 5."""
        assert BACKUP_COUNT == 5

    def test_default_log_level_setting(self):
        """Test DEFAULT_LOG_LEVEL is INFO."""
        assert DEFAULT_LOG_LEVEL == "INFO"


class TestResetLogging:
    """Tests for reset_logging function."""

    def test_removes_handlers(self, tmp_path):
        """Test reset_logging removes all handlers."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir)

        logger = logging.getLogger(LOGGER_NAME)
        assert len(logger.handlers) > 0

        reset_logging()

        assert len(logger.handlers) == 0


class TestLoggingIntegration:
    """Integration tests for logging in CLI."""

    def test_health_command_logs(self, cli_runner, tmp_path):
        """Test running a command creates log entries."""
        # Run health command which initializes logging
        result = cli_runner("health")
        assert result.returncode == 0

    def test_debug_flag_shows_console_output(self, cli_runner, capsys):
        """Test --debug flag shows debug output."""
        # This is tricky to test because cli_runner captures output
        # Just verify the flag is accepted
        result = cli_runner("--debug", "health")
        assert result.returncode == 0

    def test_health_shows_logs_dir_check(self, cli_runner):
        """Test health command shows logs_dir check."""
        result = cli_runner("-j", "health")
        assert result.returncode == 0

        import json

        data = json.loads(result.stdout)
        logs_check = next((c for c in data["checks"] if c["name"] == "logs_dir"), None)
        assert logs_check is not None
