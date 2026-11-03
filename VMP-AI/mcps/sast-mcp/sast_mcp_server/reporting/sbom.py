"""CycloneDX export for SAST MCP Server.

Produces a CycloneDX 1.5 document carrying the discovered ``vulnerabilities``
(a Vulnerability Disclosure Report / VEX-style BOM). When findings come from
SCA scanners the affected packages are also emitted as ``components`` so the
document doubles as a lightweight dependency SBOM.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sast_mcp_server.models import Finding, SeverityLevel

logger = logging.getLogger(__name__)

CYCLONEDX_SPEC_VERSION = "1.5"

# Our severity → CycloneDX rating severity vocabulary.
_CDX_SEVERITY = {
    SeverityLevel.CRITICAL: "critical",
    SeverityLevel.HIGH: "high",
    SeverityLevel.MEDIUM: "medium",
    SeverityLevel.LOW: "low",
}

# Scanners whose findings represent dependency vulnerabilities (SCA).
_SCA_SCANNERS = {"osv-scanner", "trivy"}

_PACKAGE_RE = re.compile(r"Package:\s*([^\s@]+)@([^\s\)]+)")


def _parse_package(finding: Finding) -> tuple[str, str] | None:
    """Best-effort extraction of (name, version) from an SCA finding's context."""
    match = _PACKAGE_RE.search(finding.context or "")
    if match:
        return match.group(1), match.group(2)
    return None


def _cwe_ints(cwe: str) -> list[int]:
    """Extract integer CWE ids from a free-form CWE string."""
    return [int(n) for n in re.findall(r"(\d+)", cwe or "")]


def _vuln_id(finding: Finding) -> str:
    """Derive the vulnerability identifier (the CVE/GHSA id when present)."""
    token = finding.title.split()[0] if finding.title else ""
    if token and (token.upper().startswith(("CVE-", "GHSA-")) or token[0].isalpha()):
        return token
    return finding.title or finding.finding_hash[:12]


async def syft_cyclonedx_components(
    target_path: str, timeout: int = 120
) -> list[dict] | None:
    """Return the CycloneDX ``components`` array produced by Syft, or None.

    When Syft is installed, this yields a *complete* dependency inventory
    (including components with no known vulnerability) — a true SBOM rather than
    the findings-derived list. Returns None if Syft is unavailable or errors.
    """
    cmd = ["syft", f"dir:{target_path}", "-o", "cyclonedx-json"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except (FileNotFoundError, OSError, asyncio.TimeoutError):
        return None
    if proc.returncode != 0:
        return None
    try:
        doc = json.loads(stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    components = doc.get("components")
    return components if isinstance(components, list) else None


def findings_to_cyclonedx(
    findings: list[Finding],
    version: str = "0.7.0",
    sca_only: bool = True,
    extra_components: list[dict] | None = None,
) -> dict:
    """Convert findings into a CycloneDX 1.5 BOM dict.

    Args:
        findings: Findings to include.
        version: Tool version recorded in metadata.
        sca_only: If True (default), include only dependency (SCA) findings —
            the natural scope of an SBOM/VDR. If False, include every finding.
        extra_components: Optional component inventory (e.g. from Syft) merged in
            so the BOM lists dependencies even when they have no vulnerability.

    Returns:
        A CycloneDX 1.5 document as a dict.
    """
    selected = [
        f for f in findings if (not sca_only or f.scanner in _SCA_SCANNERS)
    ]

    components: dict[str, dict] = {}
    if extra_components:
        for comp in extra_components:
            ref = comp.get("bom-ref") or comp.get("purl") or comp.get("name")
            if ref:
                components.setdefault(str(ref), comp)
    vulnerabilities: list[dict] = []

    for finding in selected:
        bom_ref: str | None = None
        pkg = _parse_package(finding)
        if pkg:
            name, ver = pkg
            purl = f"pkg:generic/{name}@{ver}"
            bom_ref = purl
            components.setdefault(
                purl,
                {
                    "type": "library",
                    "name": name,
                    "version": ver,
                    "purl": purl,
                    "bom-ref": purl,
                },
            )

        rating: dict = {"severity": _CDX_SEVERITY.get(finding.severity, "unknown")}
        if finding.cvss_score is not None:
            rating["score"] = finding.cvss_score
        if finding.cvss_vector:
            rating["vector"] = finding.cvss_vector
            rating["method"] = "CVSSv3"

        vuln: dict = {
            "id": _vuln_id(finding),
            "source": {"name": finding.scanner},
            "ratings": [rating],
        }
        cwes = _cwe_ints(finding.cwe)
        if cwes:
            vuln["cwes"] = cwes
        if finding.message:
            vuln["description"] = finding.message
        if finding.remediation:
            vuln["recommendation"] = finding.remediation
        if finding.references:
            vuln["advisories"] = [{"url": url} for url in finding.references]
        if bom_ref:
            vuln["affects"] = [{"ref": bom_ref}]
        vulnerabilities.append(vuln)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": CYCLONEDX_SPEC_VERSION,
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [
                {"vendor": "sast-mcp-server", "name": "sast-mcp-server", "version": version}
            ],
        },
        "components": list(components.values()),
        "vulnerabilities": vulnerabilities,
    }
