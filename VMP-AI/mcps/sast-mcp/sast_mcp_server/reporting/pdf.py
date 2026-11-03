"""PDF executive report (optional, requires the ``[pdf]`` extra).

reportlab is an optional dependency so the core server stays lightweight. If it
isn't installed, :func:`findings_to_pdf` raises :class:`PdfUnavailableError`,
which the ``generate_report`` tool turns into an actionable message.
"""

import io

from sast_mcp_server.models import Finding, SeverityLevel

# Order + colors for the severity rollup.
_SEVERITY_ORDER = [
    SeverityLevel.CRITICAL,
    SeverityLevel.HIGH,
    SeverityLevel.MEDIUM,
    SeverityLevel.LOW,
]
_SEVERITY_HEX = {
    SeverityLevel.CRITICAL: "#b71c1c",
    SeverityLevel.HIGH: "#e65100",
    SeverityLevel.MEDIUM: "#f9a825",
    SeverityLevel.LOW: "#2e7d32",
}


class PdfUnavailableError(RuntimeError):
    """Raised when reportlab (the ``[pdf]`` extra) is not installed."""


def pdf_available() -> bool:
    """Return True if the PDF backend (reportlab) is importable."""
    try:
        import reportlab  # noqa: F401
    except ImportError:
        return False
    return True


def findings_to_pdf(
    findings: list[Finding],
    project: str = "scan-target",
    scanners: list[str] | None = None,
) -> bytes:
    """Render findings into a standalone PDF executive report (bytes).

    Raises:
        PdfUnavailableError: if reportlab is not installed.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as err:  # pragma: no cover - exercised via pdf_available()
        raise PdfUnavailableError(
            "PDF reports require the optional 'reportlab' dependency. "
            "Install it with: pip install \"sast-mcp-server[pdf]\""
        ) from err

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title=f"Security Report — {project}")
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"Security Report — {project}", styles["Title"]))
    if scanners:
        story.append(Paragraph(f"Scanners: {', '.join(scanners)}", styles["Normal"]))
    story.append(Paragraph(f"Total findings: {len(findings)}", styles["Normal"]))
    story.append(Spacer(1, 16))

    # Severity rollup table.
    counts = {level: 0 for level in _SEVERITY_ORDER}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
    rollup = [["Severity", "Count"]]
    rollup += [[level.value, str(counts[level])] for level in _SEVERITY_ORDER]
    table = Table(rollup, hAlign="LEFT", colWidths=[120, 80])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#263238")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 18))

    story.append(Paragraph("Top findings", styles["Heading2"]))
    # Sort CRITICAL→LOW; show the top 40 so the PDF stays a summary.
    order = {lvl: i for i, lvl in enumerate(_SEVERITY_ORDER)}
    ordered = sorted(findings, key=lambda f: order.get(f.severity, 99))
    for f in ordered[:40]:
        hexc = _SEVERITY_HEX.get(f.severity, "#000000")
        heading = (
            f'<font color="{hexc}"><b>[{f.severity.value}]</b></font> '
            f"{_escape(f.title)}"
        )
        story.append(Paragraph(heading, styles["Normal"]))
        story.append(
            Paragraph(
                f"<i>{_escape(f.file)}:{f.line_start}</i> — {_escape(f.scanner)}",
                styles["Normal"],
            )
        )
        if f.message:
            story.append(Paragraph(_escape(f.message[:300]), styles["Normal"]))
        story.append(Spacer(1, 8))

    if len(ordered) > 40:
        story.append(Paragraph(f"... and {len(ordered) - 40} more findings.", styles["Italic"]))

    doc.build(story)
    return buffer.getvalue()


def _escape(text: str) -> str:
    """Escape the minimal set of characters reportlab's mini-HTML needs."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
