"""VEX (Vulnerability Exploitability eXchange) statements.

A VEX statement records a triage *decision* about a vulnerability — whether the
software is actually affected, and why. We emit it as a CycloneDX 1.5
``vulnerabilities[].analysis`` block, which is the interoperable form consumed by
DefectDojo, Dependency-Track, and other supply-chain tools.

The agent (or a human) makes the call; this module just renders the decision in
a standard shape. Used by the ``triage_finding`` tool.
"""

from datetime import datetime, timezone

from sast_mcp_server.models import Finding

# Disposition keyword (what the agent passes) → CycloneDX analysis.state value.
# https://cyclonedx.org/docs/1.5/json/#vulnerabilities_items_analysis_state
_STATE_MAP = {
    "exploitable": "exploitable",
    "affected": "exploitable",
    "in_triage": "in_triage",
    "resolved": "resolved",
    "false_positive": "false_positive",
    "not_affected": "not_affected",
}

# CycloneDX analysis.justification vocabulary (only valid when state=not_affected).
_VALID_JUSTIFICATIONS = {
    "code_not_present",
    "code_not_reachable",
    "requires_configuration",
    "requires_dependency",
    "requires_environment",
    "protected_by_compiler",
    "protected_at_runtime",
    "protected_at_perimeter",
    "protected_by_mitigating_control",
}

# Dispositions that mean "suppress this finding from future scans".
SUPPRESSING_DISPOSITIONS = {"false_positive", "not_affected", "resolved"}


def normalize_disposition(disposition: str) -> str | None:
    """Map a free-form disposition to a canonical CycloneDX state, or None."""
    return _STATE_MAP.get(disposition.lower().strip())


def build_vex_statement(
    finding: Finding,
    disposition: str,
    justification: str = "",
    detail: str = "",
) -> dict:
    """Render a single CycloneDX 1.5 vulnerability entry carrying a VEX analysis.

    Args:
        finding: The finding being triaged.
        disposition: A keyword from :data:`_STATE_MAP` (e.g. ``not_affected``).
        justification: Optional CycloneDX justification (used when not_affected).
        detail: Free-text explanation recorded on the analysis.

    Returns:
        A CycloneDX ``vulnerabilities[]`` dict with an ``analysis`` block.
    """
    state = normalize_disposition(disposition) or "in_triage"
    analysis: dict = {
        "state": state,
        "response": [],
    }
    just = justification.lower().strip()
    if state == "not_affected" and just in _VALID_JUSTIFICATIONS:
        analysis["justification"] = just
    if detail:
        analysis["detail"] = detail

    vuln_id = finding.title.split()[0] if finding.title else finding.finding_hash[:12]
    entry: dict = {
        "id": vuln_id,
        "bom-ref": finding.finding_hash,
        "source": {"name": finding.scanner},
        "analysis": analysis,
        "properties": [
            {"name": "sast:finding_hash", "value": finding.finding_hash},
            {"name": "sast:file", "value": finding.file},
            {"name": "sast:timestamp", "value": datetime.now(timezone.utc).isoformat()},
        ],
    }
    if finding.message:
        entry["description"] = finding.message
    return entry


def findings_to_vex(
    statements: list[dict],
    version: str = "0.8.0",
) -> dict:
    """Wrap one or more VEX vulnerability entries in a CycloneDX 1.5 document."""
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [
                {"vendor": "sast-mcp-server", "name": "sast-mcp-server", "version": version}
            ],
        },
        "vulnerabilities": statements,
    }
