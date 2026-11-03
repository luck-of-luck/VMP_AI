"""
Verifica os 4 servidores do predador EXATAMENTE como o OpenCode os invoca.

Por que este script existe
--------------------------
O OpenCode nao hot-reload de config: ele le opencode.jsonc no boot e spawna
cada MCP com o argv + environment de la. Este script le O MESMO arquivo,
monta os mesmos StdioServerParameters e faz initialize() + tools/list em
cada um. Se funcionar aqui, funciona no boot do OpenCode.

Ele tambem mede o tempo de startup, que e o custo invisivel: cada MCP que
sobe lento atrasa toda sessao.

NAO e um substituto do teste no OpenCode — e o pre-condicao dele. O que
falhar aqui vai falhar la.
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

CONFIG = Path(os.environ.get("OPENCODE_CONFIG", Path.home() / ".config" / "opencode" / "opencode.jsonc"))
ALVO = Path(__file__).parent / "planted.py"


def carregar_config() -> dict:
    """Le JSONC tolerante a comentarios (o OpenCode aceita o mesmo)."""
    raw = CONFIG.read_text(encoding="utf-8-sig")
    out, i, n = [], 0, len(raw)
    while i < n:
        ch = raw[i]
        if ch == '"':  # string: copia ate fechar, respeitando escape
            j = i + 1
            while j < n:
                if raw[j] == "\\":
                    j += 2
                    continue
                if raw[j] == '"':
                    break
                j += 1
            out.append(raw[i : j + 1])
            i = j + 1
            continue
        if ch == "/" and i + 1 < n and raw[i + 1] == "/":
            while i < n and raw[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and raw[i + 1] == "*":
            i = raw.find("*/", i) + 2
            continue
        out.append(ch)
        i += 1
    txt = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
    return json.loads(txt)


ALVOS = ["astgrep", "sast", "db", "semgrep"]


async def testar(nome: str, spec: dict) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    argv = spec["command"]
    env = dict(os.environ)
    env.update(spec.get("environment", {}))

    if not Path(argv[0]).exists():
        return {
            "servidor": nome,
            "ok": False,
            "erro": f"executavel nao existe: {argv[0]}",
        }

    params = StdioServerParameters(command=argv[0], args=argv[1:], env=env)
    t0 = time.perf_counter()
    try:
        async with stdio_client(params) as (rd, wr):
            async with ClientSession(rd, wr) as s:
                await s.initialize()
                r = await s.list_tools()
                dt = time.perf_counter() - t0
                return {
                    "servidor": nome,
                    "ok": True,
                    "tools": len(r.tools),
                    "startup_s": round(dt, 2),
                    "amostra": sorted(t.name for t in r.tools)[:4],
                }
    except Exception as e:
        return {
            "servidor": nome,
            "ok": False,
            "startup_s": round(time.perf_counter() - t0, 2),
            "erro": f"{type(e).__name__}: {str(e)[:220]}",
        }


async def main() -> int:
    cfg = carregar_config()
    mcp = cfg.get("mcp", {})
    print(f"config: {CONFIG}")
    print(f"servidores no arquivo: {len(mcp)}")
    print(
        f"alvo do benchmark: {ALVO.name} ({sum(1 for _ in ALVO.open(encoding='utf-8'))} linhas)"
    )
    print()

    faltando = [n for n in ALVOS if n not in mcp]
    if faltando:
        print(f"FALTA no config: {faltando}")
        return 1

    results = []
    for nome in ALVOS:
        r = await testar(nome, mcp[nome])
        results.append(r)
        if r["ok"]:
            print(
                f"  OK   {nome:9} {r['tools']:>3} tools  {r['startup_s']:>6}s  {r['amostra']}"
            )
        else:
            print(f"  ERRO {nome:9} {r['erro']}")
            print(f"       ({r['startup_s']}s)")

    ok = [r for r in results if r["ok"]]
    falhou = [r for r in results if not r["ok"]]
    total_tools = sum(r["tools"] for r in ok)
    lento = [r for r in ok if r["startup_s"] > 20]

    print()
    print(f"RESULTADO: {len(ok)}/{len(ALVOS)} sobem")
    print(f"  tools entregues: {total_tools}")
    if lento:
        print(
            f"  startup > 20s (atrasa o boot): {[(r['servidor'], r['startup_s']) for r in lento]}"
        )
    if falhou:
        print(f"  QUEBRADOS: {[r['servidor'] for r in falhou]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
