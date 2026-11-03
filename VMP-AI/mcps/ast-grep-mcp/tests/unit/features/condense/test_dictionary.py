"""Tests for zstd dictionary training."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from ast_grep_mcp.features.condense.dictionary import (
    _estimate_improvement,
    _select_samples,
    train_dictionary_impl,
)


class TestTrainDictionaryImpl:
    def test_nonexistent_path_returns_error(self):
        result = train_dictionary_impl("/nonexistent/xyz")
        assert "error" in result

    def test_file_path_returns_error(self):
        with tempfile.NamedTemporaryFile(suffix=".py") as f:
            result = train_dictionary_impl(f.name)
        assert "error" in result

    def test_empty_directory_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = train_dictionary_impl(tmp)
        assert "error" in result

    def test_no_code_files_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "readme.txt").write_text("hello\n")
            result = train_dictionary_impl(tmp)
        assert "error" in result

    def test_successful_training_mocked(self):
        """Unit test: mock _write_training_result to avoid actual zstd call."""
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(15):
                (Path(tmp) / f"module_{i}.py").write_text(f"def func_{i}(x):\n    return x + {i}\n")

            def fake_write(samples: list, dict_path: Path) -> tuple[int, int]:
                # Create a real file so stat() works
                dict_path.write_bytes(b"\x00" * 112640)
                return 15, 15000

            with patch(
                "ast_grep_mcp.features.condense.dictionary._write_training_result",
                side_effect=fake_write,
            ):
                result = train_dictionary_impl(tmp, language="python")

        assert "dict_path" in result
        assert result["samples_used"] == 15
        assert result["estimated_improvement_pct"] == 10.0
        assert result["dict_size_bytes"] == 112640

    def test_language_filter_applied(self):
        """Only files matching the language filter are used as samples."""
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(5):
                (Path(tmp) / f"m{i}.py").write_text("x = 1\n")
                (Path(tmp) / f"m{i}.ts").write_text("const x = 1;\n")

            def fake_write(samples: list, dict_path: Path) -> tuple[int, int]:
                # Verify only .py files were selected
                assert all(s.suffix == ".py" for s in samples), f"Expected only .py samples, got: {[s.suffix for s in samples]}"
                dict_path.touch()
                return len(samples), 500

            with patch(
                "ast_grep_mcp.features.condense.dictionary._write_training_result",
                side_effect=fake_write,
            ):
                result = train_dictionary_impl(tmp, language="python")

        assert "error" not in result
        assert result["language"] == "python"
        assert result["samples_used"] == 5

    def test_output_dir_respected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "custom_dicts"
            for i in range(5):
                (Path(tmp) / f"m{i}.py").write_text("x = 1\n")

            def fake_write(samples: list, dict_path: Path) -> tuple[int, int]:
                dict_path.touch()
                return 5, 500

            with patch(
                "ast_grep_mcp.features.condense.dictionary._write_training_result",
                side_effect=fake_write,
            ):
                result = train_dictionary_impl(tmp, output_dir=str(out))

        assert "dict_path" in result
        assert str(out) in result["dict_path"]


class TestSelectSamples:
    def test_respects_sample_count_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(20):
                (Path(tmp) / f"f{i}.py").write_text("x = 1\n")
            files = list(Path(tmp).glob("*.py"))
            selected = _select_samples(files, sample_count=5)
        assert len(selected) <= 5

    def test_skips_oversized_files(self):
        from ast_grep_mcp.constants import CondenseDictionaryDefaults

        with tempfile.TemporaryDirectory() as tmp:
            big = Path(tmp) / "big.py"
            big.write_bytes(b"x = 1\n" * (CondenseDictionaryDefaults.MAX_SAMPLE_SIZE_BYTES // 6 + 1))
            small = Path(tmp) / "small.py"
            small.write_text("x = 1\n")
            selected = _select_samples([big, small], sample_count=10)
        assert big not in selected
        assert small in selected

    def test_empty_list(self):
        assert _select_samples([], 10) == []


class TestEstimateImprovement:
    def test_few_samples_returns_low_estimate(self):
        assert _estimate_improvement(5, 1000) == 5.0

    def test_moderate_samples(self):
        assert _estimate_improvement(30, 10000) == 10.0

    def test_many_samples_returns_full_benefit(self):
        assert _estimate_improvement(100, 50000) == 15.0
