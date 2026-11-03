"""Typed data models for SAST findings."""

from dataclasses import dataclass, field
from enum import Enum


class SeverityLevel(str, Enum):
    """Severity levels for SAST findings."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConfidenceLevel(str, Enum):
    """Confidence levels for SAST findings."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


SEVERITY_ORDER = {
    SeverityLevel.LOW: 1,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.HIGH: 3,
    SeverityLevel.CRITICAL: 4,
}

CONFIDENCE_ORDER = {
    ConfidenceLevel.LOW: 1,
    ConfidenceLevel.MEDIUM: 2,
    ConfidenceLevel.HIGH: 3,
}


@dataclass
class DataFlowStep:
    """A single step in a data-flow trace."""
    file: str
    line: int
    code_snippet: str


@dataclass
class Finding:
    """A single SAST finding with all enrichment data."""
    scanner: str
    title: str
    message: str
    file: str
    line_start: int
    line_end: int
    severity: SeverityLevel
    confidence: ConfidenceLevel
    context: str
    finding_hash: str
    language: str = ""
    data_flow: list[DataFlowStep] = field(default_factory=list)

    # --- Enterprise reporting metadata (optional, populated when available) ---
    #: CWE identifier(s), e.g. "CWE-89". Free-form to allow scanner-native values.
    cwe: str = ""
    #: Numeric CVSS base score (0.0-10.0) when the scanner provides one.
    cvss_score: float | None = None
    #: CVSS vector string, e.g. "CVSS:3.1/AV:N/AC:L/...".
    cvss_vector: str = ""
    #: OWASP category, e.g. "A03:2021-Injection".
    owasp_category: str = ""
    #: Reference URLs (advisories, CVE pages, rule docs).
    references: list[str] = field(default_factory=list)
    #: Human-readable remediation guidance or fixed-version hint.
    remediation: str = ""

    def to_dict(self) -> dict:
        """Serialize to a plain dict for MCP output formatting."""
        result = {
            "scanner": self.scanner,
            "title": self.title,
            "message": self.message,
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "context": self.context,
            "finding_hash": self.finding_hash,
            "language": self.language,
        }
        if self.data_flow:
            result["data_flow"] = [
                {"file": s.file, "line": s.line, "code_snippet": s.code_snippet}
                for s in self.data_flow
            ]
        # Only emit metadata fields that carry information, to keep output lean.
        if self.cwe:
            result["cwe"] = self.cwe
        if self.cvss_score is not None:
            result["cvss_score"] = self.cvss_score
        if self.cvss_vector:
            result["cvss_vector"] = self.cvss_vector
        if self.owasp_category:
            result["owasp_category"] = self.owasp_category
        if self.references:
            result["references"] = list(self.references)
        if self.remediation:
            result["remediation"] = self.remediation
        return result


def meets_severity_threshold(item_level: str, threshold: str) -> bool:
    """Check if a severity level meets the minimum threshold."""
    try:
        item = SeverityLevel(item_level.upper())
        thresh = SeverityLevel(threshold.upper())
    except ValueError:
        return True  # If we can't parse, include the finding
    return SEVERITY_ORDER[item] >= SEVERITY_ORDER[thresh]


def meets_confidence_threshold(item_level: str, threshold: str) -> bool:
    """Check if a confidence level meets the minimum threshold."""
    try:
        item = ConfidenceLevel(item_level.upper())
        thresh = ConfidenceLevel(threshold.upper())
    except ValueError:
        return True
    return CONFIDENCE_ORDER[item] >= CONFIDENCE_ORDER[thresh]
