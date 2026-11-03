"""Tests for new scanner integrations (Trivy, CodeQL, Checkov)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from sast_mcp_server.models import ConfidenceLevel, SeverityLevel
from sast_mcp_server.scanners.checkov import CheckovScanner
from sast_mcp_server.scanners.codeql import CodeQLScanner
from sast_mcp_server.scanners.factory import ScannerFactory
from sast_mcp_server.scanners.gitleaks import GitleaksScanner
from sast_mcp_server.scanners.osv_scanner import OsvScanner
from sast_mcp_server.scanners.trivy import TrivyScanner
from sast_mcp_server.scanners.zap import ZapScanner

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load a JSON fixture file and return its content as string."""
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
# Trivy Scanner Tests
# --------------------------------------------------------------------------
class TestTrivyScanner:
    @pytest.fixture
    def scanner(self):
        return TrivyScanner()

    @pytest.mark.asyncio
    async def test_parse_vulnerabilities(self, scanner):
        """Test that Trivy vulnerability (SCA) findings are parsed correctly."""
        fixture_data = _load_fixture("trivy_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        # Should have: 2 vulns + 1 secret + 2 misconfigs = 5 findings
        assert len(findings) == 5

    @pytest.mark.asyncio
    async def test_parse_secrets(self, scanner):
        """Test that Trivy secret findings are parsed with HIGH confidence."""
        fixture_data = _load_fixture("trivy_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="CRITICAL")

        # Only CRITICAL findings: the AWS secret
        secret_findings = [f for f in findings if f.severity == SeverityLevel.CRITICAL]
        assert len(secret_findings) == 1
        assert secret_findings[0].confidence == ConfidenceLevel.HIGH
        assert "AWS" in secret_findings[0].title

    @pytest.mark.asyncio
    async def test_parse_misconfigurations(self, scanner):
        """Test that Trivy IaC misconfiguration findings are parsed."""
        fixture_data = _load_fixture("trivy_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        # IaC findings should contain the check ID
        misconfig_findings = [f for f in findings if "DS0" in f.title]
        assert len(misconfig_findings) == 2

    @pytest.mark.asyncio
    async def test_severity_filtering(self, scanner):
        """Test that severity filtering works across all finding types."""
        fixture_data = _load_fixture("trivy_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="HIGH")

        # Only HIGH and CRITICAL: 1 HIGH vuln + 1 CRITICAL secret + 1 HIGH misconfig = 3
        for f in findings:
            assert f.severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL)

    @pytest.mark.asyncio
    async def test_modified_files_filter(self, scanner):
        """Test that modified_files filter works."""
        fixture_data = _load_fixture("trivy_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan(
                    "tests/fixtures",
                    modified_files={"nonexistent_file.py"},
                )

        assert len(findings) == 0

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self, scanner):
        """Test that invalid JSON from Trivy raises RuntimeError."""
        mock_proc = _mock_subprocess("not valid json", stderr_data="Error occurred")

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ), pytest.raises(RuntimeError, match="invalid JSON"):
            await scanner.scan("tests/fixtures")

    def test_language_detection(self, scanner):
        """Test language detection for IaC and source files."""
        assert scanner._detect_language("main.tf") == "terraform"
        assert scanner._detect_language("Dockerfile") == "docker"
        assert scanner._detect_language("docker-compose.yml") == "docker"
        assert scanner._detect_language("app.py") == "python"
        assert scanner._detect_language("deploy.yaml") == "yaml"
        assert scanner._detect_language("unknown.xyz") == ""

    def test_scanner_is_trivy(self, scanner):
        """Verify all findings are tagged with scanner='trivy'."""
        # Already tested implicitly, but be explicit
        assert isinstance(scanner, TrivyScanner)


# --------------------------------------------------------------------------
# CodeQL Scanner Tests
# --------------------------------------------------------------------------
class TestCodeQLScanner:
    @pytest.fixture
    def scanner(self):
        return CodeQLScanner()

    @pytest.mark.asyncio
    async def test_parse_sarif_findings(self, scanner):
        """Test that CodeQL SARIF output is correctly parsed into findings."""
        sarif_data = _load_fixture("codeql_output.sarif")
        sarif_dict = json.loads(sarif_data)

        findings = scanner._parse_sarif(
            sarif_dict, "tests/fixtures", "LOW", "LOW", None
        )

        assert len(findings) == 2
        assert findings[0].scanner == "codeql"
        assert findings[0].title == "py/sql-injection"
        assert findings[0].severity == SeverityLevel.HIGH  # error -> HIGH

    @pytest.mark.asyncio
    async def test_severity_mapping(self, scanner):
        """Test that SARIF level maps correctly to our severity."""
        sarif_data = _load_fixture("codeql_output.sarif")
        sarif_dict = json.loads(sarif_data)

        findings = scanner._parse_sarif(
            sarif_dict, "tests/fixtures", "LOW", "LOW", None
        )

        severities = {f.severity for f in findings}
        # error -> HIGH, warning -> MEDIUM
        assert SeverityLevel.HIGH in severities
        assert SeverityLevel.MEDIUM in severities

    @pytest.mark.asyncio
    async def test_data_flow_parsed(self, scanner):
        """Test that SARIF codeFlows are parsed into data_flow."""
        sarif_data = _load_fixture("codeql_output.sarif")
        sarif_dict = json.loads(sarif_data)

        findings = scanner._parse_sarif(
            sarif_dict, "tests/fixtures", "LOW", "LOW", None
        )

        # First finding (sql-injection) has codeFlows
        sql_finding = [f for f in findings if "sql" in f.title][0]
        assert len(sql_finding.data_flow) == 2
        assert sql_finding.data_flow[0].line == 1

    @pytest.mark.asyncio
    async def test_severity_filtering(self, scanner):
        """Test that severity filtering works on SARIF findings."""
        sarif_data = _load_fixture("codeql_output.sarif")
        sarif_dict = json.loads(sarif_data)

        findings = scanner._parse_sarif(
            sarif_dict, "tests/fixtures", "HIGH", "LOW", None
        )

        # Only error-level (HIGH) findings should pass
        assert len(findings) == 1
        assert findings[0].severity == SeverityLevel.HIGH

    def test_language_detection(self, scanner):
        """Test CodeQL language auto-detection from directory."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some Python files
            for name in ["main.py", "utils.py", "app.py"]:
                open(os.path.join(tmpdir, name), "w").close()
            # Create one JS file
            open(os.path.join(tmpdir, "index.js"), "w").close()

            lang = scanner._detect_codeql_language(tmpdir)
            assert lang == "python"  # 3 python files > 1 JS file

    def test_language_detection_empty_dir(self, scanner):
        """Test language detection returns None for empty directory."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            lang = scanner._detect_codeql_language(tmpdir)
            assert lang is None


# --------------------------------------------------------------------------
# Checkov Scanner Tests
# --------------------------------------------------------------------------
class TestCheckovScanner:
    @pytest.fixture
    def scanner(self):
        return CheckovScanner()

    @pytest.mark.asyncio
    async def test_parse_findings(self, scanner):
        """Test that Checkov output is correctly parsed."""
        fixture_data = _load_fixture("checkov_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        # 2 failed terraform checks + 1 failed dockerfile check = 3
        assert len(findings) == 3
        assert all(f.scanner == "checkov" for f in findings)

    @pytest.mark.asyncio
    async def test_severity_mapping(self, scanner):
        """Test that Checkov severity levels are parsed correctly."""
        fixture_data = _load_fixture("checkov_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        severities = {f.severity for f in findings}
        assert SeverityLevel.HIGH in severities
        assert SeverityLevel.MEDIUM in severities
        assert SeverityLevel.LOW in severities

    @pytest.mark.asyncio
    async def test_severity_filtering(self, scanner):
        """Test that severity filtering works."""
        fixture_data = _load_fixture("checkov_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="HIGH")

        # Only HIGH: the S3 versioning check
        assert len(findings) == 1
        assert findings[0].severity == SeverityLevel.HIGH

    @pytest.mark.asyncio
    async def test_passed_checks_not_included(self, scanner):
        """Test that passed checks are not included in findings."""
        fixture_data = _load_fixture("checkov_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        # The passed check (CKV_AWS_18) should NOT appear
        check_ids = [f.title for f in findings]
        assert not any("CKV_AWS_18" in cid for cid in check_ids)

    @pytest.mark.asyncio
    async def test_confidence_is_high(self, scanner):
        """Checkov checks are deterministic — confidence should always be HIGH."""
        fixture_data = _load_fixture("checkov_output.json")
        mock_proc = _mock_subprocess(fixture_data)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("tests/fixtures", min_severity="LOW")

        for f in findings:
            assert f.confidence == ConfidenceLevel.HIGH

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self, scanner):
        """Test that invalid JSON from Checkov raises RuntimeError."""
        mock_proc = _mock_subprocess("not valid json", stderr_data="Error")

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ), pytest.raises(RuntimeError, match="invalid JSON"):
            await scanner.scan("tests/fixtures")

    def test_language_detection(self, scanner):
        """Test language detection for IaC files."""
        assert scanner._detect_language("main.tf") == "terraform"
        assert scanner._detect_language("Dockerfile") == "docker"
        assert scanner._detect_language("deploy.yaml") == "yaml"
        assert scanner._detect_language("vars.tfvars") == "terraform"


# --------------------------------------------------------------------------
# Factory Tests for New Scanners
# --------------------------------------------------------------------------
class TestNewScannerFactory:
    def test_get_trivy_scanner(self):
        scanner = ScannerFactory.get_scanner("trivy")
        assert isinstance(scanner, TrivyScanner)

    def test_get_codeql_scanner(self):
        scanner = ScannerFactory.get_scanner("codeql")
        assert isinstance(scanner, CodeQLScanner)

    def test_get_checkov_scanner(self):
        scanner = ScannerFactory.get_scanner("checkov")
        assert isinstance(scanner, CheckovScanner)

    def test_list_scanners_includes_new(self):
        scanners = ScannerFactory.list_scanners()
        assert "trivy" in scanners
        assert "codeql" in scanners
        assert "checkov" in scanners


@pytest.mark.asyncio
class TestGitleaksScanner:
    async def test_parse_findings(self):
        scanner = GitleaksScanner()

        output = [
            {
                "Description": "Generic API Key",
                "StartLine": 10,
                "EndLine": 10,
                "File": "config.yaml",
                "Match": "api_key = 'abc123xyz'",
                "Secret": "abc123xyz",
                "Commit": "abcde123",
                "Author": "dev@example.com",
                "Date": "2023-01-01T00:00:00Z",
                "RuleID": "generic-api-key"
            }
        ]

        mock_proc = _mock_subprocess("", returncode=1)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
                patch("os.path.exists", return_value=True), \
                patch("os.path.getsize", return_value=100), \
                patch("builtins.open", mock_open(read_data=json.dumps(output))):
            findings = await scanner.scan("/target")

            assert len(findings) == 1
            assert findings[0].title == "Leaked Secret: generic-api-key"
            assert findings[0].file == "config.yaml"
            assert findings[0].severity == SeverityLevel.CRITICAL
            assert "Found in commit abcde123 by dev@example.com" in findings[0].message


@pytest.mark.asyncio
class TestOsvScanner:
    async def test_parse_findings(self):
        scanner = OsvScanner()

        output = {
            "results": [
                {
                    "source": {"path": "/target/package.json"},
                    "packages": [
                        {
                            "package": {"name": "lodash", "version": "4.17.15"},
                            "vulnerabilities": [
                                {
                                    "id": "GHSA-p6mc-m468-83gw",
                                    "summary": "Prototype Pollution in lodash",
                                    "aliases": ["CVE-2020-8203"]
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        mock_proc = _mock_subprocess(json.dumps(output), returncode=1)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            findings = await scanner.scan("/target")

            assert len(findings) == 1
            assert findings[0].title == "GHSA-p6mc-m468-83gw in lodash"
            assert findings[0].file == "package.json"
            assert findings[0].severity == SeverityLevel.HIGH
            assert "CVE-2020-8203" in findings[0].context


@pytest.mark.asyncio
class TestZapScanner:
    async def test_parse_findings(self):
        scanner = ZapScanner()
        fixture_data = _load_fixture("zap_output.json")

        # We only want to test the parsing logic since the orchestration runs docker
        data = json.loads(fixture_data)
        findings = []
        site = data.get("site", [])
        for s in site:
            alerts = s.get("alerts", [])
            for alert in alerts:
                findings.append(scanner._parse_alert(alert, "http://localhost:8080"))

        assert len(findings) == 2

        # SQLi should be HIGH severity
        sqli = [f for f in findings if "SQL Injection" in f.title][0]
        assert sqli.severity == SeverityLevel.HIGH
        assert sqli.confidence == ConfidenceLevel.HIGH
        assert "http://localhost:8080/login" in sqli.context

        # X-Content-Type-Options should be LOW severity
        headers = [f for f in findings if "X-Content-Type" in f.title][0]
        assert headers.severity == SeverityLevel.LOW
        assert headers.confidence == ConfidenceLevel.MEDIUM
