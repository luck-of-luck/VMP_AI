"""Multi-scanner aggregation — run all installed scanners in parallel."""

import asyncio
import logging
import time

from sast_mcp_server import metrics
from sast_mcp_server.config import get_settings
from sast_mcp_server.models import SEVERITY_ORDER, Finding
from sast_mcp_server.scanners.factory import ScannerFactory

logger = logging.getLogger(__name__)

# Bounds the number of subprocess scanners running at once so a large scan
# fan-out can't exhaust CPU/file descriptors. Size 0 (config) = unlimited.
_max_concurrent = get_settings().max_concurrent_scans
_scan_semaphore: asyncio.Semaphore | None = (
    asyncio.Semaphore(_max_concurrent) if _max_concurrent > 0 else None
)


def _scanner_timeout(name: str, default_timeout: int) -> int:
    """Per-scanner timeout override from config, falling back to the default."""
    return get_settings().scanner_timeouts.get(name, default_timeout)


async def run_all_scanners(
    target_path: str,
    min_severity: str = "MEDIUM",
    min_confidence: str = "LOW",
    modified_files: set[str] | None = None,
    timeout: int = 300,
) -> tuple[list[Finding], list[str], list[str]]:
    """Run all installed scanners concurrently and return deduplicated findings.

    Args:
        target_path: The path to scan.
        min_severity: Minimum severity threshold.
        min_confidence: Minimum confidence threshold.
        modified_files: If set, only include findings in these files.
        timeout: Subprocess timeout per scanner.

    Returns:
        Tuple of:
        - Deduplicated list of findings, sorted by severity (CRITICAL first).
        - List of scanner names that were run successfully.
        - List of scanner names that were skipped (not installed or errored).
    """
    all_scanner_names = ScannerFactory.list_scanners()

    # Check which scanners are available
    available: list[tuple[str, object]] = []
    skipped: list[str] = []

    for name in all_scanner_names:
        scanner = ScannerFactory.get_scanner(name)
        try:
            await scanner.check_dependency()
            available.append((name, scanner))
        except RuntimeError as e:
            logger.info("Skipping %s (not installed): %s", name, e)
            skipped.append(name)

    if not available:
        return [], [], skipped

    # Run all available scanners concurrently
    async def _run_scanner(name: str, scanner) -> tuple[str, list[Finding] | Exception]:
        scanner_timeout = _scanner_timeout(name, timeout)
        start = time.time()
        try:
            if _scan_semaphore is not None:
                async with _scan_semaphore:
                    findings = await scanner.scan(
                        target_path,
                        min_severity=min_severity,
                        min_confidence=min_confidence,
                        modified_files=modified_files,
                        timeout=scanner_timeout,
                    )
            else:
                findings = await scanner.scan(
                    target_path,
                    min_severity=min_severity,
                    min_confidence=min_confidence,
                    modified_files=modified_files,
                    timeout=scanner_timeout,
                )
            metrics.inc("sast_scans_total", labels={"scanner": name})
            metrics.observe(
                "sast_scan_duration_seconds",
                time.time() - start,
                labels={"scanner": name},
            )
            return (name, findings)
        except Exception as e:
            logger.warning("Scanner %s failed: %s", name, e)
            metrics.inc("sast_scan_errors_total", labels={"scanner": name})
            return (name, e)

    tasks = [_run_scanner(name, scanner) for name, scanner in available]
    results = await asyncio.gather(*tasks)

    # Collect findings and track successes/failures
    all_findings: list[Finding] = []
    used_scanners: list[str] = []

    for name, result in results:
        if isinstance(result, Exception):
            logger.warning("Scanner %s returned error: %s", name, result)
            skipped.append(name)
        else:
            used_scanners.append(name)
            all_findings.extend(result)

    # Deduplicate by finding_hash, keeping the highest severity
    deduped = _deduplicate_findings(all_findings)

    # Sort by severity (CRITICAL first)
    deduped.sort(
        key=lambda f: SEVERITY_ORDER.get(f.severity, 0),
        reverse=True,
    )

    metrics.inc("sast_findings_total", value=len(deduped))
    return deduped, used_scanners, skipped


def _deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Deduplicate findings by finding_hash, keeping the highest severity.

    When the same vulnerability is found by multiple scanners, we keep the
    finding with the highest severity level. If equal severity, we prefer
    the finding with more context (e.g., data flow traces).
    """
    seen: dict[str, Finding] = {}

    for finding in findings:
        existing = seen.get(finding.finding_hash)
        if existing is None:
            seen[finding.finding_hash] = finding
            continue

        # Keep the one with higher severity (or richer data flow on a tie),
        # but salvage metadata from the loser so cross-scanner enrichment
        # (e.g. one scanner has CWE, another has CVSS) is not lost.
        existing_order = SEVERITY_ORDER.get(existing.severity, 0)
        new_order = SEVERITY_ORDER.get(finding.severity, 0)

        if new_order > existing_order or (
            new_order == existing_order and finding.data_flow and not existing.data_flow
        ):
            _merge_metadata(into=finding, frm=existing)
            seen[finding.finding_hash] = finding
        else:
            _merge_metadata(into=existing, frm=finding)

    return list(seen.values())


def _merge_metadata(into: Finding, frm: Finding) -> None:
    """Fill empty enterprise-metadata fields on ``into`` from ``frm``."""
    if not into.cwe and frm.cwe:
        into.cwe = frm.cwe
    if into.cvss_score is None and frm.cvss_score is not None:
        into.cvss_score = frm.cvss_score
    if not into.cvss_vector and frm.cvss_vector:
        into.cvss_vector = frm.cvss_vector
    if not into.owasp_category and frm.owasp_category:
        into.owasp_category = frm.owasp_category
    if not into.remediation and frm.remediation:
        into.remediation = frm.remediation
    if frm.references:
        seen = set(into.references)
        into.references.extend(r for r in frm.references if r not in seen)
