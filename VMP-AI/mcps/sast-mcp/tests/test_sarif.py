"""Tests for SARIF 2.1.0 export and parsing."""

import json

from sast_mcp_server.models import (
    ConfidenceLevel,
    DataFlowStep,
    Finding,
    SeverityLevel,
)
from sast_mcp_server.sarif import (
    SARIF_VERSION,
    findings_to_sarif,
    parse_sarif,
)


def _make_finding(
    title: str = "test-rule",
    severity: SeverityLevel = SeverityLevel.HIGH,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    data_flow: list | None = None,
) -> Finding:
    """Create a test Finding object."""
    return Finding(
        scanner="test",
        title=title,
        message="Test vulnerability",
        file="app/main.py",
        line_start=10,
        line_end=15,
        severity=severity,
        confidence=confidence,
        context="def vuln():\n    eval(input())",
        finding_hash="abc123",
        language="python",
        data_flow=data_flow or [],
    )


class TestFindingsToSarif:
    def test_produces_valid_sarif(self):
        """Test that output has required SARIF 2.1.0 structure."""
        findings = [_make_finding()]
        sarif = findings_to_sarif(findings, "test-scanner")

        assert sarif["version"] == SARIF_VERSION
        assert "$schema" in sarif
        assert len(sarif["runs"]) == 1

        run = sarif["runs"][0]
        assert "tool" in run
        assert "results" in run
        assert run["tool"]["driver"]["name"] == "sast-mcp-server (test-scanner)"

    def test_severity_mapping(self):
        """Test that severity levels map to correct SARIF levels."""
        findings = [
            _make_finding(title="critical", severity=SeverityLevel.CRITICAL),
            _make_finding(title="high", severity=SeverityLevel.HIGH),
            _make_finding(title="medium", severity=SeverityLevel.MEDIUM),
            _make_finding(title="low", severity=SeverityLevel.LOW),
        ]
        # Deduplicate hashes for this test
        for i, f in enumerate(findings):
            f.finding_hash = f"hash_{i}"

        sarif = findings_to_sarif(findings, "test")
        results = sarif["runs"][0]["results"]

        levels = {r["ruleId"]: r["level"] for r in results}
        assert levels["critical"] == "error"
        assert levels["high"] == "error"
        assert levels["medium"] == "warning"
        assert levels["low"] == "note"

    def test_data_flow_serialization(self):
        """Test that data flow traces are serialized to codeFlows."""
        flow = [
            DataFlowStep(file="src/input.py", line=5, code_snippet="user_data = request.get('q')"),
            DataFlowStep(file="src/db.py", line=20, code_snippet="cursor.execute(user_data)"),
        ]
        findings = [_make_finding(data_flow=flow)]

        sarif = findings_to_sarif(findings, "test")
        result = sarif["runs"][0]["results"][0]

        assert "codeFlows" in result
        thread_locs = result["codeFlows"][0]["threadFlows"][0]["locations"]
        assert len(thread_locs) == 2
        assert thread_locs[0]["location"]["message"]["text"] == "user_data = request.get('q')"

    def test_empty_findings(self):
        """Test that empty findings produce valid empty SARIF."""
        sarif = findings_to_sarif([], "test")

        assert sarif["version"] == SARIF_VERSION
        assert len(sarif["runs"]) == 1
        assert sarif["runs"][0]["results"] == []
        assert sarif["runs"][0]["tool"]["driver"]["rules"] == []

    def test_rules_deduplicated(self):
        """Test that duplicate rule IDs produce only one rule entry."""
        findings = [
            _make_finding(title="same-rule"),
            _make_finding(title="same-rule"),
        ]
        findings[0].finding_hash = "hash_0"
        findings[1].finding_hash = "hash_1"

        sarif = findings_to_sarif(findings, "test")
        rules = sarif["runs"][0]["tool"]["driver"]["rules"]

        assert len(rules) == 1
        assert rules[0]["id"] == "same-rule"

    def test_fingerprints_included(self):
        """Test that finding hashes are included as SARIF fingerprints."""
        findings = [_make_finding()]
        sarif = findings_to_sarif(findings, "test")
        result = sarif["runs"][0]["results"][0]

        assert result["fingerprints"]["primaryLocationHash"] == "abc123"

    def test_json_serializable(self):
        """Test that the SARIF output is JSON-serializable."""
        findings = [_make_finding()]
        sarif = findings_to_sarif(findings, "test")

        # Should not raise
        json_str = json.dumps(sarif, indent=2)
        assert len(json_str) > 0


class TestParseSarif:
    def test_roundtrip(self):
        """Test that findings survive a SARIF roundtrip (export → parse)."""
        original = _make_finding(
            title="roundtrip-rule",
            severity=SeverityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH,
        )
        original.finding_hash = "unique_hash_42"

        sarif = findings_to_sarif([original], "test")
        parsed = parse_sarif(sarif, "test")

        assert len(parsed) == 1
        p = parsed[0]
        assert p.title == "roundtrip-rule"
        assert p.severity == SeverityLevel.HIGH
        assert p.finding_hash == "unique_hash_42"

    def test_parse_codeql_sarif(self):
        """Test parsing real CodeQL SARIF fixture."""
        from pathlib import Path

        fixture_path = Path(__file__).parent / "fixtures" / "codeql_output.sarif"
        with open(fixture_path, encoding="utf-8") as f:
            sarif_data = json.load(f)

        findings = parse_sarif(sarif_data, "codeql")

        assert len(findings) == 2
        assert findings[0].scanner == "codeql"
        assert findings[0].title == "py/sql-injection"
        assert findings[0].severity == SeverityLevel.HIGH
        assert len(findings[0].data_flow) == 2

    def test_parse_empty_sarif(self):
        """Test parsing empty SARIF document."""
        sarif = {
            "version": "2.1.0",
            "runs": [{"tool": {"driver": {"name": "test", "rules": []}}, "results": []}],
        }
        findings = parse_sarif(sarif, "test")
        assert findings == []

    def test_data_flow_roundtrip(self):
        """Test that data flow traces survive roundtrip."""
        flow = [
            DataFlowStep(file="a.py", line=1, code_snippet="source"),
            DataFlowStep(file="b.py", line=5, code_snippet="sink"),
        ]
        original = _make_finding(data_flow=flow)

        sarif = findings_to_sarif([original], "test")
        parsed = parse_sarif(sarif, "test")

        assert len(parsed[0].data_flow) == 2
        assert parsed[0].data_flow[0].code_snippet == "source"
        assert parsed[0].data_flow[1].code_snippet == "sink"
