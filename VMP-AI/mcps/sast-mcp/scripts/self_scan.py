#!/usr/bin/env python3
"""Run the server's own scanners against a target and emit shareable artifacts.

Produces, in the output directory:
  - findings.sarif : SARIF 2.1.0 export of all findings
  - SUMMARY.md     : human-readable summary (counts, scanners used, top findings)

Used both in CI (uploaded as artifacts) and to refresh the committed example
under examples/self-scan/. Defaults to scanning this package.

    python scripts/self_scan.py --target sast_mcp_server --out-dir examples/self-scan
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sast_mcp_server import __version__
from sast_mcp_server.aggregator import run_all_scanners
from sast_mcp_server.sarif import findings_to_sarif

_SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def _sev(finding) -> str:
    sev = getattr(finding, "severity", "")
    return getattr(sev, "value", str(sev)).upper()


def _render_summary(target: str, findings, used: list[str], skipped: list[str]) -> str:
    by_sev = Counter(_sev(f) for f in findings)
    by_scanner = Counter(getattr(f, "scanner", "?") for f in findings)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Self-scan report",
        "",
        f"_SAST MCP Server v{__version__} scanning `{target}` — generated {now}._",
        "",
        "This is the server running its own scanners against its own code: real",
        "output from `scan_all`, exported to SARIF and summarized here.",
        "",
        "## Summary",
        "",
        f"- **Total findings:** {len(findings)}",
        f"- **Scanners run:** {', '.join(used) if used else 'none'}",
        f"- **Scanners skipped (not installed):** {', '.join(skipped) if skipped else 'none'}",
        "",
        "### Findings by severity",
        "",
        "| Severity | Count |",
        "|----------|------:|",
    ]
    for sev in _SEVERITY_ORDER:
        if by_sev.get(sev):
            lines.append(f"| {sev} | {by_sev[sev]} |")
    if not findings:
        lines.append("| _none_ | 0 |")

    lines += ["", "### Findings by scanner", "", "| Scanner | Count |", "|---------|------:|"]
    for scanner, count in by_scanner.most_common():
        lines.append(f"| {scanner} | {count} |")
    if not by_scanner:
        lines.append("| _none_ | 0 |")

    def rank(f):
        return _SEVERITY_ORDER.index(_sev(f)) if _sev(f) in _SEVERITY_ORDER else 99

    top = sorted(findings, key=rank)[:15]
    if top:
        lines += [
            "",
            "### Top findings",
            "",
            "| Severity | Scanner | Finding | Location |",
            "|----------|---------|---------|----------|",
        ]
        for f in top:
            path = str(getattr(f, "file", "?")).replace("\\", "/")
            loc = f"{path}:{getattr(f, 'line_start', '?')}"
            title = str(getattr(f, "title", "")).replace("|", "\\|")[:80]
            lines.append(f"| {_sev(f)} | {getattr(f, 'scanner', '?')} | {title} | `{loc}` |")

    lines.append("")
    return "\n".join(lines)


async def _amain(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    findings, used, skipped = await run_all_scanners(
        target_path=args.target, min_severity=args.min_severity
    )

    sarif = findings_to_sarif(findings, scanner_name="sast-mcp-server", version=__version__)
    (out_dir / "findings.sarif").write_text(json.dumps(sarif, indent=2), encoding="utf-8")
    (out_dir / "SUMMARY.md").write_text(
        _render_summary(args.target, findings, used, skipped), encoding="utf-8"
    )

    print(f"Wrote {len(findings)} findings to {out_dir}/ (scanners: {', '.join(used) or 'none'})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="sast_mcp_server", help="Path to scan.")
    parser.add_argument("--out-dir", default="examples/self-scan", help="Output directory.")
    parser.add_argument("--min-severity", default="LOW", help="Minimum severity to include.")
    return asyncio.run(_amain(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
