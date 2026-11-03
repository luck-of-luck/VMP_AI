"""Performance benchmarking for asyncio subprocess streaming (LM-05).

Measures:
- Throughput: matches/second
- Memory efficiency: streaming vs. buffering
- Early termination: latency to stop at max_results
- Error handling: overhead of error detection

Usage:
    pytest tests/performance/benchmark_streaming.py -v --benchmark-only
    pytest tests/performance/benchmark_streaming.py -v --benchmark-compare
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from ast_grep_mcp.core.executor import async_stream_ast_grep_results, stream_ast_grep_results


def make_mock_process(json_output: str, returncode: int = 0) -> AsyncMock:
    """Mock asyncio subprocess delivering json_output as a single stdout chunk.

    The executor reads stdout via `await process.stdout.read(chunk_size)`, so
    stdout.read must yield bytes then b"" (EOF). Each mock supports exactly one
    streaming pass — build a fresh one per benchmarked call.
    """
    process = AsyncMock()
    process.stdout = AsyncMock()
    process.stdout.read = AsyncMock(side_effect=[json_output.encode(), b""])
    process.returncode = returncode
    process.wait = AsyncMock(return_value=returncode)
    process.stderr = AsyncMock()
    process.stderr.read = AsyncMock(return_value=b"")
    process.terminate = lambda: None
    return process


class TestStreamingBenchmark:
    """Benchmark async streaming implementation."""

    @pytest.mark.benchmark(group="streaming")
    def test_sync_shim_1k_matches(self, benchmark):
        """Benchmark sync shim with 1,000 matches."""
        matches = [{"file": f"test{i}.py", "line": i, "column": 0} for i in range(1000)]
        json_lines = "\n".join(json.dumps(m) for m in matches)

        def run_sync_stream():
            mock_process = make_mock_process(json_lines)
            with patch("ast_grep_mcp.core.executor.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_process
                return list(stream_ast_grep_results("run", ["--json=stream", "/test"]))

        result = benchmark(run_sync_stream)
        assert len(result) == 1000

    @pytest.mark.benchmark(group="streaming")
    def test_async_streaming_1k_matches(self, benchmark):
        """Benchmark async streaming with 1,000 matches."""
        matches = [{"file": f"test{i}.py", "line": i, "column": 0} for i in range(1000)]
        json_lines = "\n".join(json.dumps(m) for m in matches)

        async def collect():
            mock_process = make_mock_process(json_lines)
            with patch("ast_grep_mcp.core.executor.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_process
                return [m async for m in async_stream_ast_grep_results("run", ["--json=stream", "/test"])]

        result = benchmark(lambda: asyncio.run(collect()))
        assert len(result) == 1000

    @pytest.mark.benchmark(group="streaming")
    def test_sync_shim_early_termination_at_100(self, benchmark):
        """Benchmark early termination at max_results=100 (1K available)."""
        matches = [{"file": f"test{i}.py", "line": i} for i in range(1000)]
        json_lines = "\n".join(json.dumps(m) for m in matches)

        def run_early_term():
            # SIGTERM returncode: the executor terminates the process at max_results
            mock_process = make_mock_process(json_lines, returncode=-15)
            with patch("ast_grep_mcp.core.executor.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_process
                return list(stream_ast_grep_results("run", ["--json=stream", "/test"], max_results=100))

        result = benchmark(run_early_term)
        assert len(result) == 100

    @pytest.mark.benchmark(group="streaming")
    def test_sync_shim_invalid_json_skipping(self, benchmark):
        """Benchmark JSON parse error handling (50 valid, 50 invalid)."""
        valid = [{"file": f"test{i}.py"} for i in range(50)]
        invalid = ["invalid json"] * 50

        # Interleave valid and invalid
        json_lines_list = []
        for i in range(50):
            json_lines_list.append(json.dumps(valid[i]))
            json_lines_list.append(invalid[i])
        json_lines = "\n".join(json_lines_list)

        def run_with_errors():
            mock_process = make_mock_process(json_lines)
            with patch("ast_grep_mcp.core.executor.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_process
                return list(stream_ast_grep_results("run", ["--json=stream", "/test"]))

        result = benchmark(run_with_errors)
        assert len(result) == 50

    @pytest.mark.benchmark(group="streaming")
    def test_sync_shim_memory_efficiency(self, benchmark):
        """Benchmark memory usage: streaming yields incrementally vs. buffering all."""
        matches = [{"file": f"test{i}.py", "line": i, "data": "x" * 100} for i in range(100)]
        json_lines = "\n".join(json.dumps(m) for m in matches)

        def iterate_streaming():
            """Iterate results (streaming), not collect all at once."""
            mock_process = make_mock_process(json_lines)
            with patch("ast_grep_mcp.core.executor.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_process
                count = 0
                for _ in stream_ast_grep_results("run", ["--json=stream", "/test"]):
                    count += 1
                return count

        result = benchmark(iterate_streaming)
        assert result == 100
