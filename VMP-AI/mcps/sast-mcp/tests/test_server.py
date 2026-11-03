"""Tests for the MCP server tools and integration logic."""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from sast_mcp_server.integrations import IntegrationError
from sast_mcp_server.models import ConfidenceLevel, Finding, SeverityLevel
from sast_mcp_server.server import (
    apply_patch,
    compare_baseline,
    export_sarif,
    generate_fix_prompt,
    ignore_vulnerability,
    list_ignored_vulnerabilities,
    list_scanners,
    save_baseline,
    scan_all,
    scan_vulnerabilities,
    unignore_vulnerability,
    upload_to_defectdojo,
    upload_to_github,
)


# --------------------------------------------------------------------------
# Input Validation Tests
# --------------------------------------------------------------------------
class TestScanVulnerabilitiesValidation:
    @pytest.mark.asyncio
    async def test_nonexistent_path(self):
        """Test that a nonexistent path returns a clear error."""
        result = await scan_vulnerabilities(
            target_path="/nonexistent/path/abc123",
            scanner_name="bandit",
        )
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_invalid_severity(self):
        """Test that an invalid severity value is rejected."""
        result = await scan_vulnerabilities(
            target_path=".",
            scanner_name="bandit",
            min_severity="EXTREME",
        )
        assert "Invalid min_severity" in result
        assert "EXTREME" in result

    @pytest.mark.asyncio
    async def test_invalid_confidence(self):
        """Test that an invalid confidence value is rejected."""
        result = await scan_vulnerabilities(
            target_path=".",
            scanner_name="bandit",
            min_confidence="MAYBE",
        )
        assert "Invalid min_confidence" in result

    @pytest.mark.asyncio
    async def test_invalid_scanner(self):
        """Test that an invalid scanner name returns a clear error."""
        result = await scan_vulnerabilities(
            target_path=".",
            scanner_name="nonexistent_scanner",
        )
        assert "not supported" in result

    @pytest.mark.asyncio
    async def test_negative_offset(self):
        """Test that negative offset is rejected."""
        result = await scan_vulnerabilities(
            target_path=".",
            scanner_name="bandit",
            offset=-1,
        )
        assert "offset must be >= 0" in result

    @pytest.mark.asyncio
    async def test_zero_limit(self):
        """Test that zero limit is rejected."""
        result = await scan_vulnerabilities(
            target_path=".",
            scanner_name="bandit",
            limit=0,
        )
        assert "limit must be >= 1" in result


# --------------------------------------------------------------------------
# Pagination Tests
# --------------------------------------------------------------------------
class TestPagination:
    @pytest.mark.asyncio
    async def test_pagination_limits_results(self):
        """Test that limit and offset correctly paginate results."""
        # Create mock findings
        mock_findings = [
            Finding(
                scanner="bandit",
                title=f"Finding_{i}",
                message=f"Issue {i}",
                file="test.py",
                line_start=i,
                line_end=i,
                severity=SeverityLevel.HIGH,
                confidence=ConfidenceLevel.HIGH,
                context=f"code_{i}",
                finding_hash=f"hash_{i}",
                language="python",
            )
            for i in range(10)
        ]

        mock_scanner = AsyncMock()
        mock_scanner.check_dependency = AsyncMock()
        mock_scanner.scan = AsyncMock(return_value=mock_findings)

        with patch(
            "sast_mcp_server.server.ScannerFactory.get_scanner",
            return_value=mock_scanner,
        ):
            result = await scan_vulnerabilities(
                target_path=".",
                scanner_name="bandit",
                limit=3,
                offset=0,
            )

        assert "Showing 3 of 10" in result
        assert "Finding_0" in result
        assert "Finding_2" in result

    @pytest.mark.asyncio
    async def test_pagination_offset(self):
        """Test offset skips findings correctly."""
        mock_findings = [
            Finding(
                scanner="bandit",
                title=f"Finding_{i}",
                message=f"Issue {i}",
                file="test.py",
                line_start=i,
                line_end=i,
                severity=SeverityLevel.HIGH,
                confidence=ConfidenceLevel.HIGH,
                context=f"code_{i}",
                finding_hash=f"hash_{i}",
                language="python",
            )
            for i in range(5)
        ]

        mock_scanner = AsyncMock()
        mock_scanner.check_dependency = AsyncMock()
        mock_scanner.scan = AsyncMock(return_value=mock_findings)

        with patch(
            "sast_mcp_server.server.ScannerFactory.get_scanner",
            return_value=mock_scanner,
        ):
            result = await scan_vulnerabilities(
                target_path=".",
                scanner_name="bandit",
                limit=2,
                offset=3,
            )

        assert "Showing 2 of 5" in result
        assert "Finding_3" in result
        assert "Finding_4" in result


# --------------------------------------------------------------------------
# Ignore / Unignore Tools Tests
# --------------------------------------------------------------------------
class TestIgnoreTools:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_ignore_vulnerability(self, temp_dir):
        """Test ignoring a vulnerability."""
        result = await ignore_vulnerability(
            target_path=temp_dir,
            finding_hash="test_hash_123",
            reason="False positive in test code",
        )
        assert "Successfully ignored" in result
        assert "test_hash_123" in result

    @pytest.mark.asyncio
    async def test_unignore_vulnerability(self, temp_dir):
        """Test unignoring a vulnerability."""
        # First ignore it
        await ignore_vulnerability(
            target_path=temp_dir,
            finding_hash="test_hash_456",
            reason="test",
        )

        # Then unignore
        result = await unignore_vulnerability(
            target_path=temp_dir,
            finding_hash="test_hash_456",
        )
        assert "Successfully unignored" in result

    @pytest.mark.asyncio
    async def test_unignore_nonexistent(self, temp_dir):
        """Test unignoring a hash that was never ignored."""
        result = await unignore_vulnerability(
            target_path=temp_dir,
            finding_hash="never_ignored",
        )
        assert "was not in the ignore list" in result

    @pytest.mark.asyncio
    async def test_ignore_invalid_path(self):
        """Test ignoring with invalid path."""
        result = await ignore_vulnerability(
            target_path="/nonexistent/dir/abc",
            finding_hash="hash",
        )
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_list_ignored(self, temp_dir):
        """Test listing ignored vulnerabilities."""
        await ignore_vulnerability(temp_dir, "hash1", "reason1")
        await ignore_vulnerability(temp_dir, "hash2", "reason2")

        result = await list_ignored_vulnerabilities(temp_dir)
        assert "2 total" in result
        assert "hash1" in result
        assert "hash2" in result

    @pytest.mark.asyncio
    async def test_list_ignored_empty(self, temp_dir):
        """Test listing when nothing is ignored."""
        result = await list_ignored_vulnerabilities(temp_dir)
        assert "No ignored vulnerabilities" in result


# --------------------------------------------------------------------------
# List Scanners Tool Tests
# --------------------------------------------------------------------------
class TestListScanners:
    @pytest.mark.asyncio
    async def test_list_scanners_output(self):
        """Test that list_scanners returns info about all scanners."""
        result = await list_scanners()

        assert "bandit" in result
        assert "njsscan" in result
        assert "bearer" in result
        assert "semgrep" in result
        assert "trivy" in result
        assert "codeql" in result
        assert "checkov" in result
        # Should show install status
        assert "Installed" in result or "Not installed" in result


# --------------------------------------------------------------------------
# Export SARIF Tool Tests
# --------------------------------------------------------------------------
class TestExportSarif:
    @pytest.mark.asyncio
    async def test_export_sarif_returns_sarif(self):
        """Test that export_sarif returns valid SARIF content."""
        mock_findings = [
            Finding(
                scanner="bandit",
                title="Test_Rule",
                message="Test issue",
                file="test.py",
                line_start=1,
                line_end=1,
                severity=SeverityLevel.HIGH,
                confidence=ConfidenceLevel.HIGH,
                context="code",
                finding_hash="sarif_test_hash",
                language="python",
            )
        ]

        mock_scanner = AsyncMock()
        mock_scanner.check_dependency = AsyncMock()
        mock_scanner.scan = AsyncMock(return_value=mock_findings)

        with patch(
            "sast_mcp_server.server.ScannerFactory.get_scanner",
            return_value=mock_scanner,
        ):
            result = await export_sarif(
                target_path=".",
                scanner_name="bandit",
            )

        assert "SARIF Export" in result
        assert '"version": "2.1.0"' in result
        assert "Test_Rule" in result

    @pytest.mark.asyncio
    async def test_export_sarif_to_file(self):
        """Test that export_sarif writes to file when output_path is set."""
        mock_scanner = AsyncMock()
        mock_scanner.check_dependency = AsyncMock()
        mock_scanner.scan = AsyncMock(return_value=[])

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = os.path.join(temp_dir, "results.sarif")

            with patch(
                "sast_mcp_server.server.ScannerFactory.get_scanner",
                return_value=mock_scanner,
            ):
                result = await export_sarif(
                    target_path=temp_dir,
                    scanner_name="bandit",
                    output_path=output_file,
                )

            assert "SARIF export complete" in result
            assert os.path.exists(output_file)

    @pytest.mark.asyncio
    async def test_export_sarif_invalid_path(self):
        """Test that invalid path returns error."""
        result = await export_sarif(
            target_path="/nonexistent/path/xyz",
            scanner_name="bandit",
        )
        assert "does not exist" in result


# --------------------------------------------------------------------------
# Scan All Tool Tests
# --------------------------------------------------------------------------
class TestScanAll:
    @pytest.mark.asyncio
    async def test_scan_all_runs_multiple_scanners(self):
        """Test that scan_all shows results from multiple scanners."""
        mock_findings = [
            Finding(
                scanner="bandit",
                title="Bandit_Issue",
                message="Found by bandit",
                file="test.py",
                line_start=1,
                line_end=1,
                severity=SeverityLevel.HIGH,
                confidence=ConfidenceLevel.HIGH,
                context="code",
                finding_hash="hash_bandit",
                language="python",
            ),
        ]

        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=(mock_findings, ["bandit", "semgrep"], ["trivy"]),
        ):
            result = await scan_all(target_path=".", min_severity="LOW")

        assert "Multi-Scanner SAST Results" in result
        assert "bandit" in result
        assert "semgrep" in result
        assert "trivy" in result  # In skipped list
        assert "Bandit_Issue" in result

    @pytest.mark.asyncio
    async def test_scan_all_no_scanners(self):
        """Test scan_all when no scanners are available."""
        with patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=([], [], ["bandit", "semgrep"]),
        ):
            result = await scan_all(target_path=".", min_severity="LOW")

        assert "No scanners are installed" in result

    @pytest.mark.asyncio
    async def test_scan_all_invalid_path(self):
        """Test scan_all with nonexistent path."""
        result = await scan_all(target_path="/nonexistent/abc")
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_scan_all_invalid_severity(self):
        """Test scan_all with invalid severity."""
        result = await scan_all(target_path=".", min_severity="EXTREME")
        assert "Invalid min_severity" in result


# --------------------------------------------------------------------------
# Baseline round-trip ("scan_all" aggregated baseline)
# --------------------------------------------------------------------------
class TestScanAllBaseline:
    @pytest.mark.asyncio
    async def test_compare_baseline_supports_scan_all(self):
        """save_baseline(scan_all) must be diffable by compare_baseline(scan_all).

        Regression: compare_baseline used to reject scanner_name='scan_all'
        even though save_baseline / evaluate_policy(fail_on_new=True) accept it,
        leaving an aggregated baseline impossible to compare against.
        """
        findings = [
            Finding(
                scanner="bandit",
                title="Agg_Issue",
                message="aggregated",
                file="test.py",
                line_start=1,
                line_end=1,
                severity=SeverityLevel.HIGH,
                confidence=ConfidenceLevel.HIGH,
                context="code",
                finding_hash="agg_hash",
                language="python",
            ),
        ]

        with tempfile.TemporaryDirectory() as target, patch(
            "sast_mcp_server.server.run_all_scanners",
            return_value=(findings, ["bandit", "semgrep"], []),
        ):
            saved = await save_baseline(
                target_path=target, tag="t", scanner_name="scan_all"
            )
            assert "Baseline saved" in saved

            # Same findings -> no drift, but a real comparison report.
            result = await compare_baseline(
                target_path=target, tag="t", scanner_name="scan_all"
            )

        assert "not supported" not in result
        assert "Baseline Comparison Report" in result
        assert "No changes since baseline" in result

    @pytest.mark.asyncio
    async def test_compare_baseline_scan_all_no_scanners(self):
        """compare_baseline(scan_all) reports cleanly when nothing is installed."""
        findings = [
            Finding(
                scanner="bandit",
                title="Agg_Issue",
                message="aggregated",
                file="test.py",
                line_start=1,
                line_end=1,
                severity=SeverityLevel.HIGH,
                confidence=ConfidenceLevel.HIGH,
                context="code",
                finding_hash="agg_hash",
                language="python",
            ),
        ]
        with tempfile.TemporaryDirectory() as target:
            with patch(
                "sast_mcp_server.server.run_all_scanners",
                return_value=(findings, ["bandit"], []),
            ):
                await save_baseline(
                    target_path=target, tag="t", scanner_name="scan_all"
                )
            with patch(
                "sast_mcp_server.server.run_all_scanners",
                return_value=([], [], ["bandit", "semgrep"]),
            ):
                result = await compare_baseline(
                    target_path=target, tag="t", scanner_name="scan_all"
                )
        assert "No scanners are installed" in result


# --------------------------------------------------------------------------
# Scan with Ignored Findings Tests
# --------------------------------------------------------------------------
class TestScanWithIgnored:
    @pytest.mark.asyncio
    async def test_ignored_findings_are_filtered(self):
        """Test that ignored findings don't appear in scan results."""
        mock_findings = [
            Finding(
                scanner="bandit",
                title="Ignored_Issue",
                message="This should be filtered",
                file="test.py",
                line_start=1,
                line_end=1,
                severity=SeverityLevel.HIGH,
                confidence=ConfidenceLevel.HIGH,
                context="code",
                finding_hash="ignored_hash",
                language="python",
            ),
            Finding(
                scanner="bandit",
                title="Visible_Issue",
                message="This should show",
                file="test.py",
                line_start=5,
                line_end=5,
                severity=SeverityLevel.HIGH,
                confidence=ConfidenceLevel.HIGH,
                context="code",
                finding_hash="visible_hash",
                language="python",
            ),
        ]

        mock_scanner = AsyncMock()
        mock_scanner.check_dependency = AsyncMock()
        mock_scanner.scan = AsyncMock(return_value=mock_findings)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Ignore one finding
            await ignore_vulnerability(temp_dir, "ignored_hash", "test")

            with patch(
                "sast_mcp_server.server.ScannerFactory.get_scanner",
                return_value=mock_scanner,
            ):
                result = await scan_vulnerabilities(
                    target_path=temp_dir,
                    scanner_name="bandit",
                )

            assert "Visible_Issue" in result
            assert "Ignored_Issue" not in result
            assert "1 of 1" in result


# --------------------------------------------------------------------------
# v0.6.0: Dashboard Integration Tools
# --------------------------------------------------------------------------
class TestUploadTools:
    @pytest.mark.asyncio
    async def test_defectdojo_missing_file(self):
        result = await upload_to_defectdojo("/nonexistent.sarif", engagement_id=1)
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_defectdojo_surfaces_integration_error(self):
        with tempfile.NamedTemporaryFile(suffix=".sarif", delete=False) as tf:
            tf.write(b"{}")
            sarif_path = tf.name
        try:
            with patch(
                "sast_mcp_server.server._dd_upload",
                AsyncMock(side_effect=IntegrationError("not configured")),
            ):
                result = await upload_to_defectdojo(sarif_path, engagement_id=1)
            assert "DefectDojo upload failed" in result
            assert "not configured" in result
        finally:
            os.remove(sarif_path)

    @pytest.mark.asyncio
    async def test_defectdojo_success(self):
        with tempfile.NamedTemporaryFile(suffix=".sarif", delete=False) as tf:
            tf.write(b"{}")
            sarif_path = tf.name
        try:
            with patch(
                "sast_mcp_server.server._dd_upload",
                AsyncMock(return_value={"test": 99}),
            ):
                result = await upload_to_defectdojo(sarif_path, engagement_id=5)
            assert "✅" in result
            assert "99" in result
        finally:
            os.remove(sarif_path)

    @pytest.mark.asyncio
    async def test_github_missing_file(self):
        result = await upload_to_github(
            "/nonexistent.sarif", "owner/repo", "abc", "refs/heads/main"
        )
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_github_surfaces_integration_error(self):
        with tempfile.NamedTemporaryFile(suffix=".sarif", delete=False) as tf:
            tf.write(b"{}")
            sarif_path = tf.name
        try:
            with patch(
                "sast_mcp_server.server._gh_upload",
                AsyncMock(side_effect=IntegrationError("Invalid repo 'x'")),
            ):
                result = await upload_to_github(
                    sarif_path, "x", "abc", "refs/heads/main"
                )
            assert "GitHub upload failed" in result
        finally:
            os.remove(sarif_path)


# --------------------------------------------------------------------------
# v0.6.0: AI Patch Generation Tools
# --------------------------------------------------------------------------
class TestPatchTools:
    @pytest.mark.asyncio
    async def test_generate_fix_prompt_invalid_dir(self):
        result = await generate_fix_prompt("/nonexistent/abc", "hash123")
        assert "not a valid directory" in result

    @pytest.mark.asyncio
    async def test_generate_fix_prompt_negative_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await generate_fix_prompt(temp_dir, "hash123", context_window=-1)
        assert "context_window must be >= 0" in result

    @pytest.mark.asyncio
    async def test_generate_fix_prompt_unknown_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await generate_fix_prompt(temp_dir, "missinghash")
        assert "No cached finding" in result

    @pytest.mark.asyncio
    async def test_apply_patch_invalid_dir(self):
        result = await apply_patch("/nonexistent/abc", "some patch")
        assert "not a valid directory" in result

    @pytest.mark.asyncio
    async def test_apply_patch_delegates_and_formats(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "sast_mcp_server.server.apply_unified_diff",
            AsyncMock(return_value=(True, "Patch applied successfully.")),
        ):
            result = await apply_patch(temp_dir, "--- a/x\n+++ b/x\n")
        assert "✅" in result
        assert "applied" in result

    @pytest.mark.asyncio
    async def test_apply_patch_failure_formats(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "sast_mcp_server.server.apply_unified_diff",
            AsyncMock(return_value=(False, "patch does not apply")),
        ):
            result = await apply_patch(temp_dir, "bad", check_only=True)
        assert "❌" in result
        assert "check failed" in result
