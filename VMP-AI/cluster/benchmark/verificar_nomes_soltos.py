"""
Smoke test dos MCPs que usam NOME SOLTO no opencode.jsonc.

O problema
----------
No config, 11 servidores sao chamados como ["npx", ...] ou ["uvx", ...].
Isso so funciona se o processo que o OpenCode spawn herdar um PATH com esses
bins. Medido: uvx como nome solto FALHOU (nao encontrado) porque o uvx real
esta em bin e nao estava no PATH do teste.

Este script testa cada COMBINACAO (nome solto vs caminho absoluto + env com
PATH completo) e diz qual funciona. O objetivo e trocar texto no config
so por opcao que eu MEDI que sobe — nunca por suposicao.

Como decide "sobe": faz initialize() + tools/list num subprocesso via stdio,
igual ao OpenCode faz no boot. Se um servidor sobe assim, sobe la.
"""

import asyncio
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

CONFIG = Path(os.environ.get("OPENCODE_CONFIG", Path.home() / ".config" / "opencode" / "opencode.jsonc"))
NPX_ABS = r"C:\Program Files\nodejs\npx.cmd"
UVX_ABS = r"uvx"

# PATH completo: o que um shell de usuario tem, e que o OpenCode pode nao ter
PATH_FULL = (
    r"bin;"
    r"C:\Program Files\nodejs;"
    r"AppData/Roaming/npm;"
    r"AppData/Local/Programs/Python\Python311;"
    r"AppData/Local/Programs/Python\Python313;"
    + os.environ.get("PATH", "")
)


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


NOMES_SOLTOS = {"npx", "uvx", "python", "python3", "node", "deno", "bun"}


def candidatos(nome: str) -> list:
    """Lista de (rotulo, argv[0], env_extra) para testar um nome solto."""
    abs_map = {"npx": NPX_ABS, "uvx": UVX_ABS}
    out = [("solto", nome, {})]
    if nome in abs_map:
        out.append(("absoluto", abs_map[nome], {}))
        out.append(("abs+PATH", abs_map[nome], {"PATH": PATH_FULL}))
    return out


async def testar(argv0: str, args: list, env_extra: dict, timeout: int = 90):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    if not Path(argv0).exists():
        return {"ok": False, "erro": f"executavel nao existe: {argv0}"}
    env = dict(os.environ)
    env.update(env_extra)
    t0 = time.perf_counter()
    try:
        params = StdioServerParameters(command=argv0, args=args, env=env)
        async with stdio_client(params) as (rd, wr):
            async with ClientSession(rd, wr) as s:
                await s.initialize()
                r = await s.list_tools()
                return {
                    "ok": True,
                    "tools": len(r.tools),
                    "s": round(time.perf_counter() - t0, 1),
                }
    except Exception as e:
        return {
            "ok": False,
            "s": round(time.perf_counter() - t0, 1),
            "erro": f"{type(e).__name__}: {str(e)[:110]}",
        }


async def main():
    cfg = carregar_config()
    mcp = cfg.get("mcp", {})
    alvos = [
        nome
        for nome, spec in mcp.items()
        if spec.get("type") == "local"
        and spec.get("command")
        and spec["command"][0] in NOMES_SOLTOS
    ]
    print(f"config: {CONFIG}")
    print(f"servidores locais com NOME SOLTO: {len(alvos)} -> {alvos}")
    print()

    resumo = {}
    for nome in alvos:
        spec = mcp[nome]
        argv = spec["command"]
        nome_solto, args = argv[0], argv[1:]
        env_origem = spec.get("environment", {})
        print(f"[{nome}]  {nome_solto} {' '.join(args)[:50]}")

        ganhou = None
        for rotulo, argv0, env_extra in candidatos(nome_solto):
            env_teste = dict(env_extra)
            env_teste.update(env_origem)  # env do config sempre presente
            r = await testar(argv0, args, env_teste)
            marca = "OK " if r["ok"] else "ERRO"
            extra = f"{r['tools']} tools {r['s']}s" if r["ok"] else f"{r['erro'][:60]}"
            print(f"    {marca} {rotulo:9} {extra}")
            if r["ok"] and ganhou is None:
                ganhou = (rotulo, argv0, env_extra, r["tools"], r["s"])
        resumo[nome] = ganhou
        print()

    print("=" * 70)
    print("VEREDITO POR SERVIDOR")
    print("=" * 70)
    fixaveis, ja_ok = [], []
    for nome, g in resumo.items():
        if not g:
            print(f"  {nome:22} NENHUMA COMBINACAO SOBE  <-- revisar")
        elif g[0] == "solto":
            ja_ok.append(nome)
            print(f"  {nome:22} ja funciona como esta   ({g[3]} tools, {g[4]}s)")
        else:
            fixaveis.append((nome, g))
            print(f"  {nome:22} PRECISA -> {g[0]:9} ({g[3]} tools, {g[4]}s)")

    print()
    if fixaveis:
        print(f"Para trocar no config ({len(fixaveis)}):")
        for nome, g in fixaveis:
            print(f'    "{nome}": usar {g[1]}  (env +PATH se g[0]=="abs+PATH")')
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
