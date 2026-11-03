"""Tests for enrichment modules: AST context, git diff, ignore manager."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from sast_mcp_server.enrichment.ast_context import get_function_context
from sast_mcp_server.enrichment.git_diff import get_modified_files
from sast_mcp_server.enrichment.ignore_manager import IgnoreManager

FIXTURES = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------------
# AST Context Tests
# --------------------------------------------------------------------------
class TestAstContext:
    def test_python_function_context(self):
        """Test that Python AST correctly extracts enclosing function."""
        file_path = str(FIXTURES / "test_target.py")
        snippet, start, end = get_function_context(file_path, 3)

        assert "def process_data" in snippet
        assert start == 1  # Function starts at line 1
        assert end >= 3    # Should include line 3

    def test_python_function_outside_function(self):
        """Test fallback for lines not inside a function."""
        file_path = str(FIXTURES / "test_target.py")
        # Line 10 is in 'if __name__' block, not in a function
        snippet, start, end = get_function_context(file_path, 10)

        # Should get ±10 lines fallback
        assert len(snippet) > 0

    def test_nonexistent_file(self):
        """Test graceful handling of missing files."""
        snippet, start, end = get_function_context("/nonexistent/file.py", 5)

        assert snippet == "File not found."
        assert start == 5
        assert end == 5

    def test_javascript_fallback(self):
        """Test that JS files get some context even without tree-sitter."""
        file_path = str(FIXTURES / "vulnerable_app.js")
        snippet, start, end = get_function_context(file_path, 7)

        # Should return something (either tree-sitter or ±10 line fallback)
        assert len(snippet) > 0
        assert "eval" in snippet


# --------------------------------------------------------------------------
# Git Diff Tests
# --------------------------------------------------------------------------
class TestGitDiff:
    @pytest.mark.asyncio
    async def test_get_modified_files(self):
        """Test parsing of git diff output."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"file1.py\nfile2.js\n", b"")
        )
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            files = await get_modified_files("/some/path")

        assert files == {"file1.py", "file2.js"}

    @pytest.mark.asyncio
    async def test_empty_diff(self):
        """Test handling of empty git diff."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            files = await get_modified_files("/some/path")

        assert files == set()

    @pytest.mark.asyncio
    async def test_git_not_available(self):
        """Test handling when git is not installed."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("git not found"),
        ):
            files = await get_modified_files("/some/path")

        assert files == set()

    @pytest.mark.asyncio
    async def test_not_a_git_repo(self):
        """Test handling when directory is not a git repo."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"fatal: not a git repository")
        )
        mock_proc.returncode = 128

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            files = await get_modified_files("/some/path")

        assert files == set()


# --------------------------------------------------------------------------
# Ignore Manager Tests
# --------------------------------------------------------------------------
class TestIgnoreManager:
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_ignore_and_check(self, temp_dir):
        """Test basic ignore and is_ignored functionality."""
        mgr = IgnoreManager(temp_dir)
        assert not mgr.is_ignored("abc123")

        mgr.ignore("abc123", "false positive")
        assert mgr.is_ignored("abc123")

    def test_persistence(self, temp_dir):
        """Test that ignores persist across instances."""
        mgr1 = IgnoreManager(temp_dir)
        mgr1.ignore("abc123", "test reason")

        # Create new instance — should load from disk
        mgr2 = IgnoreManager(temp_dir)
        assert mgr2.is_ignored("abc123")

    def test_unignore(self, temp_dir):
        """Test removing a finding from the ignore list."""
        mgr = IgnoreManager(temp_dir)
        mgr.ignore("abc123", "will be removed")
        assert mgr.is_ignored("abc123")

        result = mgr.unignore("abc123")
        assert result is True
        assert not mgr.is_ignored("abc123")

    def test_unignore_nonexistent(self, temp_dir):
        """Test unignoring a hash that doesn't exist."""
        mgr = IgnoreManager(temp_dir)
        result = mgr.unignore("nonexistent")
        assert result is False

    def test_list_ignored(self, temp_dir):
        """Test listing all ignored findings."""
        mgr = IgnoreManager(temp_dir)
        mgr.ignore("hash1", "reason 1")
        mgr.ignore("hash2", "reason 2")

        ignored = mgr.list_ignored()
        assert len(ignored) == 2
        hashes = {entry["hash"] for entry in ignored}
        assert hashes == {"hash1", "hash2"}

    def test_timestamp_recorded(self, temp_dir):
        """Test that ignore timestamp is recorded."""
        mgr = IgnoreManager(temp_dir)
        mgr.ignore("abc123", "test")

        ignored = mgr.list_ignored()
        assert ignored[0]["ignored_at"] != "unknown"

    def test_backward_compatible_format(self, temp_dir):
        """Test loading old-format ignore files (hash -> reason string)."""
        ignore_file = os.path.join(temp_dir, ".sast-mcp-ignore.json")
        old_format = {"hash1": "old reason", "hash2": "another reason"}
        with open(ignore_file, "w") as f:
            json.dump(old_format, f)

        mgr = IgnoreManager(temp_dir)
        assert mgr.is_ignored("hash1")
        assert mgr.is_ignored("hash2")

    def test_corrupt_ignore_file(self, temp_dir):
        """Test handling of corrupt ignore file."""
        ignore_file = os.path.join(temp_dir, ".sast-mcp-ignore.json")
        with open(ignore_file, "w") as f:
            f.write("not valid json{{{")

        # Should not raise, just start with empty
        mgr = IgnoreManager(temp_dir)
        assert not mgr.is_ignored("anything")
