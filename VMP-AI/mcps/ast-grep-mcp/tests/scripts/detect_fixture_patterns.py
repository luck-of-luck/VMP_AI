#!/usr/bin/env python3
"""
Detect common patterns in test files that could become fixtures.

Patterns detected:
- Repeated setup code (3+ occurrences)
- Common temporary file structures
- Repeated mock configurations
- Similar data generation patterns

Usage:
    python tests/scripts/detect_fixture_patterns.py
    python tests/scripts/detect_fixture_patterns.py --threshold 2
    python tests/scripts/detect_fixture_patterns.py --detailed
    python tests/scripts/detect_fixture_patterns.py --json
"""

import argparse
import ast
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

from ast_grep_mcp.constants import SemanticVolumeDefaults
from ast_grep_mcp.features.deduplication.scoring_scales import SharedTopN
from ast_grep_mcp.utils.console_logger import console

CONTEXT_LINES_STANDARD = 3
CONTEXT_LINES_EXPANDED = 5
FIXTURE_VALUE_MIN = 4.0
FIXTURE_VALUE_BASE = 5.0
FIXTURE_VALUE_COMPLEX = 6.0
FIXTURE_VALUE_RECOMMENDED = 7.0
FIXTURE_VALUE_STRONG = 8.0
FIXTURE_VALUE_TOP = 9.0


@dataclass
class PatternOccurrence:
    """Single occurrence of a pattern."""

    file: str
    line_number: int
    function_name: str
    code_snippet: str


@dataclass
class DetectedPattern:
    """A detected pattern that could become a fixture."""

    pattern_type: str
    description: str
    occurrences: int
    files_count: int
    complexity_score: float  # 0-10, higher = more complex
    fixture_value_score: float  # 0-10, higher = better fixture candidate
    occurrences_list: List[PatternOccurrence]
    suggested_fixture_name: str
    suggested_implementation: str


class PatternDetector:
    """Detect common patterns in test files."""

    def __init__(self, root: Path, threshold: int = SharedTopN.SMALL):
        self.root = root
        self.threshold = threshold
        self.patterns: List[DetectedPattern] = []

    def find_test_files(self) -> List[Path]:
        """Find all test files."""
        test_files = []

        unit_dir = self.root / "tests" / "unit"
        if unit_dir.exists():
            test_files.extend(sorted(unit_dir.glob("test_*.py")))

        integration_dir = self.root / "tests" / "integration"
        if integration_dir.exists():
            test_files.extend(sorted(integration_dir.glob("test_*.py")))

        return test_files

    def detect_temp_dir_pattern(self, test_files: List[Path]) -> DetectedPattern:
        """Detect tempfile.mkdtemp() pattern."""
        occurrences = []

        for file in test_files:
            content = file.read_text()
            lines = content.splitlines()

            for i, line in enumerate(lines, 1):
                if "tempfile.mkdtemp()" in line or "TemporaryDirectory()" in line:
                    # Find containing function
                    function_name = self._find_containing_function(content, i)

                    # Extract context (3 lines)
                    start = max(0, i - 2)
                    end = min(len(lines), i + 1)
                    snippet = "\n".join(lines[start:end])

                    occurrences.append(PatternOccurrence(file=file.name, line_number=i, function_name=function_name, code_snippet=snippet))

        files_count = len(set(occ.file for occ in occurrences))

        return DetectedPattern(
            pattern_type="temp_directory",
            description="Temporary directory creation with tempfile.mkdtemp()",
            occurrences=len(occurrences),
            files_count=files_count,
            complexity_score=2.0,  # Simple pattern
            fixture_value_score=FIXTURE_VALUE_TOP if files_count >= SharedTopN.SMALL else FIXTURE_VALUE_BASE,
            occurrences_list=occurrences,
            suggested_fixture_name="temp_dir",
            suggested_implementation="""@pytest.fixture
def temp_dir():
    '''Provide temporary directory with automatic cleanup.'''
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)""",
        )

    def detect_file_creation_pattern(self, test_files: List[Path]) -> DetectedPattern:
        """Detect repeated file creation patterns."""
        occurrences = []
        file_patterns = defaultdict(list)

        for file in test_files:
            content = file.read_text()
            lines = content.splitlines()

            # Look for: with open(..., "w") as f:
            pattern = r'with\s+open\([^,]+,\s*["\']w["\']'

            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    function_name = self._find_containing_function(content, i)

                    # Extract file path from open()
                    file_path_match = re.search(r"open\(([^,]+),", line)
                    if file_path_match:
                        file_path = file_path_match.group(1).strip()
                        file_patterns[file_path].append((file.name, i))

                    start = max(0, i - 1)
                    end = min(len(lines), i + CONTEXT_LINES_STANDARD)
                    snippet = "\n".join(lines[start:end])

                    occurrences.append(PatternOccurrence(file=file.name, line_number=i, function_name=function_name, code_snippet=snippet))

        files_count = len(set(occ.file for occ in occurrences))

        return DetectedPattern(
            pattern_type="file_creation",
            description="Creating test files with specific content",
            occurrences=len(occurrences),
            files_count=files_count,
            complexity_score=4.0,
            fixture_value_score=FIXTURE_VALUE_STRONG if files_count >= SharedTopN.SMALL else FIXTURE_VALUE_MIN,
            occurrences_list=occurrences,
            suggested_fixture_name="temp_project_with_files",
            suggested_implementation="""@pytest.fixture
def temp_project_with_files(temp_dir):
    '''Provide project with common test files.'''
    project = Path(temp_dir) / "project"
    project.mkdir()

    # Create sample files
    sample_py = project / "sample.py"
    sample_py.write_text("def hello(): pass")

    return {"project": str(project), "sample_py": str(sample_py)}""",
        )

    def detect_mock_popen_pattern(self, test_files: List[Path]) -> DetectedPattern:
        """Detect Popen mocking patterns."""
        occurrences = []

        for file in test_files:
            content = file.read_text()
            lines = content.splitlines()

            # Look for @patch("subprocess.Popen") or mock_popen
            for i, line in enumerate(lines, 1):
                if '@patch("subprocess.Popen")' in line or "@patch('subprocess.Popen')" in line:
                    function_name = self._find_containing_function(content, i)

                    start = max(0, i - 1)
                    end = min(len(lines), i + CONTEXT_LINES_EXPANDED)
                    snippet = "\n".join(lines[start:end])

                    occurrences.append(PatternOccurrence(file=file.name, line_number=i, function_name=function_name, code_snippet=snippet))

        files_count = len(set(occ.file for occ in occurrences))

        return DetectedPattern(
            pattern_type="mock_popen",
            description="Mocking subprocess.Popen for streaming",
            occurrences=len(occurrences),
            files_count=files_count,
            complexity_score=6.0,
            fixture_value_score=FIXTURE_VALUE_TOP if files_count >= SharedTopN.SMALL else FIXTURE_VALUE_COMPLEX,
            occurrences_list=occurrences,
            suggested_fixture_name="mock_popen",
            suggested_implementation="""@pytest.fixture
def mock_popen(monkeypatch):
    '''Mock subprocess.Popen for streaming commands.'''
    mock = MagicMock()
    mock.return_value.stdout = iter([])
    mock.return_value.poll.return_value = None
    mock.return_value.wait.return_value = 0
    monkeypatch.setattr("subprocess.Popen", mock)
    return mock""",
        )

    def detect_cache_initialization_pattern(self, test_files: List[Path]) -> DetectedPattern:
        """Detect cache initialization patterns."""
        occurrences = []

        for file in test_files:
            content = file.read_text()
            lines = content.splitlines()

            # Look for QueryCache or cache initialization
            for i, line in enumerate(lines, 1):
                if "QueryCache(" in line or "_query_cache =" in line:
                    function_name = self._find_containing_function(content, i)

                    start = max(0, i - 1)
                    end = min(len(lines), i + CONTEXT_LINES_STANDARD)
                    snippet = "\n".join(lines[start:end])

                    occurrences.append(PatternOccurrence(file=file.name, line_number=i, function_name=function_name, code_snippet=snippet))

        files_count = len(set(occ.file for occ in occurrences))

        return DetectedPattern(
            pattern_type="cache_initialization",
            description="Initializing QueryCache with specific configuration",
            occurrences=len(occurrences),
            files_count=files_count,
            complexity_score=5.0,
            fixture_value_score=FIXTURE_VALUE_STRONG if files_count >= SharedTopN.SMALL else FIXTURE_VALUE_BASE,
            occurrences_list=occurrences,
            suggested_fixture_name="initialized_cache",
            suggested_implementation="""@pytest.fixture
def initialized_cache():
    '''Provide initialized cache with MCP tools registered.'''
    from ast_grep_mcp.core import cache as core_cache
    from ast_grep_mcp.core import config as core_config
    core_cache.init_query_cache(max_size=10, ttl_seconds=300)
    core_config.CACHE_ENABLED = True
    yield core_cache._query_cache
    core_cache._query_cache = None
    core_config.CACHE_ENABLED = False""",
        )

    def detect_repeated_imports_pattern(self, test_files: List[Path]) -> DetectedPattern:
        """Detect repeated import patterns that could be fixtures."""
        occurrences = []
        import_counts = defaultdict(int)

        for file in test_files:
            try:
                content = file.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and "main" in node.module:
                            for alias in node.names:
                                import_counts[alias.name] += 1

                                # Record occurrence
                                occurrences.append(
                                    PatternOccurrence(
                                        file=file.name,
                                        line_number=node.lineno,
                                        function_name="module_level",
                                        code_snippet=f"from {node.module} import {alias.name}",
                                    )
                                )
            except SyntaxError:
                continue

        # Filter to frequently imported items
        frequent_imports = {k: v for k, v in import_counts.items() if v >= self.threshold}
        files_count = len(set(occ.file for occ in occurrences))

        if frequent_imports:
            most_common = max(frequent_imports.items(), key=lambda x: x[1])
            description = f"Frequently imported: {', '.join(list(frequent_imports.keys())[: SharedTopN.STANDARD])}"
        else:
            description = "No frequently repeated imports detected"
            most_common = ("unknown", 0)

        return DetectedPattern(
            pattern_type="repeated_imports",
            description=description,
            occurrences=len(occurrences),
            files_count=files_count,
            complexity_score=3.0,
            fixture_value_score=FIXTURE_VALUE_RECOMMENDED if most_common[1] >= SharedTopN.STANDARD else FIXTURE_VALUE_MIN,
            occurrences_list=occurrences[: SemanticVolumeDefaults.DETAIL_RESULTS_LIMIT],
            suggested_fixture_name="mcp_tools",
            suggested_implementation="""@pytest.fixture
def mcp_tools():
    '''Factory fixture to get MCP tools by name.'''
    def _get_tool(tool_name: str):
        import main
        main.register_mcp_tools()
        return main.mcp.tools.get(tool_name)
    return _get_tool""",
        )

    def _find_containing_function(self, content: str, line_number: int) -> str:
        """Find the function containing a given line number."""
        try:
            tree = ast.parse(content)
            content.splitlines()

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.lineno <= line_number <= (node.end_lineno or node.lineno + 100):
                        return node.name

            return "unknown"
        except SyntaxError:
            return "unknown"

    def detect_all_patterns(self) -> List[DetectedPattern]:
        """Detect all patterns."""
        test_files = self.find_test_files()

        patterns = [
            self.detect_temp_dir_pattern(test_files),
            self.detect_file_creation_pattern(test_files),
            self.detect_mock_popen_pattern(test_files),
            self.detect_cache_initialization_pattern(test_files),
            self.detect_repeated_imports_pattern(test_files),
        ]

        # Filter by threshold
        self.patterns = [p for p in patterns if p.occurrences >= self.threshold]

        # Sort by fixture value score
        self.patterns.sort(key=lambda p: p.fixture_value_score, reverse=True)

        return self.patterns


def format_pattern_report(patterns: List[DetectedPattern], detailed: bool = False) -> str:
    """Format detected patterns as readable report."""
    lines = []

    lines.append("=" * 100)
    lines.append("DETECTED FIXTURE PATTERNS")
    lines.append("=" * 100)
    lines.append("")

    if not patterns:
        lines.append("No patterns detected above threshold.")
        lines.append("")
        lines.append("Try lowering threshold: --threshold 2")
        return "\n".join(lines)

    lines.append(f"{'Pattern':<25} {'Occurs':<8} {'Files':<7} {'Value':<7} {'Complexity':<12} {'Status':<20}")
    lines.append("-" * 100)

    for pattern in patterns:
        status = "RECOMMEND FIXTURE" if pattern.fixture_value_score >= FIXTURE_VALUE_RECOMMENDED else "Consider"

        lines.append(
            f"{pattern.pattern_type:<25} "
            f"{pattern.occurrences:<8} "
            f"{pattern.files_count:<7} "
            f"{pattern.fixture_value_score:<7.1f} "
            f"{pattern.complexity_score:<12.1f} "
            f"{status:<20}"
        )

    lines.append("=" * 100)
    lines.append("")

    if detailed:
        for pattern in patterns:
            lines.append(f"\n{'=' * 100}")
            lines.append(f"PATTERN: {pattern.pattern_type}")
            lines.append(f"{'=' * 100}")
            lines.append(f"Description: {pattern.description}")
            lines.append(f"Occurrences: {pattern.occurrences} times in {pattern.files_count} files")
            lines.append(f"Fixture Value Score: {pattern.fixture_value_score}/10")
            lines.append(f"Complexity Score: {pattern.complexity_score}/10")
            lines.append(f"\nSuggested Fixture Name: {pattern.suggested_fixture_name}")
            lines.append("\nSuggested Implementation:")
            lines.append("-" * 100)
            lines.append(pattern.suggested_implementation)
            lines.append("")

            if pattern.occurrences_list:
                lines.append(f"\nExample Occurrences (showing first {SharedTopN.STANDARD}):")
                lines.append("-" * 100)
                for occ in pattern.occurrences_list[: SharedTopN.STANDARD]:
                    lines.append(f"\nFile: {occ.file}, Line: {occ.line_number}, Function: {occ.function_name}")
                    lines.append("Code:")
                    for line in occ.code_snippet.splitlines():
                        lines.append(f"  {line}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Detect common patterns for fixtures")
    parser.add_argument(
        "--threshold",
        type=int,
        default=SharedTopN.SMALL,
        help=f"Minimum occurrences to report (default: {SharedTopN.SMALL})",
    )
    parser.add_argument("--detailed", action="store_true", help="Show detailed breakdown")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    # Find root directory
    root = Path(__file__).parent.parent.parent

    # Detect patterns
    detector = PatternDetector(root, threshold=args.threshold)
    patterns = detector.detect_all_patterns()

    # Output
    if args.json:
        output = [asdict(p) for p in patterns]
        console.json(output)
    else:
        console.log(format_pattern_report(patterns, detailed=args.detailed))

    return 0


if __name__ == "__main__":
    exit(main())
