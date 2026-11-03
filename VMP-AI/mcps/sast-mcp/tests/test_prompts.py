"""Tests for MCP Prompts."""

from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP

from sast_mcp_server.prompts import register_prompts


@pytest.fixture
def mock_mcp():
    mcp = MagicMock(spec=FastMCP)
    mcp.prompt = MagicMock(return_value=lambda f: f)
    return mcp


def test_register_prompts(mock_mcp):
    register_prompts(mock_mcp)

    assert mock_mcp.prompt.call_count == 4
