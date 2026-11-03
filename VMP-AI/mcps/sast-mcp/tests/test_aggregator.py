"""Tests for multi-scanner aggregation."""

from unittest.mock import AsyncMock, patch

import pytest

from sast_mcp_server.aggregator import _deduplicate_findings, run_all_scanners
from sast_mcp_server.models import (
    ConfidenceLevel,
    DataFlowStep,
    Finding,
    SeverityLevel,
)


def _make_finding(
    scanner: str = "bandit",
    title: str = "test-rule",
    finding_hash: str = "hash_1",
    severity: SeverityLevel = SeverityLevel.HIGH,
    data_flow: list | None = None,
) -> Finding:
    """Create a test Finding."""
    return Finding(
        scanner=scanner,
        title=title,
        message="Test issue",
        file="test.py",
        line_start=1,
        line_end=5,
        severity=severity,
        confidence=ConfidenceLevel.HIGH,
        context="def vulnerable(): pass",
        finding_hash=finding_hash,
        language="python",
        data_flow=data_flow or [],
    )


class TestDeduplication:
    def test_unique_findings_preserved(self):
        """Test that unique findings are not removed."""
        findings = [
            _make_finding(finding_hash="hash_1"),
            _make_finding(finding_hash="hash_2"),
            _make_finding(finding_hash="hash_3"),
        ]
        result = _deduplicate_findings(findings)
        assert len(result) == 3

    def test_duplicate_hash_deduplicated(self):
        """Test that duplicate hashes are merged into one finding."""
        findings = [
            _make_finding(scanner="bandit", finding_hash="same_hash"),
            _make_finding(scanner="semgrep", finding_hash="same_hash"),
        ]
        result = _deduplicate_findings(findings)
        assert len(result) == 1

    def test_keeps_highest_severity(self):
        """Test that deduplication keeps the finding with highest severity."""
        findings = [
            _make_finding(
                scanner="bandit", finding_hash="hash_x", severity=SeverityLevel.MEDIUM
            ),
            _make_finding(
                scanner="semgrep", finding_hash="hash_x", severity=SeverityLevel.CRITICAL
            ),
        ]
        result = _deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].severity == SeverityLevel.CRITICAL
        assert result[0].scanner == "semgrep"

    def test_prefers_data_flow_on_equal_severity(self):
        """Test that when severity is equal, the finding with data flow wins."""
        flow = [DataFlowStep(file="a.py", line=1, code_snippet="source")]
        findings = [
            _make_finding(scanner="bandit", finding_hash="hash_y", data_flow=[]),
            _make_finding(scanner="bearer", finding_hash="hash_y", data_flow=flow),
        ]
        result = _deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].scanner == "bearer"
        assert len(result[0].data_flow) == 1

    def test_empty_list(self):
        """Test deduplication of empty list."""
        assert _deduplicate_findings([]) == []


class TestRunAllScanners:
    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Test that all available scanners are run."""
        mock_scanner_1 = AsyncMock()
        mock_scanner_1.check_dependency = AsyncMock()
        mock_scanner_1.scan = AsyncMock(
            return_value=[_make_finding(scanner="scanner1", finding_hash="h1")]
        )

        mock_scanner_2 = AsyncMock()
        mock_scanner_2.check_dependency = AsyncMock()
        mock_scanner_2.scan = AsyncMock(
            return_value=[_make_finding(scanner="scanner2", finding_hash="h2")]
        )

        # Mock factory to only return our two test scanners
        with patch(
            "sast_mcp_server.aggregator.ScannerFactory.list_scanners",
            return_value=["scanner1", "scanner2"],
        ), patch(
            "sast_mcp_server.aggregator.ScannerFactory.get_scanner",
            side_effect=[mock_scanner_1, mock_scanner_2],
        ):
            findings, used, skipped = await run_all_scanners(".")

        assert len(findings) == 2
        assert "scanner1" in used
        assert "scanner2" in used
        assert skipped == []

    @pytest.mark.asyncio
    async def test_unavailable_scanners_skipped(self):
        """Test that scanners failing dependency check are skipped."""
        mock_available = AsyncMock()
        mock_available.check_dependency = AsyncMock()
        mock_available.scan = AsyncMock(
            return_value=[_make_finding(scanner="available", finding_hash="h1")]
        )

        mock_unavailable = AsyncMock()
        mock_unavailable.check_dependency = AsyncMock(
            side_effect=RuntimeError("Not installed")
        )

        with patch(
            "sast_mcp_server.aggregator.ScannerFactory.list_scanners",
            return_value=["available", "unavailable"],
        ), patch(
            "sast_mcp_server.aggregator.ScannerFactory.get_scanner",
            side_effect=[mock_available, mock_unavailable],
        ):
            findings, used, skipped = await run_all_scanners(".")

        assert len(findings) == 1
        assert "available" in used
        assert "unavailable" in skipped

    @pytest.mark.asyncio
    async def test_scanner_failure_doesnt_crash(self):
        """Test that a scanner error during scan doesn't crash the aggregation."""
        mock_ok = AsyncMock()
        mock_ok.check_dependency = AsyncMock()
        mock_ok.scan = AsyncMock(
            return_value=[_make_finding(scanner="ok", finding_hash="h1")]
        )

        mock_broken = AsyncMock()
        mock_broken.check_dependency = AsyncMock()
        mock_broken.scan = AsyncMock(side_effect=RuntimeError("Scan crashed"))

        with patch(
            "sast_mcp_server.aggregator.ScannerFactory.list_scanners",
            return_value=["ok", "broken"],
        ), patch(
            "sast_mcp_server.aggregator.ScannerFactory.get_scanner",
            side_effect=[mock_ok, mock_broken],
        ):
            findings, used, skipped = await run_all_scanners(".")

        assert len(findings) == 1
        assert "ok" in used
        assert "broken" in skipped

    @pytest.mark.asyncio
    async def test_results_sorted_by_severity(self):
        """Test that results are sorted CRITICAL → HIGH → MEDIUM → LOW."""
        mock_scanner = AsyncMock()
        mock_scanner.check_dependency = AsyncMock()
        mock_scanner.scan = AsyncMock(
            return_value=[
                _make_finding(finding_hash="h1", severity=SeverityLevel.LOW),
                _make_finding(finding_hash="h2", severity=SeverityLevel.CRITICAL),
                _make_finding(finding_hash="h3", severity=SeverityLevel.MEDIUM),
            ]
        )

        with patch(
            "sast_mcp_server.aggregator.ScannerFactory.list_scanners",
            return_value=["scanner"],
        ), patch(
            "sast_mcp_server.aggregator.ScannerFactory.get_scanner",
            return_value=mock_scanner,
        ):
            findings, used, skipped = await run_all_scanners(".")

        assert findings[0].severity == SeverityLevel.CRITICAL
        assert findings[1].severity == SeverityLevel.MEDIUM
        assert findings[2].severity == SeverityLevel.LOW

    @pytest.mark.asyncio
    async def test_no_scanners_available(self):
        """Test behavior when no scanners are installed."""
        mock_scanner = AsyncMock()
        mock_scanner.check_dependency = AsyncMock(
            side_effect=RuntimeError("Not installed")
        )

        with patch(
            "sast_mcp_server.aggregator.ScannerFactory.list_scanners",
            return_value=["scanner"],
        ), patch(
            "sast_mcp_server.aggregator.ScannerFactory.get_scanner",
            return_value=mock_scanner,
        ):
            findings, used, skipped = await run_all_scanners(".")

        assert findings == []
        assert used == []
        assert "scanner" in skipped
