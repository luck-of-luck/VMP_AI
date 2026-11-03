"""Self-contained HTML executive report for SAST findings.

Renders a single static HTML page (no external assets) with a severity rollup,
optional baseline trend, and a per-finding table. Suitable for attaching to a
build artifact, emailing, or publishing as a CI report.
"""

import html
from datetime import datetime, timezone

from sast_mcp_server.models import SEVERITY_ORDER, Finding, SeverityLevel

_SEVERITY_COLORS = {
    SeverityLevel.CRITICAL: "#b00020",
    SeverityLevel.HIGH: "#e64a19",
    SeverityLevel.MEDIUM: "#f9a825",
    SeverityLevel.LOW: "#2e7d32",
}


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _severity_counts(findings: list[Finding]) -> dict[str, int]:
    counts = {level.value: 0 for level in SeverityLevel}
    for f in findings:
        counts[f.severity.value] += 1
    return counts


def findings_to_html(
    findings: list[Finding],
    project: str,
    scanners: list[str] | None = None,
) -> str:
    """Render findings as a standalone HTML report string."""
    counts = _severity_counts(findings)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ordered = sorted(
        findings, key=lambda f: SEVERITY_ORDER.get(f.severity, 0), reverse=True
    )
    scanners_line = ", ".join(scanners) if scanners else "n/a"

    cards = "".join(
        f'<div class="card" style="border-top:4px solid {_SEVERITY_COLORS[level]}">'
        f'<div class="count">{counts[level.value]}</div>'
        f'<div class="label">{level.value}</div></div>'
        for level in [
            SeverityLevel.CRITICAL,
            SeverityLevel.HIGH,
            SeverityLevel.MEDIUM,
            SeverityLevel.LOW,
        ]
    )

    rows = []
    for f in ordered:
        color = _SEVERITY_COLORS.get(f.severity, "#666")
        refs = ""
        if f.references:
            refs = " ".join(
                f'<a href="{_esc(u)}">ref</a>' for u in f.references[:3]
            )
        badge = (
            f'<span class="badge" style="background:{color}">'
            f"{_esc(f.severity.value)}</span>"
        )
        rows.append(
            "<tr>"
            f"<td>{badge}</td>"
            f"<td>{_esc(f.title)}</td>"
            f"<td>{_esc(f.scanner)}</td>"
            f"<td><code>{_esc(f.file)}:{_esc(f.line_start)}</code></td>"
            f"<td>{_esc(f.cwe)}</td>"
            f"<td>{_esc(f.cvss_score if f.cvss_score is not None else '')}</td>"
            f"<td>{refs}</td>"
            "</tr>"
        )
    rows_html = "\n".join(rows) if rows else (
        '<tr><td colspan="7">No findings 🎉</td></tr>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Security Report — {_esc(project)}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif;
         margin: 2rem; color: #1a1a1a; }}
  h1 {{ margin-bottom: 0.25rem; }}
  .meta {{ color: #666; margin-bottom: 1.5rem; }}
  .cards {{ display: flex; gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: #fafafa; border: 1px solid #eee; border-radius: 8px;
          padding: 1rem 1.5rem; min-width: 90px; text-align: center; }}
  .count {{ font-size: 2rem; font-weight: 700; }}
  .label {{ color: #666; font-size: 0.85rem; letter-spacing: 0.05em; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 0.5rem 0.75rem;
           border-bottom: 1px solid #eee; font-size: 0.9rem; vertical-align: top; }}
  th {{ background: #f5f5f5; }}
  .badge {{ color: #fff; padding: 0.15rem 0.5rem; border-radius: 4px;
           font-size: 0.75rem; font-weight: 600; }}
  code {{ background: #f5f5f5; padding: 0.1rem 0.3rem; border-radius: 3px; }}
</style>
</head>
<body>
  <h1>Security Report</h1>
  <div class="meta">
    <strong>{_esc(project)}</strong> &middot; {len(findings)} findings &middot;
    scanners: {_esc(scanners_line)} &middot; generated {generated}
  </div>
  <div class="cards">{cards}</div>
  <table>
    <thead>
      <tr><th>Severity</th><th>Title</th><th>Scanner</th><th>Location</th>
          <th>CWE</th><th>CVSS</th><th>Refs</th></tr>
    </thead>
    <tbody>
{rows_html}
    </tbody>
  </table>
</body>
</html>
"""
