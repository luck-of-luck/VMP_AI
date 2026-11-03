"""Unit tests for utils/tool_context.py — shared error handling backbone."""

import time
from unittest.mock import patch

import pytest

from ast_grep_mcp.utils.tool_context import ToolRun, async_tool_context, tool_context


class TestToolContext:
    """Tests for the synchronous tool_context context manager."""

    def test_yields_tool_run_with_start_time(self) -> None:
        before = time.time()
        with tool_context("test_tool") as run:
            after = time.time()
        assert isinstance(run, ToolRun)
        assert before <= run.start_time <= after

    def test_logs_tool_completed_on_success(self) -> None:
        with patch("ast_grep_mcp.utils.tool_context.get_logger") as mock_get:
            mock_logger = mock_get.return_value
            with tool_context("my_tool"):
                pass
            mock_logger.info.assert_called_once()
            args, kwargs = mock_logger.info.call_args
            assert args[0] == "tool_completed"
            assert kwargs["tool"] == "my_tool"
            assert kwargs["status"] == "success"
            assert "execution_time_seconds" in kwargs

    def test_completion_fields_included_in_log(self) -> None:
        with patch("ast_grep_mcp.utils.tool_context.get_logger") as mock_get:
            mock_logger = mock_get.return_value
            with tool_context("my_tool") as run:
                run.add_completion_fields(items_found=3, filtered=True)
            kwargs = mock_logger.info.call_args[1]
            assert kwargs["items_found"] == 3
            assert kwargs["filtered"] is True

    def test_no_tool_completed_log_on_error(self) -> None:
        with patch("ast_grep_mcp.utils.tool_context.get_logger") as mock_get:
            mock_logger = mock_get.return_value
            with patch("ast_grep_mcp.utils.tool_context.sentry_sdk.capture_exception"):
                with pytest.raises(ValueError):
                    with tool_context("my_tool"):
                        raise ValueError("x")
            mock_logger.info.assert_not_called()

    def test_reraises_exception(self) -> None:
        with pytest.raises(ValueError, match="boom"):
            with tool_context("test_tool"):
                raise ValueError("boom")

    @patch("ast_grep_mcp.utils.tool_context.sentry_sdk.capture_exception")
    def test_captures_to_sentry_on_error(self, mock_capture: object) -> None:
        exc = RuntimeError("fail")
        with pytest.raises(RuntimeError):
            with tool_context("my_tool", folder="/tmp"):
                raise exc
        mock_capture.assert_called_once()  # type: ignore[union-attr]
        call_kwargs = mock_capture.call_args  # type: ignore[union-attr]
        assert call_kwargs[0][0] is exc
        extras = call_kwargs[1]["extras"]
        assert extras["tool"] == "my_tool"
        assert extras["folder"] == "/tmp"
        assert "execution_time_seconds" in extras

    @patch("ast_grep_mcp.utils.tool_context.sentry_sdk.capture_exception")
    def test_no_sentry_on_success(self, mock_capture: object) -> None:
        with tool_context("test_tool"):
            pass
        mock_capture.assert_not_called()  # type: ignore[union-attr]

    def test_logs_status_failed(self) -> None:
        with patch("ast_grep_mcp.utils.tool_context.get_logger") as mock_get:
            mock_logger = mock_get.return_value
            with pytest.raises(ValueError):
                with tool_context("my_tool"):
                    raise ValueError("x")
            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args[1]
            assert call_kwargs["status"] == "failed"
            assert call_kwargs["tool"] == "my_tool"


class TestAsyncToolContext:
    """Tests for the async variant."""

    @pytest.mark.asyncio
    async def test_yields_tool_run_with_start_time(self) -> None:
        before = time.time()
        async with async_tool_context("test_tool") as run:
            after = time.time()
        assert isinstance(run, ToolRun)
        assert before <= run.start_time <= after

    @pytest.mark.asyncio
    async def test_logs_tool_completed_on_success(self) -> None:
        with patch("ast_grep_mcp.utils.tool_context.get_logger") as mock_get:
            mock_logger = mock_get.return_value
            async with async_tool_context("my_tool") as run:
                run.add_completion_fields(result_count=2)
            mock_logger.info.assert_called_once()
            args, kwargs = mock_logger.info.call_args
            assert args[0] == "tool_completed"
            assert kwargs["tool"] == "my_tool"
            assert kwargs["status"] == "success"
            assert kwargs["result_count"] == 2

    @pytest.mark.asyncio
    async def test_reraises_exception(self) -> None:
        with pytest.raises(ValueError, match="boom"):
            async with async_tool_context("test_tool"):
                raise ValueError("boom")

    def test_handle_tool_error_uses_provided_logger(self) -> None:
        """_handle_tool_error uses caller-supplied logger instead of creating one."""
        from unittest.mock import MagicMock

        from ast_grep_mcp.utils.tool_context import _handle_tool_error

        custom_logger = MagicMock()
        with patch("ast_grep_mcp.utils.tool_context.sentry_sdk.capture_exception"):
            with patch("ast_grep_mcp.utils.tool_context.get_logger") as mock_get:
                _handle_tool_error("my_tool", time.time(), RuntimeError("x"), {}, logger=custom_logger)
                mock_get.assert_not_called()
                custom_logger.error.assert_called_once()

    def test_handle_tool_error_creates_logger_when_none(self) -> None:
        """_handle_tool_error creates logger when none provided."""
        from ast_grep_mcp.utils.tool_context import _handle_tool_error

        with patch("ast_grep_mcp.utils.tool_context.sentry_sdk.capture_exception"):
            with patch("ast_grep_mcp.utils.tool_context.get_logger") as mock_get:
                mock_get.return_value.error = lambda *a, **kw: None
                _handle_tool_error("my_tool", time.time(), RuntimeError("x"), {})
                mock_get.assert_called_once_with("tool.my_tool")

    @pytest.mark.asyncio
    @patch("ast_grep_mcp.utils.tool_context.sentry_sdk.capture_exception")
    async def test_captures_to_sentry_on_error(self, mock_capture: object) -> None:
        exc = RuntimeError("fail")
        with pytest.raises(RuntimeError):
            async with async_tool_context("my_tool", input_type="file"):
                raise exc
        mock_capture.assert_called_once()  # type: ignore[union-attr]
        extras = mock_capture.call_args[1]["extras"]  # type: ignore[union-attr]
        assert extras["tool"] == "my_tool"
        assert extras["input_type"] == "file"
