"""Tests for v0.7.0 server features: auth gating, JSON output, policy, reporting."""

import json
from unittest.mock import patch

import pytest

from sast_mcp_server import server
from sast_mcp_server.auth import (
    SCOPE_CONFIG_WRITE,
    SCOPE_SCAN_READ,
    create_jwt,
)
from sast_mcp_server.models import ConfidenceLevel, Finding, SeverityLevel


def _finding(severity=SeverityLevel.HIGH, fhash="h1") -> Finding:
    return Finding(
        scanner="bandit",
        title="B602",
        message="shell=True",
        file="app.py",
        line_start=1,
        line_end=1,
        severity=severity,
        confidence=ConfidenceLevel.HIGH,
        context="subprocess.call(x, shell=True)",
        finding_hash=fhash,
        cwe="CWE-78",
    )


# ---------------------------------------------------------------------------
# Structured JSON output
# ---------------------------------------------------------------------------
class TestOutputFormat:
    @pytest.mark.asyncio
    async def test_scan_all_json(self, tmp_path):
        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=([_finding()], ["bandit"], ["semgrep"]),
        ):
            result = await server.scan_all(
                target_path=str(tmp_path), output_format="json"
            )
        data = json.loads(result)
        assert data["total"] == 1
        assert data["scanners_used"] == ["bandit"]
        assert data["findings"][0]["cwe"] == "CWE-78"

    @pytest.mark.asyncio
    async def test_invalid_output_format(self, tmp_path):
        result = await server.scan_all(
            target_path=str(tmp_path), output_format="xml"
        )
        assert "Invalid output_format" in result


# ---------------------------------------------------------------------------
# Policy gate
# ---------------------------------------------------------------------------
class TestEvaluatePolicy:
    @pytest.mark.asyncio
    async def test_pass(self, tmp_path):
        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=([_finding(SeverityLevel.LOW)], ["bandit"], []),
        ):
            result = await server.evaluate_policy(
                target_path=str(tmp_path), max_critical=0, output_format="json"
            )
        data = json.loads(result)
        assert data["verdict"] == "PASS"
        assert data["passed"] is True

    @pytest.mark.asyncio
    async def test_fail_on_critical(self, tmp_path):
        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=([_finding(SeverityLevel.CRITICAL)], ["bandit"], []),
        ):
            result = await server.evaluate_policy(
                target_path=str(tmp_path), max_critical=0, output_format="json"
            )
        data = json.loads(result)
        assert data["verdict"] == "FAIL"
        assert data["counts"]["CRITICAL"] == 1
        assert any("CRITICAL" in v for v in data["violations"])

    @pytest.mark.asyncio
    async def test_markdown_verdict(self, tmp_path):
        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=([_finding(SeverityLevel.HIGH)], ["bandit"], []),
        ):
            result = await server.evaluate_policy(
                target_path=str(tmp_path), max_high=0
            )
        assert "❌ FAIL" in result


# ---------------------------------------------------------------------------
# Reporting tools
# ---------------------------------------------------------------------------
class TestReportingTools:
    @pytest.mark.asyncio
    async def test_export_sbom_inline(self, tmp_path):
        sca = _finding()
        sca.scanner = "trivy"
        sca.context = "Package: lodash@4.17.0 (fix: 4.17.21)"
        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=([sca], ["trivy"], []),
        ):
            result = await server.export_sbom(target_path=str(tmp_path))
        assert "CycloneDX" in result

    @pytest.mark.asyncio
    async def test_generate_report_to_file(self, tmp_path):
        out = tmp_path / "report.html"
        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=([_finding()], ["bandit"], []),
        ):
            result = await server.generate_report(
                target_path=str(tmp_path), output_path=str(out)
            )
        assert "✅" in result
        assert out.exists()
        assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Auth scope enforcement (HTTP transports)
# ---------------------------------------------------------------------------
class TestAuthEnforcement:
    @pytest.mark.asyncio
    async def test_missing_token_denied(self, monkeypatch):
        monkeypatch.setenv("SAST_MCP_JWT_SECRET", "s3cret")
        monkeypatch.setattr(server, "_current_token", lambda: None)
        result = await server.list_scanners()
        assert "authentication failed" in result

    @pytest.mark.asyncio
    async def test_read_token_allows_read_tool(self, monkeypatch):
        monkeypatch.setenv("SAST_MCP_JWT_SECRET", "s3cret")
        token = create_jwt("u", "s3cret", [SCOPE_SCAN_READ])
        monkeypatch.setattr(server, "_current_token", lambda: token)
        result = await server.list_scanners()
        assert "authentication failed" not in result

    @pytest.mark.asyncio
    async def test_read_token_denied_for_config_tool(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SAST_MCP_JWT_SECRET", "s3cret")
        token = create_jwt("u", "s3cret", [SCOPE_SCAN_READ])
        monkeypatch.setattr(server, "_current_token", lambda: token)
        # ignore_vulnerability requires config:write
        result = await server.ignore_vulnerability(
            target_path=str(tmp_path), finding_hash="abc", reason="x"
        )
        assert "authentication failed" in result
        assert SCOPE_CONFIG_WRITE in result

    @pytest.mark.asyncio
    async def test_expired_token_denied(self, monkeypatch):
        monkeypatch.setenv("SAST_MCP_JWT_SECRET", "s3cret")
        expired = create_jwt("u", "s3cret", [SCOPE_SCAN_READ], expires_in=-10)
        monkeypatch.setattr(server, "_current_token", lambda: expired)
        result = await server.list_scanners()
        assert "authentication failed" in result

    @pytest.mark.asyncio
    async def test_no_auth_mode_allows_all(self, monkeypatch):
        monkeypatch.delenv("SAST_MCP_JWT_SECRET", raising=False)
        monkeypatch.delenv("SAST_MCP_API_KEY", raising=False)
        result = await server.list_scanners()
        assert "authentication failed" not in result
