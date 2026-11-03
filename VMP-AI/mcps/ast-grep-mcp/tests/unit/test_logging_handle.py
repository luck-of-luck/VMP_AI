"""Tests for configure_logging file handle management."""

import tempfile
from pathlib import Path

import pytest
import structlog

import ast_grep_mcp.core.logging as logging_mod
from ast_grep_mcp.core.logging import configure_logging


@pytest.fixture(autouse=True)
def _reset_logging():
    """Reset module-level handle and structlog config after each test."""
    yield
    if logging_mod._log_file_handle is not None:
        logging_mod._log_file_handle.close()
        logging_mod._log_file_handle = None
    structlog.reset_defaults()


class TestConfigureLoggingFileHandle:
    """Test that file handles are properly managed across calls."""

    def test_stderr_default_no_file_handle(self):
        configure_logging(log_level="INFO", log_file=None)
        assert logging_mod._log_file_handle is None

    def test_file_log_creates_handle(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            path = f.name
        configure_logging(log_level="INFO", log_file=path)
        assert logging_mod._log_file_handle is not None
        assert not logging_mod._log_file_handle.closed
        Path(path).unlink(missing_ok=True)

    def test_repeated_calls_close_previous_handle(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f1:
            path1 = f1.name
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f2:
            path2 = f2.name

        configure_logging(log_level="INFO", log_file=path1)
        first_handle = logging_mod._log_file_handle

        configure_logging(log_level="INFO", log_file=path2)
        assert first_handle.closed
        assert not logging_mod._log_file_handle.closed

        Path(path1).unlink(missing_ok=True)
        Path(path2).unlink(missing_ok=True)

    def test_switch_from_file_to_stderr_keeps_handle(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            path = f.name
        configure_logging(log_level="INFO", log_file=path)
        assert logging_mod._log_file_handle is not None

        # Switch to stderr — file handle remains (not closed by None path)
        configure_logging(log_level="INFO", log_file=None)
        assert logging_mod._log_file_handle is not None
        Path(path).unlink(missing_ok=True)
