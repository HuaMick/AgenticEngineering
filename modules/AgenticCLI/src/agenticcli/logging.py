"""Logging utilities for AgenticCLI.

Provides centralized logging with rotation, level management, and diagnostics.
Logs are stored in ~/.config/agenticcli/logs/.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Logger name for all AgenticCLI loggers
LOGGER_NAME = "agenticcli"

# Default log settings
DEFAULT_LOG_LEVEL = "INFO"
MAX_LOG_BYTES = 1024 * 1024  # 1MB
BACKUP_COUNT = 5

# Flag to track if logging has been initialized
_logging_initialized = False


def setup_logging(
    log_dir: Path,
    level: str | None = None,
    debug_to_console: bool = False,
) -> logging.Logger:
    """Configure application logging with rotation.

    Args:
        log_dir: Directory to store log files.
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to AGENTIC_LOG_LEVEL env var or INFO.
        debug_to_console: If True, also log to console at DEBUG level.

    Returns:
        Configured root logger for AgenticCLI.
    """
    global _logging_initialized

    # Determine log level from env or argument
    level = level or os.environ.get("AGENTIC_LOG_LEVEL", DEFAULT_LOG_LEVEL)
    level_int = getattr(logging, level.upper(), logging.INFO)

    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agenticcli.log"

    # Get or create root logger
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level_int)

    # Only add handlers once
    if not _logging_initialized:
        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
        )
        file_handler.setLevel(level_int)
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Optional console handler for debug mode
        if debug_to_console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.DEBUG)
            console_formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        _logging_initialized = True

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Optional logger name suffix. If provided, returns a child logger
              of the main agenticcli logger.

    Returns:
        Logger instance.
    """
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logging.getLogger(LOGGER_NAME)


def reset_logging():
    """Reset logging state. Primarily for testing."""
    global _logging_initialized
    logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    _logging_initialized = False
