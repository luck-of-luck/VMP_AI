#!/usr/bin/env python3
"""Sonda de capacidades do space-bunny-free no relay do OpenCode Zen.

Cada teste mira UMA capacidade necessaria para um cluster de agentes:
  1. inferencia basica          -> o modelo responde?
  2. tool-calling / function    -> o agente pode ATUAR, ou so conversar?
  3. tool-call de verdade       -> ele executa e devolve o resultado?
  4. raciocinio (reasoning)      -> tem budget de thought?
  5. contexto longo             -> cabe um arquivo de codigo inteiro?
  6. JSON estrito               -> da para maquina ler a saida?
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV = REPO_ROOT / ".env"
URL = "https://opencode.ai/zen/v1/chat/completions"
MODEL = os.environ.get("PROBE_MODEL", "space-bunny-free")


def key() -> str:
    m = re.search(
        r"^OPENCODE_ZEN_API_KEY\s*=\s*(.+)$", ENV.read_text(encoding="utf-8"), re.M
    )
    if not m:
        sys.exit("OPENCODE_ZEN_API_KEY nao encontrado")
    return m.group(1).strip().strip('"').strip("'")


K = key()


def call(payload, timeout=180):
    """Chama o relay. Devolve (ok, parsed_or_raw, elapsed)."""
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {K}",
            "User-Agent": "cluster-probe/1.0",
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
        return True, json.loads(raw), time.time() - t0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return False, json.loads(body), time.time() - t0
        except Exception:
            return False, {"http": e.code, "raw": body[:300]}, time.time() - t0
    except Exception as e:
        return False, {"exc": str(e)[:200]}, time.time() - t0


def head(t):
    print(f"\n{'=' * 66}\n{t}\n{'=' * 66}")


# ── 1. inferencia basica ───────────────────────────────────────────────
head("1. INFERENCIA BASICA")
ok, r, dt = call(
    {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Reply with exactly: PONG"}],
        "max_tokens": 32,
    }
)
txt = (r.get("choices") or [{}])[0].get("message", {}).get("content", "") if ok else ""
print(f"ok={ok} {dt:.1f}s  resposta={txt!r}")
if not ok:
    print(f"ERRO: {json.dumps(r)[:300]}")
    print("\nO relay recusou. Nenhum teste seguinte faz sentido.")
    sys.exit(1)
print(f"usage: {r.get('usage')}")
BASIC = ok and bool(txt.strip())

# ── 2. tool-calling ────────────────────────────────────────────────────
head("2. TOOL-CALLING (o cluster depende disto)")
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from disk and return its contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "absolute file path"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]
ok, r, dt = call(
    {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a coding agent. Use tools to act."},
            {
                "role": "user",
                "content": "Use the read_file tool to read C:\\Windows\\System32\\drivers\\etc\\hosts. Do not guess — call the tool.",
            },
        ],
        "tools": tools,
        "tool_choice": "auto",
        "max_tokens": 512,
    }
)
if not ok:
    print(f"REQUEST REJEITADO: {json.dumps(r)[:300]}")
    print("=> tool-calling NAO suportado (o relay rejeitou o campo 'tools').")
    TC = False
else:
    msg = (r.get("choices") or [{}])[0].get("message", {})
    calls = msg.get("tool_calls") or []
    print(f"ok {dt:.1f}s  finish={(r.get('choices') or [{}])[0].get('finish_reason')}")
    print(f"content : {str(msg.get('content'))[:120]!r}")
    print(f"tool_calls: {len(calls)}")
    for c in calls:
        print(
            f"   -> {c.get('function', {}).get('name')}({c.get('function', {}).get('arguments')})"
        )
    TC = bool(calls)

# ── 3. tool_call de verdade (ida e volta) ──────────────────────────────
head("3. EXECUTAR TOOL E DEVOLVER RESULTADO (2 round-trips)")
if TC:
    msgs = [
        {
            "role": "system",
            "content": "You are a coding agent. Use tools to act, never guess.",
        },
        {
            "role": "user",
            "content": "Use read_file on C:\\Windows\\System32\\drivers\\etc\\hosts then tell me the first comment line.",
        },
    ]
    ok, r, dt = call(
        {"model": MODEL, "messages": msgs, "tools": tools, "max_tokens": 512}
    )
    calls = ((r.get("choices") or [{}])[0].get("message", {}) or {}).get(
        "tool_calls"
    ) or []
    if calls:
        fc = calls[0]["function"]
        args = json.loads(fc.get("arguments") or "{}")
        try:
            content = Path(args["path"]).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            content = f"ERRO_LEITURA: {e}"
        print(f"executando {fc['name']}({args}) -> {len(content)} chars")
        msgs.append({"role": "assistant", "content": None, "tool_calls": calls})
        msgs.append(
            {"role": "tool", "tool_call_id": calls[0]["id"], "content": content[:3000]}
        )
        ok2, r2, dt2 = call(
            {"model": MODEL, "messages": msgs, "tools": tools, "max_tokens": 512}
        )
        if ok2:
            final = ((r2.get("choices") or [{}])[0].get("message", {}) or {}).get(
                "content", ""
            )
            print(f"RESPOSTA FINAL ({dt2:.1f}s): {str(final)[:300]!r}")
            LOOP = bool(final.strip())
        else:
            print(f"falha no 2o round-trip: {json.dumps(r2)[:200]}")
            LOOP = False
    else:
        LOOP = False
else:
    LOOP = False

# ── 4. reasoning ───────────────────────────────────────────────────────
head("4. RACIOCINIO / reasoning_effort")
for eff in ["low", "high", "max"]:
    ok, r, dt = call(
        {
            "model": MODEL,
            "messages": [
                {"role": "user", "content": "2+2? Answer with just the number."}
            ],
            "reasoning_effort": eff,
            "max_tokens": 2000,
        }
    )
    msg = (r.get("choices") or [{}])[0].get("message", {}) if ok else {}
    think = msg.get("reasoning") or msg.get("reasoning_content") or ""
    usage = r.get("usage", {}) if ok else {}
    detail = (r.get("error", {}) or {}).get("message", "") if not ok else ""
    print(
        f"effort={eff:<5} ok={ok} content={str(msg.get('content'))[:40]!r} reasoning_chars={len(think)} completion={usage.get('completion_tokens')} {detail[:80]}"
    )

# ── 5. contexto longo ──────────────────────────────────────────────────
head("5. CONTEXTO LONGO (cabe um arquivo de codigo?)")
src = REPO_ROOT / "hermes_cli" / "config.py"
code = src.read_text(encoding="utf-8", errors="replace") if src.exists() else ""
approx = len(code) // 4
print(f"arquivo: {src.name}  {len(code)} chars (~{approx} tokens)")
ok, r, dt = call(
    {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": f"Aqui esta um arquivo de codigo:\n\n{code}\n\nResponda APENAS com o nome da primeira funcao def definida no arquivo.",
            }
        ],
        "max_tokens": 64,
    }
)
if ok:
    msg = (r.get("choices") or [{}])[0].get("message", {})
    print(f"ok {dt:.1f}s  finish={(r.get('choices') or [{}])[0].get('finish_reason')}")
    print(f"resposta: {str(msg.get('content'))[:200]!r}")
    print(f"usage: {r.get('usage')}")
else:
    print(f"REJEITADO: {json.dumps(r)[:300]}")

# ── 6. JSON estrito ────────────────────────────────────────────────────
head("6. JSON ESTRITO (saida legivel por maquina)")
ok, r, dt = call(
    {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": 'Return ONLY valid JSON: {"status":"ok","count":3,"items":["a","b","c"]}',
            }
        ],
        "max_tokens": 200,
    }
)
if ok:
    c = ((r.get("choices") or [{}])[0].get("message", {}) or {}).get("content", "")
    cleaned = re.sub(r"^```(?:json)?|```$", "", c.strip(), flags=re.M).strip()
    try:
        parsed = json.loads(cleaned)
        print(f"JSON VALIDO: {parsed}")
        STRICT_JSON = True
    except Exception as e:
        print(f"JSON INVALIDO ({e}): {c[:200]!r}")
        STRICT_JSON = False
else:
    STRICT_JSON = False
    print(f"REJEITADO: {json.dumps(r)[:200]}")

# ── VEREDITO ───────────────────────────────────────────────────────────
head("VEREDITO — o que da para construir com este modelo")
rows = [
    ("inferencia basica", BASIC),
    ("tool-calling", TC),
    ("loop de ferramentas", LOOP),
    ("JSON estrito", STRICT_JSON),
]
for name, val in rows:
    print(f"  {'[OK]' if val else '[X] '} {name}")
print()
if BASIC and TC and LOOP:
    print("=> AGENTES AUTONOMOS: possivel. Leem arquivos, chamam tools, respondem.")
elif BASIC and not TC:
    print("=> AGENTES DE TEXTO: so conversam. Ainda util (revisor/pesquisador/prompt),")
    print("   mas precisam de ferramentas FORA do modelo (o orquestrador le o arquivo")
    print("   e injeta o conteudo no prompt).")
else:
    print("=> relay nao esta servindo este modelo de forma utilizavel.")
