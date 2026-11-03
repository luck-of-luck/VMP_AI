"""
Verificacao FINAL de todos os MCPs locais do opencode.jsonc.

Por que este script
-------------------
Ate agora eu verifiquei os 4 do predador e os 11 que usavam nome solto.
Falta o conjunto: TODOS os servidores locais, com o argv e o environment
exatamente como estao no config. Este e o teste que responde a pergunta
"o config esta saudavel?" — nao "aquele servidor funciona?".

O que ele mede, por servidor:
  - sobe (initialize + tools/list)
  - quantas tools entrega
  - quanto tempo leva (custo de boot)
  - se o PATH declarado no environment existe mesmo

Nao e teste do OpenCode. E o pre-condicao dele: o que falha aqui falha no
boot. O teste no OpenCode real ainda precisa ser feito.
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

CONFIG = Path(os.environ.get("OPENCODE_CONFIG", Path.home() / ".config" / "opencode" / "opencode.jsonc"))
SOMENTE = sys.argv[1:] if len(sys.argv) > 1 else None


def carregar_config() -> dict:
    raw = CONFIG.read_text(encoding="utf-8-sig")
    out, i, n = [], 0, len(raw)
    while i < n:
        ch = raw[i]
        if ch == '"':
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
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", "".join(out)))


async def testar(nome, spec, timeout=120):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    argv = spec["command"]
    env = dict(os.environ)
    env.update(spec.get("environment", {}))

    exe = argv[0]
    if not re.match(r"^[A-Za-z]:", exe):
        return {"estado": "NOME_SOLTO", "detalhe": exe}
    if not Path(exe.replace("/", "\\")).exists():
        return {"estado": "EXE_AUSENTE", "detalhe": exe}

    # o PATH declarado no environment existe?
    path_decl = spec.get("environment", {}).get("PATH", "")
    pau = [p for p in path_decl.split(";") if p and not Path(p).exists()]

    t0 = time.perf_counter()
    try:
        params = StdioServerParameters(command=exe, args=argv[1:], env=env)
        async with stdio_client(params) as (rd, wr):
            async with ClientSession(rd, wr) as s:
                await s.initialize()
                r = await s.list_tools()
                dt = time.perf_counter() - t0
                return {
                    "estado": "OK",
                    "tools": len(r.tools),
                    "s": round(dt, 1),
                    "path_invalido": pau,
                }
    except Exception as e:
        return {
            "estado": "FALHOU",
            "s": round(time.perf_counter() - t0, 1),
            "detalhe": f"{type(e).__name__}: {str(e)[:90]}",
            "path_invalido": pau,
        }


async def main():
    cfg = carregar_config()
    mcp = cfg.get("mcp", {})
    locais = {
        k: v
        for k, v in mcp.items()
        if v.get("type") == "local" and v.get("enabled", True)
    }
    if SOMENTE:
        locais = {k: v for k, v in locais.items() if k in SOMENTE}

    print(f"config: {CONFIG}")
    print(f"servidores locais ENABLED: {len(locais)}")
    print("=" * 78)

    res = {}
    for nome, spec in locais.items():
        r = await testar(nome, spec)
        res[nome] = r
        if r["estado"] == "OK":
            aviso = ""
            if r.get("path_invalido"):
                aviso = f"  [!] PATH invalido: {r['path_invalido']}"
            print(f"  OK    {nome:22} {r['tools']:>3} tools  {r['s']:>6}s{aviso}")
        elif r["estado"] == "NOME_SOLTO":
            print(f"  AVISO {nome:22} usa NOME SOLTO: {r['detalhe']}")
        elif r["estado"] == "EXE_AUSENTE":
            print(f"  ERRO  {nome:22} executavel nao existe: {r['detalhe']}")
        else:
            print(f"  ERRO  {nome:22} {r.get('s')}s  {r.get('detalhe')}")

    ok = [k for k, v in res.items() if v["estado"] == "OK"]
    problemas = {k: v for k, v in res.items() if v["estado"] != "OK"}
    tools = sum(res[k]["tools"] for k in ok)
    lentos = sorted(
        [(k, res[k]["s"]) for k in ok if res[k]["s"] > 25],
        key=lambda x: -x[1],
    )

    print("=" * 78)
    print(f"OK: {len(ok)}/{len(locais)}   |   tools totais: {tools}")
    if lentos:
        print(f"boot lento (>25s): {lentos}")
    if problemas:
        print("PROBLEMAS:")
        for k, v in problemas.items():
            print(f"  {k}: {v['estado']} {v.get('detalhe', '')}")
    return 0 if not problemas else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
