"""Tests for scanner output parsing and filtering logic."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sast_mcp_server.models import ConfidenceLevel, SeverityLevel
from sast_mcp_server.scanners.bandit import BanditScanner
from sast_mcp_server.scanners.bearer import BearerScanner
from sast_mcp_server.scanners.factory import ScannerFactory
from sast_mcp_server.scanners.njsscan import NjsscanScanner

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load a JSON fixture file and return its content as bytes."""
    with open(FIXTURES / name, encoding="utf-8") as f:
        return f.read()


def _mock_subprocess(stdout_data: str, stderr_data: str = "", returncode: int = 0):
    """Create a mock for asyncio.create_subprocess_exec."""
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(
        return_value=(
            stdout_data.encode("utf-8"),
            stderr_data.encode("utf-8"),
        )
    )
    mock_proc.returncode = returncode
    mock_proc.kill = MagicMock()
    return mock_proc


# --------------------------------------------------------------------------
# Bandit Scanner Tests
# --------------------------------------------------------------------------
class TestBanditScanner:
    @pytest.fixture
    def scanner(self):
        return BanditScanner()

    @pytest.mark.asyncio
    async def test_parse_findings(self, scanner):
        """Test that bandit output is correctly parsed into Finding objects."""
        fixture_data = _load_fixture("bandit_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        assert len(findings) == 2
        assert findings[0].scanner == "bandit"
        assert findings[0].title == "B307"
        assert findings[0].severity == SeverityLevel.MEDIUM
        assert findings[0].confidence == ConfidenceLevel.HIGH
        assert findings[0].language == "python"

    @pytest.mark.asyncio
    async def test_severity_filtering(self, scanner):
        """Test that findings below the severity threshold are filtered out."""
        fixture_data = _load_fixture("bandit_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="MEDIUM")

        # Only the MEDIUM severity finding should pass (LOW is filtered)
        assert len(findings) == 1
        assert findings[0].severity == SeverityLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_confidence_filtering(self, scanner):
        """Test that findings below the confidence threshold are filtered out."""
        fixture_data = _load_fixture("bandit_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan(
                    "tests/fixtures", min_severity="LOW", min_confidence="HIGH"
                )

        # Only the HIGH confidence finding should pass
        assert len(findings) == 1
        assert findings[0].confidence == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_modified_files_filter(self, scanner):
        """Test that modified_files filter works correctly."""
        fixture_data = _load_fixture("bandit_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan(
                    "tests/fixtures",
                    modified_files={"nonexistent_file.py"},
                )

        assert len(findings) == 0

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self, scanner):
        """Test that invalid JSON from bandit raises RuntimeError."""
        mock_proc = _mock_subprocess("not valid json", stderr_data="Error occurred")

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ), pytest.raises(RuntimeError, match="invalid JSON"):
            await scanner.scan("tests/fixtures")

    @pytest.mark.asyncio
    async def test_hash_stability(self, scanner):
        """Test that finding hashes don't depend on line numbers."""
        hash1 = scanner.generate_hash("file.py", "B307", "eval(user_input)")
        hash2 = scanner.generate_hash("file.py", "B307", "eval(user_input)")
        hash3 = scanner.generate_hash("file.py", "B307", "eval( user_input )")

        # Same inputs should produce same hash
        assert hash1 == hash2
        # Whitespace-normalized inputs should also match
        assert hash1 == hash3


# --------------------------------------------------------------------------
# Bearer Scanner Tests
# --------------------------------------------------------------------------
class TestBearerScanner:
    @pytest.fixture
    def scanner(self):
        return BearerScanner()

    @pytest.mark.asyncio
    async def test_parse_findings(self, scanner):
        """Test that Bearer output is correctly parsed."""
        fixture_data = _load_fixture("bearer_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        assert len(findings) == 2
        assert findings[0].scanner == "bearer"
        assert findings[0].title == "SQL Injection"
        assert findings[0].severity == SeverityLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_confidence_not_hardcoded(self, scanner):
        """Verify that confidence is parsed from output, not hardcoded to HIGH."""
        fixture_data = _load_fixture("bearer_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        # First finding has HIGH, second has MEDIUM — should NOT all be HIGH
        confidences = {f.confidence for f in findings}
        assert ConfidenceLevel.MEDIUM in confidences

    @pytest.mark.asyncio
    async def test_data_flow_parsed(self, scanner):
        """Test that data flow traces are correctly parsed."""
        fixture_data = _load_fixture("bearer_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        # First finding has data_flow
        assert len(findings[0].data_flow) == 2
        assert findings[0].data_flow[0].line == 1

    @pytest.mark.asyncio
    async def test_language_detection(self, scanner):
        """Test file extension to language mapping."""
        assert scanner._detect_language("app.py") == "python"
        assert scanner._detect_language("index.js") == "javascript"
        assert scanner._detect_language("component.tsx") == "typescript"
        assert scanner._detect_language("unknown.xyz") == ""


# --------------------------------------------------------------------------
# njsscan Scanner Tests
# --------------------------------------------------------------------------
class TestNjsscanScanner:
    @pytest.fixture
    def scanner(self):
        return NjsscanScanner()

    @pytest.mark.asyncio
    async def test_parse_findings(self, scanner):
        """Test that njsscan output is correctly parsed."""
        fixture_data = _load_fixture("njsscan_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        # Should have findings from both 'nodejs' and 'templates' categories
        assert len(findings) >= 3  # 2 from node_eval (multi-file) + 1 from xss

    @pytest.mark.asyncio
    async def test_severity_not_hardcoded(self, scanner):
        """Verify severity is parsed from metadata, not hardcoded to HIGH."""
        fixture_data = _load_fixture("njsscan_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        severities = {f.severity for f in findings}
        # Should have both HIGH (from ERROR) and MEDIUM (from WARNING)
        assert SeverityLevel.HIGH in severities
        assert SeverityLevel.MEDIUM in severities

    @pytest.mark.asyncio
    async def test_multi_file_findings(self, scanner):
        """Test that ALL files in a multi-file finding are processed (was bug #3)."""
        fixture_data = _load_fixture("njsscan_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        # The node_eval_injection rule has 2 files — both should produce findings
        eval_findings = [f for f in findings if f.title == "node_eval_injection"]
        assert len(eval_findings) == 2


# --------------------------------------------------------------------------
# Semgrep Scanner Tests
# --------------------------------------------------------------------------
class TestSemgrepScanner:
    @pytest.fixture
    def scanner(self):
        from sast_mcp_server.scanners.semgrep import SemgrepScanner
        return SemgrepScanner()

    @pytest.mark.asyncio
    async def test_parse_findings(self, scanner):
        """Test that Semgrep output is correctly parsed."""
        fixture_data = _load_fixture("semgrep_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        assert len(findings) == 2
        assert findings[0].scanner == "semgrep"
        assert findings[0].title == "python.lang.security.audit.dangerous-system-call"
        assert findings[0].severity == SeverityLevel.HIGH  # ERROR -> HIGH
        assert findings[0].confidence == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_severity_mapping(self, scanner):
        """Test that Semgrep ERROR/WARNING/INFO map correctly to our levels."""
        fixture_data = _load_fixture("semgrep_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        severities = {f.severity for f in findings}
        # ERROR -> HIGH, WARNING -> MEDIUM
        assert SeverityLevel.HIGH in severities
        assert SeverityLevel.MEDIUM in severities

    @pytest.mark.asyncio
    async def test_severity_filtering(self, scanner):
        """Test that severity filtering works with mapped values."""
        fixture_data = _load_fixture("semgrep_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="HIGH")

        # Only the ERROR (-> HIGH) finding should pass
        assert len(findings) == 1
        assert findings[0].severity == SeverityLevel.HIGH

    @pytest.mark.asyncio
    async def test_language_detection(self, scanner):
        """Test extended language detection for Semgrep."""
        assert scanner._detect_language("main.rs") == "rust"
        assert scanner._detect_language("App.kt") == "kotlin"
        assert scanner._detect_language("code.c") == "c"


# --------------------------------------------------------------------------
# Factory Tests
# --------------------------------------------------------------------------
class TestScannerFactory:
    def test_get_valid_scanner(self):
        scanner = ScannerFactory.get_scanner("bandit")
        assert isinstance(scanner, BanditScanner)

    def test_get_scanner_case_insensitive(self):
        scanner = ScannerFactory.get_scanner("BANDIT")
        assert isinstance(scanner, BanditScanner)

    def test_get_invalid_scanner(self):
        with pytest.raises(ValueError, match="not supported"):
            ScannerFactory.get_scanner("nonexistent")

    def test_list_scanners(self):
        scanners = ScannerFactory.list_scanners()
        assert "bandit" in scanners
        assert "njsscan" in scanners
        assert "bearer" in scanners
        assert "semgrep" in scanners
        assert "trivy" in scanners
        assert "codeql" in scanners
        assert "checkov" in scanners

    def test_get_semgrep_scanner(self):
        from sast_mcp_server.scanners.semgrep import SemgrepScanner
        scanner = ScannerFactory.get_scanner("semgrep")
        assert isinstance(scanner, SemgrepScanner)

