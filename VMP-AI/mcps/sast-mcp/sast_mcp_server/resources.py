"""MCP Resources — read-only context data for AI agents.

Exposes scanner info, server config, cached scan results, and
a security dashboard as MCP Resources that agents can fetch
without running a full scan.
"""

import json
import logging
import os

from sast_mcp_server.auth import AuthProvider
from sast_mcp_server.cache import ScanCache
from sast_mcp_server.enrichment.ignore_manager import IgnoreManager
from sast_mcp_server.scanners.factory import SCANNER_INFO, ScannerFactory

logger = logging.getLogger(__name__)

# Configurable scan timeout
SCAN_TIMEOUT = int(os.environ.get("SAST_MCP_TIMEOUT", "300"))


def register_resources(mcp) -> None:
    """Register all MCP resources on the given FastMCP server instance.

    Args:
        mcp: The FastMCP server instance.
    """

    @mcp.resource("sast://scanners")
    def get_scanner_info() -> str:
        """List all available scanners, their install status, and languages."""
        output = []
        for name in ScannerFactory.list_scanners():
            info = SCANNER_INFO.get(name, {})
            output.append({
                "name": name,
                "description": info.get("description", ""),
                "languages": info.get("languages", ""),
                "install": info.get("install", ""),
            })
        return json.dumps(output, indent=2)

    @mcp.resource("sast://config")
    def get_server_config() -> str:
        """Current server configuration."""
        auth = AuthProvider()
        config = {
            "version": _get_version(),
            "scan_timeout": SCAN_TIMEOUT,
            "auth": auth.get_status(),
            "cache_ttl": int(
                os.environ.get("SAST_MCP_CACHE_TTL", "86400")
            ),
            "log_level": os.environ.get("SAST_MCP_LOG_LEVEL", "INFO"),
            "registered_scanners": ScannerFactory.list_scanners(),
        }
        return json.dumps(config, indent=2)

    @mcp.resource("sast://cache/{target_path}/latest")
    def get_latest_scan(target_path: str) -> str:
        """Get the most recent cached scan results for a project."""
        if not os.path.exists(target_path):
            return json.dumps({"error": f"Path '{target_path}' not found"})

        cache = ScanCache(target_path)
        scans = cache.list_scans()
        if not scans:
            return json.dumps({
                "message": "No cached scans found for this project.",
                "target_path": target_path,
            })

        # Return metadata for all cached scans
        return json.dumps(
            [
                {
                    "cache_id": s.cache_id,
                    "scanner": s.scanner,
                    "timestamp": s.timestamp,
                    "tag": s.tag,
                    "finding_count": s.finding_count,
                    "min_severity": s.min_severity,
                }
                for s in scans
            ],
            indent=2,
        )

    @mcp.resource("sast://cache/{target_path}/baseline/{tag}")
    def get_baseline(target_path: str, tag: str) -> str:
        """Get a named baseline scan for comparison."""
        if not os.path.exists(target_path):
            return json.dumps({"error": f"Path '{target_path}' not found"})

        cache = ScanCache(target_path)

        # Try each scanner for this tag
        for scanner_name in ScannerFactory.list_scanners():
            baseline = cache.load_by_tag(scanner_name, tag)
            if baseline:
                return json.dumps({
                    "cache_id": baseline.cache_id,
                    "scanner": baseline.scanner,
                    "timestamp": baseline.timestamp,
                    "tag": baseline.tag,
                    "finding_count": baseline.finding_count,
                    "findings_summary": _summarize_findings(
                        baseline.findings
                    ),
                })

        return json.dumps({
            "message": f"No baseline with tag '{tag}' found.",
            "target_path": target_path,
        })

    @mcp.resource("sast://ignore/{target_path}")
    def get_ignored_findings(target_path: str) -> str:
        """List all ignored findings for a project."""
        if not os.path.exists(target_path):
            return json.dumps({"error": f"Path '{target_path}' not found"})

        mgr = IgnoreManager(target_path)
        ignored = mgr.list_ignored()
        return json.dumps({
            "target_path": target_path,
            "count": len(ignored),
            "ignored": ignored,
        }, indent=2)

    @mcp.resource("sast://dashboard/{target_path}")
    def get_security_dashboard(target_path: str) -> str:
        """Security posture dashboard with severity distribution and trends."""
        if not os.path.exists(target_path):
            return json.dumps({"error": f"Path '{target_path}' not found"})

        cache = ScanCache(target_path)
        all_scans = cache.list_scans()

        # Severity distribution from the latest scan per scanner
        severity_dist = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        scanner_coverage: dict[str, str] = {}
        total_findings = 0

        seen_scanners: set[str] = set()
        for scan_meta in all_scans:
            if scan_meta.scanner in seen_scanners:
                continue
            seen_scanners.add(scan_meta.scanner)

            scanner_coverage[scan_meta.scanner] = scan_meta.timestamp
            total_findings += scan_meta.finding_count

            # Load full scan to get severity breakdown
            full_scan = cache.load_latest(scan_meta.scanner)
            if full_scan:
                for finding in full_scan.findings:
                    sev = finding.severity.value
                    if sev in severity_dist:
                        severity_dist[sev] += 1

        # Ignored count
        mgr = IgnoreManager(target_path)
        ignored_count = len(mgr.list_ignored())

        dashboard = {
            "target_path": target_path,
            "total_findings": total_findings,
            "severity_distribution": severity_dist,
            "scanner_coverage": scanner_coverage,
            "ignored_findings": ignored_count,
            "cached_scans": len(all_scans),
        }

        return json.dumps(dashboard, indent=2)


def _get_version() -> str:
    """Get the current server version."""
    try:
        from sast_mcp_server import __version__
        return __version__
    except ImportError:
        return "unknown"


def _summarize_findings(findings: list) -> dict:
    """Create a summary of findings by severity."""
    summary: dict[str, int] = {}
    for f in findings:
        sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        summary[sev] = summary.get(sev, 0) + 1
    return summary
