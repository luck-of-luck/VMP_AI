"""SPDX 2.3 export.

Some organizations standardize on SPDX rather than CycloneDX. SPDX has no
first-class vulnerability object (that's CycloneDX/VEX territory); instead, SPDX
2.3 carries security data as package ``externalRefs`` of category ``SECURITY``.
We emit one package per affected dependency with advisory references, which is
the interoperable shape consumed by SPDX tooling.
"""

import re
from datetime import datetime, timezone

from sast_mcp_server.models import Finding

SPDX_VERSION = "SPDX-2.3"

# Scanners whose findings represent dependency vulnerabilities (SCA).
_SCA_SCANNERS = {"osv-scanner", "trivy", "grype"}
_PACKAGE_RE = re.compile(r"Package:\s*([^\s@]+)@([^\s\)]+)")


def _parse_package(finding: Finding) -> tuple[str, str] | None:
    match = _PACKAGE_RE.search(finding.context or "")
    if match:
        return match.group(1), match.group(2)
    return None


def _spdx_id(raw: str) -> str:
    """Sanitize a string into a valid SPDX element id fragment."""
    return re.sub(r"[^A-Za-z0-9.\-]", "-", raw) or "unknown"


def findings_to_spdx(
    findings: list[Finding],
    project: str = "scan-target",
    version: str = "0.8.0",
    sca_only: bool = True,
) -> dict:
    """Convert findings into an SPDX 2.3 document.

    Args:
        findings: Findings to include.
        project: Document name (usually the scanned project).
        version: Tool version recorded in creationInfo.
        sca_only: If True (default), include only dependency (SCA) findings.

    Returns:
        An SPDX 2.3 document as a dict.
    """
    selected = [
        f for f in findings if (not sca_only or f.scanner in _SCA_SCANNERS)
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    packages: dict[str, dict] = {}
    relationships: list[dict] = []

    for finding in selected:
        pkg = _parse_package(finding)
        if pkg:
            name, ver = pkg
        else:
            name = finding.title.split()[0] if finding.title else "unknown"
            ver = "NOASSERTION"
        pkg_id = f"SPDXRef-Package-{_spdx_id(name)}-{_spdx_id(ver)}"

        entry = packages.setdefault(
            pkg_id,
            {
                "name": name,
                "SPDXID": pkg_id,
                "versionInfo": ver,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "externalRefs": [],
            },
        )
        # Attach the vulnerability as a SECURITY external reference.
        vuln_id = finding.title.split()[0] if finding.title else finding.finding_hash[:12]
        ref_locator = finding.references[0] if finding.references else vuln_id
        entry["externalRefs"].append(
            {
                "referenceCategory": "SECURITY",
                "referenceType": "advisory",
                "referenceLocator": ref_locator,
            }
        )

    for pkg_id in packages:
        relationships.append(
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relatedSpdxElement": pkg_id,
                "relationshipType": "DESCRIBES",
            }
        )

    return {
        "spdxVersion": SPDX_VERSION,
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": project,
        "documentNamespace": f"https://sast-mcp-server/spdx/{_spdx_id(project)}-{now}",
        "creationInfo": {
            "created": now,
            "creators": [f"Tool: sast-mcp-server-{version}"],
        },
        "packages": list(packages.values()),
        "relationships": relationships,
    }
