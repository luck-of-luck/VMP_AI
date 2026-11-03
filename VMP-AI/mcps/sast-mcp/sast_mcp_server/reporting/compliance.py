"""Compliance posture mapping: findings → OWASP / SANS / PCI / CIS frameworks.

This module owns the canonical framework category lists (also consumed by
``prompts.py``) and maps findings into them using each finding's ``owasp_category``
and ``cwe`` metadata, so a scan can be reported against a compliance framework.
"""

import re

from sast_mcp_server.models import Finding, SeverityLevel


# ---------------------------------------------------------------------------
# Canonical framework category lists (single source of truth).
# ---------------------------------------------------------------------------
def owasp_top_10_categories() -> list[str]:
    """OWASP Top 10 (2021) categories."""
    return [
        "A01: Broken Access Control",
        "A02: Cryptographic Failures",
        "A03: Injection",
        "A04: Insecure Design",
        "A05: Security Misconfiguration",
        "A06: Vulnerable and Outdated Components",
        "A07: Identification and Authentication Failures",
        "A08: Software and Data Integrity Failures",
        "A09: Security Logging and Monitoring Failures",
        "A10: Server-Side Request Forgery (SSRF)",
    ]


def sans_top_25_categories() -> list[str]:
    """SANS/CWE Top 25 Most Dangerous Software Weaknesses."""
    return [
        "CWE-787: Out-of-bounds Write",
        "CWE-79: Cross-site Scripting (XSS)",
        "CWE-89: SQL Injection",
        "CWE-416: Use After Free",
        "CWE-78: OS Command Injection",
        "CWE-20: Improper Input Validation",
        "CWE-125: Out-of-bounds Read",
        "CWE-22: Path Traversal",
        "CWE-352: Cross-Site Request Forgery (CSRF)",
        "CWE-434: Unrestricted Upload",
    ]


def pci_dss_categories() -> list[str]:
    """PCI DSS v4.0 relevant requirements."""
    return [
        "Req 6.2: Secure Development — no known vulns in custom code",
        "Req 6.3: Security Vulnerabilities — identify and manage",
        "Req 6.4: Public-facing Web Applications — protected from attacks",
        "Req 6.5: Change Management — secure coding practices",
        "Req 8.3: Strong Authentication — no hardcoded credentials",
        "Req 10.2: Audit Logging — security-relevant events logged",
    ]


def cis_benchmark_categories() -> list[str]:
    """CIS Benchmark categories for infrastructure."""
    return [
        "Identity and Access Management",
        "Logging and Monitoring",
        "Networking",
        "Storage",
        "Compute/VMs",
        "Databases",
        "Kubernetes",
        "Docker/Container Security",
    ]


# Map a CWE id (int) → OWASP 2021 category prefix. Covers the common weaknesses;
# anything unmapped falls into "Unmapped".
_CWE_TO_OWASP: dict[int, str] = {
    # A01 Broken Access Control
    22: "A01", 284: "A01", 285: "A01", 639: "A01", 352: "A01",
    # A02 Cryptographic Failures
    327: "A02", 328: "A02", 330: "A02", 326: "A02", 759: "A02", 798: "A02",
    # A03 Injection
    79: "A03", 89: "A03", 78: "A03", 77: "A03", 90: "A03", 91: "A03",
    94: "A03", 564: "A03",
    # A04 Insecure Design
    209: "A04", 256: "A04", 501: "A04",
    # A05 Security Misconfiguration
    16: "A05", 611: "A05", 776: "A05", 1004: "A05",
    # A06 Vulnerable and Outdated Components
    1035: "A06", 1104: "A06", 937: "A06",
    # A07 Identification and Authentication Failures
    287: "A07", 384: "A07", 620: "A07", 613: "A07",
    # A08 Software and Data Integrity Failures
    502: "A08", 829: "A08", 494: "A08",
    # A09 Logging/Monitoring Failures
    532: "A09", 778: "A09",
    # A10 SSRF
    918: "A10",
}


def _cwe_ints(cwe: str) -> list[int]:
    return [int(n) for n in re.findall(r"(\d+)", cwe or "")]


def _owasp_bucket(finding: Finding) -> str:
    """Return the OWASP category label a finding maps to (or 'Unmapped')."""
    categories = owasp_top_10_categories()
    by_prefix = {c.split(":", 1)[0]: c for c in categories}

    # Prefer an explicit owasp_category like "A03:2021" or "A03".
    if finding.owasp_category:
        prefix = finding.owasp_category.split(":", 1)[0].strip().upper()
        if prefix in by_prefix:
            return by_prefix[prefix]

    for cwe_id in _cwe_ints(finding.cwe):
        mapped_prefix = _CWE_TO_OWASP.get(cwe_id)
        if mapped_prefix:
            return by_prefix[mapped_prefix]
    return "Unmapped"


def findings_to_compliance(findings: list[Finding], framework: str = "owasp") -> dict:
    """Bucket findings against a compliance framework.

    Returns a dict with ``framework``, ordered ``categories`` (each with its
    matched findings + counts), an ``unmapped`` count, and a ``total``.
    """
    framework = framework.lower().strip()

    if framework == "sans":
        labels = sans_top_25_categories()
        buckets: dict[str, list[Finding]] = {c: [] for c in labels}
        top25_ids = {int(m.group(1)): c for c in labels if (m := re.match(r"CWE-(\d+)", c))}
        unmapped = 0
        for f in findings:
            matched = False
            for cwe_id in _cwe_ints(f.cwe):
                if cwe_id in top25_ids:
                    buckets[top25_ids[cwe_id]].append(f)
                    matched = True
                    break
            if not matched:
                unmapped += 1
    elif framework == "owasp":
        labels = owasp_top_10_categories()
        buckets = {c: [] for c in labels}
        unmapped = 0
        for f in findings:
            label = _owasp_bucket(f)
            if label == "Unmapped":
                unmapped += 1
            else:
                buckets[label].append(f)
    elif framework in {"pci", "cis"}:
        labels = pci_dss_categories() if framework == "pci" else cis_benchmark_categories()
        # PCI/CIS don't map per-finding by CWE; report posture by counts only.
        buckets = {c: [] for c in labels}
        unmapped = len(findings)
    else:
        raise ValueError(f"Unknown framework '{framework}' (owasp/sans/pci/cis).")

    categories = [
        {
            "category": label,
            "count": len(items),
            "findings": items,
        }
        for label, items in buckets.items()
    ]
    return {
        "framework": framework,
        "categories": categories,
        "unmapped": unmapped,
        "total": len(findings),
    }


def compliance_to_markdown(report: dict, project: str = "") -> str:
    """Render a compliance report dict as a markdown posture summary."""
    framework = report["framework"].upper()
    lines = [f"### Compliance Report — {framework}"]
    if project:
        lines.append(f"**Project:** {project}")
    lines.append(f"**Total findings:** {report['total']}\n")

    for cat in report["categories"]:
        count = cat["count"]
        mark = "🔴" if count else "🟢"
        lines.append(f"#### {mark} {cat['category']} — {count}")
        for f in cat["findings"][:5]:
            sev = f.severity.value if isinstance(f.severity, SeverityLevel) else f.severity
            lines.append(f"- [{sev}] {f.title} — {f.file}:{f.line_start}")
        if count > 5:
            lines.append(f"  _(... and {count - 5} more)_")
    if report["unmapped"]:
        lines.append(f"\n**Unmapped findings:** {report['unmapped']}")
    return "\n".join(lines)
