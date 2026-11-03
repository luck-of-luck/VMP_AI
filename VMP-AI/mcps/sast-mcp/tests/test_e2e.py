"""End-to-end smoke test running a real scanner (Bandit) on a fixture.

Skipped automatically when Bandit isn't importable, so the suite stays green in
minimal environments while still exercising the real subprocess path where it can.
"""

import importlib.util

import pytest

from sast_mcp_server.server import scan_vulnerabilities

_HAS_BANDIT = importlib.util.find_spec("bandit") is not None

pytestmark = pytest.mark.skipif(
    not _HAS_BANDIT, reason="bandit not installed; skipping real-scanner e2e"
)

_VULNERABLE_SOURCE = """\
import subprocess


def run(cmd):
    # B602: subprocess call with shell=True is a known Bandit finding.
    return subprocess.call(cmd, shell=True)
"""


@pytest.mark.asyncio
async def test_bandit_finds_planted_issue(tmp_path):
    src = tmp_path / "vuln.py"
    src.write_text(_VULNERABLE_SOURCE, encoding="utf-8")

    result = await scan_vulnerabilities(
        target_path=str(tmp_path),
        scanner_name="bandit",
        min_severity="LOW",
        min_confidence="LOW",
    )

    # Should not be an error and should report at least one finding.
    assert "Error" not in result.splitlines()[0]
    assert "vuln.py" in result


@pytest.mark.asyncio
async def test_bandit_json_output(tmp_path):
    import json

    src = tmp_path / "vuln.py"
    src.write_text(_VULNERABLE_SOURCE, encoding="utf-8")

    result = await scan_vulnerabilities(
        target_path=str(tmp_path),
        scanner_name="bandit",
        min_severity="LOW",
        output_format="json",
    )
    data = json.loads(result)
    assert data["scanner"] == "bandit"
    assert isinstance(data["findings"], list)
