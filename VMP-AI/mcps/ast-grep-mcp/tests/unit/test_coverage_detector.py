"""Tests for CoverageDetector - test coverage detection for deduplication analysis.

Tests cover:
- Test file pattern generation for all supported languages
- Potential test path generation
- Import pattern checking
- Test file reference detection
- Coverage detection (sequential and batch)
- Parallel and sequential batch processing
- Module-level functions
- Edge cases and error handling
"""

import os
import tempfile
from unittest.mock import patch

from ast_grep_mcp.features.deduplication.coverage import (
    CoverageDetector,
    _get_javascript_patterns,
    _get_ruby_patterns,
)


class TestHelperFunctions:
    """Tests for helper pattern functions."""

    def test_get_javascript_patterns(self):
        """Test JavaScript import pattern generation."""
        patterns = _get_javascript_patterns("myModule")

        assert len(patterns) == 3
        assert any("from" in p for p in patterns)
        assert any("require" in p for p in patterns)
        assert any("import" in p for p in patterns)

    def test_get_ruby_patterns(self):
        """Test Ruby import pattern generation."""
        patterns = _get_ruby_patterns("myModule")

        assert len(patterns) == 1
        assert "require" in patterns[0]
        assert "myModule" in patterns[0]


class TestCoverageDetectorInit:
    """Tests for CoverageDetector initialization."""

    def test_init_creates_logger(self):
        """Test that initialization creates a logger."""
        detector = CoverageDetector()
        assert detector.logger is not None


class TestFindTestFilePatterns:
    """Tests for find_test_file_patterns method."""

    def test_python_patterns(self):
        """Test Python test file patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("python")

        assert "test_*.py" in patterns
        assert "*_test.py" in patterns
        assert "**/tests/*.py" in patterns

    def test_javascript_patterns(self):
        """Test JavaScript test file patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("javascript")

        assert "*.test.js" in patterns
        assert "*.spec.js" in patterns
        assert "__tests__/*.js" in patterns

    def test_js_shorthand_patterns(self):
        """Test js shorthand gives same patterns as javascript."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("js")

        assert "*.test.js" in patterns

    def test_typescript_patterns(self):
        """Test TypeScript test file patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("typescript")

        assert "*.test.ts" in patterns
        assert "*.spec.ts" in patterns
        assert "*.test.tsx" in patterns

    def test_ts_shorthand_patterns(self):
        """Test ts shorthand patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("ts")

        assert "*.test.ts" in patterns

    def test_tsx_shorthand_patterns(self):
        """Test tsx shorthand patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("tsx")

        assert "*.test.tsx" in patterns

    def test_java_patterns(self):
        """Test Java test file patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("java")

        assert "*Test.java" in patterns
        assert "*Tests.java" in patterns
        assert "src/test/**/*.java" in patterns

    def test_go_patterns(self):
        """Test Go test file patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("go")

        assert "*_test.go" in patterns

    def test_ruby_patterns(self):
        """Test Ruby test file patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("ruby")

        assert "*_test.rb" in patterns
        assert "*_spec.rb" in patterns

    def test_rb_shorthand_patterns(self):
        """Test rb shorthand patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("rb")

        assert "*_spec.rb" in patterns

    def test_rust_patterns(self):
        """Test Rust test file patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("rust")

        assert "**/tests/*.rs" in patterns

    def test_rs_shorthand_patterns(self):
        """Test rs shorthand patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("rs")

        assert "**/tests/*.rs" in patterns

    def test_csharp_patterns(self):
        """Test C# test file patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("csharp")

        assert "*Tests.cs" in patterns
        assert "*Test.cs" in patterns

    def test_cs_shorthand_patterns(self):
        """Test cs shorthand patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("cs")

        assert "*Tests.cs" in patterns

    def test_csharp_hash_patterns(self):
        """Test c# pattern."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("c#")

        assert "*Tests.cs" in patterns

    def test_unknown_language_patterns(self):
        """Test unknown language returns generic patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("fortran")

        assert "**/test*" in patterns
        assert "**/tests/*" in patterns

    def test_case_insensitive_language(self):
        """Test that language matching is case insensitive."""
        detector = CoverageDetector()
        patterns_lower = detector.find_test_file_patterns("python")
        patterns_upper = detector.find_test_file_patterns("PYTHON")
        patterns_mixed = detector.find_test_file_patterns("Python")

        assert patterns_lower == patterns_upper == patterns_mixed


class TestGetPotentialTestPaths:
    """Tests for _get_potential_test_paths method."""

    def test_python_potential_paths(self):
        """Test Python potential test paths."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "src", "mymodule.py")
            paths = detector._get_potential_test_paths(source_file, "python", tmpdir)

            # Check that expected patterns are present
            path_strs = [str(p) for p in paths]
            assert any("test_mymodule.py" in p for p in path_strs)
            assert any("mymodule_test.py" in p for p in path_strs)

    def test_javascript_potential_paths(self):
        """Test JavaScript potential test paths."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "src", "component.js")
            paths = detector._get_potential_test_paths(source_file, "javascript", tmpdir)

            path_strs = [str(p) for p in paths]
            assert any("component.test.js" in p for p in path_strs)
            assert any("component.spec.js" in p for p in path_strs)

    def test_typescript_potential_paths(self):
        """Test TypeScript potential test paths."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "src", "service.ts")
            paths = detector._get_potential_test_paths(source_file, "typescript", tmpdir)

            path_strs = [str(p) for p in paths]
            assert any("service.test.ts" in p for p in path_strs)

    def test_tsx_potential_paths(self):
        """Test TSX potential test paths preserves tsx extension."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "src", "Component.tsx")
            paths = detector._get_potential_test_paths(source_file, "tsx", tmpdir)

            path_strs = [str(p) for p in paths]
            assert any("Component.test.tsx" in p for p in path_strs)

    def test_java_potential_paths(self):
        """Test Java potential test paths."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "src", "main", "java", "MyClass.java")
            paths = detector._get_potential_test_paths(source_file, "java", tmpdir)

            path_strs = [str(p) for p in paths]
            assert any("MyClassTest.java" in p for p in path_strs)
            assert any("MyClassTests.java" in p for p in path_strs)

    def test_go_potential_paths(self):
        """Test Go potential test paths."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "pkg", "handler.go")
            paths = detector._get_potential_test_paths(source_file, "go", tmpdir)

            path_strs = [str(p) for p in paths]
            assert any("handler_test.go" in p for p in path_strs)

    def test_ruby_potential_paths(self):
        """Test Ruby potential test paths."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "lib", "helper.rb")
            paths = detector._get_potential_test_paths(source_file, "ruby", tmpdir)

            path_strs = [str(p) for p in paths]
            assert any("helper_test.rb" in p for p in path_strs)
            assert any("helper_spec.rb" in p for p in path_strs)

    def test_handles_value_error_in_relpath(self):
        """Test handling of ValueError in os.path.relpath (Windows drive mismatch)."""
        detector = CoverageDetector()

        # This simulates when relpath fails (different drives on Windows)
        with patch("os.path.relpath", side_effect=ValueError("different drives")):
            with tempfile.TemporaryDirectory() as tmpdir:
                source_file = os.path.join(tmpdir, "mymodule.py")
                paths = detector._get_potential_test_paths(source_file, "python", tmpdir)

                # Should still return paths using basename
                assert len(paths) > 0


class TestReadFileContent:
    """Tests for _read_file_content method."""

    def test_read_existing_file(self):
        """Test reading an existing file."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import mymodule\n")
            f.flush()

            content = detector._read_file_content(f.name)

            assert content == "import mymodule\n"

            os.unlink(f.name)

    def test_read_nonexistent_file(self):
        """Test reading a nonexistent file returns None."""
        detector = CoverageDetector()

        content = detector._read_file_content("/nonexistent/path/file.py")

        assert content is None

    def test_read_file_with_encoding_errors(self):
        """Test reading file with encoding errors is handled."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
            # Write some invalid UTF-8 bytes
            f.write(b"valid text \xff\xfe invalid bytes")
            f.flush()

            content = detector._read_file_content(f.name)

            # Should return content (with errors ignored)
            assert content is not None
            assert "valid text" in content

            os.unlink(f.name)


class TestCheckImportPatterns:
    """Tests for _check_import_patterns method."""

    def test_matching_pattern(self):
        """Test that matching pattern returns True."""
        detector = CoverageDetector()
        patterns = ["from mymodule import", "import mymodule"]
        content = "from mymodule import something"

        assert detector._check_import_patterns(patterns, content) is True

    def test_no_matching_pattern(self):
        """Test that no matching pattern returns False."""
        detector = CoverageDetector()
        patterns = ["from mymodule import", "import mymodule"]
        content = "from other_module import something"

        assert detector._check_import_patterns(patterns, content) is False

    def test_case_insensitive_matching(self):
        """Test that pattern matching is case insensitive."""
        detector = CoverageDetector()
        patterns = ["from MyModule import"]
        content = "from mymodule import Something"

        assert detector._check_import_patterns(patterns, content) is True


class TestCheckGoSameDirectory:
    """Tests for _check_go_same_directory method."""

    def test_same_directory(self):
        """Test files in same directory returns True."""
        detector = CoverageDetector()

        result = detector._check_go_same_directory("/project/pkg/handler_test.go", "/project/pkg/handler.go")

        assert result is True

    def test_different_directory(self):
        """Test files in different directories returns False."""
        detector = CoverageDetector()

        result = detector._check_go_same_directory("/project/tests/handler_test.go", "/project/pkg/handler.go")

        assert result is False


class TestCheckTestFileReferencesSource:
    """Tests for _check_test_file_references_source method."""

    def test_python_import_detected(self):
        """Test Python import is detected."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="w", suffix="_test.py", delete=False) as f:
            f.write("from mymodule import MyClass\n")
            f.flush()

            result = detector._check_test_file_references_source(f.name, "/project/mymodule.py", "python")

            assert result is True
            os.unlink(f.name)

    def test_javascript_import_detected(self):
        """Test JavaScript import is detected."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".test.js", delete=False) as f:
            f.write("import { func } from '../mymodule'\n")
            f.flush()

            result = detector._check_test_file_references_source(f.name, "/project/mymodule.js", "javascript")

            assert result is True
            os.unlink(f.name)

    def test_javascript_require_detected(self):
        """Test JavaScript require is detected."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".test.js", delete=False) as f:
            f.write("const mod = require('./mymodule')\n")
            f.flush()

            result = detector._check_test_file_references_source(f.name, "/project/mymodule.js", "javascript")

            assert result is True
            os.unlink(f.name)

    def test_go_same_directory_detected(self):
        """Test Go files in same directory are detected."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = os.path.join(tmpdir, "handler_test.go")
            source_file = os.path.join(tmpdir, "handler.go")

            with open(test_file, "w") as f:
                f.write("package main\n")

            result = detector._check_test_file_references_source(test_file, source_file, "go")

            assert result is True

    def test_go_import_detected(self):
        """Test Go import is detected."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="w", suffix="_test.go", delete=False) as f:
            f.write('import "mypackage/handler"\n')
            f.flush()

            result = detector._check_test_file_references_source(f.name, "/other/dir/handler.go", "go")

            assert result is True
            os.unlink(f.name)

    def test_java_import_detected(self):
        """Test Java import is detected."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="w", suffix="Test.java", delete=False) as f:
            f.write("import com.example.MyService;\n")
            f.flush()

            result = detector._check_test_file_references_source(f.name, "/project/MyService.java", "java")

            assert result is True
            os.unlink(f.name)

    def test_ruby_require_detected(self):
        """Test Ruby require is detected."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="w", suffix="_spec.rb", delete=False) as f:
            f.write("require 'helper'\n")
            f.flush()

            result = detector._check_test_file_references_source(f.name, "/project/helper.rb", "ruby")

            assert result is True
            os.unlink(f.name)

    def test_fallback_name_in_content(self):
        """Test fallback: source name found in content."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="w", suffix="_test.py", delete=False) as f:
            f.write("# Tests for myspecialmodule functionality\n")
            f.flush()

            result = detector._check_test_file_references_source(f.name, "/project/myspecialmodule.py", "python")

            assert result is True
            os.unlink(f.name)

    def test_no_reference_found(self):
        """Test no reference found returns False."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="w", suffix="_test.py", delete=False) as f:
            f.write("from other_module import something\n")
            f.flush()

            result = detector._check_test_file_references_source(f.name, "/project/mymodule.py", "python")

            assert result is False
            os.unlink(f.name)

    def test_nonexistent_test_file(self):
        """Test nonexistent test file returns False."""
        detector = CoverageDetector()

        result = detector._check_test_file_references_source("/nonexistent/test.py", "/project/mymodule.py", "python")

        assert result is False


class TestHasTestCoverage:
    """Tests for has_test_coverage method."""

    def test_coverage_found_by_potential_path(self):
        """Test coverage found via potential test path."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            source_file = os.path.join(tmpdir, "mymodule.py")
            with open(source_file, "w") as f:
                f.write("def my_func(): pass\n")

            # Create matching test file
            test_file = os.path.join(tmpdir, "test_mymodule.py")
            with open(test_file, "w") as f:
                f.write("def test_my_func(): pass\n")

            result = detector.has_test_coverage(source_file, "python", tmpdir)

            assert result is True

    def test_no_coverage_found(self):
        """Test no coverage returns False."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file with no matching test
            source_file = os.path.join(tmpdir, "isolated_module.py")
            with open(source_file, "w") as f:
                f.write("def lonely_func(): pass\n")

            result = detector.has_test_coverage(source_file, "python", tmpdir)

            assert result is False

    def test_coverage_found_by_reference(self):
        """Test coverage found by test file reference."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            source_file = os.path.join(tmpdir, "utility.py")
            with open(source_file, "w") as f:
                f.write("def helper(): pass\n")

            # Create tests directory with a test that references source
            tests_dir = os.path.join(tmpdir, "tests")
            os.makedirs(tests_dir)
            test_file = os.path.join(tests_dir, "test_all.py")
            with open(test_file, "w") as f:
                f.write("from utility import helper\n")

            result = detector.has_test_coverage(source_file, "python", tmpdir)

            assert result is True


class TestFindAllTestFiles:
    """Tests for _find_all_test_files method."""

    def test_finds_test_files(self):
        """Test finding all test files in project."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test1 = os.path.join(tmpdir, "test_one.py")
            test2 = os.path.join(tmpdir, "test_two.py")

            with open(test1, "w") as f:
                f.write("def test(): pass\n")
            with open(test2, "w") as f:
                f.write("def test(): pass\n")

            result = detector._find_all_test_files("python", tmpdir)

            assert len(result) >= 2
            assert any("test_one.py" in f for f in result)
            assert any("test_two.py" in f for f in result)

    def test_returns_set(self):
        """Test that result is a set (no duplicates)."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = detector._find_all_test_files("python", tmpdir)

            assert isinstance(result, set)


class TestHasTestCoverageOptimized:
    """Tests for _has_test_coverage_optimized method."""

    def test_finds_coverage_in_precomputed_set(self):
        """Test finding coverage using pre-computed test file set."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source and test files
            source_file = os.path.join(tmpdir, "module.py")
            test_file = os.path.join(tmpdir, "test_module.py")

            with open(source_file, "w") as f:
                f.write("def func(): pass\n")
            with open(test_file, "w") as f:
                f.write("from module import func\n")

            # Pre-compute test files
            test_files = {os.path.normpath(test_file)}

            result = detector._has_test_coverage_optimized(source_file, "python", tmpdir, test_files)

            assert result is True

    def test_finds_coverage_by_reference(self):
        """Test finding coverage by reference in pre-computed set."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            source_file = os.path.join(tmpdir, "helper.py")
            with open(source_file, "w") as f:
                f.write("def help(): pass\n")

            # Create test file that references source
            test_file = os.path.join(tmpdir, "test_integration.py")
            with open(test_file, "w") as f:
                f.write("from helper import help\n")

            # Pre-compute test files
            test_files = {os.path.normpath(test_file)}

            result = detector._has_test_coverage_optimized(source_file, "python", tmpdir, test_files)

            assert result is True


class TestGetTestCoverageForFiles:
    """Tests for get_test_coverage_for_files method."""

    def test_returns_coverage_map(self):
        """Test returning coverage map for files."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source files
            file1 = os.path.join(tmpdir, "covered.py")
            file2 = os.path.join(tmpdir, "uncovered.py")

            with open(file1, "w") as f:
                f.write("def func1(): pass\n")
            with open(file2, "w") as f:
                f.write("def func2(): pass\n")

            # Create test for file1 only
            test_file = os.path.join(tmpdir, "test_covered.py")
            with open(test_file, "w") as f:
                f.write("from covered import func1\n")

            result = detector.get_test_coverage_for_files([file1, file2], "python", tmpdir)

            assert isinstance(result, dict)
            assert file1 in result
            assert file2 in result
            assert result[file1] is True
            assert result[file2] is False


class TestGetTestCoverageForFilesBatch:
    """Tests for get_test_coverage_for_files_batch method."""

    def test_empty_file_list(self):
        """Test empty file list returns empty dict."""
        detector = CoverageDetector()

        result = detector.get_test_coverage_for_files_batch([], "python", "/tmp")

        assert result == {}

    def test_sequential_processing(self):
        """Test sequential batch processing."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a source file
            source_file = os.path.join(tmpdir, "module.py")
            with open(source_file, "w") as f:
                f.write("def func(): pass\n")

            result = detector.get_test_coverage_for_files_batch([source_file], "python", tmpdir, parallel=False)

            assert isinstance(result, dict)
            assert source_file in result

    def test_parallel_processing(self):
        """Test parallel batch processing."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple source files
            files = []
            for i in range(3):
                source_file = os.path.join(tmpdir, f"module{i}.py")
                with open(source_file, "w") as f:
                    f.write(f"def func{i}(): pass\n")
                files.append(source_file)

            result = detector.get_test_coverage_for_files_batch(files, "python", tmpdir, parallel=True, max_workers=2)

            assert len(result) == 3
            for f in files:
                assert f in result


class TestBatchContentCache:
    """Batch coverage reads each test file's content once, not once per source file (BUG-11)."""

    def test_test_file_contents_read_once_per_batch(self):
        """N source files against M test files trigger M reads, not N*M."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_files = []
            for i in range(4):
                source_file = os.path.join(tmpdir, f"srcmod{i}.py")
                with open(source_file, "w") as f:
                    f.write(f"def func{i}(): pass\n")
                source_files.append(source_file)

            test_files = []
            for i in range(3):
                test_file = os.path.join(tmpdir, f"test_other{i}.py")
                with open(test_file, "w") as f:
                    f.write("import unrelated\n")
                test_files.append(test_file)

            original_read = detector._read_file_content
            read_paths = []

            def counting_read(file_path):
                read_paths.append(os.path.normpath(file_path))
                return original_read(file_path)

            with patch.object(detector, "_read_file_content", side_effect=counting_read):
                detector.get_test_coverage_for_files_batch(source_files, "python", tmpdir, parallel=False)

            for test_file in test_files:
                assert read_paths.count(os.path.normpath(test_file)) == 1

    def test_unreadable_cached_file_not_reread(self):
        """A file unreadable at cache-build time is skipped, not re-read per source file."""
        detector = CoverageDetector()

        test_files = {os.path.normpath("/gone/test_x.py")}
        content_cache = {os.path.normpath("/gone/test_x.py"): None}

        with patch.object(detector, "_read_file_content") as mock_read:
            result = detector._has_test_coverage_optimized("/src/mod.py", "python", "/src", test_files, content_cache)

        assert result is False
        mock_read.assert_not_called()

    def test_cached_content_used_for_reference_match(self):
        """Reference detection works from cached content without touching disk."""
        detector = CoverageDetector()

        test_path = os.path.normpath("/proj/test_helper.py")
        test_files = {test_path}
        content_cache = {test_path: "from helper import help\n"}

        with patch.object(detector, "_read_file_content") as mock_read:
            result = detector._has_test_coverage_optimized("/proj/helper.py", "python", "/proj", test_files, content_cache)

        assert result is True
        mock_read.assert_not_called()


class TestProcessFileCoverage:
    """Tests for _process_file_coverage method."""

    def test_handles_exception(self):
        """Test exception handling in file coverage processing."""
        detector = CoverageDetector()

        # Mock to raise exception
        with patch.object(detector, "_has_test_coverage_optimized", side_effect=RuntimeError("Test error")):
            result = detector._process_file_coverage("/some/file.py", "python", "/project", set())

            assert result is False


class TestProcessParallelBatch:
    """Tests for _process_parallel_batch method."""

    def test_parallel_batch_processing(self):
        """Test parallel batch processing returns correct results."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files
            files = []
            for i in range(2):
                f = os.path.join(tmpdir, f"mod{i}.py")
                with open(f, "w") as fp:
                    fp.write("pass\n")
                files.append(f)

            coverage_map, covered_count = detector._process_parallel_batch(files, "python", tmpdir, set(), max_workers=2)

            assert len(coverage_map) == 2
            assert isinstance(covered_count, int)


class TestProcessSequentialBatch:
    """Tests for _process_sequential_batch method."""

    def test_sequential_batch_processing(self):
        """Test sequential batch processing."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files
            files = []
            for i in range(2):
                f = os.path.join(tmpdir, f"mod{i}.py")
                with open(f, "w") as fp:
                    fp.write("pass\n")
                files.append(f)

            coverage_map, covered_count = detector._process_sequential_batch(files, "python", tmpdir, set())

            assert len(coverage_map) == 2
            assert isinstance(covered_count, int)


class TestParallelBatchErrorHandling:
    """Coverage-check failures degrade to False per file, not a stage abort.

    Replaces the direct tests of the removed _get_future_result helpers; error
    routing now runs through utils.futures.map_with_per_item_timeout.
    """

    def test_failed_coverage_check_yields_false(self):
        """A file whose coverage check raises is reported uncovered."""
        detector = CoverageDetector()

        def raise_for_bad(file_path, language, project_root, test_files, content_cache=None):
            if "bad" in file_path:
                raise RuntimeError("check failed")
            return True

        with patch.object(detector, "_has_test_coverage_optimized", side_effect=raise_for_bad):
            coverage_map, covered_count = detector._process_parallel_batch(
                ["/some/good.py", "/some/bad.py"], "python", "/some", set(), max_workers=2
            )

        assert coverage_map == {"/some/good.py": True, "/some/bad.py": False}
        assert covered_count == 1


class TestLogBatchResults:
    """Tests for _log_batch_results method."""

    def test_logs_results(self):
        """Test that batch results are logged."""
        detector = CoverageDetector()

        # Should not raise
        detector._log_batch_results(total_files=10, covered_count=7, parallel=True, test_files_count=5)


class TestClassMethods:
    """Tests for CoverageDetector class methods (formerly module-level functions)."""

    def test_find_test_file_patterns(self):
        """Test CoverageDetector.find_test_file_patterns."""
        detector = CoverageDetector()
        patterns = detector.find_test_file_patterns("python")

        assert "test_*.py" in patterns

    def test_has_test_coverage(self):
        """Test CoverageDetector.has_test_coverage."""
        detector = CoverageDetector()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "lonely.py")
            with open(source_file, "w") as f:
                f.write("pass\n")

            result = detector.has_test_coverage(source_file, "python", tmpdir)

            assert isinstance(result, bool)

    def test_get_test_coverage_for_files(self):
        """Test CoverageDetector.get_test_coverage_for_files."""
        detector = CoverageDetector()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "module.py")
            with open(source_file, "w") as f:
                f.write("pass\n")

            result = detector.get_test_coverage_for_files([source_file], "python", tmpdir)

            assert isinstance(result, dict)
            assert source_file in result

    def test_check_test_file_references_source(self):
        """Test CoverageDetector._check_test_file_references_source."""
        detector = CoverageDetector()
        with tempfile.NamedTemporaryFile(mode="w", suffix="_test.py", delete=False) as f:
            f.write("from mymodule import func\n")
            f.flush()

            result = detector._check_test_file_references_source(f.name, "/project/mymodule.py", "python")

            assert result is True
            os.unlink(f.name)

    def test_get_potential_test_paths(self):
        """Test CoverageDetector._get_potential_test_paths."""
        detector = CoverageDetector()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "module.py")

            result = detector._get_potential_test_paths(source_file, "python", tmpdir)

            assert isinstance(result, list)
            assert len(result) > 0
            assert any("test_module.py" in p for p in result)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_glob_exception_handling(self):
        """Test that glob exceptions are handled gracefully."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "module.py")
            with open(source_file, "w") as f:
                f.write("pass\n")

            # Mock glob to raise exception
            with patch("glob.glob", side_effect=OSError("Permission denied")):
                result = detector.has_test_coverage(source_file, "python", tmpdir)

                # Should return False, not raise
                assert result is False

    def test_find_all_test_files_glob_exception(self):
        """Test _find_all_test_files handles glob exceptions."""
        detector = CoverageDetector()

        with patch("glob.glob", side_effect=OSError("Error")):
            result = detector._find_all_test_files("python", "/tmp")

            assert isinstance(result, set)

    def test_read_file_io_error(self):
        """Test _read_file_content handles IOError."""
        detector = CoverageDetector()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("content\n")
            f.flush()
            file_path = f.name

        # Mock open to raise IOError
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            result = detector._read_file_content(file_path)

            assert result is None

        os.unlink(file_path)

    def test_parallel_batch_with_covered_files(self):
        """Test parallel batch processing with files that have coverage."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source files
            files = []
            for i in range(3):
                source_file = os.path.join(tmpdir, f"module{i}.py")
                with open(source_file, "w") as f:
                    f.write(f"def func{i}(): pass\n")
                files.append(source_file)

                # Create matching test file
                test_file = os.path.join(tmpdir, f"test_module{i}.py")
                with open(test_file, "w") as f:
                    f.write(f"from module{i} import func{i}\n")

            # Run batch with parallel processing
            result = detector.get_test_coverage_for_files_batch(files, "python", tmpdir, parallel=True, max_workers=2)

            # All files should have coverage
            assert all(result[f] is True for f in files)

    def test_sequential_batch_with_covered_files(self):
        """Test sequential batch processing with files that have coverage."""
        detector = CoverageDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source files
            files = []
            for i in range(2):
                source_file = os.path.join(tmpdir, f"mod{i}.py")
                with open(source_file, "w") as f:
                    f.write(f"def fn{i}(): pass\n")
                files.append(source_file)

                # Create matching test file
                test_file = os.path.join(tmpdir, f"test_mod{i}.py")
                with open(test_file, "w") as f:
                    f.write(f"from mod{i} import fn{i}\n")

            # Run batch with sequential processing
            result = detector.get_test_coverage_for_files_batch(files, "python", tmpdir, parallel=False)

            # All files should have coverage
            assert all(result[f] is True for f in files)
