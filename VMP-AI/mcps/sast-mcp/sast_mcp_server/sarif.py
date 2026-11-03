"""SARIF 2.1.0 export and parsing for interoperability with CI/CD platforms.

Supports:
- Converting Finding objects to SARIF 2.1.0 format (for CI/CD integration)
- Parsing SARIF 2.1.0 documents into Finding objects (used by CodeQL scanner)

SARIF spec: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

import logging

from sast_mcp_server.enrichment.ast_context import get_function_context
from sast_mcp_server.models import (
    ConfidenceLevel,
    DataFlowStep,
    Finding,
    SeverityLevel,
)

logger = logging.getLogger(__name__)

# SARIF schema URI
SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json"
SARIF_VERSION = "2.1.0"

# Our SeverityLevel → SARIF result.level
_SEVERITY_TO_SARIF_LEVEL = {
    SeverityLevel.CRITICAL: "error",
    SeverityLevel.HIGH: "error",
    SeverityLevel.MEDIUM: "warning",
    SeverityLevel.LOW: "note",
}

# SARIF result.level → our SeverityLevel
_SARIF_LEVEL_TO_SEVERITY = {
    "error": "HIGH",
    "warning": "MEDIUM",
    "note": "LOW",
    "none": "LOW",
}


def findings_to_sarif(
    findings: list[Finding],
    scanner_name: str,
    version: str = "0.3.0",
) -> dict:
    """Convert a list of Finding objects to a SARIF 2.1.0 document.

    Args:
        findings: List of Finding objects to convert.
        scanner_name: Name of the scanner that produced the findings.
        version: Version string for the tool driver.

    Returns:
        A dict representing a valid SARIF 2.1.0 JSON document.
    """
    # Collect unique rules and the CWE taxonomy referenced across findings.
    rules_map: dict[str, dict] = {}
    sarif_results = []
    cwe_taxa: dict[str, dict] = {}

    for finding in findings:
        rule_id = finding.title
        cwe_ids = _parse_cwe_ids(finding.cwe)

        # Build rule entry if not seen before
        if rule_id not in rules_map:
            rule_entry: dict = {
                "id": rule_id,
                "shortDescription": {"text": rule_id},
                "defaultConfiguration": {
                    "level": _SEVERITY_TO_SARIF_LEVEL.get(
                        finding.severity, "warning"
                    )
                },
            }
            if finding.message:
                rule_entry["fullDescription"] = {"text": finding.message}

            # Rule-level properties consumed by dashboards (GitHub etc.).
            rule_props: dict = {}
            tags = list(cwe_ids)
            if finding.owasp_category:
                tags.append(finding.owasp_category)
            if tags:
                rule_props["tags"] = tags
            if finding.cvss_score is not None:
                # GitHub Code Scanning ranks findings by this string.
                rule_props["security-severity"] = str(finding.cvss_score)
            if rule_props:
                rule_entry["properties"] = rule_props
            if finding.references:
                rule_entry["helpUri"] = finding.references[0]
            rules_map[rule_id] = rule_entry

        # Build SARIF result
        result_props: dict = {
            "scanner": finding.scanner,
            "confidence": finding.confidence.value,
        }
        if finding.cwe:
            result_props["cwe"] = finding.cwe
        if finding.owasp_category:
            result_props["owasp"] = finding.owasp_category
        if finding.cvss_score is not None:
            result_props["cvss_score"] = finding.cvss_score
        if finding.cvss_vector:
            result_props["cvss_vector"] = finding.cvss_vector
        if finding.references:
            result_props["references"] = list(finding.references)
        if finding.remediation:
            result_props["remediation"] = finding.remediation

        sarif_result: dict = {
            "ruleId": rule_id,
            "level": _SEVERITY_TO_SARIF_LEVEL.get(finding.severity, "warning"),
            "message": {"text": finding.message or finding.title},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": finding.file.replace("\\", "/"),
                        },
                        "region": {
                            "startLine": max(1, finding.line_start),
                            "endLine": max(1, finding.line_end),
                        },
                    }
                }
            ],
            "fingerprints": {
                "primaryLocationHash": finding.finding_hash,
            },
            "properties": result_props,
        }

        # Reference CWE taxa (and register them in the run taxonomy).
        if cwe_ids:
            sarif_result["taxa"] = [
                {"id": cid, "toolComponent": {"name": "CWE"}} for cid in cwe_ids
            ]
            for cid in cwe_ids:
                cwe_taxa.setdefault(cid, {"id": cid})

        # Add code flows for data flow traces
        if finding.data_flow:
            thread_flow_locations = []
            for step in finding.data_flow:
                thread_flow_locations.append(
                    {
                        "location": {
                            "physicalLocation": {
                                "artifactLocation": {
                                    "uri": step.file.replace("\\", "/"),
                                },
                                "region": {
                                    "startLine": step.line,
                                },
                            },
                            "message": {"text": step.code_snippet},
                        }
                    }
                )

            sarif_result["codeFlows"] = [
                {
                    "threadFlows": [
                        {"locations": thread_flow_locations}
                    ]
                }
            ]

        sarif_results.append(sarif_result)

    # Build the SARIF document
    run: dict = {
        "tool": {
            "driver": {
                "name": f"sast-mcp-server ({scanner_name})",
                "version": version,
                "informationUri": "https://github.com/abdellah/sast-mcp-server",
                "rules": list(rules_map.values()),
            }
        },
        "results": sarif_results,
    }

    # Emit a CWE taxonomy when any finding carried a CWE id.
    if cwe_taxa:
        run["taxonomies"] = [
            {
                "name": "CWE",
                "organization": "MITRE",
                "shortDescription": {"text": "Common Weakness Enumeration"},
                "taxa": list(cwe_taxa.values()),
            }
        ]

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [run],
    }


def _parse_cwe_ids(cwe: str) -> list[str]:
    """Normalize a free-form CWE string into canonical ``CWE-<n>`` ids."""
    if not cwe:
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for token in cwe.replace(";", ",").split(","):
        token = token.strip()
        if not token:
            continue
        # Accept "CWE-89", "89", or "CWE-89: SQL Injection".
        head = token.split(":", 1)[0].strip().upper()
        digits = "".join(ch for ch in head if ch.isdigit())
        if digits:
            canonical = f"CWE-{digits}"
            if canonical not in seen:
                seen.add(canonical)
                ids.append(canonical)
    return ids


def parse_sarif(sarif_data: dict, scanner_name: str = "codeql") -> list[Finding]:
    """Parse a SARIF 2.1.0 document into Finding objects.

    Used by CodeQL scanner and potentially other SARIF-producing tools.

    Args:
        sarif_data: A dict representing a SARIF 2.1.0 JSON document.
        scanner_name: Scanner name to assign to parsed findings.

    Returns:
        List of Finding objects.
    """
    findings: list[Finding] = []

    for run in sarif_data.get("runs", []):
        # Build a rule lookup for metadata
        rules: dict[str, dict] = {}
        driver = run.get("tool", {}).get("driver", {})
        for rule in driver.get("rules", []):
            rules[rule.get("id", "")] = rule

        for result in run.get("results", []):
            rule_id = result.get("ruleId", "unknown")
            level = result.get("level", "warning")
            message = result.get("message", {}).get("text", "")

            # Map SARIF level to our severity
            severity_str = _SARIF_LEVEL_TO_SEVERITY.get(level, "MEDIUM")

            # Extract location
            locations = result.get("locations", [])
            file_path = ""
            line_start = 1

            if locations:
                phys = locations[0].get("physicalLocation", {})
                artifact = phys.get("artifactLocation", {})
                file_path = artifact.get("uri", artifact.get("uriBaseId", ""))
                region = phys.get("region", {})
                line_start = region.get("startLine", 1)

            # Try to get function context
            context_code, ctx_start, ctx_end = get_function_context(
                file_path, line_start
            )

            # Extract confidence from properties or rule metadata
            properties = result.get("properties", {})
            confidence_str = properties.get("confidence", "MEDIUM").upper()
            if confidence_str not in ConfidenceLevel.__members__:
                confidence_str = "MEDIUM"

            # Enrich rule info from rules array
            rule_meta = rules.get(rule_id, {})
            if not message and rule_meta:
                desc = rule_meta.get("fullDescription") or rule_meta.get("shortDescription") or {}
                message = desc.get("text", rule_id) if isinstance(desc, dict) else rule_id

            # Parse data flows / code flows
            data_flow: list[DataFlowStep] = []
            for code_flow in result.get("codeFlows", []):
                for thread_flow in code_flow.get("threadFlows", []):
                    for loc_wrapper in thread_flow.get("locations", []):
                        loc = loc_wrapper.get("location", {})
                        phys_loc = loc.get("physicalLocation", {})
                        flow_file = phys_loc.get("artifactLocation", {}).get("uri", "")
                        flow_line = phys_loc.get("region", {}).get("startLine", 0)
                        flow_msg = loc.get("message", {}).get("text", "")
                        data_flow.append(
                            DataFlowStep(
                                file=flow_file,
                                line=flow_line,
                                code_snippet=flow_msg,
                            )
                        )

            # Detect language from file extension
            language = _detect_language_from_path(file_path)

            # Generate stable hash
            from sast_mcp_server.scanners.base import BaseScanner
            finding_hash = BaseScanner.generate_hash(file_path, rule_id, context_code)

            # Extract fingerprint if available
            fingerprints = result.get("fingerprints", {})
            if "primaryLocationHash" in fingerprints:
                finding_hash = fingerprints["primaryLocationHash"]

            cvss_score = properties.get("cvss_score")
            if not isinstance(cvss_score, (int, float)):
                cvss_score = None

            findings.append(
                Finding(
                    scanner=scanner_name,
                    title=rule_id,
                    message=message,
                    file=file_path,
                    line_start=ctx_start,
                    line_end=ctx_end,
                    severity=SeverityLevel(severity_str)
                    if severity_str in SeverityLevel.__members__
                    else SeverityLevel.MEDIUM,
                    confidence=ConfidenceLevel(confidence_str),
                    context=context_code,
                    language=language,
                    finding_hash=finding_hash,
                    data_flow=data_flow,
                    cwe=str(properties.get("cwe", "")),
                    cvss_score=float(cvss_score) if cvss_score is not None else None,
                    cvss_vector=str(properties.get("cvss_vector", "")),
                    owasp_category=str(properties.get("owasp", "")),
                    references=list(properties.get("references", []))
                    if isinstance(properties.get("references"), list)
                    else [],
                    remediation=str(properties.get("remediation", "")),
                )
            )

    return findings


def _detect_language_from_path(file_path: str) -> str:
    """Infer language from file extension."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rb": "ruby",
        ".c": "c",
        ".cpp": "cpp",
        ".cs": "csharp",
        ".swift": "swift",
        ".kt": "kotlin",
        ".rs": "rust",
        ".php": "php",
    }
    for ext, lang in ext_map.items():
        if file_path.endswith(ext):
            return lang
    return ""
