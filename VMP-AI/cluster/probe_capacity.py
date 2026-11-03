#!/usr/bin/env python3
"""Sonda 2: contexto, concorrencia e limites reais do relay.

O teste anterior provou tool-calling, mas duas perguntas continuam abertas e
sao o que decide a arquitetura do cluster:

  A. CONTEXTO — quantos tokens de entrada aceita? Se for baixo, os agentes
     nao podem "ler o projeto": o orquestrador tem que resumir antes.
  B. CONCORRENCIA — quantas chamadas simultaneas aguentam sem 429? E o
     rate limit que aparece na pratica (por janela)?

Responde com numeros, nao com suposicao.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV = REPO_ROOT / ".env"
URL = "https://opencode.ai/zen/v1/chat/completions"
MODEL = os.environ.get("PROBE_MODEL", "space-bunny-free")


def key():
    m = re.search(
        r"^OPENCODE_ZEN_API_KEY\s*=\s*(.+)$", ENV.read_text(encoding="utf-8"), re.M
    )
    return m.group(1).strip().strip('"').strip("'") if m else sys.exit("sem key")


K = key()
STATS = {"ok": 0, "429": 0, "402": 0, "err": 0, "timeouts": 0}


def call(payload, timeout=240):
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {K}",
            "User-Agent": "cluster-probe2/1.0",
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        STATS["ok"] += 1
        return True, d, time.time() - t0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if e.code == 429:
            STATS["429"] += 1
        elif e.code == 402:
            STATS["402"] += 1
        else:
            STATS["err"] += 1
        try:
            return False, json.loads(body), time.time() - t0
        except Exception:
            return False, {"http": e.code, "raw": body[:200]}, time.time() - t0
    except Exception as e:
        STATS["timeouts"] += 1
        return False, {"exc": str(e)[:150]}, time.time() - t0


def head(t):
    print(f"\n{'=' * 68}\n{t}\n{'=' * 68}")


# ── A. contexto de entrada ─────────────────────────────────────────────
head("A. CONTEXTO DE ENTRADA — ate quantos tokens aguenta?")
src = REPO_ROOT / "hermes_cli" / "config.py"
code = src.read_text(encoding="utf-8", errors="replace") if src.exists() else ""
if not code:
    cand = list(
        (REPO_ROOT / "hermes-agent").rglob("run_agent.py")
    )
    if cand:
        code = cand[0].read_text(encoding="utf-8", errors="replace")
        src = cand[0]
print(f"fonte: {src}  {len(code)} chars (~{len(code) // 4} tokens)")

first_def = None
m = re.search(r"^\s*def\s+(\w+)", code, re.M)
if m:
    first_def = m.group(1)
print(f"primeira def no arquivo: {first_def}")

# Escalona o tamanho da entrada ate o relay recusar.
sizes = [2_000, 8_000, 20_000, 50_000, 100_000, 200_000, 300_000]
print(f"\n{'chars':>9} {'~tokens':>8}  resultado")
best_ok = None
for n in sizes:
    chunk = (code * (n // max(len(code), 1) + 2))[:n]
    ok, r, dt = call(
        {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": f"Código:\n\n{chunk}\n\nResponda APENAS com o nome da primeira função def. Se não houver, diga NONE.",
                }
            ],
            "max_tokens": 48,
        },
        timeout=300,
    )
    if ok:
        got = ((r.get("choices") or [{}])[0].get("message", {}) or {}).get(
            "content", ""
        )
        fin = (r.get("choices") or [{}])[0].get("finish_reason")
        pt = (r.get("usage") or {}).get("prompt_tokens")
        correct = "SIM" if first_def and first_def in str(got) else "nao"
        print(
            f"{n:>9} {str(pt):>8}  OK {dt:>5.1f}s finish={fin:<8} acerto={correct}  -> {str(got)[:60]!r}"
        )
        best_ok = n
    else:
        msg = (r.get("error", {}) or {}).get("message", json.dumps(r))[:120]
        print(f"{n:>9} {'-':>8}  REJEITOU: {msg}")
        break
print(
    f"\nmaior entrada aceita: {best_ok} chars (~{best_ok // 4 if best_ok else 0} tokens)"
)

# ── B. concorrencia ────────────────────────────────────────────────────
head("B. CONCORRENCIA — N agentes ao mesmo tempo")

for n in [3, 5, 8, 10]:
    for k in STATS:
        STATS[k] = 0
    # Cada worker recebe seu proprio indice via lambda do executor.
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n) as ex:
        futs = [
            ex.submit(
                call,
                {
                    "model": MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Responda apenas com o numero {i}. Sem texto.",
                        }
                    ],
                    "max_tokens": 32,
                },
            )
            for i in range(n)
        ]
        res = [f.result() for f in futs]
    el = time.time() - t0
    good = sum(1 for ok, _, _ in res if ok)
    lat = [dt for ok, _, dt in res if ok]
    print(
        f"n={n:<3} ok={good}/{n} 429={STATS['429']} err={STATS['err']} to={STATS['timeouts']} "
        f"t={el:>5.1f}s lat_min={min(lat):.1f}s lat_max={max(lat):.1f}s"
        if lat
        else f"n={n:<3} ok={good}/{n} (sem sucesso)"
    )
    if STATS["429"]:
        print(f"     ^^ RATE LIMIT atingido em {n} simultaneos")
        break

# ── C. burst de tool-calling (carga real de cluster) ───────────────────
head("C. BURST DE TOOL-CALLING — 6 agentes cada um chamando 1 tool")
tools = [
    {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo text back.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }
]
for k in STATS:
    STATS[k] = 0
t0 = time.time()
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = [
        ex.submit(
            call,
            {
                "model": MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Call the echo tool with text='agente-{i}'. Do not answer in text.",
                    }
                ],
                "tools": tools,
                "max_tokens": 256,
            },
        )
        for i in range(6)
    ]
    res = [f.result() for f in futs]
el = time.time() - t0
tc = 0
for ok, r, dt in res:
    if ok:
        c = ((r.get("choices") or [{}])[0].get("message", {}) or {}).get(
            "tool_calls"
        ) or []
        tc += len(c)
print(
    f"ok={sum(1 for ok, _, _ in res if ok)}/6 429={STATS['429']} err={STATS['err']} tool_calls={tc}  t={el:.1f}s"
)

head("ESTATISTICAS GLOBAIS")
print(STATS)
