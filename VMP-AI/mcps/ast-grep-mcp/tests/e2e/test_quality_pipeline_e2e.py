"""E2E tests for the quality enforcement → auto-fix → validation pipeline.

Tests the full workflow: detect violations → classify fixes → apply fixes →
verify correctness. Specifically validates that prefer-const does NOT break
reassigned variables (the bug that caused ~160 TS2588 errors).
"""

from pathlib import Path

import pytest

from ast_grep_mcp.features.quality.fixer import (
    _is_variable_reassigned,
    classify_fix_safety,
)
from ast_grep_mcp.features.quality.tools import (
    apply_standards_fixes_tool,
    enforce_standards_tool,
)

# -- Fixtures ----------------------------------------------------------------

TYPESCRIPT_REASSIGNED = """\
// Variables that MUST stay let — they are reassigned
let counter = 0;
for (let i = 0; i < 10; i++) {
  counter += i;
}

let result = '';
result = computeSomething();

let accumulator = 0;
accumulator++;

let flag = false;
flag = true;

// Variable that CAN become const — never reassigned
let immutable = 42;
console.log(immutable);
"""

TYPESCRIPT_SAFE_CONST = """\
let name = 'Alice';
console.log(name);

let items = [1, 2, 3];
console.log(items.length);

let config = { debug: true };
console.log(config.debug);
"""

TYPESCRIPT_FOR_LOOPS = """\
for (let i = 0; i < 10; i++) {
  process(i);
}

for (let j = 0; j < 100; j++) {
  total += j;
}

let written = 0;
for (const item of items) {
  write(item);
  written++;
}
"""


@pytest.fixture
def ts_project(tmp_path: Path) -> str:
    """Create a temp TypeScript project with test files."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "reassigned.ts").write_text(TYPESCRIPT_REASSIGNED)
    (src / "safe.ts").write_text(TYPESCRIPT_SAFE_CONST)
    (src / "loops.ts").write_text(TYPESCRIPT_FOR_LOOPS)
    return str(tmp_path)


PYTHON_BARE_EXCEPT = """\
import json

def parse_config(raw):
    try:
        return json.loads(raw)
    except:
        return {}

def safe_divide(a, b):
    try:
        return a / b
    except:
        return None
"""


@pytest.fixture
def py_project(tmp_path: Path) -> str:
    """Create a temp Python project with test files."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("x = 10\ndef hello():\n    print('hi')\n    return x\n")
    (src / "bare_except.py").write_text(PYTHON_BARE_EXCEPT)
    return str(tmp_path)


# -- Tests: Reassignment Detection ------------------------------------------


class TestPreferConstReassignmentE2E:
    """E2E: prefer-const must NOT convert reassigned variables."""

    def test_reassigned_counter_not_converted(self, ts_project: str):
        """counter += i means counter must stay let."""
        path = str(Path(ts_project) / "src" / "reassigned.ts")
        assert _is_variable_reassigned(path, "counter", 2) is True

    def test_reassigned_result_not_converted(self, ts_project: str):
        path = str(Path(ts_project) / "src" / "reassigned.ts")
        assert _is_variable_reassigned(path, "result", 7) is True

    def test_reassigned_accumulator_not_converted(self, ts_project: str):
        path = str(Path(ts_project) / "src" / "reassigned.ts")
        assert _is_variable_reassigned(path, "accumulator", 10) is True

    def test_reassigned_flag_not_converted(self, ts_project: str):
        path = str(Path(ts_project) / "src" / "reassigned.ts")
        assert _is_variable_reassigned(path, "flag", 13) is True

    def test_immutable_can_be_converted(self, ts_project: str):
        """immutable is never reassigned — safe to convert."""
        path = str(Path(ts_project) / "src" / "reassigned.ts")
        # let immutable = 42; is on line 17
        assert _is_variable_reassigned(path, "immutable", 17) is False

    def test_for_loop_iterator_not_converted(self, ts_project: str):
        """for (let i = 0; i < ...; i++) — i is reassigned on the same line."""
        path = str(Path(ts_project) / "src" / "loops.ts")
        assert _is_variable_reassigned(path, "i", 1) is True

    def test_written_counter_not_converted(self, ts_project: str):
        """written++ means written must stay let."""
        path = str(Path(ts_project) / "src" / "loops.ts")
        assert _is_variable_reassigned(path, "written", 9) is True


# -- Tests: Full Enforcement → Fix Pipeline ---------------------------------


class TestEnforcementPipelineE2E:
    """E2E: enforce_standards → apply_fixes round-trip."""

    def test_enforce_finds_prefer_const_violations(self, ts_project: str):
        """Enforcement should detect let declarations as prefer-const violations."""
        result = enforce_standards_tool(
            project_folder=ts_project,
            language="typescript",
            rule_set="style",
            include_patterns=["**/*.ts"],
        )
        violations = result["violations"]
        prefer_const = [v for v in violations if v["rule_id"] == "prefer-const"]
        assert len(prefer_const) > 0

    def test_apply_fixes_skips_reassigned_variables(self, ts_project: str):
        """Auto-fix must skip variables that are reassigned."""
        result = enforce_standards_tool(
            project_folder=ts_project,
            language="typescript",
            rule_set="style",
            include_patterns=["**/reassigned.ts"],
        )
        violations = result.get("violations", [])
        prefer_const = [v for v in violations if v["rule_id"] == "prefer-const"]

        apply_standards_fixes_tool(
            violations=prefer_const,
            language="typescript",
            fix_types=["safe"],
            dry_run=False,
            create_backup=False,
        )

        content = (Path(ts_project) / "src" / "reassigned.ts").read_text()

        # Reassigned variables must still be let
        assert "let counter" in content
        assert "let result" in content
        assert "let accumulator" in content
        assert "let flag" in content

        # The immutable variable should have been converted
        assert "const immutable" in content

    def test_apply_fixes_preserves_for_loop_iterators(self, ts_project: str):
        """for (let i = 0; ...; i++) must not become for (const i = 0; ...; i++)."""
        result = enforce_standards_tool(
            project_folder=ts_project,
            language="typescript",
            rule_set="style",
            include_patterns=["**/loops.ts"],
        )
        violations = result.get("violations", [])
        prefer_const = [v for v in violations if v["rule_id"] == "prefer-const"]

        apply_standards_fixes_tool(
            violations=prefer_const,
            language="typescript",
            fix_types=["safe"],
            dry_run=False,
            create_backup=False,
        )

        content = (Path(ts_project) / "src" / "loops.ts").read_text()

        # Loop iterators must stay let
        assert "for (let i" in content
        assert "for (let j" in content
        assert "let written" in content

    def test_safe_const_variables_are_converted(self, ts_project: str):
        """Variables that are never reassigned should be converted to const."""
        result = enforce_standards_tool(
            project_folder=ts_project,
            language="typescript",
            rule_set="style",
            include_patterns=["**/safe.ts"],
        )
        violations = result.get("violations", [])
        prefer_const = [v for v in violations if v["rule_id"] == "prefer-const"]
        assert len(prefer_const) > 0

        apply_standards_fixes_tool(
            violations=prefer_const,
            language="typescript",
            fix_types=["safe"],
            dry_run=False,
            create_backup=False,
        )

        content = (Path(ts_project) / "src" / "safe.ts").read_text()

        # All should be const now
        assert "const name" in content
        assert "const items" in content
        assert "const config" in content
        assert "let " not in content

    def test_dry_run_does_not_modify_files(self, ts_project: str):
        """Dry run should preview fixes without changing files."""
        original = (Path(ts_project) / "src" / "safe.ts").read_text()

        result = enforce_standards_tool(
            project_folder=ts_project,
            language="typescript",
            rule_set="style",
            include_patterns=["**/safe.ts"],
        )
        violations = result.get("violations", [])

        fix_result = apply_standards_fixes_tool(
            violations=violations,
            language="typescript",
            fix_types=["safe"],
            dry_run=True,
            create_backup=False,
        )

        after = (Path(ts_project) / "src" / "safe.ts").read_text()
        assert original == after
        assert fix_result["summary"]["fixes_attempted"] == 0

    def test_backup_created_when_requested(self, ts_project: str):
        """Backup should be created before applying fixes."""
        result = enforce_standards_tool(
            project_folder=ts_project,
            language="typescript",
            rule_set="style",
            include_patterns=["**/safe.ts"],
        )
        violations = result.get("violations", [])

        fix_result = apply_standards_fixes_tool(
            violations=violations,
            language="typescript",
            fix_types=["safe"],
            dry_run=False,
            create_backup=True,
        )

        backup_id = fix_result.get("backup_id")
        assert backup_id is not None
        # Backup is created relative to the source files directory
        backup_dir = Path(ts_project).resolve() / "src" / ".ast-grep-backups" / backup_id
        assert backup_dir.exists()


# -- Tests: no-bare-except Fix -----------------------------------------------


class TestNoBareExceptFixE2E:
    """E2E: no-bare-except auto-fix replaces except: with except Exception:."""

    def test_apply_fixes_converts_bare_except(self, py_project: str):
        """Auto-fix should convert bare except: to except Exception:."""
        result = enforce_standards_tool(
            project_folder=py_project,
            language="python",
            rule_set="recommended",
            include_patterns=["**/bare_except.py"],
        )
        violations = result.get("violations", [])
        bare = [v for v in violations if v["rule_id"] == "no-bare-except"]
        assert len(bare) == 2

        fix_result = apply_standards_fixes_tool(
            violations=bare,
            language="python",
            fix_types=["safe"],
            dry_run=False,
            create_backup=False,
        )
        assert fix_result["summary"]["fixes_successful"] == 2
        assert fix_result["summary"]["fixes_failed"] == 0

        content = (Path(py_project) / "src" / "bare_except.py").read_text()
        assert "except:" not in content
        assert content.count("except Exception:") == 2

    def test_dry_run_does_not_modify_bare_except(self, py_project: str):
        """Dry run should preview without changing files."""
        original = (Path(py_project) / "src" / "bare_except.py").read_text()

        result = enforce_standards_tool(
            project_folder=py_project,
            language="python",
            rule_set="recommended",
            include_patterns=["**/bare_except.py"],
        )
        violations = result.get("violations", [])
        bare = [v for v in violations if v["rule_id"] == "no-bare-except"]

        apply_standards_fixes_tool(
            violations=bare,
            language="python",
            fix_types=["safe"],
            dry_run=True,
            create_backup=False,
        )

        after = (Path(py_project) / "src" / "bare_except.py").read_text()
        assert original == after


# -- Tests: Multi-Language Enforcement ---------------------------------------


class TestMultiLanguageEnforcementE2E:
    """E2E: enforcement works across languages."""

    def test_typescript_enforcement(self, ts_project: str):
        result = enforce_standards_tool(
            project_folder=ts_project,
            language="typescript",
            rule_set="recommended",
        )
        assert "violations" in result
        assert "summary" in result
        assert result["summary"]["rules_executed"] > 0

    def test_python_enforcement(self, py_project: str):
        result = enforce_standards_tool(
            project_folder=py_project,
            language="python",
            rule_set="recommended",
        )
        assert "violations" in result
        assert "summary" in result


# -- Tests: Fix Safety Classification ---------------------------------------


class TestFixSafetyClassificationE2E:
    """E2E: fix safety classification for all rule types."""

    @pytest.mark.parametrize(
        "rule_id,expected_safe",
        [
            ("prefer-const", True),
            ("no-var", True),
            ("no-console-log", True),
            ("no-debugger", True),
            ("no-double-equals", True),
            ("no-bare-except", True),
            ("no-empty-catch", False),
            ("no-eval-exec", False),
        ],
    )
    def test_classify_fix_safety(self, rule_id: str, expected_safe: bool):
        from ast_grep_mcp.models.standards import RuleViolation

        violation = RuleViolation(
            file="test.ts",
            line=1,
            column=1,
            end_line=1,
            end_column=10,
            severity="info",
            rule_id=rule_id,
            message="test",
            code_snippet="test",
        )
        result = classify_fix_safety(rule_id, violation)
        assert result.is_safe == expected_safe
