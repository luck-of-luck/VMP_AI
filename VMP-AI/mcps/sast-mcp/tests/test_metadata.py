"""Tests for enterprise metadata: scanner extraction, dedup merge, SARIF taxa."""

from sast_mcp_server.aggregator import _deduplicate_findings
from sast_mcp_server.enrichment.metadata import (
    extract_cvss_score,
    join_values,
    to_str_list,
)
from sast_mcp_server.models import ConfidenceLevel, Finding, SeverityLevel
from sast_mcp_server.sarif import _parse_cwe_ids, findings_to_sarif
from sast_mcp_server.scanners.osv_scanner import OsvScanner
from sast_mcp_server.scanners.trivy import TrivyScanner


class TestMetadataHelpers:
    def test_to_str_list(self):
        assert to_str_list(None) == []
        assert to_str_list("a") == ["a"]
        assert to_str_list(["a", "", "b"]) == ["a", "b"]
        assert to_str_list(123) == ["123"]

    def test_join_values(self):
        assert join_values(["CWE-79", "CWE-89"]) == "CWE-79, CWE-89"
        assert join_values("CWE-79") == "CWE-79"

    def test_extract_cvss_score(self):
        assert extract_cvss_score(7.5) == 7.5
        assert extract_cvss_score("9.8") == 9.8
        assert extract_cvss_score(11.0) is None
        assert extract_cvss_score("x") is None


class TestCweParsing:
    def test_parse_cwe_ids(self):
        assert _parse_cwe_ids("CWE-89") == ["CWE-89"]
        assert _parse_cwe_ids("CWE-79: XSS, CWE-89") == ["CWE-79", "CWE-89"]
        assert _parse_cwe_ids("89") == ["CWE-89"]
        assert _parse_cwe_ids("") == []


class TestTrivyMetadata:
    def test_vulnerability_metadata(self):
        scanner = TrivyScanner()
        vuln = {
            "Severity": "HIGH",
            "VulnerabilityID": "CVE-2021-1234",
            "PkgName": "lodash",
            "InstalledVersion": "4.17.0",
            "FixedVersion": "4.17.21",
            "Title": "Prototype pollution",
            "CweIDs": ["CWE-1321"],
            "PrimaryURL": "https://avd.aquasec.com/cve-2021-1234",
            "References": ["https://example.com/advisory"],
            "CVSS": {"nvd": {"V3Score": 7.5, "V3Vector": "CVSS:3.1/AV:N"}},
        }
        f = scanner._parse_vulnerability(vuln, "package-lock.json", "LOW", "LOW", None)
        assert f is not None
        assert f.cwe == "CWE-1321"
        assert f.cvss_score == 7.5
        assert f.cvss_vector == "CVSS:3.1/AV:N"
        assert "https://avd.aquasec.com/cve-2021-1234" in f.references
        assert "4.17.21" in f.remediation

    def test_extract_cvss_prefers_nvd(self):
        cvss = {
            "redhat": {"V3Score": 5.0, "V3Vector": "RH"},
            "nvd": {"V3Score": 9.8, "V3Vector": "NVD"},
        }
        score, vector = TrivyScanner._extract_cvss({"CVSS": cvss})
        assert score == 9.8
        assert vector == "NVD"


class TestOsvMetadata:
    def test_vuln_metadata(self):
        scanner = OsvScanner()
        vuln = {
            "id": "GHSA-xxxx",
            "summary": "Bad thing",
            "aliases": ["CVE-2022-9999"],
            "database_specific": {"severity": "HIGH", "cwe_ids": ["CWE-400"]},
            "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L"}],
            "references": [{"type": "WEB", "url": "https://example.com/ghsa"}],
            "affected": [
                {"ranges": [{"events": [{"introduced": "0"}, {"fixed": "2.0.0"}]}]}
            ],
        }
        f = scanner._parse_vuln(vuln, "requirements.txt", "somepkg", "1.0.0")
        assert f.cwe == "CWE-400"
        assert f.cvss_vector == "CVSS:3.1/AV:N/AC:L"
        assert "https://osv.dev/vulnerability/GHSA-xxxx" in f.references
        assert "https://example.com/ghsa" in f.references
        assert "https://nvd.nist.gov/vuln/detail/CVE-2022-9999" in f.references
        assert "2.0.0" in f.remediation


class TestDedupMetadataMerge:
    def test_merge_fills_blank_fields(self):
        a = Finding(
            scanner="bandit", title="X", message="", file="a.py",
            line_start=1, line_end=1, severity=SeverityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH, context="code", finding_hash="same",
            cwe="CWE-89",
        )
        b = Finding(
            scanner="semgrep", title="X", message="", file="a.py",
            line_start=1, line_end=1, severity=SeverityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH, context="code", finding_hash="same",
            cvss_score=8.1, references=["https://r"],
        )
        merged = _deduplicate_findings([a, b])
        assert len(merged) == 1
        f = merged[0]
        # Kept finding gains metadata from the duplicate.
        assert f.cwe == "CWE-89"
        assert f.cvss_score == 8.1
        assert "https://r" in f.references


class TestSarifTaxa:
    def test_taxonomy_and_taxa_emitted(self):
        f = Finding(
            scanner="semgrep", title="rule.x", message="m", file="a.py",
            line_start=1, line_end=1, severity=SeverityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH, context="c", finding_hash="h",
            cwe="CWE-79", owasp_category="A03:2021", cvss_score=7.0,
            references=["https://docs"], remediation="fix it",
        )
        doc = findings_to_sarif([f], "semgrep")
        run = doc["runs"][0]
        tax = run["taxonomies"][0]
        assert tax["name"] == "CWE"
        assert tax["taxa"][0]["id"] == "CWE-79"
        assert run["results"][0]["taxa"][0]["id"] == "CWE-79"
        rule = run["tool"]["driver"]["rules"][0]
        assert rule["properties"]["security-severity"] == "7.0"
        assert "CWE-79" in rule["properties"]["tags"]
        props = run["results"][0]["properties"]
        assert props["remediation"] == "fix it"
