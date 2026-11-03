"""Tests for condense estimator (non-destructive reduction estimation)."""

import tempfile
from pathlib import Path

from ast_grep_mcp.features.condense.estimator import (
    _collect_files,
    _language_to_extensions,
    _rank_reduction_candidates,
    estimate_condensation_impl,
)


class TestEstimateCondensationImpl:
    def test_nonexistent_path_returns_error(self):
        result = estimate_condensation_impl("/nonexistent/path/xyz")
        assert "error" in result
        assert result["total_files"] == 0

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = estimate_condensation_impl(tmp)
        assert result["total_files"] == 0
        assert result["total_bytes"] == 0

    def test_single_python_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "module.py"
            fp.write_text("def foo():\n    return 42\n")
            result = estimate_condensation_impl(tmp, language="python")
        assert result["total_files"] == 1
        assert result["total_bytes"] > 0
        assert "ai_chat" in result["estimated_condensed_bytes"]
        assert "ai_analysis" in result["estimated_condensed_bytes"]
        assert result["estimated_condensed_bytes"]["ai_chat"] < result["total_bytes"]

    def test_multiple_strategies_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("x = 1\n")
            result = estimate_condensation_impl(tmp)
        strategies = set(result["estimated_condensed_bytes"].keys())
        assert strategies == {"ai_chat", "ai_analysis", "archival", "polyglot"}

    def test_token_estimates_proportional(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("def foo(): pass\n" * 50)
            result = estimate_condensation_impl(tmp)
        # ai_chat should produce fewest tokens
        tokens = result["estimated_tokens"]
        assert tokens["ai_chat"] < tokens["ai_analysis"]
        assert tokens["ai_analysis"] < tokens["archival"]

    def test_top_candidates_limited(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(15):
                (Path(tmp) / f"m{i}.py").write_text(f"# module {i}\n" * (i + 1))
            result = estimate_condensation_impl(tmp)
        assert len(result["top_reduction_candidates"]) <= 10

    def test_language_filter_excludes_other_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("x = 1\n")
            (Path(tmp) / "b.ts").write_text("const x = 1;\n")
            result_py = estimate_condensation_impl(tmp, language="python")
            result_ts = estimate_condensation_impl(tmp, language="typescript")
        assert result_py["total_files"] == 1
        assert result_ts["total_files"] == 1

    def test_large_file_skipped(self):
        from ast_grep_mcp.constants import CondenseDefaults

        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "big.py"
            fp.write_bytes(b"x = 1\n" * (CondenseDefaults.MAX_FILE_SIZE_BYTES // 6 + 1))
            result = estimate_condensation_impl(tmp)
        assert result["total_files"] == 0


class TestCollectFiles:
    def test_skips_image_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "logo.png").write_bytes(b"\x89PNG")
            (Path(tmp) / "main.py").write_text("pass\n")
            files = _collect_files(Path(tmp), None)
        names = [f.name for f in files]
        assert "logo.png" not in names
        assert "main.py" in names

    def test_language_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("pass\n")
            (Path(tmp) / "b.go").write_text("package main\n")
            files = _collect_files(Path(tmp), "python")
        assert all(f.suffix == ".py" for f in files)


class TestLanguageToExtensions:
    def test_python(self):
        exts = _language_to_extensions("python")
        assert ".py" in exts

    def test_typescript(self):
        exts = _language_to_extensions("typescript")
        assert ".ts" in exts
        assert ".tsx" in exts

    def test_unknown_falls_back_to_code_extensions(self):
        from ast_grep_mcp.constants import CondenseFileRouting

        exts = _language_to_extensions("cobol")
        assert exts == CondenseFileRouting.CODE_EXTENSIONS


class TestRankReductionCandidates:
    def test_empty_returns_empty(self):
        assert _rank_reduction_candidates([]) == []

    def test_returns_sorted_by_lines(self):
        stats = [
            {"file": "a.py", "lines": 10, "bytes": 100},
            {"file": "b.py", "lines": 50, "bytes": 500},
            {"file": "c.py", "lines": 5, "bytes": 50},
        ]
        result = _rank_reduction_candidates(stats)
        assert result[0]["file"] == "b.py"
        assert result[0]["lines"] == 50

    def test_reducible_pct_sums_to_100(self):
        stats = [{"file": f"{i}.py", "lines": 10, "bytes": 100} for i in range(5)]
        result = _rank_reduction_candidates(stats)
        total_pct = sum(r["reducible_pct"] for r in result)
        assert abs(total_pct - 100.0) < 1.0
