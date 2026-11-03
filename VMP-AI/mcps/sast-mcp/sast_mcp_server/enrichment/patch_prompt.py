"""Build an LLM-ready prompt for generating a security fix as a unified diff.

The MCP server's role is to *package context*: it recovers a finding from the
scan cache, pulls an expanded window of the surrounding source, and renders a
strict prompt that instructs an LLM to emit a unified diff. The agent is then
responsible for generating the patch (and, via the ``apply_patch`` tool,
applying it). Keeping generation on the agent side avoids baking a specific
model/provider into the server.
"""

import logging
import os

from sast_mcp_server.cache import ScanCache
from sast_mcp_server.models import Finding

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_WINDOW = 15


def _resolve_path(target_path: str, finding_file: str) -> str:
    """Resolve a finding's file path against the scanned target."""
    if os.path.isabs(finding_file):
        return finding_file
    return os.path.join(target_path, finding_file)


def _read_window(
    file_path: str, line_start: int, line_end: int, context_window: int
) -> tuple[str, int]:
    """Return source lines around a finding plus the window's first line number.

    The returned snippet is numbered so the LLM can anchor the diff correctly.
    """
    with open(file_path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    start = max(1, line_start - context_window)
    end = min(len(lines), line_end + context_window)

    numbered = []
    for n in range(start, end + 1):
        numbered.append(f"{n:>5} | {lines[n - 1].rstrip(chr(10))}")
    return ("\n".join(numbered), start)


def build_patch_prompt(
    target_path: str,
    finding_hash: str,
    context_window: int = DEFAULT_CONTEXT_WINDOW,
) -> str:
    """Build a prompt that asks an LLM to fix a cached finding via unified diff.

    Args:
        target_path: Root of the scanned project (where ``.sast-mcp-cache`` lives).
        finding_hash: Hash of the finding to remediate (from scan output).
        context_window: Number of source lines to include before/after the finding.

    Returns:
        A ready-to-use prompt string, or a human-readable error message if the
        finding or its source file cannot be located.
    """
    cache = ScanCache(target_path)
    finding: Finding | None = cache.find_finding_by_hash(finding_hash)

    if finding is None:
        return (
            f"Error: No cached finding with hash `{finding_hash}` was found for "
            f"`{target_path}`. Run a scan (e.g. `scan_all` or `save_baseline`) "
            "first so the finding is cached, then retry."
        )

    file_path = _resolve_path(target_path, finding.file)
    if not os.path.isfile(file_path):
        return (
            f"Error: The source file for this finding (`{finding.file}`) could "
            f"not be found under `{target_path}`. It may have been moved or "
            "deleted since the scan."
        )

    try:
        snippet, window_start = _read_window(
            file_path, finding.line_start, finding.line_end, context_window
        )
    except OSError as err:
        return f"Error: Could not read `{file_path}`: {err}"

    rel_file = finding.file.replace("\\", "/")
    language = finding.language or ""

    return f"""You are a senior application security engineer. Fix the following \
vulnerability by producing a single, minimal **unified diff** patch.

## Vulnerability
- **Title:** {finding.title}
- **Severity:** {finding.severity.value}
- **Confidence:** {finding.confidence.value}
- **Scanner:** {finding.scanner}
- **Location:** {rel_file}:{finding.line_start}-{finding.line_end}
- **Finding hash:** {finding_hash}

## Description
{finding.message or "(no scanner message provided)"}

## Source (line-numbered, window starts at line {window_start})
```{language}
{snippet}
```

## Requirements
1. Output **only** a valid unified diff — no prose, no markdown fences around it.
2. Use the exact file path `{rel_file}` in both the `---` and `+++` headers
   (i.e. `--- a/{rel_file}` and `+++ b/{rel_file}`).
3. Provide correct `@@ -start,count +start,count @@` hunk headers with at least
   3 lines of unchanged context where available.
4. Make the **smallest** change that removes the vulnerability. Preserve the
   surrounding behavior, naming, and formatting style.
5. Do not introduce new dependencies unless strictly required; if you do, note
   them in a trailing comment line that begins with `# NOTE:` *after* the diff.
6. After the patch is generated, apply it with the `apply_patch` tool
   (target_path=`{target_path}`); run it with `check_only=true` first to verify
   the diff applies cleanly.
"""
