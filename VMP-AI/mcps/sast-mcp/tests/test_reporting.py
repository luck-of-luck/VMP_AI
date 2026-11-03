"""Tests for CycloneDX SBOM and HTML report generation."""

from sast_mcp_server.models import ConfidenceLevel, Finding, SeverityLevel
from sast_mcp_server.reporting import findings_to_cyclonedx, findings_to_html


def _sca_finding() -> Finding:
    return Finding(
        scanner="osv-scanner",
        title="CVE-2021-1234 in lodash",
        message="Prototype pollution",
        file="package-lock.json",
        line_start=1,
        line_end=1,
        severity=SeverityLevel.HIGH,
        confidence=ConfidenceLevel.HIGH,
        context="Package: lodash@4.17.0\nVulnerability ID: CVE-2021-1234",
        finding_hash="hash1",
        cwe="CWE-1321",
        cvss_score=7.5,
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H",
        references=["https://osv.dev/vulnerability/CVE-2021-1234"],
        remediation="Upgrade lodash to 4.17.21 or later.",
    )


def _sast_finding() -> Finding:
    return Finding(
        scanner="bandit",
        title="B602",
        message="subprocess with shell=True",
        file="app.py",
        line_start=5,
        line_end=5,
        severity=SeverityLevel.MEDIUM,
        confidence=ConfidenceLevel.HIGH,
        context="subprocess.call(cmd, shell=True)",
        finding_hash="hash2",
        cwe="CWE-78",
    )


class TestCycloneDX:
    def test_basic_shape(self):
        bom = findings_to_cyclonedx([_sca_finding()])
        assert bom["bomFormat"] == "CycloneDX"
        assert bom["specVersion"] == "1.5"
        assert bom["version"] == 1
        assert "metadata" in bom and "timestamp" in bom["metadata"]

    def test_vulnerability_and_component(self):
        bom = findings_to_cyclonedx([_sca_finding()])
        assert len(bom["vulnerabilities"]) == 1
        vuln = bom["vulnerabilities"][0]
        assert vuln["id"] == "CVE-2021-1234"
        assert vuln["cwes"] == [1321]
        assert vuln["ratings"][0]["score"] == 7.5
        assert vuln["recommendation"].startswith("Upgrade lodash")
        # Affected component extracted from context
        assert bom["components"][0]["purl"] == "pkg:generic/lodash@4.17.0"
        assert vuln["affects"][0]["ref"] == "pkg:generic/lodash@4.17.0"

    def test_sca_only_filters_sast(self):
        bom = findings_to_cyclonedx([_sca_finding(), _sast_finding()], sca_only=True)
        assert len(bom["vulnerabilities"]) == 1  # bandit excluded

    def test_include_all(self):
        bom = findings_to_cyclonedx([_sca_finding(), _sast_finding()], sca_only=False)
        assert len(bom["vulnerabilities"]) == 2


class TestHtmlReport:
    def test_renders_standalone_html(self):
        html = findings_to_html([_sca_finding(), _sast_finding()], "demo", ["osv-scanner"])
        assert html.lstrip().startswith("<!DOCTYPE html>")
        assert "Security Report" in html
        assert "CVE-2021-1234 in lodash" in html
        assert "demo" in html

    def test_escapes_content(self):
        f = _sast_finding()
        f.title = "<script>alert(1)</script>"
        html = findings_to_html([f], "proj", ["bandit"])
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_empty_findings(self):
        html = findings_to_html([], "proj", [])
        assert "No findings" in html
