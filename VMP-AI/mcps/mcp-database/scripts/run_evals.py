"""Runs docs/evals question files through the claude CLI (headless) against one stdio server.

Usage: NAME=... URI=... MODE=... [EVAL_MODEL=...] python scripts/run_evals.py <eval.json> <report.md>
Each question spawns `claude -p` with only the mcp-database server attached; the answer passes
when the expected value appears in the reply. Exits non-zero if any question fails.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROMPT = (
    "{question}\n\n"
    "Use only the MCP tools from the mcp-database server to find the answer. "
    "Reply with only the final answer, nothing else."
)
QUESTION_TIMEOUT_S = 300


def server_config() -> dict:
    env = {key: os.environ[key] for key in ("NAME", "URI", "MODE") if key in os.environ}
    if "URI" not in env:
        sys.exit("URI is required (NAME/URI/MODE env vars configure the server)")
    return {
        "mcpServers": {
            "mcp-database": {
                "command": "uv",
                "args": ["run", "--directory", ".", "mcp-database"],
                "env": env,
            }
        }
    }


def ask(question: str, mcp_config: str, model: str) -> str:
    claude = shutil.which("claude") or sys.exit("claude CLI not found on PATH")
    result = subprocess.run(  # noqa: S603
        [
            claude,
            "-p",
            PROMPT.format(question=question),
            "--mcp-config",
            mcp_config,
            "--strict-mcp-config",
            "--allowedTools",
            "mcp__mcp-database",
            "--model",
            model,
            "--output-format",
            "text",
        ],
        capture_output=True,
        text=True,
        timeout=QUESTION_TIMEOUT_S,
    )
    if result.returncode != 0:
        return f"[claude exited {result.returncode}: {result.stderr.strip()[:200]}]"
    return result.stdout.strip()


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip())
    eval_file, report_file = Path(sys.argv[1]), Path(sys.argv[2])
    model = os.environ.get("EVAL_MODEL", "sonnet")
    items = json.loads(eval_file.read_text())

    tmp_dir = Path("temp")
    tmp_dir.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", dir=tmp_dir, delete=False) as cfg:
        json.dump(server_config(), cfg)
        cfg_path = cfg.name

    rows, passed = [], 0
    try:
        for i, item in enumerate(items, 1):
            reply = ask(item["question"], cfg_path, model)
            ok = item["answer"].strip().lower() in reply.lower()
            passed += ok
            flat = " ".join(reply.split())[:200] or "(empty)"
            rows.append((i, item["question"], item["answer"], flat, ok))
            print(f"[{i}/{len(items)}] {'PASS' if ok else 'FAIL'}: {item['question']}")
    finally:
        os.unlink(cfg_path)

    lines = [
        f"# Agent evals — {eval_file.name}",
        "",
        f"Model: `{model}` — **{passed}/{len(items)} passed**",
        "",
        "| # | Question | Expected | Got | Result |",
        "|---|----------|----------|-----|--------|",
    ]
    lines += [f"| {i} | {q} | `{expected}` | {got} | {'✅' if ok else '❌'} |" for i, q, expected, got, ok in rows]
    report_file.write_text("\n".join(lines) + "\n")
    print(f"report: {report_file} ({passed}/{len(items)} passed)")
    if passed < len(items):
        sys.exit(1)


if __name__ == "__main__":
    main()
