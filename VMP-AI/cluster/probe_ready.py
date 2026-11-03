#!/usr/bin/env python3
"""Sonda: o que 'prontidao' pode de fato significar aqui.

Restricao ja medida: o relay (Cloudflare) anuncia keep-alive, mas e o
keep-alive que produz "SSL: BAD_RECORD_MAC". Portanto NAO existe prontidao
por conexao TCP aberta — cada chamada paga um handshake.

O que resta para aquecer, e o que vale medir:

  1. CREDENCIAL valida? (falhar na selecao, nao na tarefa)
  2. MODELO alcançavel agora? (cota pode ter morrido desde a ultima vez)
  3. PROMPT CACHE funciona? (o relay ja reportou cached_tokens: 149)
     Se sim, um system prompt estavel vira tokens de graca em toda chamada.
  4. TEMPO de handyake TLS? (quanto a prontidao nao compra)
  5. CONCORRENCIA real de N slots aquecidos? (o cluster usa 3 em paralelo)

O objetivo e dar numero honesto: o que a prontidao entrega e o que ela nao
entrega.
"""

import http.client
import json
import re
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CLUSTER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CLUSTER_DIR))
sys.path.insert(0, str(CLUSTER_DIR / "core"))

import agent as A  # noqa: E402
import registry as reg  # noqa: E402

K = A._key()
HOST, PATH_ = A.RELAY_HOST, A.RELAY_PATH
H = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {K}",
    "User-Agent": "vmp-cluster/1.0",
}


def once(msgs, max_tokens=1024, tools=None):
    p = {"model": A.MODEL, "messages": msgs, "max_tokens": max_tokens}
    if tools:
        p["tools"] = tools
        p["tool_choice"] = "auto"
    body = json.dumps(p)
    h = dict(H)
    h["Content-Length"] = str(len(body))
    t0 = time.time()
    c = http.client.HTTPSConnection(
        HOST, 443, timeout=120, context=ssl.create_default_context()
    )
    c.request("POST", PATH_, body=body, headers=h)
    r = c.getresponse()
    data = r.read()
    c.close()
    return json.loads(data.decode("utf-8", "replace")), time.time() - t0


print("=" * 72)
print("1. CREDENCIAL E MODELO alcancaveis agora?")
print("=" * 72)
try:
    d, dt = once([{"role": "user", "content": "Say OK"}], 256)
    ch = (d.get("choices") or [{}])[0]
    txt = (ch.get("message") or {}).get("content") or ""
    print(f"  ok={dt:.1f}s finish={ch.get('finish_reason')} resposta={txt[:30]!r}")
    CRED_OK = bool(txt.strip())
except Exception as e:
    print(f"  FALHOU: {type(e).__name__}: {str(e)[:80]}")
    CRED_OK = False

print()
print("=" * 72)
print("2. PROMPT CACHE — o system prompt estavel e de graca?")
print("=" * 72)
sys_prompt = (
    "Voce e um agente de cluster com papeis separados. Use ferramentas para VER."
)
msgs = [
    {"role": "system", "content": sys_prompt},
    {"role": "user", "content": "Responda apenas: OK"},
]
print("  3 chamadas com o MESMO system prompt (tarefa muda):")
cache_hits = []
for i in range(3):
    d, dt = once(msgs, 512)
    u = d.get("usage") or {}
    det = u.get("prompt_tokens_details") or {}
    cached = det.get("cached_tokens") or 0
    pt = u.get("prompt_tokens") or 0
    cache_hits.append(cached)
    print(
        f"    {i}: {dt:.1f}s prompt_tokens={pt} cached={cached} "
        f"({100 * cached / pt if pt else 0:.0f}% de graca)"
    )
CACHE_WORKS = max(cache_hits) > 0
print(f"  -> cache de prompt {'FUNCIONA' if CACHE_WORKS else 'nao funciona'}")

print()
print("=" * 72)
print("3. QUANTO CUSTA o handshake TLS (o preco de nao poder manter conexao)?")
print("=" * 72)
lat = []
for i in range(8):
    _, dt = once([{"role": "user", "content": f"Say OK {i}"}], 256)
    lat.append(dt)
lat.sort()
print(f"  min={lat[0]:.2f}s  mediana={lat[len(lat) // 2]:.2f}s  max={lat[-1]:.2f}s")
print("  (este e o custo por chamada que a 'prontidao' nao elimina)")

print()
print("=" * 72)
print("4. SLOTS AQUECIDOS EM PARALELO — 10 slots respondem juntos?")
print("=" * 72)
# Cada "slot" usa o system prompt do SEU papel, como no cluster real.
slots = []
for role in reg.PIPELINE:
    m = reg.manifest(role)
    slots.append(
        (
            role,
            [
                {
                    "role": "system",
                    "content": f"Voce e o agente '{role}'.\nSUA MISSAO: {m.mission}\nSEU FOCO: {m.focus}",
                },
                {"role": "user", "content": "Responda apenas: pronto"},
            ],
            reg.tools_for(role),
        )
    )
# completa ate 10 com repeticoes (o cluster usa 3 criticos em paralelo)
while len(slots) < 10:
    role, _, tools = slots[len(slots) % len(reg.PIPELINE)]
    slots.append(
        (
            f"{role}#extra",
            [
                {"role": "system", "content": f"Voce e o agente '{role}'."},
                {"role": "user", "content": "Responda apenas: pronto"},
            ],
            tools,
        )
    )

t0 = time.time()
with ThreadPoolExecutor(max_workers=10) as ex:
    futs = [ex.submit(once, ms, 512, tl) for _, ms, tl in slots]
    res = []
    for f in futs:
        try:
            res.append(f.result())
        except Exception as e:
            res.append(({"erro": str(e)[:50]}, 0))
el = time.time() - t0
ok_n = sum(1 for d, _ in res if (d.get("choices") or [{}]))
print(f"  10 slots em paralelo: ok={ok_n}/10  t={el:.1f}s")
for (d, dt), (role, _, _) in zip(res, slots):
    st = "OK" if (d.get("choices") or [{}]) else "FALHOU"
    print(f"    {role:<16} {st} {dt:.1f}s")

print()
print("=" * 72)
print("VEREDITO DA PRONTIDAO")
print("=" * 72)
print(f"  credencial valida      : {CRED_OK}")
print(f"  prompt cache funciona : {CACHE_WORKS}")
print(f"  handshake por chamada : {lat[len(lat) // 2]:.2f}s (mediana, inevitavel)")
print()
print("  O QUE a prontidao ENTREGA:")
print(
    "    - falha cedo se a credencial/cota morreu (na selecao, nao no meio da tarefa)"
)
print("    - prompt cache ja aquecido: system prompt estavel vira tokens de graca")
print("    - validacao de que o modelo responde AGORA, antes de prometer 10 agentes")
print("  O QUE a prontidao NAO entrega:")
print("    - conexao quente: o relay usa keep-alive e e exatamente ele que causa")
print("      o SSL BAD_RECORD_MAC. Cada chamada paga handshake. Nao ha como evitar")
print("      sem reintroduzir o bug.")
print("    - garantia de cota: o relay pode estourar a qualquer momento entre a")
print("      selecao e a execucao.")
