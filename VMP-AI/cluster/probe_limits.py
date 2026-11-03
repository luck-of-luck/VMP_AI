#!/usr/bin/env python3
"""Sonda 3: os dois pontos que a sonda 2 deixou em aberto.

A. CONTEXTO: todo teste terminou em finish=length com resposta VAZIA. Isso
   pode ser (a) max_tokens consumidos em reasoning antes de responder,
   (b) o relay cortar o prompt, ou (c) bug da sonda. Sem resolver isso nao
   sabemos se o agente consegue ler um arquivo de verdade.

B. LATENCIA: um worker levou 83.9s enquanto os outros levaram ~1.2s. Se o
   relay tem cauda longa, o orquestrador precisa de timeout e retry — nao
   pode esperar indefinidamente por um agente.

C. DURABILIDADE: quanto tempo o relay segura a carga? 20 chamadas seguidas
   revelam se ha rate limit por janela que so aparece depois de um tempo.
"""

import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV = REPO_ROOT / ".env"
URL = "https://opencode.ai/zen/v1/chat/completions"
MODEL = "space-bunny-free"


def key():
    m = re.search(
        r"^OPENCODE_ZEN_API_KEY\s*=\s*(.+)$", ENV.read_text(encoding="utf-8"), re.M
    )
    return m.group(1).strip().strip('"').strip("'") if m else sys.exit("sem key")


K = key()


def call(payload, timeout=240):
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {K}",
            "User-Agent": "cluster-probe3/1.0",
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (
                True,
                json.loads(r.read().decode("utf-8", "replace")),
                time.time() - t0,
            )
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "replace")
        try:
            return False, json.loads(b), time.time() - t0
        except Exception:
            return False, {"http": e.code, "raw": b[:200]}, time.time() - t0
    except Exception as e:
        return False, {"exc": str(e)[:150]}, time.time() - t0


def head(t):
    print(f"\n{'=' * 68}\n{t}\n{'=' * 68}")


# ── A. por que a resposta veio vazia? ──────────────────────────────────
head("A. DIAGNOSTICO DO finish=length")
src = REPO_ROOT / "hermes-agent" / "run_agent.py"
code = src.read_text(encoding="utf-8", errors="replace")
m = re.search(r"^\s*def\s+(\w+)", code, re.M)
first_def = m.group(1) if m else ""
print(f"arquivo: {len(code)} chars | primeira def = {first_def}\n")

print(
    f"{'max_tokens':>11} {'finish':>9} {'content_len':>12} {'reason_tok':>11} {'acentou?':>9}"
)
for mt in [48, 256, 1024, 4096]:
    ok, r, dt = call(
        {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": f"Código:\n\n{code[:20000]}\n\nResponda APENAS com o nome da primeira função def. Se não houver, diga NONE.",
                }
            ],
            "max_tokens": mt,
        },
        timeout=300,
    )
    ch = (r.get("choices") or [{}])[0]
    msg = ch.get("message", {}) or {}
    content = msg.get("content") or ""
    reason_tok = ((r.get("usage") or {}).get("completion_tokens_details") or {}).get(
        "reasoning_tokens"
    )
    hit = "SIM" if first_def in str(content) else "nao"
    print(
        f"{mt:>11} {str(ch.get('finish_reason')):>9} {len(content):>12} {str(reason_tok):>11} {hit:>9}"
    )
    if content:
        print(f"            resposta: {content[:150]!r}")

# ── B. latencia / cauda longa ───────────────────────────────────────────
head("B. LATENCIA — 15 chamadas, medindo a cauda")
times = []
for i in range(15):
    ok, r, dt = call(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": f"Responda apenas: {i}"}],
            "max_tokens": 24,
        }
    )
    times.append(dt)
print(
    f"min={min(times):.1f}s  mediana={statistics.median(times):.1f}s  media={statistics.mean(times):.1f}s  max={max(times):.1f}s"
)
print(f"acima de 10s: {sum(1 for t in times if t > 10)}/{len(times)}")
print(f"acima de 30s: {sum(1 for t in times if t > 30)}/{len(times)}")
slow = [f"{t:.0f}s" for t in times if t > 10]
if slow:
    print(
        f"-> cauda longa confirmada: {slow}. O orquestrador PRECISA de timeout+retry."
    )

# ── C. durabilidade sob carga ───────────────────────────────────────────
head("C. DURABILIDADE — 20 chamadas em 3 ondas de 10 simultaneas")
for wave in range(3):
    with ThreadPoolExecutor(max_workers=10) as ex:
        res = [
            f.result()
            for f in [
                ex.submit(
                    call,
                    {
                        "model": MODEL,
                        "messages": [{"role": "user", "content": f"PING {wave}-{i}"}],
                        "max_tokens": 24,
                    },
                )
                for i in range(10)
            ]
        ]
    ok_n = sum(1 for ok, _, _ in res if ok)
    codes = {}
    for ok, r, _ in res:
        if not ok:
            codes[
                str(
                    r.get("http")
                    or (r.get("error", {}) or {}).get("code")
                    or r.get("exc", "?")[:30]
                )
            ] = (
                codes.get(
                    str(
                        r.get("http")
                        or (r.get("error", {}) or {}).get("code")
                        or r.get("exc", "?")[:30]
                    ),
                    0,
                )
                + 1
            )
    lats = [d for ok, _, d in res if ok]
    print(
        f"onda {wave + 1}: ok={ok_n}/10 lat_max={max(lats) if lats else 0:.1f}s falhas={codes or 'nenhuma'}"
    )
    time.sleep(2)

head("CONCLUSAO OPERACIONAL")
print("Se acima: ok=10/10 nas 3 ondas e sem 429 => o relay aguenta 10 agentes")
print("permanentes. Com lat_max alto, o desenho do orquestrador deve usar:")
print("  - timeout por chamada (ex.: 120s) + retry com backoff")
print("  - sem agente bloqueando os outros: cada um e uma tarefa assincrona")
print("  - o orquestrador decide o quao paralelo vai, em vez de confiar no relay")
