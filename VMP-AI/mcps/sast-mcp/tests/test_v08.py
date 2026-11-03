"""Tests for v0.8.0: closed-loop remediation, ingestion, supply chain, ops."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from sast_mcp_server import metrics, server
from sast_mcp_server.cache import ScanCache, compute_target_fingerprint
from sast_mcp_server.enrichment.patch_apply import apply_unified_diff
from sast_mcp_server.models import ConfidenceLevel, Finding, SeverityLevel
from sast_mcp_server.ratelimit import RateLimiter
from sast_mcp_server.reporting import (
    build_vex_statement,
    findings_to_compliance,
    findings_to_spdx,
    findings_to_vex,
)
from sast_mcp_server.reporting.vex import normalize_disposition
from sast_mcp_server.scanners.grype import GrypeScanner


def _finding(severity=SeverityLevel.HIGH, fhash="h1", scanner="bandit") -> Finding:
    return Finding(
        scanner=scanner,
        title="CVE-2021-1 (lodash)",
        message="prototype pollution",
        file="app.py",
        line_start=1,
        line_end=1,
        severity=severity,
        confidence=ConfidenceLevel.HIGH,
        context="Package: lodash@4.17.0 (fix: 4.17.21)",
        finding_hash=fhash,
        cwe="CWE-89",
        references=["https://x"],
        remediation="upgrade lodash",
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
class TestMetrics:
    def test_counter_and_summary(self):
        metrics.reset()
        metrics.inc("sast_tool_calls_total", labels={"tool": "scan_all", "status": "ok"})
        metrics.inc("sast_tool_calls_total", labels={"tool": "scan_all", "status": "ok"})
        metrics.observe("sast_tool_duration_seconds", 1.5, labels={"tool": "scan_all"})
        text = metrics.render_prometheus()
        assert 'sast_tool_calls_total{status="ok",tool="scan_all"} 2' in text
        assert "sast_tool_duration_seconds_count" in text
        assert "sast_uptime_seconds" in text

    def test_snapshot(self):
        metrics.reset()
        metrics.inc("sast_findings_total", value=3)
        snap = metrics.snapshot()
        assert snap.counters["sast_findings_total"][()] == 3


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
class TestRateLimiter:
    def test_disabled_by_default(self):
        rl = RateLimiter(0)
        assert not rl.enabled
        assert all(rl.check("c") for _ in range(100))

    def test_token_bucket(self):
        rl = RateLimiter(3)
        assert rl.enabled
        assert rl.check("a") and rl.check("a") and rl.check("a")
        assert not rl.check("a")
        # Separate client has its own bucket.
        assert rl.check("b")


# ---------------------------------------------------------------------------
# Incremental cache fingerprint
# ---------------------------------------------------------------------------
class TestIncrementalCache:
    def test_fingerprint_changes_with_content(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        fp1 = compute_target_fingerprint(str(tmp_path))
        (tmp_path / "a.py").write_text("x = 2\nrint\n")
        fp2 = compute_target_fingerprint(str(tmp_path))
        assert fp1 != fp2
        assert len(fp1) == 64

    def test_load_fresh_matches(self, tmp_path):
        cache = ScanCache(str(tmp_path))
        fp = "abc123"
        cache.save_scan("bandit", [_finding()], fingerprint=fp)
        assert cache.load_fresh("bandit", fp) is not None
        assert cache.load_fresh("bandit", "different") is None
        assert cache.load_fresh("bandit", "") is None


# ---------------------------------------------------------------------------
# Patch reverse (rollback primitive)
# ---------------------------------------------------------------------------
class TestPatchReverse:
    @pytest.mark.asyncio
    async def test_apply_then_reverse(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("line1\nline2\n", encoding="utf-8")
        diff = (
            "--- a/a.txt\n+++ b/a.txt\n@@ -1,2 +1,2 @@\n"
            " line1\n-line2\n+CHANGED\n"
        )
        ok, _ = await apply_unified_diff(str(tmp_path), diff)
        assert ok and "CHANGED" in f.read_text()
        ok, detail = await apply_unified_diff(str(tmp_path), diff, reverse=True)
        assert ok and "reverted" in detail
        assert "CHANGED" not in f.read_text()


# ---------------------------------------------------------------------------
# VEX / SPDX / compliance shapes
# ---------------------------------------------------------------------------
class TestReportingShapes:
    def test_vex(self):
        assert normalize_disposition("not_affected") == "not_affected"
        assert normalize_disposition("bogus") is None
        entry = build_vex_statement(
            _finding(), "not_affected", "code_not_reachable", "no input path"
        )
        assert entry["analysis"]["state"] == "not_affected"
        assert entry["analysis"]["justification"] == "code_not_reachable"
        doc = findings_to_vex([entry])
        assert doc["bomFormat"] == "CycloneDX"
        assert len(doc["vulnerabilities"]) == 1

    def test_spdx(self):
        doc = findings_to_spdx([_finding(scanner="trivy")], "demo")
        assert doc["spdxVersion"] == "SPDX-2.3"
        assert len(doc["packages"]) == 1
        assert doc["relationships"][0]["relationshipType"] == "DESCRIBES"

    def test_compliance_owasp(self):
        report = findings_to_compliance([_finding()], "owasp")  # CWE-89 → A03
        a03 = [c for c in report["categories"] if c["category"].startswith("A03")][0]
        assert a03["count"] == 1

    def test_compliance_sans(self):
        report = findings_to_compliance([_finding()], "sans")  # CWE-89 in Top 25
        matched = [c for c in report["categories"] if c["count"] > 0]
        assert any("CWE-89" in c["category"] for c in matched)


# ---------------------------------------------------------------------------
# Grype parsing
# ---------------------------------------------------------------------------
class TestGrype:
    def test_parse_match(self):
        match = {
            "vulnerability": {
                "id": "CVE-2022-1",
                "severity": "High",
                "description": "bad",
                "cvss": [{"metrics": {"baseScore": 7.5}, "vector": "CVSS:3.1/AV:N"}],
                "fix": {"versions": ["2.0.0"], "state": "fixed"},
                "urls": ["https://advisory"],
                "dataSource": "https://nvd",
            },
            "artifact": {
                "name": "left-pad",
                "version": "1.0.0",
                "language": "javascript",
                "locations": [{"path": "package-lock.json"}],
            },
        }
        f = GrypeScanner()._parse_match(match, "LOW", None)
        assert f is not None
        assert f.severity == SeverityLevel.HIGH
        assert f.cvss_score == 7.5
        assert "2.0.0" in f.remediation
        assert "left-pad" in f.context

    def test_severity_filter(self):
        match = {
            "vulnerability": {"id": "X", "severity": "Negligible"},
            "artifact": {"name": "p", "version": "1", "locations": []},
        }
        assert GrypeScanner()._parse_match(match, "HIGH", None) is None


# ---------------------------------------------------------------------------
# Server tools: import_sarif, triage_finding, remediate_and_verify, scan_image
# ---------------------------------------------------------------------------
class TestIngestion:
    @pytest.mark.asyncio
    async def test_import_sarif(self, tmp_path):
        sarif = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "snyk", "rules": []}},
                    "results": [
                        {
                            "ruleId": "SQLI",
                            "level": "error",
                            "message": {"text": "SQL injection"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "app.py"},
                                        "region": {"startLine": 5},
                                    }
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        sarif_file = tmp_path / "ext.sarif"
        sarif_file.write_text(json.dumps(sarif), encoding="utf-8")
        result = await server.import_sarif(
            target_path=str(tmp_path), sarif_path=str(sarif_file), scanner_name="snyk"
        )
        assert "Imported 1" in result
        # Cached so a later lookup finds it.
        assert ScanCache(str(tmp_path)).load_latest("snyk") is not None


class TestTriage:
    @pytest.mark.asyncio
    async def test_prompt_mode(self, tmp_path):
        ScanCache(str(tmp_path)).save_scan("bandit", [_finding()])
        result = await server.triage_finding(
            target_path=str(tmp_path), finding_hash="h1"
        )
        assert "security engineer" in result.lower()

    @pytest.mark.asyncio
    async def test_record_false_positive_suppresses(self, tmp_path):
        ScanCache(str(tmp_path)).save_scan("bandit", [_finding()])
        result = await server.triage_finding(
            target_path=str(tmp_path),
            finding_hash="h1",
            disposition="false_positive",
            justification="test code only",
        )
        assert "false_positive" in result
        from sast_mcp_server.enrichment.ignore_manager import IgnoreManager

        assert IgnoreManager(str(tmp_path)).is_ignored("h1")


class TestRemediateAndVerify:
    @pytest.mark.asyncio
    async def test_pass_when_finding_cleared(self, tmp_path):
        f = _finding(fhash="h1")
        ScanCache(str(tmp_path)).save_scan("bandit", [f])
        with patch(
            "sast_mcp_server.server.apply_unified_diff",
            new=AsyncMock(return_value=(True, "ok")),
        ), patch(
            "sast_mcp_server.server._scan_path_for_findings",
            new=AsyncMock(side_effect=[[f], []]),  # before has it, after clear
        ):
            result = await server.remediate_and_verify(
                target_path=str(tmp_path), finding_hash="h1", patch="diff"
            )
        assert "PASS" in result
        assert "cleared:** yes" in result

    @pytest.mark.asyncio
    async def test_fail_and_rollback_when_finding_persists(self, tmp_path):
        f = _finding(fhash="h1")
        ScanCache(str(tmp_path)).save_scan("bandit", [f])
        with patch(
            "sast_mcp_server.server.apply_unified_diff",
            new=AsyncMock(return_value=(True, "ok")),
        ), patch(
            "sast_mcp_server.server._scan_path_for_findings",
            new=AsyncMock(side_effect=[[f], [f]]),  # still present after
        ):
            result = await server.remediate_and_verify(
                target_path=str(tmp_path), finding_hash="h1", patch="diff"
            )
        assert "FAIL" in result
        assert "reverted" in result


class TestScanImage:
    @pytest.mark.asyncio
    async def test_scan_image_trivy(self, monkeypatch):
        from sast_mcp_server.scanners.trivy import TrivyScanner

        monkeypatch.setattr(TrivyScanner, "check_dependency", AsyncMock())
        monkeypatch.setattr(
            TrivyScanner, "scan_image", AsyncMock(return_value=[_finding(scanner="trivy")])
        )
        result = await server.scan_image(image_ref="nginx:1.25", scanner_name="trivy")
        assert "nginx:1.25" in result

    @pytest.mark.asyncio
    async def test_invalid_scanner(self):
        result = await server.scan_image(image_ref="x", scanner_name="bandit")
        assert "must be 'trivy' or 'grype'" in result


# ---------------------------------------------------------------------------
# SBOM format + report format
# ---------------------------------------------------------------------------
class TestExportFormats:
    @pytest.mark.asyncio
    async def test_export_sbom_spdx(self, tmp_path):
        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=([_finding(scanner="trivy")], ["trivy"], []),
        ), patch(
            "sast_mcp_server.server.syft_cyclonedx_components",
            new=AsyncMock(return_value=None),
        ):
            result = await server.export_sbom(
                target_path=str(tmp_path), format="spdx"
            )
        assert "SPDX" in result

    @pytest.mark.asyncio
    async def test_generate_report_pdf_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(server, "pdf_available", lambda: False)
        out = tmp_path / "r.pdf"
        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=([_finding()], ["bandit"], []),
        ):
            result = await server.generate_report(
                target_path=str(tmp_path), output_path=str(out), format="pdf"
            )
        assert "reportlab" in result

    @pytest.mark.asyncio
    async def test_compliance_report_tool(self, tmp_path):
        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=([_finding()], ["bandit"], []),
        ):
            result = await server.compliance_report(
                target_path=str(tmp_path), framework="owasp"
            )
        assert "Compliance Report" in result
        assert "A03" in result
